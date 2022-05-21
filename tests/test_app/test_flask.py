import difflib
import json
import random
import sys
from typing import Callable, Generator, Type
from unittest import mock

import pytest
from flask import Flask, Response
from flask.ctx import AppContext
from flask.testing import FlaskClient
from pytest_mock import MockFixture

from example.param_verify import flask_example
from pait.api_doc.html import get_redoc_html, get_swagger_ui_html
from pait.api_doc.open_api import PaitOpenAPI
from pait.app import auto_load_app, get_app_attribute, set_app_attribute
from pait.app.flask import TestHelper as _TestHelper
from pait.app.flask import load_app
from pait.model import response
from tests.conftest import enable_plugin, grpc_test_create_user_request, grpc_test_openapi
from tests.test_app.base_test import BaseTest


@pytest.fixture
def client() -> Generator[FlaskClient, None, None]:
    # Flask provides a way to test your application by exposing the Werkzeug test Client
    # and handling the context locals for you.
    app: Flask = flask_example.create_app()
    client: FlaskClient = app.test_client()
    # Establish an application context before running the tests.
    ctx: AppContext = app.app_context()
    ctx.push()
    yield client  # this is where the testing happens!
    ctx.pop()


@pytest.fixture
def base_test() -> Generator[BaseTest, None, None]:
    # Flask provides a way to test your application by exposing the Werkzeug test Client
    # and handling the context locals for you.
    app: Flask = flask_example.create_app()
    client: FlaskClient = app.test_client()
    # Establish an application context before running the tests.
    ctx: AppContext = app.app_context()
    ctx.push()
    yield BaseTest(client, _TestHelper)
    ctx.pop()


def response_test_helper(
    client: FlaskClient, route_handler: Callable, pait_response: Type[response.PaitBaseResponseModel]
) -> None:
    from pait.app.flask.plugin.mock_response import MockPlugin

    test_helper: _TestHelper = _TestHelper(client, route_handler)
    test_helper.get()

    with enable_plugin(route_handler, MockPlugin.build()):
        resp: Response = test_helper.get()
        for key, value in pait_response.header.items():
            assert resp.headers[key] == value
        if issubclass(pait_response, response.PaitHtmlResponseModel) or issubclass(
            pait_response, response.PaitTextResponseModel
        ):
            assert resp.get_data().decode() == pait_response.get_example_value()
        else:
            assert resp.get_data() == pait_response.get_example_value()


