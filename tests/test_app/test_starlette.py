import asyncio
import difflib
import json
import random
import sys
from contextlib import contextmanager
from queue import Queue
from typing import Callable, Generator, Tuple, Type
from unittest import mock

import pytest
from pytest_mock import MockFixture
from redis import Redis  # type: ignore
from requests import Response  # type: ignore
from starlette.applications import Starlette
from starlette.testclient import TestClient

from example.common import response_model
from example.starlette_example import main_example
from pait.app import auto_load_app, get_app_attribute, set_app_attribute
from pait.app.base.doc_route import default_doc_fn_dict
from pait.app.starlette import TestHelper as _TestHelper
from pait.app.starlette import load_app
from pait.app.starlette.plugin.mock_response import MockPlugin
from pait.model import response
from pait.openapi.openapi import InfoModel, OpenAPI, ServerModel
from tests.conftest import enable_plugin, grpc_request_test, grpc_test_openapi
from tests.test_app.base_test import BaseTest


@contextmanager
def client_ctx() -> Generator[TestClient, None, None]:
    # starlette run after sanic
    # fix starlette.testclient get_event_loop status is close
    # def get_event_loop() -> asyncio.AbstractEventLoop:
    #     try:
    #         loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
    #         if loop.is_closed():
    #             loop = asyncio.new_event_loop()
    #     except RuntimeError:
    #         loop = asyncio.new_event_loop()
    #         asyncio.set_event_loop(loop)
    #     return loop
    #
    # mocker.patch("asyncio.get_event_loop").return_value = get_event_loop()
    # asyncio.set_event_loop(asyncio.new_event_loop())
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        asyncio.set_event_loop(asyncio.new_event_loop())
    with TestClient(main_example.create_app()) as client:
        yield client


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    with client_ctx() as client:
        yield client


@contextmanager
def base_test_ctx() -> Generator[BaseTest, None, None]:
    with client_ctx() as client:
        yield BaseTest(client, _TestHelper)


@pytest.fixture
def base_test() -> Generator[BaseTest, None, None]:
    with base_test_ctx() as base_test:
        yield base_test


@contextmanager
def grpc_client() -> Generator[Tuple[TestClient, Queue], None, None]:
    app = main_example.create_app()
    main_example.add_grpc_gateway_route(app)
    main_example.add_api_doc_route(app)
    with grpc_request_test(app) as queue:
        with TestClient(app) as client:
            yield client, queue


def response_test_helper(
    client: TestClient,
    route_handler: Callable,
    pait_response: Type[response.BaseResponseModel],
    plugin: Type[MockPlugin],
) -> None:
    test_helper: _TestHelper = _TestHelper(client, route_handler)
    test_helper.get()

    with enable_plugin(route_handler, plugin.build()):
        resp: Response = test_helper.get()
        for key, value in pait_response.get_header_example_dict().items():
            assert resp.headers[key] == value
        if issubclass(pait_response, response.HtmlResponseModel) or issubclass(
            pait_response, response.TextResponseModel
        ):
            assert resp.text == pait_response.get_example_value()
        else:
            assert resp.content == pait_response.get_example_value()


