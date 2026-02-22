from .._types import Callback, StateValueCallback
from ..types.params import ConfigParams
from ..types.values import StateValue
from . import State


class MockState(State):
    def load(self, params: ConfigParams, callback: Callback) -> None: callback(True, "")
    def read_value(self, key: str, callback: StateValueCallback) -> None: callback(True, "", {})
    def write_value(self, key: str, value: StateValue, callback: Callback) -> None: callback(True, "")
    def save(self, callback: Callback) -> None: callback(True, "")
