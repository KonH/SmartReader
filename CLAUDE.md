# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

SmartReader has abstractions implemented in `src/smartreader/`. The `docs/` directory contains the full architecture and data specifications.

## Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt   # once created
```

## Running Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/
```

**IMPORTANT**: Always use `.venv/bin/python`, never bare `python` or `python3` — the system Python does not have pytest or any project dependencies installed.

Runtime on WSL (Windows Subsystem for Linux). Secrets are provided via **environment variables** (not config files).

## Architecture

Six modules coordinated by a **Main Coordinator**. All async operations use a uniform callback convention: every callback receives `success<bool>` and `error<string>`.

| Module | Role | Implementation |
|--------|------|----------------|
| UI | User interface | Terminal or Telegram (one of) |
| Input | Fetch content | RSS and/or Telegram (any of) |
| Config | App config | TOML file |
| State | Persistent state | SQLite (optionally wrapped with Encryption) |
| Scoring | Rank content | KeywordScoring |
| Summarize | Summarize content | OpenAI API |
| Secrets | Credential access | Environment variables |

State uses **SQLite** with a `key = value<json>` pattern. Config uses **TOML**.

## Processing Pipeline

```
Ask / Cron ──► Read sources ──► Score (L1) ──► Select top_n_l1 ──► Summarize ──► Score (L2) ──► Select top_n_l2 ──► Show ──► Feedback
                                     ▲                                                                                               │
                                     └─────────────────────────────── Interests ◄──────────────────────────────────────────────────┘
```

- **Level 1 scoring**: Fast keyword pass on raw content — filters bulk before calling OpenAI.
- **Level 2 scoring**: Refined pass on summarized text for final ranking.
- **Feedback loop**: User scores update the Interest model (`common_keyword_interests` and `category_interests`), improving future L1 scoring.
- **Display order**: Content is shown sorted by `published_ts` ascending (oldest first, newest last). Score is only used for Top N selection, not UI ordering.

## Git

**Never commit automatically.** Only commit when the user explicitly runs the `/commit` command.

## Key Conventions

- **Callback signature**: `callback(success: bool, error: str)` — used on every async operation. Callbacks that return a value add a third positional argument (e.g. `callback(success, error, content)`).
- **No `Any`**: Never use `typing.Any`. Always define a specific type — add a dataclass or `TypeAlias` to `src/smartreader/types/` when no suitable type exists yet. Callback type aliases live in `src/smartreader/_types.py`.
- **Domain types**: `src/smartreader/types/content.py` (`Content`), `types/params.py` (`UIParams`, `TriggerParams`, `ConfigParams`, `SecretsParams`), `types/values.py` (`StateValue`), `types/app_state.py` (`AppStateData`, `SourceStateEntry`).
- **Pluggable abstractions**: UI, Input, Config, State, and Scoring are defined as abstract interfaces with swappable implementations. New sources or storage backends should follow this pattern.
- **Two-level interest model**: Interests are stored at both global (`common_keyword_interests`) and per-category (`category_interests`) granularity. Both feed into L1 scoring.

## Config Schema (TOML)

```toml
[common]
initial_days_scan_interval = 7  # days to scan back on first run per source

[telegram_ui]
active = false                  # set true to enable Telegram Bot UI
controller_usernames = []       # Telegram usernames allowed to trigger runs (no @).
                                # WARNING: empty list = any Telegram user can trigger!
upvote_reaction = "👍"
downvote_reaction = "👎"

[telegram]
active = false        # set true to enable Telegram channel sources (input)

[summarize.trim]
active = false        # set true to trim summaries after summarization
lines = 10            # max lines to keep
# chars = 500         # optional: max total chars (omit = no limit)

[scoring]
top_n_l1 = 10         # max articles passed to summarizer after L1 scoring
top_n_l2 = 5          # max articles shown to user after L2 scoring

[scoring.keyword]
common_weight = <float>
category_weight = <float>
skip = []             # stop-words excluded from keyword matching; editable at runtime via 'skip' command

[sources]
[[sources.<name>]]
type = "rss"          # or "telegram"
externalId = "..."    # feed URL or channel ID
category = "..."      # optional, used for category-level interest scoring
custom = {}           # optional extra metadata
```

Secrets for Telegram Bot UI (environment variables):

