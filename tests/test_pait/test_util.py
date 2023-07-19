import datetime
import enum
import inspect
import typing
from typing import Any, Dict, Generator, List, Optional, Type, Union

import pytest
import typing_extensions
from pydantic import BaseModel, Field, conint, constr
from pytest_mock import MockFixture

import pait.util._pydantic_util
from pait import _pydanitc_adapter, field, util

pytestmark = pytest.mark.asyncio


class TestUtil:
    def test_create_factory(self) -> None:
        def demo(a: int, b: int) -> int:
            return a + b

        assert util.create_factory(demo)(1, 2)() == 3

    def test_partial_wrapper(self) -> None:
        def demo(a: int, b: int = 1, c: int = 2) -> int:
            return a + b + c

        assert demo(1) == 4
        demo1 = util.partial_wrapper(demo, b=3)
        assert demo1(1) == 6
        demo2 = util.partial_wrapper(demo, b=3, c=4)
        assert demo2(1) == 8

    def test_example_value_handle(self) -> None:
        class DemoEnum(enum.Enum):
            a = 1
            b = 2

        assert util.example_value_handle(DemoEnum.a) == 1

        def demo() -> int:
            return 1

        assert util.example_value_handle(demo) == 1

    def test_get_real_annotation(self) -> None:
        class Demo:
            class SubDemo:
                pass

            a: SubDemo

        assert "test_get_real_annotation.<locals>.Demo.SubDemo'" in str(
            util.get_real_annotation(Demo.__annotations__["a"], Demo)
        )

        # support postponed annotations
        class Demo1:
            class SubDemo1:
                pass

            a: "SubDemo1"

        assert "test_get_real_annotation.<locals>.Demo1.SubDemo1'" in str(
            util.get_real_annotation(Demo1.__annotations__["a"], Demo1)
        )

        # Closures
        def demo2() -> None:
            class Demo2:
                class SubDemo2:
                    pass

                a: "SubDemo2"

            assert ("test_get_real_annotation.<locals>.demo2.<locals>.Demo2.SubDemo2") in str(
                util.get_real_annotation(Demo2.__annotations__["a"], Demo2)
            )

        demo2()

    def test_get_pydantic_annotation(self) -> None:
        class SubDemo1(BaseModel):
            a: int = Field()

        class SubDemo2(BaseModel):
            b: conint(ge=0) = Field(default=0)  # type: ignore[valid-type]
            c: constr(min_length=0) = Field(default="")  # type: ignore[valid-type]

        class Demo(SubDemo1, SubDemo2):
            pass

        assert util.get_pydantic_annotation("a", Demo) == int
        assert util.get_pydantic_annotation("b", Demo) == int
        assert util.get_pydantic_annotation("c", Demo) == str

    def test_get_pait_response_model(self) -> None:
        from example.common.response_model import TextRespModel, UserSuccessRespModel2, UserSuccessRespModel3
        from pait.model import JsonResponseModel

        class DemoTestRespModel(TextRespModel):
            pass

        # Find target pait response class
        assert UserSuccessRespModel3 == util.get_pait_response_model(
            [DemoTestRespModel, UserSuccessRespModel3], JsonResponseModel
        )

        assert UserSuccessRespModel2 == util.get_pait_response_model([UserSuccessRespModel2])

    def test_gen_example_value_from_python(self) -> None:
        assert util.gen_example_value_from_python(
            {
                "a": 3,
                "b": "xxx",
                "c": False,
                "d": {
                    "a": [1, 2, 3],
                    "b": {"c": 3, "d": 4},
                },
            }
        ) == {"a": 0, "b": "", "c": True, "d": {"a": [], "b": {"c": 0, "d": 0}}}

    def test_gen_example_value_from_type(self) -> None:
        from typing_extensions import TypedDict

        class Demo(TypedDict):
            class SubDemo(TypedDict):  # type: ignore[misc]
                a: bool
                b: float

            a: int
            b: str
            c: bool
            d: SubDemo

        assert util.gen_example_value_from_type(Demo) == {"a": 0, "b": "", "c": True, "d": {"a": True, "b": 0.0}}
        assert util.gen_example_value_from_type(Optional[int]) == 0  # type: ignore[arg-type]
        assert util.gen_example_value_from_type(Generator[int, None, None]) == 0

    def test_gen_example_value_from_pydantic_model(self) -> None:
        class SexEnum(enum.Enum):
            man = "man"
            woman = "woman"

        class Empty(object):
            pass

        class Demo(BaseModel):
            a: int = Field()
            b: str = Field(example="mock")
            c: bool = Field(alias="alias_c")
            d: float = Field(default=2.1)
            e: int = Field(default_factory=lambda: 10)
            f: datetime.date = Field()
            g: SexEnum = Field()
            h: List[str] = Field()
            i: Dict[str, List[int]] = Field()

        assert util.gen_example_dict_from_pydantic_base_model(Demo) == {
            "a": 0,
            "b": "mock",
            "alias_c": True,
            "d": 2.1,
            "e": 10,
            "f": datetime.date.today(),
            "g": "man",
            "h": [""],
            "i": {},
        }

        class Demo1(BaseModel):
            a: int = Field(example=1)
            b: int = Field(new_example_column=2)

        assert util.gen_example_dict_from_pydantic_base_model(Demo1, example_column_name="new_example_column") == {
            "a": 0,
            "b": 2,
        }

    def test_gen_example_value_from_schema(self) -> None:
        assert util.gen_example_dict_from_schema({}) == {}

        class SexEnum(enum.Enum):
            man = "man"
            woman = "woman"

        class Empty(object):
            pass

        class Demo(BaseModel):
            a: int = Field()
            b: str = Field(example="mock")
            c: bool = Field(alias="alias_c")
            d: float = Field(default=2.1)
            e: int = Field(default_factory=lambda: 10)
            f: datetime.date = Field()
            g: SexEnum = Field()
            h: List[str] = Field()
            i: Dict[str, List[int]] = Field()

        assert util.gen_example_dict_from_schema(_pydanitc_adapter.model_json_schema(Demo)) == {
            "a": 0,
            "b": "mock",
            "alias_c": True,
            "d": 2.1,
            "e": 0,
            "f": "",
            "g": "man",
            "h": [],
            "i": {},
        }
        assert (
            util.gen_example_json_from_schema(_pydanitc_adapter.model_json_schema(Demo))
            == '{"a": 0, "b": "mock", "alias_c": true, "d": 2.1, "e": 0, "f": "", "g": "man", "h": [], "i": {}}'
        )

    def test_create_pydantic_model(self) -> None:
        pydantic_model_class: Type[BaseModel] = pait.util._pydantic_util.create_pydantic_model(
            {"a": (int, ...), "b": (str, ...)}
        )
        pydantic_model = pydantic_model_class(a=1, b="a")
        assert _pydanitc_adapter.model_dump(pydantic_model) == {"a": 1, "b": "a"}

    def test_func_sig(self) -> None:
        def demo(a: int, b: str) -> int:
            return 0

        func_sig: util.FuncSig = util.get_func_sig(demo)
        assert func_sig.func == demo
        assert func_sig.sig == inspect.signature(demo)
        sig: inspect.Signature = inspect.signature(demo)
        assert func_sig.param_list == [
            sig.parameters[key]
            for key in sig.parameters
            if sig.parameters[key].annotation != sig.empty or sig.parameters[key].name == "self"
        ]

        def demo1(self, a) -> int:  # type: ignore
            pass

        func_sig = util.get_func_sig(demo1)
        assert len(func_sig.param_list) == 1
        assert func_sig.param_list[0].name == "self"

    def test_get_parameter_list_from_class(self) -> None:
        value: Any = field.Body.i()

        class Demo1(object):
            pass

        class Demo2(object):
            a: int
            b: str = ""
            c: str = value

        assert [] == util.get_parameter_list_from_class(Demo1)
        result: List["inspect.Parameter"] = util.get_parameter_list_from_class(Demo2)
        assert len(result) == 1
        assert result[0].name == "c"
        assert result[0].annotation == str
        assert result[0].default == value

    def test_parse_typing(self) -> None:
        assert [dict] == util.parse_typing(dict)
        assert [list] == util.parse_typing(List)
        assert [list] == util.parse_typing(List[str])
        assert [dict] == util.parse_typing(Dict)
        assert [set] == util.parse_typing(typing.Set)
        assert [dict] == util.parse_typing(Union[dict])
        assert [dict] == util.parse_typing(Union[Dict])
        assert [dict] == util.parse_typing(Union[Dict[str, Any]])
        assert [dict] == util.parse_typing(typing.AsyncIterator[Dict])
        assert [dict] == util.parse_typing(typing.Iterator[Dict])
        assert [dict] == util.parse_typing(typing.Generator[Dict, None, None])
        assert [dict] == util.parse_typing(typing.AsyncGenerator[Dict, None])
        assert [tuple] == util.parse_typing(typing.Tuple[str, int])

        typed_dict_test_list = [
            (typing_extensions.TypedDict, typing_extensions.is_typeddict),  # type: ignore[attr-defined]
        ]
        try:
            from typing import TypedDict, is_typeddict  # type: ignore[attr-defined]

            typed_dict_test_list.append((TypedDict, is_typeddict))
        except ImportError:
            pass

        for _TypedDict, _is_typeddict in typed_dict_test_list:
            if inspect.isfunction(_TypedDict):
                assert [dict] == util.parse_typing(_TypedDict("demo"), _is_typeddict)
            else:
                assert [dict] == util.parse_typing(_TypedDict, _is_typeddict)
        # multi value
        assert [dict, str, int] == util.parse_typing(Union[Dict, str, int])
        assert [dict, type(None)] == util.parse_typing(Optional[Dict])
        assert [dict, type(None)] == util.parse_typing(Optional[dict])
        # Relatively rarely used scenes
        assert [int] == util.parse_typing(typing.NewType("UserId", int))
        assert [int] == util.parse_typing(typing.Callable[[], int])
        assert [int] == util.parse_typing(typing.Callable[[], typing.Awaitable[int]])
        s = typing.TypeVar("s", int, str)
        assert [int, str] == util.parse_typing(s)
        assert [str] == util.parse_typing(typing_extensions.Literal["a", "b"])
        assert [str] == util.parse_typing(typing_extensions.LiteralString)

        class Demo:
            pass

        assert [int] == util.parse_typing(typing_extensions.Annotated[int, Demo])
        # Unresolved type, returned directly
        from pait.util._types import _TYPING_NOT_PARSE_TYPE_SET

        for i in _TYPING_NOT_PARSE_TYPE_SET:
            assert [i] == util.parse_typing(i)


