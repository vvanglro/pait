from typing import Any

from pait.plugin.auto_complete_json_resp import AutoCompleteJsonRespPlugin as _AutoCompleteJsonRespPlugin
from pait.plugin.base import PluginContext

from .unified_response import UnifiedResponsePluginProtocol

__all__ = ["AsyncAutoCompleteJsonRespPlugin", "AutoCompleteJsonRespPlugin"]


class AutoCompleteJsonRespPlugin(UnifiedResponsePluginProtocol, _AutoCompleteJsonRespPlugin):
    def _sync_call(self, context: PluginContext) -> Any:
        response: Any = super()._sync_call(context)
        return self._gen_response(response, context)

    async def _async_call(self, context: PluginContext) -> Any:
        response: Any = await super()._async_call(context)
        return self._gen_response(response, context)


class AsyncAutoCompleteJsonRespPlugin(AutoCompleteJsonRespPlugin):
    """"""
