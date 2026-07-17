from .._types import ContentListCallback
from . import Input


class MockInput(Input):
    def read_sources(self, start_ts: float, type: str, id: str, callback: ContentListCallback) -> None: callback(True, "", [])
