import pytest

from smartreader.config import Config
from smartreader.scoring.adapter import ScoringAdapter
from smartreader.scoring.keyword import L1KeywordScoring, L2KeywordScoring
from smartreader.state import State
from smartreader.types.content import Content
from smartreader.types.params import ConfigParams
from smartreader.types.values import StateValue


# ── stubs ─────────────────────────────────────────────────────────────────────

class StubState(State):
    def __init__(self, data: dict[str, StateValue] | None = None) -> None:
        self._data: dict[str, StateValue] = data or {}
        self.written: dict[str, StateValue] = {}

    def load(self, params: ConfigParams, callback) -> None: callback(True, "")
    def read_value(self, key: str, callback) -> None: callback(True, "", self._data.get(key, {}))
    def write_value(self, key: str, value: StateValue, callback) -> None:
        self._data[key] = value
        self.written[key] = value
        callback(True, "")
    def read_all(self, callback) -> None: callback(True, "", self._data)
    def save(self, callback) -> None: callback(True, "")


class StubConfig(Config):
    def __init__(self, scoring: dict) -> None:
        self._scoring = scoring

    def load(self, params: ConfigParams, callback) -> None: callback(True, "")
    def read_value(self, key: str, callback) -> None:
        callback(True, "", self._scoring if key == "scoring" else {})
    def write_value(self, key: str, value: StateValue, callback) -> None: callback(True, "")
    def save(self, callback) -> None: callback(True, "")


def _content(title: str, body: str = "", summary: str | None = None,
             category: str | None = None) -> Content:
    return Content(id="x", title=title, body=body, source_id="s",
                   source_type="rss", published_ts=1.0, summary=summary, category=category)


def _make_l1(
    common_kw: dict = {}, category_kw: dict = {},
    common_weight: float = 1.0, category_weight: float = 1.0,
    skip: list[str] | None = None,
) -> tuple[L1KeywordScoring, StubState]:
    state = StubState({
        "common_keyword_interests": common_kw,
        "category_interests": category_kw,
    })
    cfg: dict = {}
    if skip is not None:
        cfg["skip"] = skip
    config = StubConfig(cfg)
    scoring = L1KeywordScoring(state=state, config=config,
                               common_weight=common_weight, category_weight=category_weight)
    scoring.initialize(lambda ok, err: None)
    return scoring, state


def _make_scoring(common_kw: dict = {}, category_kw: dict = {},
                  common_weight: float = 1.0, category_weight: float = 1.0) -> L1KeywordScoring:
    scoring, _ = _make_l1(common_kw, category_kw, common_weight, category_weight)
    return scoring


def _score(scoring, content: Content, effort: int = 1) -> float:
    result: list = []
    scoring.score(content, effort, lambda *a: result.extend(a))
    ok, err, score = result
    assert ok, err
    return score


# ── basic scoring tests ───────────────────────────────────────────────────────

def test_score_zero_when_no_interests() -> None:
    scoring = _make_scoring()
    assert _score(scoring, _content("Hello world")) == 0.0


def test_common_keyword_match_adds_score() -> None:
    scoring = _make_scoring(common_kw={"python": 0.8})
    assert _score(scoring, _content("Python tutorial")) > 0.0


def test_common_keyword_no_match_zero_score() -> None:
    scoring = _make_scoring(common_kw={"rust": 0.8})
    assert _score(scoring, _content("Python tutorial")) == 0.0


def test_common_weight_applied() -> None:
    s1 = _make_scoring(common_kw={"python": 1.0}, common_weight=1.0)
    s2 = _make_scoring(common_kw={"python": 1.0}, common_weight=2.0)
    assert _score(s2, _content("python")) == pytest.approx(_score(s1, _content("python")) * 2)


def test_category_keyword_match_adds_score() -> None:
    scoring = _make_scoring(
        category_kw={"tech": {"ai": 0.9}},
        category_weight=1.5,
    )
    content = _content("ai revolution", category="tech")
    assert _score(scoring, content) > 0.0


def test_category_keyword_wrong_category_no_score() -> None:
    scoring = _make_scoring(category_kw={"tech": {"ai": 0.9}})
    content = _content("ai revolution", category="news")
    assert _score(scoring, content) == 0.0


def test_category_keyword_no_category_field_no_score() -> None:
    scoring = _make_scoring(category_kw={"tech": {"ai": 0.9}})
    content = _content("ai revolution", category=None)
    assert _score(scoring, content) == 0.0


def test_l1_uses_body() -> None:
    scoring = _make_scoring(common_kw={"keyword": 1.0})
    content = _content(title="Title", body="keyword is here", summary="no match")
    assert _score(scoring, content, effort=1) > 0.0


def test_case_insensitive_matching() -> None:
    scoring = _make_scoring(common_kw={"python": 1.0})
    assert _score(scoring, _content("PYTHON is great")) > 0.0


def test_multiple_keywords_scores_accumulate() -> None:
    scoring = _make_scoring(common_kw={"python": 0.5, "ai": 0.5})
    single = _score(scoring, _content("python"))
    both = _score(scoring, _content("python ai"))
    assert both > single