class AnyStringWith(str):
    def __eq__(self, other: Any) -> bool:
        return self in other


class StringNotIn(str):
    def __eq__(self, other: Any) -> bool:
        return self not in other


class Demo:
    pass


class FakeField(field.BaseField):
    pass


class TestGenTipExc:
    def test_raise_and_tip_param_value_is_empty(self, mocker: MockFixture) -> None:
        patch = mocker.patch("pait.param_handle.base.logging.debug")
        parameter: inspect.Parameter = inspect.Parameter(
            "b",
            inspect.Parameter.POSITIONAL_ONLY,
            annotation=str,
        )
        with pytest.raises(Exception):
            raise pait.util._gen_tip.gen_tip_exc(Demo(), Exception(), parameter)
        patch.assert_called_with(AnyStringWith("class: `Demo`  attributes error"))

    def test_raise_and_tip_param_value_is_pait_field(self, mocker: MockFixture) -> None:
        patch = mocker.patch("pait.param_handle.base.logging.debug")
        parameter: inspect.Parameter = inspect.Parameter(
            "b", inspect.Parameter.POSITIONAL_ONLY, annotation=str, default=FakeField.i()
        )
        with pytest.raises(Exception):
            raise pait.util._gen_tip.gen_tip_exc(Demo(), Exception(), parameter)

        patch.assert_called_with(AnyStringWith("class: `Demo`  attributes error"))

    def test_raise_and_tip_param_value_is_not_pait_field(self, mocker: MockFixture) -> None:
        patch = mocker.patch("pait.param_handle.base.logging.debug")
        parameter: inspect.Parameter = inspect.Parameter(
            "b", inspect.Parameter.POSITIONAL_ONLY, annotation=str, default=""
        )
        with pytest.raises(Exception):
            raise pait.util._gen_tip.gen_tip_exc(Demo(), Exception(), parameter)
        patch.assert_called_with(StringNotIn("alias"))
        patch.assert_called_with(AnyStringWith("class: `Demo`  attributes error"))


