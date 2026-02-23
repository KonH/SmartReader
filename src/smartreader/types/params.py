from dataclasses import dataclass


@dataclass
class UIParams:
    """Initialization parameters for a UI implementation."""


@dataclass
class TriggerParams:
    """Payload delivered by UI.wait_trigger when a run is initiated."""
    mode: str               # "ask" | "cron"
    category: str | None = None  # None means ALL categories


@dataclass
class ConfigParams:
    """Initialization parameters for a Config implementation."""


@dataclass
class SecretsParams:
    """Initialization parameters for a Secrets implementation."""
