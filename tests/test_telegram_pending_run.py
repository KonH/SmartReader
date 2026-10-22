from pathlib import Path

from smartreader.state.sqlite import SQLiteState
from smartreader.types.params import ConfigParams
from smartreader.ui import telegram
from smartreader.ui.telegram import pending_run
from smartreader.ui.telegram.state import TelegramSharedUIState


def make_state(path: Path) -> SQLiteState:
    state = SQLiteState(path)
    state.load(ConfigParams(), lambda ok, err: None)
    return state


def make_shared(monkeypatch) -> tuple[TelegramSharedUIState, list[str]]:
    s = TelegramSharedUIState()
    sent: list[str] = []
    monkeypatch.setattr(telegram, "run_async", lambda _s, coro: coro.close())
    monkeypatch.setattr(telegram, "async_send_text", lambda _s, _id, text: sent.append(text) or _noop())
    monkeypatch.setattr(telegram, "send_action_menu", lambda _s, _id: None)
    return s, sent


async def _noop() -> None:
    return None


def test_no_pending_run_does_nothing(tmp_path: Path, monkeypatch) -> None:
    s, sent = make_shared(monkeypatch)
    telegram._resume_interrupted_run(s, make_state(tmp_path / "s.sqlite"))
    assert s.trigger_queue.empty() and not sent


def test_interrupted_run_is_resumed_with_counter(tmp_path: Path, monkeypatch) -> None:
    s, sent = make_shared(monkeypatch)
    state = make_state(tmp_path / "s.sqlite")
    pending_run.mark_run_started(state, 7, "tech", 0)
    telegram._resume_interrupted_run(s, state)
    assert s.trigger_queue.get_nowait() == {"sender_id": 7, "mode": "run", "category": "tech", "resumes": 1}
    assert pending_run.load_pending_run(state) == {}


def test_gives_up_after_max_resumes(tmp_path: Path, monkeypatch) -> None:
    s, sent = make_shared(monkeypatch)
    monkeypatch.setattr(pending_run, "previous_log_tail", lambda: "boom")
    state = make_state(tmp_path / "s.sqlite")
    pending_run.mark_run_started(state, 7, None, pending_run.MAX_RESUMES)
    telegram._resume_interrupted_run(s, state)
    assert s.trigger_queue.empty()
    assert "```\nboom\n```" in sent[0]
    assert pending_run.load_pending_run(state) == {}


def test_finished_run_is_not_resumed(tmp_path: Path, monkeypatch) -> None:
    s, sent = make_shared(monkeypatch)
    state = make_state(tmp_path / "s.sqlite")
    pending_run.mark_run_started(state, 7, None, 0)
    pending_run.mark_run_finished(state)
    telegram._resume_interrupted_run(s, state)
    assert s.trigger_queue.empty() and not sent
