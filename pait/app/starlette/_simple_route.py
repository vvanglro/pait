from starlette.applications import Starlette

from pait.app.base.simple_route import SimpleRoute, add_route_plugin
from pait.app.starlette.plugin.unified_response import UnifiedResponsePlugin


def add_simple_route(
    app: Starlette,
    simple_route: "SimpleRoute",
    prefix: str = "/",
    title: str = "",
) -> None:
    add_route_plugin(simple_route, UnifiedResponsePlugin)
    if prefix == "/" and simple_route.url.startswith("/"):
        url: str = simple_route.url
    else:
        url = prefix + simple_route.url
    app.add_route(url, simple_route.route, methods=simple_route.methods, name=title)


def add_multi_simple_route(
    app: Starlette,
    *simple_route_list: "SimpleRoute",
    prefix: str = "/",
    title: str = "",
) -> None:
    for simple_route in simple_route_list:
        add_simple_route(app, simple_route, prefix=prefix, title=title)
