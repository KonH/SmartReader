from .._types import Callback, TriggerCallback, FeedbackListCallback
from ..types.content import Content
from ..types.params import UIParams
from . import UI


class MockUI(UI):
    def initialize(self, params: UIParams, callback: Callback) -> None: callback(True, "")
    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None: pass
    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None: callback(True, "", [])
    def receive_score(self, id: str, score: float) -> None: pass
    def terminate(self) -> None: pass
