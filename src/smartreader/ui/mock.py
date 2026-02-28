from .._types import Callback, TriggerCallback, FeedbackListCallback, NewSourceCallback
from ..types.app_state import AppStateData
from ..types.content import Content
from ..types.params import UIParams
from . import UI


class MockUI(UI):
    def initialize(self, params: UIParams, callback: Callback) -> None: callback(True, "")
    def wait_trigger(self, categories: list[str], callback: TriggerCallback) -> None: pass
    def show_content_list(self, content: list[Content], callback: FeedbackListCallback) -> None: callback(True, "", [])
    def receive_score(self, id: str, score: float) -> None: pass
    def prompt_new_source(self, callback: NewSourceCallback) -> None: callback(True, "", None)
    def show_logs(self, lines: list[str], callback: Callback) -> None: callback(True, "")
    def show_state(self, data: AppStateData, callback: Callback) -> None: callback(True, "")
    def terminate(self) -> None: pass
