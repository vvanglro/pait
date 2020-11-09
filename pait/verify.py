import inspect
from functools import wraps
from typing import Callable, Type

from pait.app.base import (
    BaseAsyncAppDispatch,
    BaseAppDispatch,
)
from pait.param_handle import (
    async_class_param_handle,
    async_func_param_handle,
    class_param_handle,
    func_param_handle
)
from pait.util import (
    FuncSig,
    get_func_sig,
)


def async_params_verify(app: 'Type[BaseAsyncAppDispatch]'):
    def wrapper(func: Callable):
        func_sig: FuncSig = get_func_sig(func)
        qualname = func.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0]
        class_ = getattr(inspect.getmodule(func), qualname)

        @wraps(func)
        async def dispatch(*args, **kwargs):
            dispatch_web: BaseAsyncAppDispatch = app(class_, args, kwargs)
            func_args, func_kwargs = await async_func_param_handle(dispatch_web, func_sig)
            if dispatch_web.request_args:
                func_args.extend(dispatch_web.request_args)
            await async_class_param_handle(dispatch_web)
            return await func(*func_args, **func_kwargs)
        return dispatch
    return wrapper


def sync_params_verify(web: 'Type[BaseAppDispatch]'):
    def wrapper(func: Callable):
        func_sig: FuncSig = get_func_sig(func)
        qualname = func.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0]
        class_ = getattr(inspect.getmodule(func), qualname)

        @wraps(func)
        def dispatch(*args, **kwargs):
            dispatch_web: BaseAppDispatch = web(class_, args, kwargs)
            func_args, func_kwargs = func_param_handle(dispatch_web, func_sig)
            if dispatch_web.request_args:
                func_args.extend(dispatch_web.request_args)
            class_param_handle(dispatch_web)
            return func(*func_args, **func_kwargs)
        return dispatch
    return wrapper
