import os

from .._types import Callback, StringCallback
from ..types.params import SecretsParams
from . import Secrets


class EnvSecrets(Secrets):
    """Reads secrets from environment variables."""

    def initialize(self, params: SecretsParams, callback: Callback) -> None:
        callback(True, "")

    def read_value(self, key: str, callback: StringCallback) -> None:
        val = os.environ.get(key, "")
        if val:
            callback(True, "", val)
        else:
            callback(False, f"environment variable {key!r} is not set", "")
