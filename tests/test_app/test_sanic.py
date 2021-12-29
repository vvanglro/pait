import sys
from tempfile import NamedTemporaryFile
from typing import Callable, Generator, Type
from unittest import mock

import pytest
from pytest_mock import MockFixture
from sanic import Sanic
from sanic_testing import TestManager as SanicTestManager  # type: ignore
from sanic_testing.testing import SanicTestClient
from sanic_testing.testing import TestingResponse as Response  # type: ignore

from example.param_verify.sanic_example import create_app
from example.param_verify.sanic_example import test_check_param as check_param_route
from example.param_verify.sanic_example import test_check_resp as check_resp_route
from example.param_verify.sanic_example import test_depend_async_contextmanager as depend_async_contextmanager
from example.param_verify.sanic_example import test_depend_contextmanager as depend_contextmanager
from example.param_verify.sanic_example import test_file_response as file_response
from example.param_verify.sanic_example import test_get as get_route
from example.param_verify.sanic_example import test_html_response as html_response
from example.param_verify.sanic_example import test_other_field as other_field_route
from example.param_verify.sanic_example import test_post as post_route
from example.param_verify.sanic_example import test_pre_depend_async_contextmanager as pre_depend_async_contextmanager
from example.param_verify.sanic_example import test_pre_depend_contextmanager as pre_depend_contextmanager
from example.param_verify.sanic_example import test_same_alias as same_alias_route
from example.param_verify.sanic_example import test_text_response as text_response
from pait.app import auto_load_app
from pait.app.sanic import SanicTestHelper
from pait.model import response
from tests.conftest import enable_mock


@pytest.fixture
def client() -> Generator[SanicTestClient, None, None]:
    app: Sanic = create_app()
    SanicTestManager(app)
    yield app.test_client


def response_test_helper(
    client: SanicTestClient, route_handler: Callable, pait_response: Type[response.PaitBaseResponseModel]
) -> None:
    test_helper: SanicTestHelper = SanicTestHelper(client, route_handler)
    test_helper.get()

    with enable_mock(test_helper):
        resp: Response = test_helper.get()
        for key, value in pait_response.header.items():
            assert resp.headers[key] == value
        if issubclass(pait_response, response.PaitHtmlResponseModel) or issubclass(
            pait_response, response.PaitTextResponseModel
        ):
            assert resp.text == pait_response.get_example_value()
        else:
            assert resp.content == pait_response.get_example_value()


