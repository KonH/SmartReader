from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._types import LiveFeedbackHandler


@dataclass
class UIParams:
    """Initialization parameters for a UI implementation."""
    live_feedback: LiveFeedbackHandler | None = field(default=None)


@dataclass
class TriggerParams:
    """Payload delivered by UI.wait_trigger when a run is initiated."""
    mode: str               # "ask" | "add" | "logs" | "state"
    category: str | None = None  # None means ALL categories


@dataclass
class NewSourceParams:
    """Parameters for a new source to be added to the config."""
    name: str           # config key: [[sources.<name>]]
    source_type: str    # "rss" | "telegram"
    external_id: str    # feed URL or channel ID
    category: str | None = None


@dataclass
class ConfigParams:
    """Initialization parameters for a Config implementation."""


@dataclass
class SecretsParams:
    """Initialization parameters for a Secrets implementation."""
