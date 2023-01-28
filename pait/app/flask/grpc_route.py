from typing import Any, Callable, List

from flask import Flask, Response, jsonify

from pait.app.base.grpc_route import GrpcGatewayRoute as BaseGrpcRouter
from pait.app.flask import pait
from pait.app.flask._simple_route import SimpleRoute, add_multi_simple_route


def make_response(_: Any, resp_dict: dict) -> Response:
    return jsonify(resp_dict)


class GrpcGatewayRoute(BaseGrpcRouter):
    pait = pait
    make_response: Callable = make_response

    def _add_route(self, app: Flask) -> Any:
        for parse_stub in self.parse_stub_list:
            simple_route: List[SimpleRoute] = []
            for _, grpc_model_list in parse_stub.method_list_dict.items():
                for grpc_model in grpc_model_list:
                    _route = self._gen_route_func(grpc_model)
                    if not _route:
                        continue
                    simple_route.append(
                        SimpleRoute(
                            url=self.url_handler(grpc_model.grpc_service_model.url),
                            route=_route,
                            methods=[grpc_model.grpc_service_model.http_method],
                        )
                    )
            add_multi_simple_route(
                app, *simple_route, prefix=self.prefix, title=self.title + parse_stub.name, import_name=__name__
            )
