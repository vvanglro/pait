import inspect
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, Generic, List, Optional, Tuple, Type, TypeVar, Union

from pydantic import BaseModel, Field
from typing_extensions import Self  # type: ignore

from pait import _pydanitc_adapter, field
from pait._pydanitc_adapter import PydanticUndefined, PydanticUndefinedType, get_field_extra
from pait.exceptions import (
    FieldValueTypeException,
    NotFoundFieldException,
    PaitBaseException,
    ParseTypeError,
    TipException,
)
from pait.plugin.base import PluginProtocol
from pait.types import CallType
from pait.util import (
    FuncSig,
    gen_tip_exc,
    get_func_sig,
    get_parameter_list_from_class,
    get_parameter_list_from_pydantic_basemodel,
    ignore_pre_check,
    is_bounded_func,
    is_type,
)

from . import rule

if TYPE_CHECKING:
    from pait.model.context import ContextModel
    from pait.model.core import PaitCoreModel


def raise_multiple_exc(exc_list: List[Exception]) -> None:
    """
    Multiple exceptions may be thrown during the parsing process, and these will be thrown one by one like a stack
    """
    if not exc_list:
        return
    try:
        raise exc_list.pop()
    finally:
        raise_multiple_exc(exc_list)


_CtxT = TypeVar("_CtxT", bound="ContextModel")


