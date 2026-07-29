"""Tests for EVAL prompt resolution: stage > channel > category > global."""

from smartreader.scoring.openai_scorer import (
    _DEFAULT_PROMPT,
    OpenAIScoring,
    resolve_eval_prompt,
)
from smartreader.types.content import Content


def test_resolve_uses_default_when_empty() -> None:
    assert resolve_eval_prompt() == _DEFAULT_PROMPT


def test_resolve_global_over_default() -> None:
    assert resolve_eval_prompt(global_prompt="GLOBAL") == "GLOBAL"


def test_resolve_category_over_global() -> None:
    assert resolve_eval_prompt(
        global_prompt="GLOBAL",
        category_prompts={"tech": "CAT"},
        category="tech",
    ) == "CAT"


def test_resolve_channel_over_category() -> None:
    assert resolve_eval_prompt(
        global_prompt="GLOBAL",
        category_prompts={"tech": "CAT"},
        channel_prompts={"src_a": "CH"},
        source_id="src_a",
        category="tech",
    ) == "CH"


def test_resolve_stage_over_channel() -> None:
    assert resolve_eval_prompt(
        stage_prompt="STAGE",
        global_prompt="GLOBAL",
        category_prompts={"tech": "CAT"},
        channel_prompts={"src_a": "CH"},
        source_id="src_a",
        category="tech",
    ) == "STAGE"


def test_resolve_ignores_empty_map_entries() -> None:
    assert resolve_eval_prompt(
        global_prompt="GLOBAL",
        category_prompts={"tech": ""},
        channel_prompts={"src_a": ""},
        source_id="src_a",
        category="tech",
    ) == "GLOBAL"


def test_resolve_missing_keys_fall_through() -> None:
    assert resolve_eval_prompt(
        global_prompt="GLOBAL",
        category_prompts={"other": "CAT"},
        channel_prompts={"other_src": "CH"},
        source_id="src_a",
        category="tech",
    ) == "GLOBAL"


def test_openai_scoring_resolves_per_content() -> None:
    from smartreader.secrets.mock import MockSecrets
    from smartreader.state.mock import MockState

    scorer = OpenAIScoring(
        state=MockState(),
        secrets=MockSecrets(),
        entry={
            "prompt": "",
            "global_prompt": "GLOBAL",
            "category_prompts": {"tech": "CAT"},
            "channel_prompts": {"src_a": "CH"},
        },
    )
    item_ch = Content(
        id="1", title="t", body="b", source_id="src_a",
        source_type="rss", published_ts=0.0, category="tech",
    )
    item_cat = Content(
        id="2", title="t", body="b", source_id="src_b",
        source_type="rss", published_ts=0.0, category="tech",
    )
    item_global = Content(
        id="3", title="t", body="b", source_id="src_b",
        source_type="rss", published_ts=0.0, category="world",
    )
    assert scorer._resolve_prompt(item_ch) == "CH"
    assert scorer._resolve_prompt(item_cat) == "CAT"
    assert scorer._resolve_prompt(item_global) == "GLOBAL"


def test_build_pipeline_passes_prompt_maps() -> None:
    from smartreader.config.mock import MockConfig
    from smartreader.pipeline.adapter import build_pipeline
    from smartreader.pipeline.stages.openai_score import OpenAIScoreStage
    from smartreader.secrets.mock import MockSecrets
    from smartreader.state.mock import MockState

    adapter = build_pipeline(
        [{"type": "openai_score"}],
        MockState(),
        MockConfig(),
        secrets=MockSecrets(),
        global_prompt="GLOBAL",
        category_prompts={"tech": "CAT"},
        channel_prompts={"src_a": "CH"},
    )
    stage = adapter._stages[0]
    assert isinstance(stage, OpenAIScoreStage)
    inner = stage._inner
    assert inner._global_prompt == "GLOBAL"
    assert inner._category_prompts == {"tech": "CAT"}
    assert inner._channel_prompts == {"src_a": "CH"}
    assert inner._stage_prompt == ""


def test_set_prompt_command_writes_maps() -> None:
    from smartreader.config import Config
    from smartreader.state import State
    from smartreader.state.app_state import AppState
    from smartreader.types.params import ConfigParams
    from smartreader.types.values import StateValue
    from smartreader.ui.command import SharedUIState
    from smartreader.ui.commands import SetPromptCommand

    class MemConfig(Config):
        def __init__(self) -> None:
            self.data: dict = {
                "scoring": {"openai_prompt": "GLOBAL"},
                "sources": {
                    "src_a": [{"type": "rss", "externalId": "u", "category": "tech"}],
                },
            }
            self.saved = False

        def load(self, params: ConfigParams, callback) -> None:
            callback(True, "")

        def read_value(self, key: str, callback) -> None:
            callback(True, "", self.data.get(key, {}))

        def write_value(self, key: str, value: StateValue, callback) -> None:
            self.data[key] = value
            callback(True, "")

        def save(self, callback) -> None:
            self.saved = True
            callback(True, "")

    class MemState(State):
        def load(self, params: ConfigParams, callback) -> None:
            callback(True, "")

        def read_value(self, key: str, callback) -> None:
            callback(True, "", {})

        def write_value(self, key: str, value: StateValue, callback) -> None:
            callback(True, "")

        def read_all(self, callback) -> None:
            callback(True, "", {})

        def save(self, callback) -> None:
            callback(True, "")

    class DummyShared(SharedUIState):
        pass

    class Concrete(SetPromptCommand):
        @property
        def control_title(self) -> str:
            return "prompt"

        def execute(self) -> None:
            pass

    cfg = MemConfig()
    app = AppState(state=MemState(), config=cfg)
    app.pipeline_factory = lambda cb: cb(True, "")
    cmd = Concrete(app, DummyShared())

    assert cmd._list_categories() == ["tech"]
    assert cmd._list_channels() == ["src_a"]

    cmd._set_mapped_prompt_and_restart("category_prompts", "tech", "CAT")
    assert cfg.data["scoring"]["category_prompts"]["tech"] == "CAT"
    assert cfg.saved

    cmd._set_mapped_prompt_and_restart("channel_prompts", "src_a", "CH")
    assert cfg.data["scoring"]["channel_prompts"]["src_a"] == "CH"

    cmd._set_mapped_prompt_and_restart("channel_prompts", "src_a", "")
    assert "channel_prompts" not in cfg.data["scoring"]
