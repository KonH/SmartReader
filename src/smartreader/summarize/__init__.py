from abc import ABC, abstractmethod

from .._types import Callback, ContentCallback
from ..types.content import Content


class Summarize(ABC):
    @abstractmethod
    def initialize(self, callback: Callback) -> None: ...

    @abstractmethod
    def summarize(self, content: Content, callback: ContentCallback) -> None: ...