class BaseParamHandler(PluginProtocol, Generic[_CtxT]):
    _is_async: bool = False
    tip_exception_class: Optional[Type[TipException]] = TipException
    _pait_pre_load_dc: rule.PreLoadDc

    @staticmethod
    def is_self_param(parameter: inspect.Parameter) -> bool:
        if parameter.annotation == Self or parameter.name == "self":
            return True
        return False

    def prd_handle(
        self,
        context: _CtxT,
        _object: Union[FuncSig, Type, None],
        prd: rule.ParamRuleDict,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        raise NotImplementedError()

    def depend_handle(
        self, context: _CtxT, pld: rule.PreLoadDc, func_class_prd: Optional[rule.ParamRuleDict] = None
    ) -> Any:
        pass

    # def __post_init__(self, pait_core_model: "PaitCoreModel", args: tuple, kwargs: dict) -> None:
    #     super(BaseParamHandler, self).__post_init__(pait_core_model, args, kwargs)

    #     # cbv handle
    #     context_model: "ContextModel" = pait_context.get()
    #     self.cbv_instance: Optional[Any] = context_model.cbv_instance
    #     self._app_helper: "BaseAppHelper" = context_model.app_helper
    #     self.cbv_type: Optional[Type] = None

    #     if self.cbv_instance:
    #         self.cbv_type = self.cbv_instance.__class__
    #         self.cbv_param_list: List["inspect.Parameter"] = get_parameter_list_from_class(self.cbv_type)
    #     else:
    #         self.cbv_param_list = []
    #         # cbv_type = getattr(
    #               inspect.getmodule(func),
    #               func.__qualname__.split(".<locals>", 1)[0].rsplit(".", 1)[0]
    #               )
    #     self.pre_depend_list: List[Callable] = pait_core_model.pre_depend_list
    #     self.pydantic_model_config: Type[BaseConfig] = pait_core_model.pydantic_model_config

    @classmethod
    def check_param_field_by_parameter(
        cls,
        pait_core_model: "PaitCoreModel",
        parameter: inspect.Parameter,
    ) -> None:
        if isinstance(parameter.default, field.Depends):
            func_sig: FuncSig = get_func_sig(parameter.default.func)  # get and cache func sig
            if not is_type(parameter.annotation, func_sig.return_param):
                raise FieldValueTypeException(
                    parameter.name,
                    f"{parameter.name}'s Depends.callable return annotation"
                    f" must:{parameter.annotation}, not {func_sig.return_param}",
                )
        elif isinstance(parameter.default, field.BaseRequestResourceField):
            if parameter.default.alias and not isinstance(parameter.default.alias, str):
                raise FieldValueTypeException(
                    parameter.name,
                    f"{parameter.name}'s Field.alias type must str. value: {parameter.default.alias}",
                )
            if not getattr(pait_core_model.app_helper_class.request_class, parameter.default.get_field_name()):
                raise NotFoundFieldException(
                    parameter.name,
                    f"field name: {parameter.default.get_field_name()}"
                    f" not found in {pait_core_model.app_helper_class.request_class}",
                )  # pragma: no cover
            try:
                check_list: List[Tuple[str, Any]] = [
                    ("default", parameter.default.default),
                    ("example", get_field_extra(parameter.default).get("example", PydanticUndefined)),
                ]
                if parameter.default.default_factory:
                    check_list.append(("default_factory", parameter.default.default_factory()))
                for title, value in check_list:
                    if value is ...:
                        return
                    if isinstance(value, PydanticUndefinedType):
                        return
                    if inspect.isclass(parameter.annotation) and isinstance(value, parameter.annotation):
                        return
                    if getattr(value, "__call__", None):
                        value = value()
                    try:
                        _pydanitc_adapter.PaitModelField(
                            value_name=parameter.name,
                            annotation=parameter.annotation,
                            field_info=Field(...),
                            request_param=parameter.default.get_field_name(),
                        ).validate(value)
                    except Exception:
                        raise ParseTypeError(
                            f"{parameter.name}'s Field.{title} type must {parameter.annotation}. value:{value}"
                        )
            except ParseTypeError as e:
                raise FieldValueTypeException(parameter.name, str(e))
        else:
            raise NotFoundFieldException(parameter.name, f"{parameter.name}'s Field not found")  # pragma: no cover

    @classmethod
    def _depend_pre_handle(cls, pait_core_model: "PaitCoreModel", func: CallType) -> rule.PreLoadDc:
        """gen depend's pre-load dataclass"""
        if inspect.ismethod(func) and not is_bounded_func(func):
            raise ValueError(f"Method: {func.__qualname__} is not a bounded function")  # pragma: no cover
        func_sig: FuncSig = get_func_sig(func, cache_sig=False)
        _pre_load_obj_dc = rule.PreLoadDc(
            pait_handler=func,  # depend func not get pait handler in pre-load
            param=cls._param_field_pre_handle(pait_core_model, func_sig.func, func_sig.param_list),
        )
        return _pre_load_obj_dc

    @classmethod
    def _param_field_pre_handle(
        cls,
        pait_core_model: "PaitCoreModel",
        _object: Any,
        param_list: List["inspect.Parameter"],
    ) -> rule.ParamRuleDict:
        """gen param rule dict"""
        param_rule_dict: rule.ParamRuleDict = {}
        for index, parameter in enumerate(param_list):
            field_type_enum: rule.FieldTypeEnum = rule.FieldTypeEnum.empty
            param_func: Optional[rule.ParamRuleFuncProtocol] = None
            sub_pld = rule.PreLoadDc(pait_handler=rule.empty_pr_func)

            try:
                if parameter.default != parameter.empty:
                    # kwargs param
                    # support model: def demo(pydantic.BaseModel: BaseModel = pait.field.BaseRequestResourceField())
                    if not ignore_pre_check:
                        cls.check_param_field_by_parameter(pait_core_model, parameter)

                    if isinstance(parameter.default, field.Depends):
                        sub_pld = cls._depend_pre_handle(pait_core_model, parameter.default.func)
                        field_type_enum = rule.FieldTypeEnum.request_depend
                        param_func = field_type_enum.value.async_func if cls._is_async else field_type_enum.value.func
                        depend_func = parameter.default.func
                        if inspect.isclass(depend_func):
                            # If this depend func is class, then its class attributes need to be processed
                            param_func = partial(  # type: ignore
                                param_func,
                                func_class_prd=cls._param_field_pre_handle(
                                    pait_core_model,
                                    depend_func,
                                    get_parameter_list_from_class(depend_func),  # type: ignore
                                ),
                            )

                    elif isinstance(parameter.default, field.BaseRequestResourceField):
                        field_type_enum = rule.FieldTypeEnum.request_field
                        if not parameter.default.alias:
                            parameter.default.request_key = parameter.name
                        # Creating a model field is very performance-intensive (especially for Pydantic V2),
                        # so it needs to be cached
                        pait_model_field: _pydanitc_adapter.PaitModelField
                        param_func = partial(  # type: ignore
                            field_type_enum.value.async_func if cls._is_async else field_type_enum.value.func,
                            pait_model_field=_pydanitc_adapter.PaitModelField(
                                value_name=parameter.name,
                                annotation=parameter.annotation,
                                field_info=parameter.default,
                                request_param=parameter.default.get_field_name(),
                            ),
                        )
                elif cls.is_self_param(parameter) and _object is pait_core_model.func:
                    # self param
                    field_type_enum = rule.FieldTypeEnum.cbv_class
                elif inspect.isclass(parameter.annotation):
                    # args param
                    if issubclass(
                        parameter.annotation, pait_core_model.app_helper_class.request_class.RequestType  # type: ignore
                    ):
                        # request param
                        field_type_enum = rule.FieldTypeEnum.request
                    elif issubclass(parameter.annotation, pait_core_model.app_helper_class.CbvType):
                        # self param
                        field_type_enum = rule.FieldTypeEnum.cbv_class
                    elif issubclass(parameter.annotation, BaseModel):
                        # support model: model: ModelType
                        param_list = get_parameter_list_from_pydantic_basemodel(
                            parameter.annotation, default_field_class=pait_core_model.default_field_class
                        )
                        sub_pld.param = cls._param_field_pre_handle(pait_core_model, parameter.annotation, param_list)
                        for _parameter in param_list:
                            raw_name = _parameter.name
                            # Each value in PaitModel does not need to valida by `pr func`
                            sub_pld.param[raw_name].param_func = (
                                rule.async_request_field_get_value_pr_func  # type: ignore[assignment]
                                if cls._is_async
                                else rule.request_field_get_value_pr_func
                            )
                            # If the value in Pait Model has alias, then the key of param should be alias
                            real_name = _parameter.default.request_key
                            if raw_name != real_name:
                                sub_pld.param[real_name] = sub_pld.param.pop(raw_name)
                        field_type_enum = rule.FieldTypeEnum.pait_model
            except PaitBaseException as e:
                raise gen_tip_exc(_object, e, parameter, tip_exception_class=cls.tip_exception_class) from e
            param_rule_dict[parameter.name] = rule.ParamRule(
                name=parameter.name,
                type_=parameter.annotation,
                index=index,
                parameter=parameter,
                param_func=param_func
                or (field_type_enum.value.async_func if cls._is_async else field_type_enum.value.func),
                sub=sub_pld,
            )
        return param_rule_dict

    @classmethod
    def pre_hook(cls, pait_core_model: "PaitCoreModel", kwargs: Dict) -> None:
        func_sig: FuncSig = get_func_sig(pait_core_model.func, cache_sig=False)
        # check and load param from pre depend
        _pait_pre_load_dc = rule.PreLoadDc(pait_handler=func_sig.func)
        for pre_depend in pait_core_model.pre_depend_list:
            _pait_pre_load_dc.pre_depend.append(cls._depend_pre_handle(pait_core_model, pre_depend))

        # check and load param from func
        _pait_pre_load_dc.param = cls._param_field_pre_handle(pait_core_model, func_sig.func, func_sig.param_list)
        kwargs["_pait_pre_load_dc"] = _pait_pre_load_dc
        # TODO support cbv class Attribute
        # I don't know how to get the class of the decorated function at the initialization of the decorator,
        # which may be an unattainable requirement
        # TODO Will be initialized when the plugin's initialization completes

    @classmethod
    def pre_load_hook(cls, pait_core_model: "PaitCoreModel", kwargs: Dict) -> Dict:
        super().pre_load_hook(pait_core_model, kwargs)
        if ignore_pre_check:
            # pre_check has helped to do the same task as pre_load
            cls.pre_hook(pait_core_model, kwargs)  # pragma: no cover
        return kwargs

    @classmethod
    def pre_check_hook(cls, pait_core_model: "PaitCoreModel", kwargs: Dict) -> None:
        super().pre_check_hook(pait_core_model, kwargs)
        cls.pre_hook(pait_core_model, kwargs)