| Variable | Purpose |
|----------|---------|
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_API_ID` | MTProto API id (shared with telegram input if both active) |
| `TELEGRAM_API_HASH` | MTProto API hash (shared with telegram input if both active) |

## State Keys (SQLite)

| Key | Value |
|-----|-------|
| `sourceStates` | `list[sourceId]` |
| `source_<sourceId>` | `{active: bool, lastReadTs: timestamp}` |
| `common_keyword_interests` | `dict[keyword, score]` |
| `category_interests` | `dict[category, dict[keyword, score]]` |

## Module Interfaces

```
UI:        initialize(params, cb) | waitTrigger(categories[], cb<params>) | showContentList(content[], cb) | receiveScore(id, score) | terminate()
Input:     initialize(secrets, config, cb) | readSources(startTs, type, id, cb)
Config:    load(params, cb) | readValue(key, cb<dict>) | writeValue(key, cb) | save(cb)
State:     inherits Config interface
Scoring:   initialize(cb) | score(content, effortLevel, cb<score>)
Summarize: initialize(cb) | summarize(content, cb<content>)
Secrets:   initialize(params, cb) | readValue(key, cb<string>)
```

- **Coordinator init order**: `secrets → config → state → scoring → summarize → ui → input`. Input init runs last so it has access to loaded secrets and config.
- **Input.initialize**: optional hook (default no-op). `SourceReader` delegates to any registered reader that implements it. Returning `success=False` aborts the app.
- **lastReadTs invariant**: only sources whose `read_sources` call succeeded get their `lastReadTs` updated. Failed reads are skipped with a warning and will be retried next run.
- **Feature gating pattern**: optional integrations are enabled via a top-level TOML section, e.g. `[telegram] active = true`. The implementation checks this flag in its `initialize` and skips setup when inactive.
- **TOML `None` is not serializable**: `tomli_w` cannot write `None` values. Omit optional keys from `_DEFAULTS` entirely instead of setting them to `None`; callers use `.get(key)` which returns `None` for absent keys.
- **Decorator pattern for Summarize**: post-processing (e.g. trimming) is added by wrapping an inner `Summarize` impl, not by modifying the UI. `TrimSummarize(inner, config)` is the established example.
- **`UIParams.live_feedback`**: optional `LiveFeedbackHandler` passed to `UI.initialize`; used by non-blocking UIs (e.g. `TelegramUI`) to push async vote feedback directly to the coordinator without waiting for `show_content_list` to return.
- **`config.schema.toml`**: user-facing reference file in the project root — update it alongside CLAUDE.md whenever config sections are added or changed. Also update `.env.example` whenever new secrets are introduced.
- **`AppState` wrapper**: `state/app_state.py` wraps `State` with typed access — `read_all_typed(cb<AppStateData>)` parses raw keys into sorted, typed structures; `remove_keyword(word, cb)` removes a word from both interest keys. Instantiated in `__main__.py` and passed to `Coordinator`.
- **`TriggerParams.mode`**: `"ask" | "add" | "logs" | "state" | "skip"`. `"skip"` carries `skip_word: str` and triggers the skip-word flow (add to `scoring.keyword.skip` config list, remove from state interests, restart).
- **Interactive Telegram flows**: multi-step conversations (add source, skip word) block `wait_trigger` using `_add_step_queue`; a boolean flag (`_in_add_mode`, `_in_skip_mode`) prevents trigger commands from interrupting. Cancel buttons put `None` on the queue; text messages put the typed value.
- **State file path**: `SQLiteState` accepts `path: Path`. `__main__.py` reads `sys.argv[1]` as the state path (default `state.sqlite`). `run.sh` forwards `$@` to Python; `retry_run.sh` forwards `$@` to `run.sh`.
- **Telegram content messages use HTML mode**: `show_content_list` builds messages with `parse_mode="html"`. Title and body go through `_md_to_html` (HTML-escapes `&<>`, then converts `[text](url)` → `<a href>`, `**bold**` → `<b>`, `` `code` `` → `<code>`). Menu/prompt messages keep `parse_mode="md"`. Telethon parses Markdown client-side before sending, so `_escape_md` backslash sequences appear literally — HTML mode is the correct choice for arbitrary article text.
- **Pipeline steps with callbacks must be iterative, not recursive**: All coordinator steps that loop over items calling synchronous callbacks (`_score_l1`, `_score_l2`, `_summarize_all`) use a plain `for` loop — callbacks fire synchronously and mutate items in place or append to a local list. Recursive designs hit Python's call stack limit. Never introduce a recursive pipeline step.
- **Pipeline must always reach `show_content_list`**: Every code path (including "no sources", "no new content", "empty after scoring") must call `self._show([])` so the UI sends user feedback and its action menu. Returning early without calling `_show` leaves the user with no response and no menu.

## Reference Docs

- `docs/architecture.md` — Module details and dependency graph
- `docs/flow.md` — Full pipeline and feedback loop description
- `docs/data.md` — Config and State schemas
- `docs/environment.md` — Runtime environment details