class TestStarlette:
    def test_test_helper_not_support_mutil_method(self, client: TestClient) -> None:
        app: Starlette = client.app  # type: ignore
        app.add_route("/api/new-text-resp", main_example.text_response_route, methods=["GET", "POST"])
        with pytest.raises(RuntimeError) as e:
            _TestHelper(client, main_example.text_response_route).request()
        exec_msg: str = e.value.args[0]
        assert exec_msg == "Pait Can not auto select method, please choice method in ['GET', 'POST']"

    def test_post(self, client: TestClient) -> None:
        test_helper: _TestHelper = _TestHelper(
            client,
            main_example.post_route,
            body_dict={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
            header_dict={"user-agent": "customer_agent"},
        )
        for resp in [
            test_helper.json(),
            client.post(
                "/api/field/post",
                headers={"user-agent": "customer_agent"},
                json={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
            ).json(),
        ]:
            assert resp["code"] == 0
            assert resp["data"] == {
                "uid": 123,
                "user_name": "appl",
                "age": 2,
                "content_type": "application/json",
                "sex": "man",
            }

    def test_check_json_route(self, client: TestClient) -> None:
        for url, api_code in [
            # sync route
            (
                "/api/plugin/check-json-plugin?uid=123&user_name=appl&sex=man&age=10",
                -1,
            ),
            ("/api/plugin/check-json-plugin?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
            ("/api/plugin/check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10", -1),
            ("/api/plugin/check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
            # async route
            ("/api/plugin/async-check-json-plugin?uid=123&user_name=appl&sex=man&age=10", -1),
            ("/api/plugin/async-check-json-plugin?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
            ("/api/plugin/async-check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10", -1),
            ("/api/plugin/async-check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
        ]:
            resp: dict = client.get(url).json()
            assert resp["code"] == api_code
            if api_code == -1:
                assert resp["msg"] == "miss param: ['data', 'age']"

    def test_text_response(self, client: TestClient) -> None:
        from pait.app.starlette.plugin.mock_response import MockPlugin

        response_test_helper(client, main_example.text_response_route, response.TextResponseModel, MockPlugin)
        response_test_helper(client, main_example.async_text_response_route, response.TextResponseModel, MockPlugin)

    def test_html_response(self, client: TestClient) -> None:
        from pait.app.starlette.plugin.mock_response import MockPlugin

        response_test_helper(client, main_example.html_response_route, response.HtmlResponseModel, MockPlugin)
        response_test_helper(client, main_example.async_html_response_route, response.HtmlResponseModel, MockPlugin)

    def test_file_response(self, client: TestClient) -> None:
        from pait.app.starlette.plugin.mock_response import MockPlugin

        response_test_helper(client, main_example.file_response_route, response.FileResponseModel, MockPlugin)
        response_test_helper(client, main_example.async_file_response_route, response.FileResponseModel, MockPlugin)

    def test_doc_route(self, client: TestClient) -> None:
        main_example.add_api_doc_route(client.app)
        for doc_route_path in default_doc_fn_dict.keys():
            assert client.get(f"/{doc_route_path}").status_code == 404
            assert client.get(f"/api-doc/{doc_route_path}").status_code == 200

        for doc_route_path, fn in default_doc_fn_dict.items():
            assert client.get(f"/{doc_route_path}?pin-code=6666").text == fn(
                f"{client.base_url}/openapi.json?pin-code=6666", title="Pait Api Doc(private)"
            )

        assert (
            json.loads(client.get("/openapi.json?pin-code=6666&template-token=xxx").text)["paths"]["/api/user"]["get"][
                "parameters"
            ][0]["schema"]["example"]
            == "xxx"
        )
        assert (
            difflib.SequenceMatcher(
                None,
                str(client.get("/openapi.json?pin-code=6666").text),
                str(
                    OpenAPI(
                        load_app(client.app),  # type: ignore
                        openapi_info_model=InfoModel(title="Pait Doc"),
                        server_model_list=[ServerModel(url="http://localhost")],
                    ).content()
                ),
            ).quick_ratio()
            > 0.95
        )

    def test_auto_load_app_class(self) -> None:
        for i in auto_load_app.app_list:
            sys.modules.pop(i, None)
        import starlette

        with mock.patch.dict("sys.modules", sys.modules):
            assert starlette == auto_load_app.auto_load_app_class()

    def test_app_attribute(self, client: TestClient) -> None:
        key: str = "test_app_attribute"
        value: int = random.randint(1, 100)
        set_app_attribute(client.app, key, value)
        assert get_app_attribute(client.app, key) == value

    def test_raise_tip_route(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.raise_tip_route(main_example.raise_tip_route, mocker=mocker)

    def test_raise_not_tip_route(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.raise_tip_route(main_example.raise_not_tip_route, mocker=mocker, is_raise=False)

    def test_auto_complete_json_route(self, base_test: BaseTest) -> None:
        base_test.auto_complete_json_route(main_example.auto_complete_json_route)

    def test_depend_route(self, base_test: BaseTest) -> None:
        base_test.depend_route(main_example.depend_route)

    def test_same_alias_name(self, base_test: BaseTest) -> None:
        base_test.same_alias_name(main_example.same_alias_route)

    def test_field_default_factory_route(self, base_test: BaseTest) -> None:
        base_test.field_default_factory_route(main_example.field_default_factory_route)

    def test_pait_base_field_route(self, base_test: BaseTest) -> None:
        base_test.pait_base_field_route(main_example.pait_base_field_route)

    def test_param_at_most_one_of_route(self, base_test: BaseTest) -> None:
        base_test.param_at_most_one_of_route(main_example.param_at_most_one_of_route_by_extra_param)
        base_test.param_at_most_one_of_route(main_example.param_at_most_one_of_route)

    def test_param_required_route(self, base_test: BaseTest) -> None:
        base_test.param_required_route(main_example.param_required_route_by_extra_param)
        base_test.param_required_route(main_example.param_required_route)

    def test_check_response(self, base_test: BaseTest) -> None:
        base_test.check_response(main_example.check_response_route)

    def test_mock_route(self, base_test: BaseTest) -> None:
        base_test.mock_route(main_example.mock_route, response_model.UserSuccessRespModel2)

    def test_async_mock_route(self, base_test: BaseTest) -> None:
        base_test.mock_route(main_example.async_mock_route, response_model.UserSuccessRespModel2)

    def test_pait_model(self, base_test: BaseTest) -> None:
        base_test.pait_model(main_example.pait_model_route)

    def test_depend_contextmanager(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.depend_contextmanager(main_example.depend_contextmanager_route, mocker)

    def test_depend_async_contextmanager(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.depend_contextmanager(main_example.depend_async_contextmanager_route, mocker)

    def test_pre_depend_async_contextmanager(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.pre_depend_contextmanager(main_example.pre_depend_async_contextmanager_route, mocker)

    def test_api_key_route(self, base_test: BaseTest) -> None:
        base_test.api_key_route(main_example.api_key_cookie_route, {"cookie_dict": {"token": "my-token"}})
        base_test.api_key_route(main_example.api_key_header_route, {"header_dict": {"token": "my-token"}})
        base_test.api_key_route(main_example.api_key_query_route, {"query_dict": {"token": "my-token"}})

    def test_oauth2_password_route(self, base_test: BaseTest) -> None:
        base_test.oauth2_password_route(
            login_route=main_example.oauth2_login,
            user_name_route=main_example.oauth2_user_name,
            user_info_route=main_example.oauth2_user_info,
        )

    def test_get_user_name_by_http_bearer(self, base_test: BaseTest) -> None:
        base_test.get_user_name_by_http_bearer(main_example.get_user_name_by_http_bearer)

    def test_get_user_name_by_http_digest(self, base_test: BaseTest) -> None:
        base_test.get_user_name_by_http_digest(main_example.get_user_name_by_http_digest)

    def test_get_user_name_by_http_basic_credentials(self, base_test: BaseTest) -> None:
        base_test.get_user_name_by_http_basic_credentials(main_example.get_user_name_by_http_basic_credentials)

    def test_get_cbv(self, base_test: BaseTest) -> None:
        base_test.get_cbv(main_example.CbvRoute.get)

    def test_post_cbv(self, base_test: BaseTest) -> None:
        base_test.post_cbv(main_example.CbvRoute.post)

    def test_cache_response(self, base_test: BaseTest) -> None:
        base_test.cache_response(main_example.cache_response, main_example.cache_response1, app="starlette")

    def test_cache_other_response_type(self, base_test: BaseTest) -> None:
        main_example.CacheResponsePlugin.set_redis_to_app(base_test.client.app, Redis(decode_responses=True))
        base_test.cache_other_response_type(
            main_example.text_response_route,
            main_example.html_response_route,
            main_example.CacheResponsePlugin,
        )

    def test_cache_response_param_name(self, base_test: BaseTest) -> None:
        base_test.cache_response_param_name(
            main_example.post_route,
            main_example.CacheResponsePlugin,
            main_example.Redis(decode_responses=True),
        )


class TestStarletteGrpc:
    def test_create_user(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.user.user_pb2 import CreateUserRequest

        with grpc_client() as grpc_client_tuple:
            for url in ("/api/user/create", "/api/static/user/create"):
                client, queue = grpc_client_tuple
                body: bytes = client.post(
                    url,
                    json={"uid": "10086", "user_name": "so1n", "pw": "123456", "sex": 0},
                    headers={"token": "token"},
                ).content
                assert body == b'{"code":0,"msg":"","data":{}}'
                message: CreateUserRequest = queue.get(timeout=1)
                assert message.uid == "10086"
                assert message.user_name == "so1n"
                assert message.password == "123456"
                assert message.sex == 0

    def test_get_book(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.book.manager_pb2 import GetBookRequest

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple

            for url in ("/api/book/get", "/api/static/book/get"):
                body: bytes = client.post(url + "?isbn=xxxa", headers={"token": "token"}).content
                assert json.loads(body.decode()) == {
                    "code": 0,
                    "data": {"bookAuthor": "", "bookDesc": "", "bookName": "", "bookUrl": "", "isbn": ""},
                    "msg": "",
                }
                queue.get(timeout=1)
                message: GetBookRequest = queue.get(timeout=1)
                assert message.isbn == "xxxa"

    def test_get_book_list(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.book.manager_pb2 import GetBookListRequest

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple

            for url in ("/api/book/get-list", "/api/static/book/get-list"):
                body: bytes = client.post(
                    url, json={"limit": 0, "next_create_time": "2023-04-10 18:44:36"}, headers={"token": "token"}
                ).content
                assert json.loads(body.decode()) == {"code": 0, "data": {"result": []}, "msg": ""}
                queue.get(timeout=1)
                message: GetBookListRequest = queue.get(timeout=1)
                assert message.limit == 0

    def test_get_book_like(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.book.social_pb2 import (
            GetBookLikesRequest,
            NestedGetBookLikesRequest,
        )

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple

            for url in (
                "/api/book/get-book-like",
                "/api/book/get-book-like-other",
                "/api/static/book/get-book-like",
                "/api/static/book/get-book-like-other",
            ):
                body: bytes = client.post(url, json={"isbn": ["xxxa", "xxxb"]}, headers={"token": "token"}).content
                assert json.loads(body.decode()) == {"code": 0, "data": {"result": []}, "msg": ""}
                queue.get(timeout=1)
                if not url.endswith("other"):
                    message1: GetBookLikesRequest = queue.get(timeout=1)
                    assert message1.isbn == ["xxxa", "xxxb"]
                else:
                    message2: NestedGetBookLikesRequest = queue.get(timeout=1)
                    assert message2.nested.isbn == ["xxxa", "xxxb"]

    def test_login(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.user.user_pb2 import LoginUserRequest

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple
            for url in ("/api/user/login", "/api/static/user/login"):
                body: bytes = client.post(url, json={"uid": "10086", "password": "pw"}).content
                assert body == b'{"code":0,"msg":"","data":{"uid":"","userName":"","token":""}}'
                message: LoginUserRequest = queue.get(timeout=1)
                assert message.uid == "10086"
                assert message.password == "pw"

    def test_logout(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.user.user_pb2 import LogoutUserRequest

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple
            for url in ("/api/user/logout", "/api/static/user/logout"):
                body: bytes = client.post(url, json={"uid": "10086"}, headers={"token": "token"}).content
                assert body == b'{"code":0,"msg":"","data":{}}'
                message: LogoutUserRequest = queue.get(timeout=1)
                assert message.uid == "10086"
                assert message.token == "token"

    def test_delete_fail_token(self) -> None:
        from example.grpc_common.python_example_proto_code.example_proto.user.user_pb2 import GetUidByTokenRequest

        with grpc_client() as grpc_client_tuple:
            client, queue = grpc_client_tuple
            for url in ("/api/user/delete", "/api/static/user/delete"):
                body: bytes = client.post(
                    url,
                    json={"uid": "10086"},
                    headers={"token": "fail_token"},
                ).content
                assert body == b'{"code":-1,"msg":"Not found user by token:fail_token"}'
                message: GetUidByTokenRequest = queue.get(timeout=1)
                assert message.token == "fail_token"

    def test_grpc_openapi(self) -> None:
        from pait.app.starlette import load_app

        app = main_example.create_app()
        main_example.add_grpc_gateway_route(app)

        with TestClient(app) as client:
            grpc_test_openapi(load_app(client.app))
            grpc_test_openapi(load_app(client.app), url_prefix="/api/static", option_str="_by_option")

    def test_grpc_openapi_by_protobuf_file(self, base_test: BaseTest) -> None:
        from pait.app.starlette import load_app
        from pait.grpc import AsyncGrpcGatewayRoute as GrpcGatewayRoute

        base_test.grpc_openapi_by_protobuf_file(base_test.client.app, GrpcGatewayRoute, load_app)

    def test_grpc_openapi_by_option(self) -> None:
        from pait.app.starlette import load_app
        from pait.grpc import AsyncGrpcGatewayRoute as GrpcGatewayRoute

        with base_test_ctx() as base_test:
            base_test.grpc_openapi_by_option(base_test.client.app, GrpcGatewayRoute, load_app)
