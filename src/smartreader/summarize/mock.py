from .._types import Callback, ContentCallback
from ..types.content import Content
from . import Summarize


class MockSummarize(Summarize):
    def initialize(self, callback: Callback) -> None: callback(True, "")
    def summarize(self, content: Content, callback: ContentCallback) -> None: callback(True, "", content)