class TestFlask:
    def test_post(self, client: FlaskClient) -> None:
        flask_test_helper: _TestHelper = _TestHelper(
            client,
            flask_example.post_route,
            body_dict={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
            header_dict={"user-agent": "customer_agent"},
        )
        for resp in [
            flask_test_helper.json(),
            client.post(
                "/api/post",
                headers={"user-agent": "customer_agent"},
                json={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
            ).get_json(),
        ]:
            assert resp["code"] == 0
            assert resp["data"] == {
                "uid": 123,
                "user_name": "appl",
                "age": 2,
                "content_type": "application/json",
                "sex": "man",
            }

    def test_check_json_route(self, client: FlaskClient) -> None:
        for url, api_code in [
            (
                "/api/check-json-plugin?uid=123&user_name=appl&sex=man&age=10",
                -1,
            ),
            ("/api/check-json-plugin?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
            ("/api/check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10", -1),
            ("/api/check-json-plugin-1?uid=123&user_name=appl&sex=man&age=10&display_age=1", 0),
        ]:
            resp: dict = client.get(url).get_json()
            assert resp["code"] == api_code
            if api_code == -1:
                assert resp["msg"] == "miss param: ['data', 'age']"

    def test_test_helper_not_support_mutil_method(self, client: FlaskClient) -> None:
        client.application.add_url_rule(
            "/api/text-resp", view_func=flask_example.text_response_route, methods=["GET", "POST"]
        )
        with pytest.raises(RuntimeError) as e:
            _TestHelper(client, flask_example.text_response_route).request()
        exec_msg: str = e.value.args[0]
        assert exec_msg == "Pait Can not auto select method, please choice method in ['GET', 'POST']"

    def test_doc_route(self, client: FlaskClient) -> None:
        flask_example.add_api_doc_route(client.application)
        assert client.get("/swagger").status_code == 404
        assert client.get("/redoc").status_code == 404
        assert client.get("/swagger?pin_code=6666").get_data().decode() == get_swagger_ui_html(
            "http://localhost/openapi.json?pin_code=6666", "Pait Api Doc(private)"
        )
        assert client.get("/redoc?pin_code=6666").get_data().decode() == get_redoc_html(
            "http://localhost/openapi.json?pin_code=6666", "Pait Api Doc(private)"
        )
        assert (
            json.loads(client.get("/openapi.json?pin_code=6666&template-token=xxx").get_data().decode())["paths"][
                "/api/user"
            ]["get"]["parameters"][0]["schema"]["example"]
            == "xxx"
        )
        assert (
            difflib.SequenceMatcher(
                None,
                str(client.get("/openapi.json?pin_code=6666").json),
                str(
                    PaitOpenAPI(
                        load_app(client.application),
                        title="Pait Doc",
                        open_api_server_list=[{"url": "http://localhost", "description": ""}],
                    ).open_api_dict
                ),
            ).quick_ratio()
            > 0.95
        )

    def test_auto_load_app_class(self) -> None:
        for i in auto_load_app.app_list:
            sys.modules.pop(i, None)
        import flask

        with mock.patch.dict("sys.modules", sys.modules):
            assert flask == auto_load_app.auto_load_app_class()

    def test_app_attribute(self, client: FlaskClient) -> None:
        key: str = "app_test_app_attribute"
        value: int = random.randint(1, 100)
        set_app_attribute(client.application, key, value)

        is_call: bool = False

        def demo_route() -> None:
            assert get_app_attribute(client.application, key) == value
            nonlocal is_call
            is_call = True

        url: str = "/api/test-invoke-demo"
        client.application.add_url_rule(url, view_func=demo_route)
        client.get(url)
        assert is_call

    def test_text_response(self, client: FlaskClient) -> None:
        response_test_helper(client, flask_example.text_response_route, response.PaitTextResponseModel)

    def test_html_response(self, client: FlaskClient) -> None:
        response_test_helper(client, flask_example.html_response_route, response.PaitHtmlResponseModel)

    def test_file_response(self, client: FlaskClient) -> None:
        response_test_helper(client, flask_example.file_response_route, response.PaitFileResponseModel)

    def test_raise_tip_route(self, base_test: BaseTest) -> None:
        base_test.raise_tip_route(flask_example.raise_tip_route)

    def test_auto_complete_json_route(self, base_test: BaseTest) -> None:
        base_test.auto_complete_json_route(flask_example.auto_complete_json_route)

    def test_depend_route(self, base_test: BaseTest) -> None:
        base_test.depend_route(flask_example.depend_route)

    def test_same_alias_name(self, base_test: BaseTest) -> None:
        base_test.same_alias_name(flask_example.same_alias_route)

    def test_field_default_factory_route(self, base_test: BaseTest) -> None:
        base_test.field_default_factory_route(flask_example.field_default_factory_route)

    def test_pait_base_field_route(self, base_test: BaseTest) -> None:
        base_test.pait_base_field_route(flask_example.pait_base_field_route, ignore_path=False)

    def test_check_param(self, base_test: BaseTest) -> None:
        base_test.check_param(flask_example.check_param_route)

    def test_check_response(self, base_test: BaseTest) -> None:
        base_test.check_response(flask_example.check_response_route)

    def test_mock_route(self, base_test: BaseTest) -> None:
        base_test.mock_route(flask_example.mock_route, flask_example.UserSuccessRespModel2)

    def test_pait_model(self, base_test: BaseTest) -> None:
        base_test.pait_model(flask_example.pait_model_route)

    def test_depend_contextmanager(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.depend_contextmanager(flask_example.depend_contextmanager_route, mocker)

    def test_pre_depend_contextmanager(self, base_test: BaseTest, mocker: MockFixture) -> None:
        base_test.pre_depend_contextmanager(flask_example.pre_depend_contextmanager_route, mocker)

    def test_get_cbv(self, base_test: BaseTest) -> None:
        base_test.get_cbv(flask_example.CbvRoute.get)

    def test_post_cbv(self, base_test: BaseTest) -> None:
        base_test.post_cbv(flask_example.CbvRoute.post)

    def test_cache_response(self, base_test: BaseTest) -> None:
        base_test.cache_response(flask_example.cache_response, flask_example.cache_response1)

    def test_cache_other_response_type(self, base_test: BaseTest) -> None:
        flask_example.CacheResponsePlugin.set_redis_to_app(
            base_test.client.application, flask_example.Redis(decode_responses=True)
        )
        base_test.cache_other_response_type(
            flask_example.text_response_route, flask_example.html_response_route, flask_example.CacheResponsePlugin
        )

    def test_cache_response_param_name(self, base_test: BaseTest) -> None:
        base_test.cache_response_param_name(
            flask_example.post_route, flask_example.CacheResponsePlugin, flask_example.Redis(decode_responses=True)
        )


class TestFlaskGrpc:
    def test_create_user(self, client: FlaskClient) -> None:
        flask_example.add_grpc_gateway_route(client.application)
        flask_example.add_api_doc_route(client.application)

        def _(request_dict: dict) -> None:
            body: bytes = client.post("/api/user/create", json=request_dict).data
            assert body == b"{}\n"

        grpc_test_create_user_request(client.application, _)

    def test_grpc_openapi(self, client: FlaskClient) -> None:
        flask_example.add_grpc_gateway_route(client.application)

        from pait.app.flask import load_app

        grpc_test_openapi(load_app(client.application))

    def test_grpc_openapi_by_protobuf_file(self, client: FlaskClient) -> None:
        import os

        from example.example_grpc.python_example_proto_code.example_proto.book import manager_pb2_grpc, social_pb2_grpc
        from example.example_grpc.python_example_proto_code.example_proto.user import user_pb2_grpc
        from pait.app.flask import load_app
        from pait.app.flask.grpc_route import GrpcGatewayRoute
        from pait.util.grpc_inspect.message_to_pydantic import grpc_timestamp_int_handler

        project_path: str = os.getcwd().split("pait/")[0]
        if project_path.endswith("pait"):
            project_path += "/"
        elif not project_path.endswith("pait/"):
            project_path = os.path.join(project_path, "pait/")
        grpc_path: str = project_path + "example/example_grpc/"

        prefix: str = "/api-test"

        GrpcGatewayRoute(
            client.application,
            user_pb2_grpc.UserStub,
            social_pb2_grpc.BookSocialStub,
            manager_pb2_grpc.BookManagerStub,
            prefix=prefix + "/",
            title="Grpc-test",
            grpc_timestamp_handler_tuple=(int, grpc_timestamp_int_handler),
            parse_msg_desc=grpc_path,
        )
        grpc_test_openapi(load_app(client.application), url_prefix=prefix)
