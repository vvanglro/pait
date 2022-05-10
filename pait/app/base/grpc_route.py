import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import grpc
from pydantic import BaseModel, Field

from pait.core import Pait
from pait.field import BaseField, Body, Depends
from pait.model.response import PaitJsonResponseModel
from pait.model.tag import Tag
from pait.util.grpc_inspect.message_to_pydantic import GRPC_TIMESTAMP_HANDLER_TUPLE_T, parse_msg_to_pydantic_model
from pait.util.grpc_inspect.stub import GrpcModel, ParseStub
from pait.util.grpc_inspect.types import Message, MessageToDict

grpc_tag: Tag = Tag("grpc", desc="grpc route")


class GrpcPaitModel(BaseModel):
    name: str = Field("")
    tag: List[Tuple[str, str]] = Field(default_factory=list)
    group: str = Field("")
    desc: str = Field("")
    summary: str = Field("")
    url: str = Field("")
    enable: bool = Field(True)


def get_pait_info_from_grpc_desc(grpc_model: GrpcModel) -> GrpcPaitModel:
    pait_dict: dict = {}
    for line in grpc_model.service_desc.split("\n") + grpc_model.desc.split("\n"):
        line = line.strip()
        if not line.startswith("pait: {"):
            continue
        line = line.replace("pait:", "")
        pait_dict.update(json.loads(line))
    return GrpcPaitModel(**pait_dict)


