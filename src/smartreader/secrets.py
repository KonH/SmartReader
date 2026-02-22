from abc import ABC, abstractmethod

from ._types import Callback, StringCallback
from .types.params import SecretsParams


class Secrets(ABC):
    @abstractmethod
    def initialize(self, params: SecretsParams, callback: Callback) -> None: ...

    @abstractmethod
    def read_value(self, key: str, callback: StringCallback) -> None: ...
