from dataclasses import MISSING
from typing import Any, Coroutine, Dict, List, Mapping, Optional

from starlette.datastructures import FormData, Headers, UploadFile
from starlette.endpoints import HTTPEndpoint
from starlette.requests import Request

from pait.app.base import BaseAppHelper, BaseRequestExtend
from pait.util import LazyProperty

__all__ = ["AppHelper", "RequestExtend"]


class RequestExtend(BaseRequestExtend[Request]):
    @property
    def scheme(self) -> str:
        return self.request.url.scheme

    @property
    def path(self) -> str:
        return self.request.url.path

    @property
    def hostname(self) -> str:
        if self.request.url.port:
            return f"{self.request.url.hostname}:{self.request.url.port}"
        return self.request.url.hostname


class AppHelper(BaseAppHelper[Request, RequestExtend]):
    RequestType = Request
    FormType = FormData
    FileType = UploadFile
    HeaderType = Headers
    CbvType = (HTTPEndpoint,)
    app_name = "starlette"

    def __init__(self, args: List[Any], kwargs: Mapping[str, Any]):
        super().__init__(args, kwargs)
        self._form: Optional[FormData] = None

    def get_attributes(self, key: str, default: Any = MISSING) -> Any:
        if default is MISSING:
            return getattr(self.request.app.state, key)
        else:
            return getattr(self.request.app.state, key, default)

    def request_extend(self) -> RequestExtend:
        return RequestExtend(self.request)

    def body(self) -> Coroutine[Any, Any, dict]:
        return self.request.json()

    def cookie(self) -> dict:
        return self.request.cookies

    async def get_form(self) -> FormData:
        if self._form:
            return self._form
        form: FormData = await self.request.form()
        self._form = form
        return form

    def file(self) -> Coroutine[Any, Any, FormData]:
        async def _() -> FormData:
            return await self.get_form()

        return _()

    def form(self) -> Coroutine[Any, Any, Dict[str, Any]]:
        @LazyProperty()
        async def _form() -> Dict[str, Any]:
            form_data: FormData = await self.get_form()
            return {key: form_data.getlist(key)[0] for key, _ in form_data.items()}

        return _form()

    def header(self) -> Headers:
        return self.request.headers

    def path(self) -> dict:
        return self.request.path_params

    def query(self) -> dict:
        return dict(self.request.query_params)

    def multiform(self) -> Coroutine[Any, Any, Dict[str, List[Any]]]:
        @LazyProperty()
        async def _multiform() -> Dict[str, List[Any]]:
            form_data: FormData = await self.get_form()
            return {
                key: [i for i in form_data.getlist(key) if not isinstance(i, UploadFile)]
                for key, _ in form_data.items()
            }

        return _multiform()

    @LazyProperty()
    def multiquery(self) -> Dict[str, Any]:
        return {key: self.request.query_params.getlist(key) for key, _ in self.request.query_params.items()}