class TestLazyProperty:
    async def test_lazy_property_fun(self) -> None:
        @util.LazyProperty(self)
        def _demo(a: int, b: int) -> int:
            return a + b

        @util.LazyProperty(self)
        async def _async_demo(a: int, b: int) -> int:
            return a + b

        assert _demo(1, 3) == _demo(1, 4)
        assert await _async_demo(1, 5) == await _async_demo(1, 6)
        assert _demo(2, 1) != await _async_demo(2, 1)

    async def test_lazy_property_class(self) -> None:
        class Demo(object):
            @util.LazyProperty()
            def demo_func(self, a: int, b: int) -> int:
                return a + b

            @util.LazyProperty()
            async def async_demo_func(self, a: int, b: int) -> int:
                return a + b

        demo: Demo = Demo()
        demo1: Demo = Demo()
        assert demo.demo_func(1, 2) == demo.demo_func(1, 3)
        assert demo1.demo_func(1, 4) == demo1.demo_func(1, 5)

        assert await demo.async_demo_func(2, 2) == await demo.async_demo_func(2, 3)
        assert await demo1.async_demo_func(2, 4) == await demo1.async_demo_func(2, 5)

        assert demo.demo_func(3, 1) != demo1.demo_func(3, 1)
        assert await demo.async_demo_func(3, 2) != await demo1.async_demo_func(3, 2)