# ── L1 / L2 split ─────────────────────────────────────────────────────────────

def test_l2_uses_summary_when_available() -> None:
    state = StubState({"common_keyword_interests": {"keyword": 1.0}, "category_interests": {}})
    config = StubConfig({})
    l2 = L2KeywordScoring(state=state, config=config, common_weight=1.0, category_weight=1.0)
    l2.initialize(lambda ok, err: None)
    content = _content(title="Title", body="no match", summary="keyword is here")
    assert _score(l2, content, effort=2) > 0.0


def test_l2_falls_back_to_body_when_no_summary() -> None:
    state = StubState({"common_keyword_interests": {"keyword": 1.0}, "category_interests": {}})
    config = StubConfig({})
    l2 = L2KeywordScoring(state=state, config=config, common_weight=1.0, category_weight=1.0)
    l2.initialize(lambda ok, err: None)
    content = _content(title="Title", body="keyword is here", summary=None)
    assert _score(l2, content, effort=2) > 0.0


# ── skip list ─────────────────────────────────────────────────────────────────

def test_skip_words_not_scored() -> None:
    # "the" is in the interest model but also in skip list → should not score
    scoring, _ = _make_l1(common_kw={"the": 1.0}, skip=["the"])
    assert _score(scoring, _content("the best article")) == 0.0


def test_non_skip_word_still_scores() -> None:
    scoring, _ = _make_l1(common_kw={"python": 1.0, "the": 1.0}, skip=["the"])
    assert _score(scoring, _content("the python tutorial")) > 0.0


# ── update_score ──────────────────────────────────────────────────────────────

def test_update_score_upvote_adds_keywords() -> None:
    scoring, state = _make_l1(
        common_kw={},
        skip=[],
    )
    result: list = []
    scoring.update_score(_content(title="python rocks"), upvote=True, callback=lambda *a: result.extend(a))
    assert result[0], result[1]  # success
    assert "python" in state.written.get("common_keyword_interests", {})


def test_update_score_downvote_decreases_keywords() -> None:
    scoring, state = _make_l1(
        common_kw={"python": 2.0},
        skip=[],
    )
    scoring.update_score(_content(title="python rocks"), upvote=False, callback=lambda ok, err: None)
    assert state.written["common_keyword_interests"]["python"] < 2.0


def test_update_score_skip_words_not_added() -> None:
    scoring, state = _make_l1(common_kw={}, skip=["the", "is"])
    scoring.update_score(_content(title="the python is great"), upvote=True, callback=lambda ok, err: None)
    written = state.written.get("common_keyword_interests", {})
    assert "the" not in written
    assert "is" not in written
    assert "python" in written


def test_update_score_category_interests_updated() -> None:
    scoring, state = _make_l1(common_kw={}, category_kw={}, skip=[])
    content = _content(title="machine learning", category="tech")
    scoring.update_score(content, upvote=True, callback=lambda ok, err: None)
    cat = state.written.get("category_interests", {}).get("tech", {})
    assert "machine" in cat or "learning" in cat


# ── ScoringAdapter ─────────────────────────────────────────────────────────────

def _make_adapter(
    common_kw: dict = {}, category_kw: dict = {},
    common_weight: float = 1.0, category_weight: float = 1.0,
) -> tuple[ScoringAdapter, StubState]:
    state = StubState({
        "common_keyword_interests": common_kw,
        "category_interests": category_kw,
    })
    config = StubConfig({
        "l1": [{"type": "keyword", "common_weight": common_weight, "category_weight": category_weight}],
        "l2": [{"type": "keyword", "common_weight": common_weight, "category_weight": category_weight}],
    })
    shared_common: dict[str, float] = {}
    shared_category: dict[str, dict[str, float]] = {}
    adapter = ScoringAdapter(config, state, shared_common, shared_category)
    adapter.initialize(lambda ok, err: None)
    return adapter, state


def test_adapter_delegates_l1_for_effort_1() -> None:
    adapter, _ = _make_adapter(common_kw={"python": 1.0})
    # L1 uses body; keyword only in body → should score > 0
    content = _content(title="nothing", body="python tutorial", summary="nothing")
    assert _score(adapter, content, effort=1) > 0.0


def test_adapter_delegates_l2_for_effort_2() -> None:
    adapter, _ = _make_adapter(common_kw={"python": 1.0})
    # L2 uses summary; keyword only in summary → should score > 0
    content = _content(title="nothing", body="nothing", summary="python rocks")
    assert _score(adapter, content, effort=2) > 0.0


def test_adapter_update_score_updates_shared_interests() -> None:
    adapter, state = _make_adapter()
    content = _content(title="python rocks", body="deep learning", summary="neural networks")
    adapter.update_score(content, upvote=True, callback=lambda ok, err: None)
    written = state.written.get("common_keyword_interests", {})
    # Words from both L1 (body) and L2 (summary) should be in interests
    assert "python" in written
    assert any(w in written for w in ("learning", "learn", "neural", "network", "networks"))