class TestSanic:
    def test_get(self, client: SanicTestClient) -> None:
        sanic_test_helper: SanicTestHelper = SanicTestHelper(
            client,
            get_route,
            path_dict={"age": 3},
            query_dict={"uid": "123", "user_name": "appl", "sex": "man", "multi_user_name": ["abc", "efg"]},
        )
        request, response = client.get(
            "/api/get/3?uid=123&user_name=appl&sex=man&multi_user_name=abc&multi_user_name=efg"
        )
        for resp in [sanic_test_helper.json(), response.json]:
            assert resp["code"] == 0
            assert resp["data"] == {
                "uid": 123,
                "user_name": "appl",
                "email": "example@xxx.com",
                "age": 3,
                "sex": "man",
                "multi_user_name": ["abc", "efg"],
            }

    def test_check_param(self, client: SanicTestClient) -> None:
        sanic_test_helper: SanicTestHelper = SanicTestHelper(
            client,
            check_param_route,
            query_dict={"uid": 123, "user_name": "appl", "sex": "man", "age": 10, "alias_user_name": "appe"},
        )
        assert "requires at most one of param user_name or alias_user_name" in sanic_test_helper.json()["msg"]
        sanic_test_helper = SanicTestHelper(
            client, check_param_route, query_dict={"uid": 123, "sex": "man", "age": 10, "alias_user_name": "appe"}
        )
        assert "birthday requires param alias_user_name, which if not none" in sanic_test_helper.json()["msg"]

    def test_text_response(self, client: SanicTestClient) -> None:
        response_test_helper(client, text_response, response.PaitTextResponseModel)

    def test_html_response(self, client: SanicTestClient) -> None:
        response_test_helper(client, html_response, response.PaitHtmlResponseModel)

    def test_file_response(self, client: SanicTestClient) -> None:
        response_test_helper(client, file_response, response.PaitFileResponseModel)

    def test_check_response(self, client: SanicTestClient) -> None:
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            check_resp_route,
            query_dict={"uid": 123, "user_name": "appl", "sex": "man", "age": 10},
        )
        with pytest.raises(RuntimeError):
            test_helper.json()
        test_helper = SanicTestHelper(
            client,
            check_resp_route,
            query_dict={"uid": 123, "user_name": "appl", "sex": "man", "age": 10, "display_age": 1},
        )
        test_helper.json()

    def test_depend_contextmanager(self, client: SanicTestClient, mocker: MockFixture) -> None:
        error_logger = mocker.patch("example.param_verify.model.logging.error")
        info_logger = mocker.patch("example.param_verify.model.logging.info")
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            depend_contextmanager,
            query_dict={"uid": 123},
        )
        test_helper.get()
        info_logger.assert_called_once_with("context_depend exit")
        test_helper = SanicTestHelper(
            client,
            depend_contextmanager,
            query_dict={"uid": 123, "is_raise": True},
        )
        test_helper.get()
        error_logger.assert_called_once_with("context_depend error")

    def test_depend_async_contextmanager(self, client: SanicTestClient, mocker: MockFixture) -> None:
        error_logger = mocker.patch("example.param_verify.model.logging.error")
        info_logger = mocker.patch("example.param_verify.model.logging.info")
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            depend_async_contextmanager,
            query_dict={"uid": 123},
        )
        test_helper.get()
        info_logger.assert_called_once_with("context_depend exit")
        test_helper = SanicTestHelper(
            client,
            depend_async_contextmanager,
            query_dict={"uid": 123, "is_raise": True},
        )
        test_helper.get()
        error_logger.assert_called_once_with("context_depend error")

    def test_pre_depend_contextmanager(self, client: SanicTestClient, mocker: MockFixture) -> None:
        error_logger = mocker.patch("example.param_verify.model.logging.error")
        info_logger = mocker.patch("example.param_verify.model.logging.info")
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            pre_depend_contextmanager,
            query_dict={"uid": 123},
        )
        test_helper.get()
        info_logger.assert_called_once_with("context_depend exit")
        test_helper = SanicTestHelper(
            client,
            pre_depend_contextmanager,
            query_dict={"uid": 123, "is_raise": True},
        )
        test_helper.get()
        error_logger.assert_called_once_with("context_depend error")

    def test_pre_depend_async_contextmanager(self, client: SanicTestClient, mocker: MockFixture) -> None:
        error_logger = mocker.patch("example.param_verify.model.logging.error")
        info_logger = mocker.patch("example.param_verify.model.logging.info")
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            pre_depend_async_contextmanager,
            query_dict={"uid": 123},
        )
        test_helper.get()
        info_logger.assert_called_once_with("context_depend exit")
        test_helper = SanicTestHelper(
            client,
            pre_depend_async_contextmanager,
            query_dict={"uid": 123, "is_raise": True},
        )
        test_helper.get()
        error_logger.assert_called_once_with("context_depend error")

    def test_mock_get(self, client: SanicTestClient) -> None:
        request, response = client.get(
            "/api/mock/3?uid=123&user_name=appl&sex=man&multi_user_name=abc&multi_user_name=efg"
        )
        assert response.json == {
            "code": 0,
            "data": {
                "age": 99,
                "email": "example@so1n.me",
                "uid": 666,
                "user_name": "mock_name",
                "multi_user_name": [],
                "sex": "man",
            },
            "msg": "success",
        }

    def test_depend(self, client: SanicTestClient) -> None:
        request, response = client.post(
            "/api/depend?uid=123&user_name=appl", headers={"user-agent": "customer_agent"}, json={"age": 2}
        )
        resp: dict = response.json
        assert resp["code"] == 0
        assert resp["data"] == {"uid": 123, "user_name": "appl", "age": 2, "user_agent": "customer_agent"}

    def test_get_cbv(self, client: SanicTestClient) -> None:
        request, response = client.get(
            "/api/cbv?uid=123&user_name=appl&age=2", headers={"user-agent": "customer_agent"}
        )
        resp: dict = response.json
        assert resp["code"] == 0
        assert resp["data"] == {"uid": 123, "user_name": "appl", "email": "example@xxx.com", "age": 2}

    def test_post_cbv(self, client: SanicTestClient) -> None:
        request, response = client.post(
            "/api/cbv", headers={"user-agent": "customer_agent"}, json={"uid": 123, "user_name": "appl", "age": 2}
        )
        resp: dict = response.json
        assert resp["code"] == 0
        assert resp["data"] == {"uid": 123, "user_name": "appl", "age": 2, "user_agent": "customer_agent"}

    def test_post(self, client: SanicTestClient) -> None:
        sanic_test_helper: SanicTestHelper = SanicTestHelper(
            client,
            post_route,
            body_dict={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
            header_dict={"user-agent": "customer_agent"},
        )
        request, response = client.post(
            "/api/post",
            headers={"user-agent": "customer_agent"},
            json={"uid": 123, "user_name": "appl", "age": 2, "sex": "man"},
        )
        for resp in [sanic_test_helper.json(), response.json]:
            assert resp["code"] == 0
            assert resp["data"] == {
                "uid": 123,
                "user_name": "appl",
                "age": 2,
                "content_type": "application/json",
                "sex": "man",
            }

    def test_pait_model(self, client: SanicTestClient) -> None:
        request, response = client.post(
            "/api/pait_model?uid=123&user_name=appl", headers={"user-agent": "customer_agent"}, json={"age": 2}
        )
        resp: dict = response.json
        assert resp["code"] == 0
        assert resp["data"] == {"uid": 123, "user_name": "appl", "age": 2, "user_agent": "customer_agent"}

    def test_raise_tip(self, client: SanicTestClient) -> None:
        request, response = client.post(
            "/api/raise_tip", headers={"user-agent": "customer_agent"}, json={"uid": 123, "user_name": "appl", "age": 2}
        )
        resp: dict = response.json
        assert "msg" in resp

    def test_same_alias_name(self, client: SanicTestClient) -> None:
        test_helper: SanicTestHelper = SanicTestHelper(
            client,
            same_alias_route,
            query_dict={"token": "query"},
            header_dict={"token": "header"},
        )
        assert test_helper.json() == {"query_token": "query", "header_token": "header"}
        test_helper = SanicTestHelper(
            client,
            same_alias_route,
            query_dict={"token": "query1"},
            header_dict={"token": "header1"},
        )
        assert test_helper.json() == {"query_token": "query1", "header_token": "header1"}

    def test_other_field(self, client: SanicTestClient) -> None:
        cookie_str: str = "abcd=abcd;"

        file_content: str = "Hello Word!"

        with NamedTemporaryFile(delete=True) as f1:
            file_name: str = f1.name
            f1.write(file_content.encode())
            f1.seek(0)
            with NamedTemporaryFile(delete=True) as f2:
                f2.name = file_name  # type: ignore
                f2.write(file_content.encode())
                f2.seek(0)

                sanic_test_helper: SanicTestHelper = SanicTestHelper(
                    client,
                    other_field_route,
                    cookie_dict={"cookie": cookie_str},
                    file_dict={"upload_file": f1},
                    form_dict={"a": "1", "b": "2", "c": "3"},
                )
                request, response = client.post(
                    "/api/other_field",
                    headers={"cookie": cookie_str},
                    data={"a": "1", "b": "2", "c": "3"},
                    files={"upload_file": f2},
                )
                for resp in [sanic_test_helper.json(), response.json]:
                    assert {
                        "filename": file_name.split("/")[-1],
                        "content": file_content,
                        "form_a": "1",
                        "form_b": "2",
                        "form_c": ["3"],
                        "cookie": {"abcd": "abcd"},
                    } == resp["data"]

    def test_auto_load_app_class(self) -> None:
        for i in auto_load_app.app_list:
            sys.modules.pop(i, None)
        import starlette

        with mock.patch.dict("sys.modules", sys.modules):
            assert starlette == auto_load_app.auto_load_app_class()
