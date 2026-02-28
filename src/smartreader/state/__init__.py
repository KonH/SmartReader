from abc import abstractmethod

from .._types import AllStateCallback
from ..config import Config


class State(Config):
    """
    Persistent state store. Inherits the full Config interface.

    Implementations wrap a storage backend (e.g. SQLite) and may add an
    optional encryption layer on top.
    """

    @abstractmethod
    def read_all(self, callback: AllStateCallback) -> None: ...
