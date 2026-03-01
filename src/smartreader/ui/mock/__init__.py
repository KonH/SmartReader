from ..._types import Callback
from ...types.params import UIParams
from ..command import UICommand
from .. import UI


class MockUI(UI):
    def initialize(self, params: UIParams, callback: Callback) -> None:
        callback(True, "")

    def get_commands(self) -> list[type[UICommand]]:
        return []

    def loop(self, commands: list[UICommand]) -> None:
        pass

    def terminate(self) -> None:
        pass