class GrpcGatewayRoute(object):
    is_async: bool
    pait: Pait
    make_response: Callable
    channel: Union[grpc.Channel, grpc.aio.Channel]

    def __init__(
        self,
        app: Any,
        *stub_list: Any,
        parse_msg_desc: Optional[str] = None,
        prefix: str = "",
        title: str = "",
        msg_to_dict: Callable = MessageToDict,
        parse_dict: Optional[Callable] = None,
        pait: Optional[Pait] = None,
        make_response: Optional[Callable] = None,
        url_handler: Callable[[str], str] = lambda x: x.replace(".", "-"),
        request_param_field_dict: Optional[Dict[str, Union[Type[BaseField], Depends]]] = None,
        grpc_timestamp_handler_tuple: Optional[GRPC_TIMESTAMP_HANDLER_TUPLE_T] = None,
    ):
        self.prefix: str = prefix
        self.title: str = title
        self.parse_stub_list: List[ParseStub] = [ParseStub(i, parse_msg_desc=parse_msg_desc) for i in stub_list]
        self.stub_list: Tuple[Any, ...] = stub_list
        self.msg_to_dict: Callable = msg_to_dict
        self.parse_dict: Optional[Callable] = parse_dict

        self.url_handler: Callable[[str], str] = url_handler
        self._request_param_field_dict: Optional[Dict[str, Union[Type[BaseField], Depends]]] = request_param_field_dict
        self._grpc_timestamp_handler_tuple: Optional[GRPC_TIMESTAMP_HANDLER_TUPLE_T] = grpc_timestamp_handler_tuple
        self._pait: Pait = pait or self.pait
        self._make_response: Callable = make_response or self.make_response
        self._is_gen: bool = False
        self._tag_dict: Dict[str, Tag] = {}
        self.method_func_dict: Dict[str, Callable] = {}

        self._gen_route(app)

    def _gen_request_pydantic_class_from_grpc_model(self, grpc_model: GrpcModel) -> Type[BaseModel]:
        return parse_msg_to_pydantic_model(
            grpc_model.request,
            default_field=Body,
            request_param_field_dict=self._request_param_field_dict,
            grpc_timestamp_handler_tuple=self._grpc_timestamp_handler_tuple,
        )

    def _gen_pait_from_grpc_method(
        self, method_name: str, grpc_model: GrpcModel, grpc_pait_model: GrpcPaitModel
    ) -> Pait:
        tag_tuple: Tuple[Tag, ...] = (grpc_tag,)
        for tag, desc in grpc_pait_model.tag + [("grpc" + "-" + method_name.split("/")[1].split(".")[0], "")]:
            if tag in self._tag_dict:
                pait_tag: Tag = self._tag_dict[tag]
            else:
                pait_tag = Tag(tag, desc)
                self._tag_dict[tag] = pait_tag
            tag_tuple += (pait_tag,)

        class CustomerJsonResponseModel(PaitJsonResponseModel):
            name: str = grpc_model.response.DESCRIPTOR.name
            response_data: Type[BaseModel] = parse_msg_to_pydantic_model(grpc_model.response)

        return self._pait.create_sub_pait(
            name=grpc_pait_model.name,
            group=grpc_pait_model.group or method_name.split("/")[1],
            tag=tag_tuple,
            desc=grpc_pait_model.desc,
            summary=grpc_pait_model.summary,
            response_model_list=[CustomerJsonResponseModel],
        )

    def get_grpc_func(self, method_name: str) -> Callable:
        func: Optional[Callable] = self.method_func_dict.get(method_name, None)
        if not func:
            raise RuntimeError(f"{method_name}'s func is not found, Please call init_channel to register the channel")
        return func

    def get_msg_from_dict(self, msg: Type[Message], request_dict: dict) -> Message:
        if self.parse_dict:
            request_msg: Message = self.parse_dict(request_dict, msg)
        else:
            request_msg = msg(**request_dict)  # type: ignore
        return request_msg

    def _gen_route_func(self, method_name: str, grpc_model: GrpcModel) -> Tuple[Optional[Callable], GrpcPaitModel]:
        grpc_pait_model: GrpcPaitModel = get_pait_info_from_grpc_desc(grpc_model)
        if grpc_pait_model.enable is False:
            return None, grpc_pait_model
        if not grpc_pait_model.url:
            grpc_pait_model.url = method_name

        request_pydantic_model_class: Type[BaseModel] = self._gen_request_pydantic_class_from_grpc_model(grpc_model)
        pait: Pait = self._gen_pait_from_grpc_method(method_name, grpc_model, grpc_pait_model)

        if self.is_async:
            import asyncio

            async def _route(request_pydantic_model: request_pydantic_model_class) -> Any:  # type: ignore
                func: Callable = self.get_grpc_func(method_name)
                request_dict: dict = request_pydantic_model.dict()  # type: ignore
                request_msg: Message = self.get_msg_from_dict(grpc_model.request, request_dict)
                loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
                if loop != func._loop:  # type: ignore
                    raise RuntimeError(
                        "Loop is not same, "
                        "the grpc channel must be initialized after the event loop of the api server is initialized"
                    )
                else:
                    grpc_msg: Message = await func(request_msg)
                return self._make_response(self.msg_to_dict(grpc_msg))

        else:

            def _route(request_pydantic_model: request_pydantic_model_class) -> Any:  # type: ignore
                func: Callable = self.get_grpc_func(method_name)
                request_dict: dict = request_pydantic_model.dict()  # type: ignore
                request_msg: Message = self.get_msg_from_dict(grpc_model.request, request_dict)
                grpc_msg: Message = func(request_msg)
                return self._make_response(self.msg_to_dict(grpc_msg))

        # change route func name and qualname
        _route.__name__ = self.title + method_name.replace(".", "_")
        _route.__qualname__ = _route.__qualname__.replace("._route", "." + _route.__name__)

        _route = pait()(_route)
        return _route, grpc_pait_model

    def _gen_route(self, app: Any) -> Any:  # type: ignore
        raise NotImplementedError()

    def reinit_channel(
        self, channel: Union[grpc.Channel, grpc.aio.Channel]
    ) -> Union[grpc.Channel, grpc.aio.Channel, None]:
        old_channel: Union[grpc.Channel, grpc.aio.Channel, None] = getattr(self, "channel", None)
        self.init_channel(channel)
        return old_channel

    def init_channel(self, channel: Union[grpc.Channel, grpc.aio.Channel]) -> None:
        self.channel: Union[grpc.Channel, grpc.aio.Channel] = channel
        if isinstance(channel, grpc.Channel) and self.is_async:
            raise RuntimeError("Channel is not supported, please use aio.Channel")
        elif isinstance(channel, grpc.aio.Channel) and not self.is_async:
            raise RuntimeError("Asyncio channel is not supported, please use channel")
        for stub_class in self.stub_list:
            stub = stub_class(channel)
            for func in stub.__dict__.values():
                method = func._method  # type: ignore
                if isinstance(method, bytes):
                    method = method.decode()
                self.method_func_dict[method] = func
