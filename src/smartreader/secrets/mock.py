from .._types import Callback, StringCallback
from ..types.params import SecretsParams
from . import Secrets


class MockSecrets(Secrets):
    def initialize(self, params: SecretsParams, callback: Callback) -> None: callback(True, "")
    def read_value(self, key: str, callback: StringCallback) -> None: callback(True, "", "")
