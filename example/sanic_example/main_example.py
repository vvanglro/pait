from __future__ import annotations

import hashlib

import aiofiles  # type: ignore
from pydantic import ValidationError
from redis.asyncio import Redis  # type: ignore
from sanic import response
from sanic.app import Sanic
from sanic.views import HTTPMethodView

from example.common import tag
from example.common.request_model import SexEnum, UserOtherModel
from example.common.response_model import (
    FailRespModel,
    LoginRespModel,
    SimpleRespModel,
    SuccessRespModel,
    UserSuccessRespModel,
    link_login_token_model,
)
from example.common.utils import NotTipAsyncParamHandler
from example.sanic_example.depend_route import (
    depend_async_contextmanager_route,
    depend_contextmanager_route,
    depend_route,
    pre_depend_async_contextmanager_route,
    pre_depend_contextmanager_route,
)
from example.sanic_example.field_route import (
    field_default_factory_route,
    pait_base_field_route,
    pait_model_route,
    post_route,
    same_alias_route,
)
from example.sanic_example.grpc_route import add_grpc_gateway_route
from example.sanic_example.plugin_route import (
    auto_complete_json_route,
    cache_response,
    cache_response1,
    check_json_plugin_route,
    check_json_plugin_route1,
    mock_route,
    param_at_most_one_of_route,
    param_at_most_one_of_route_by_extra_param,
    param_required_route,
    param_required_route_by_extra_param,
)
from example.sanic_example.response_route import (
    check_response_route,
    file_response_route,
    html_response_route,
    text_response_route,
)
from example.sanic_example.security_route import (
    api_key_cookie_route,
    api_key_header_route,
    api_key_query_route,
    oauth2_login,
    oauth2_user_info,
    oauth2_user_name,
)
from example.sanic_example.utils import api_exception, global_pait
from pait.app.sanic import AddDocRoute, Pait, add_doc_route, load_app, pait
from pait.app.sanic.plugin.cache_response import CacheResponsePlugin
from pait.exceptions import PaitBaseException
from pait.extra.config import MatchRule
from pait.field import Header, Json, Query
from pait.model.status import PaitStatus
from pait.model.template import TemplateVar

test_filename: str = ""


user_pait: Pait = global_pait.create_sub_pait(group="user")
link_pait: Pait = global_pait.create_sub_pait(
    group="links",
    status=PaitStatus.release,
    tag=(tag.links_tag,),
)
other_pait: Pait = pait.create_sub_pait(author=("so1n",), status=PaitStatus.test, group="other")


@other_pait(
    desc="test pait raise tip",
    status=PaitStatus.abandoned,
    tag=(tag.raise_tag,),
    response_model_list=[SimpleRespModel, FailRespModel],
)
async def raise_tip_route(
    content__type: str = Header.i(description="Content-Type"),  # in flask, Content-Type's key is content_type
) -> dict:
    """Prompted error from pait when test does not find value"""
    return {"code": 0, "msg": "", "data": {"content_type": content__type}}


@other_pait(
    desc="test pait raise tip",
    status=PaitStatus.abandoned,
    tag=(tag.raise_tag,),
    response_model_list=[SimpleRespModel, FailRespModel],
    param_handler_plugin=NotTipAsyncParamHandler,
)
async def raise_not_tip_route(
    content__type: str = Header.i(description="Content-Type"),  # in flask, Content-Type's key is content_type
) -> dict:
    """Prompted error from pait when test does not find value"""
    return {"code": 0, "msg": "", "data": {"content_type": content__type}}


class CbvRoute(HTTPMethodView):
    content_type: str = Header.i(alias="Content-Type")

    @user_pait(
        status=PaitStatus.release,
        tag=(tag.cbv_tag,),
        response_model_list=[UserSuccessRespModel, FailRespModel],
    )
    async def get(
        self,
        uid: int = Query.i(description="user id", gt=10, lt=1000),
        user_name: str = Query.i(description="user name", min_length=2, max_length=4),
        sex: SexEnum = Query.i(description="sex"),
        model: UserOtherModel = Query.i(raw_return=True),
    ) -> response.HTTPResponse:
        """Text cbv route get"""
        return response.json(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "uid": uid,
                    "user_name": user_name,
                    "sex": sex.value,
                    "age": model.age,
                    "content_type": self.content_type,
                },
            }
        )

    @user_pait(
        desc="test cbv post method",
        tag=(tag.cbv_tag,),
        status=PaitStatus.release,
        response_model_list=[UserSuccessRespModel, FailRespModel],
    )
    async def post(
        self,
        uid: int = Json.i(description="user id", gt=10, lt=1000),
        user_name: str = Json.i(description="user name", min_length=2, max_length=4),
        sex: SexEnum = Json.i(description="sex"),
        model: UserOtherModel = Json.i(raw_return=True),
    ) -> response.HTTPResponse:
        """Text cbv route post"""
        return response.json(
            {
                "code": 0,
                "msg": "",
                "data": {
                    "uid": uid,
                    "user_name": user_name,
                    "sex": sex.value,
                    "age": model.age,
                    "content_type": self.content_type,
                },
            }
        )


class NotPaitCbvRoute(HTTPMethodView):
    user_name: str = Query.i()

    async def get(self) -> response.HTTPResponse:
        return response.text(self.user_name, 200)

    async def post(self) -> response.HTTPResponse:
        return response.text(self.user_name, 200)


@link_pait(response_model_list=[LoginRespModel])
def login_route(
    uid: str = Json.i(description="user id"), password: str = Json.i(description="password")
) -> response.HTTPResponse:
    # only use test
    return response.json(
        {"code": 0, "msg": "", "data": {"token": hashlib.sha256((uid + password).encode("utf-8")).hexdigest()}}
    )


