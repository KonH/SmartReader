from abc import ABC, abstractmethod

from ._types import Callback, StateValueCallback
from .types.params import ConfigParams
from .types.values import StateValue


class Config(ABC):
    @abstractmethod
    def load(self, params: ConfigParams, callback: Callback) -> None: ...

    @abstractmethod
    def read_value(self, key: str, callback: StateValueCallback) -> None: ...

    @abstractmethod
    def write_value(self, key: str, value: StateValue, callback: Callback) -> None: ...

    @abstractmethod
    def save(self, callback: Callback) -> None: ...
