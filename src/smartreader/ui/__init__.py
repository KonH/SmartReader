from abc import ABC, abstractmethod

from .._types import Callback
from ..types.params import UIParams
from .command import UICommand


class UI(ABC):
    @abstractmethod
    def initialize(self, params: UIParams, callback: Callback) -> None: ...

    @abstractmethod
    def get_commands(self) -> list[type[UICommand]]: ...

    @abstractmethod
    def loop(self, commands: list[UICommand]) -> None: ...

    @abstractmethod
    def terminate(self) -> None: ...