@link_pait(response_model_list=[SuccessRespModel])
def get_user_route(
    token: str = Header.i(
        "",
        description="token",
        links=link_login_token_model,
        example=TemplateVar("token"),
    )
) -> response.HTTPResponse:
    if token:
        return response.json({"code": 0, "msg": ""})
    else:
        return response.json({"code": 1, "msg": ""})


async def not_pait_route(
    uid: int = Query.i(description="user id", gt=10, lt=1000),
) -> response.HTTPResponse:
    return response.text(str(uid), 200)


def add_api_doc_route(app: Sanic) -> None:
    """Split out to improve the speed of test cases"""
    add_doc_route(app, pin_code="6666", prefix="/", title="Pait Api Doc(private)")
    AddDocRoute(prefix="/api-doc", title="Pait Api Doc", app=app)


def create_app(configure_logging: bool = True) -> Sanic:
    app: Sanic = Sanic(name=__name__, configure_logging=configure_logging)
    CacheResponsePlugin.set_redis_to_app(app, Redis(decode_responses=True))
    app.add_route(login_route, "/api/login", methods={"POST"})
    app.add_route(get_user_route, "/api/user", methods={"GET"})
    app.add_route(raise_tip_route, "/api/raise-tip", methods={"POST"})
    app.add_route(raise_not_tip_route, "/api/raise-not-tip", methods={"POST"})
    app.add_route(CbvRoute.as_view(), "/api/cbv")
    app.add_route(NotPaitCbvRoute.as_view(), "/api/not-pait-cbv")
    app.add_route(not_pait_route, "/api/not-pait", methods={"GET"})

    app.add_route(post_route, "/api/field/post", methods={"POST"})
    app.add_route(pait_base_field_route, "/api/field/pait-base-field/<age>", methods={"POST"})
    app.add_route(field_default_factory_route, "/api/field/field-default-factory", methods={"POST"})
    app.add_route(same_alias_route, "/api/field/same-alias", methods={"GET"})
    app.add_route(pait_model_route, "/api/field/pait-model", methods={"POST"})

    app.add_route(check_response_route, "/api/resp/check-resp", methods={"GET"})
    app.add_route(text_response_route, "/api/resp/text-resp", methods={"GET"})
    app.add_route(html_response_route, "/api/resp/html-resp", methods={"GET"})
    app.add_route(file_response_route, "/api/resp/file-resp", methods={"GET"})

    app.add_route(mock_route, "/api/plugin/mock/<age>", methods={"GET"})
    app.add_route(cache_response, "/api/plugin/cache-response", methods={"GET"})
    app.add_route(cache_response1, "/api/plugin/cache-response1", methods={"GET"})
    app.add_route(check_json_plugin_route, "/api/plugin/check-json-plugin", methods={"GET"})
    app.add_route(auto_complete_json_route, "/api/plugin/auto-complete-json-plugin", methods={"GET"})
    app.add_route(check_json_plugin_route1, "/api/plugin/check-json-plugin-1", methods={"GET"})
    app.add_route(
        param_at_most_one_of_route_by_extra_param, "/api/plugin/at-most-one-of-by-extra-param", methods={"GET"}
    )
    app.add_route(param_at_most_one_of_route, "/api/plugin/at-most-one-of", methods={"GET"})
    app.add_route(param_required_route_by_extra_param, "/api/plugin/required-by-extra-param", methods={"GET"})
    app.add_route(param_required_route, "/api/plugin/required", methods={"GET"})

    app.add_route(depend_route, "/api/depend/depend", methods={"POST"})
    app.add_route(depend_contextmanager_route, "/api/depend/check-depend-contextmanager", methods={"GET"})
    app.add_route(pre_depend_contextmanager_route, "/api/depend/check-pre-depend-contextmanager", methods={"GET"})
    app.add_route(depend_async_contextmanager_route, "/api/depend/check-depend-async-contextmanager", methods={"GET"})
    app.add_route(
        pre_depend_async_contextmanager_route, "/api/depend/check-pre-depend-async-contextmanager", methods={"GET"}
    )

    app.add_route(api_key_cookie_route, "/api/security/api-key-cookie-route", methods={"GET"})
    app.add_route(api_key_query_route, "/api/security/api-key-header-route", methods={"GET"})
    app.add_route(api_key_header_route, "/api/security/api-key-query-route", methods={"GET"})

    app.add_route(oauth2_login, "/api/security/oauth2-login", methods={"POST"})
    app.add_route(oauth2_user_name, "/api/security/oauth2-user-name", methods={"GET"})
    app.add_route(oauth2_user_info, "/api/security/oauth2-user-info", methods={"GET"})
    app.exception(PaitBaseException)(api_exception)
    app.exception(ValidationError)(api_exception)
    app.exception(RuntimeError)(api_exception)
    load_app(app, auto_load_route=True)
    return app


if __name__ == "__main__":
    import uvicorn  # type: ignore
    from pydantic import BaseModel

    from pait.extra.config import apply_block_http_method_set, apply_extra_openapi_model
    from pait.g import config

    class ExtraModel(BaseModel):
        extra_a: str = Query.i(default="", description="Fields used to demonstrate the expansion module")
        extra_b: int = Query.i(default=0, description="Fields used to demonstrate the expansion module")

    config.init_config(
        apply_func_list=[
            apply_block_http_method_set({"HEAD", "OPTIONS"}),
            apply_extra_openapi_model(ExtraModel, match_rule=MatchRule(key="!tag", target="grpc")),
        ]
    )
    sanic_app: Sanic = create_app()
    add_grpc_gateway_route(sanic_app)
    add_api_doc_route(sanic_app)
    uvicorn.run(sanic_app)
