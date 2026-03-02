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
| Scoring | Rank content | Multi-scorer pipeline (keyword, noise, …) via ScoringAdapter |
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
upvote_power = 1.5
downvote_power = -1.0
skip = []             # stop-words excluded from all keyword scorers; editable at runtime via 'skip' command

[[scoring.l1]]        # one or more scorer entries (array-of-tables)
type = "keyword"      # "keyword" | "noise"
common_weight = 1.0
category_weight = 1.5

[[scoring.l2]]
type = "keyword"
common_weight = 1.0
category_weight = 1.5

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
UI:        initialize(params, cb) | get_commands() → list[type[UICommand]] | loop(commands) | terminate()
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
- **`AppState` wrapper**: `state/app_state.py` wraps `State` with typed access — `read_all_typed(cb<AppStateData>)` and `remove_keyword(word, cb)`. Constructor: `AppState(state, config, scoring, summarize, input)` — holds module refs plus runtime fields (`categories`, `active_source_ids`, `successful_source_ids`, `shown_items`, `trigger_category`, `initial_days_interval`). Instantiated in `__main__.py` and passed to `Coordinator` and all commands.
- **`UICommand` / `SharedUIState` pattern**: `ui/command.py` defines `UICommand` ABC (`control_title: str`, `execute() → None`) and `SharedUIState` ABC (empty marker). Abstract command classes with WHAT-logic live in `ui/commands/__init__.py`; concrete HOW-implementations in `ui/terminal/commands/` and `ui/telegram/commands/`. All commands take `(app_state: AppState, shared_ui_state: SharedUIState)`.
- **`UI.loop(commands)` contract**: UI is responsible for its own interaction loop. It extracts `app_state` from the `ShowContentCommand` instance (`cmd._app_state`), refreshes categories each iteration via `app_state.config.read_value("sources", ...)`, and dispatches by matching user input to `cmd.control_title`.
- **`TriggerParams`** still exists in `types/params.py` but is now internal to `TelegramUI.loop()` — the Coordinator no longer dispatches on mode. `TelegramSharedUIState` holds all Telegram-specific state (`trigger_queue`, `category_queue`, `add_step_queue`, `in_add_mode`, `in_skip_mode`, `waiting_for_category`, etc.).
- **Interactive Telegram flows**: multi-step conversations (add source, skip word) block inside `TelegramAddSourceCommand.execute()` / `TelegramSkipWordCommand.execute()` using `add_step_queue`; `in_add_mode` / `in_skip_mode` flags on `TelegramSharedUIState` prevent trigger commands from interrupting. Cancel buttons put `None` on the queue; text messages put the typed value.
- **State file path**: `SQLiteState` accepts `path: Path`. `__main__.py` reads `sys.argv[1]` as the state path (default `state.sqlite`). `run.sh` forwards `$@` to Python; `retry_run.sh` forwards `$@` to `run.sh`.
- **Telegram content messages use HTML mode**: `show_content_list` builds messages with `parse_mode="html"`. Title and body go through `_md_to_html` (HTML-escapes `&<>`, then converts `[text](url)` → `<a href>`, `**bold**` → `<b>`, `` `code` `` → `<code>`). Menu/prompt messages keep `parse_mode="md"`. Telethon parses Markdown client-side before sending, so `_escape_md` backslash sequences appear literally — HTML mode is the correct choice for arbitrary article text.
- **Pipeline steps with callbacks must be iterative, not recursive**: All coordinator steps that loop over items calling synchronous callbacks (`_score_l1`, `_score_l2`, `_summarize_all`) use a plain `for` loop — callbacks fire synchronously and mutate items in place or append to a local list. Recursive designs hit Python's call stack limit. Never introduce a recursive pipeline step. Exception: chaining over a small, fixed-size list (e.g. 2–3 scorer implementations) is safe and acceptable.
- **`ScoringAdapter` constructor**: `ScoringAdapter(config, state, shared_common, shared_category)`. It reads `scoring.l1` / `scoring.l2` arrays from config at `initialize()` time and builds scorer instances internally — `__main__.py` does not instantiate individual scorers. Scorer type is resolved by `type` field: `"keyword"` → `L1/L2KeywordScoring`, `"noise"` → `NoiseScoring`. Per-scorer weights (`common_weight`, `category_weight`) come from the entry dict, not from config reads inside the scorer. `skip` is global (read from top-level `scoring` dict by each keyword scorer).
- **`NoiseScoring`** (`scoring/noise.py`): adds `random() * noise_factor` to score; useful for diversifying results. `noise_factor` comes from the scorer entry dict.
- **Keyword tokenizer** (`scoring/keyword.py`): uses `pymorphy3` (not `pymorphy2` — broken on Python 3.12 due to removed `inspect.getargspec`) for Cyrillic; `simplemma` for Latin with lang tuple `('en', 'hbs')` — Serbian is `hbs` (Serbo-Croatian), `sr` is not a valid simplemma code. `simplemma` returns capitalized lemmas for proper nouns — always call `.lower()` on the result. Skip lemmatization for Latin words <4 chars (`simplemma` mis-lemmatizes short tokens, e.g. `"ai"` → `"be"`). `_morph = pymorphy3.MorphAnalyzer()` is a module-level singleton.
- **Interest keys are always lowercase**: scoring checks `kw.lower() in tokens`; both stored interest keys and the tokens set returned by `_tokenize` must be lowercase or matches silently fail.
- **Summary length is controlled by `[summarize.trim]` only**: UI code must never hard-code a character/line cap on displayed summaries — that overrides user config.
- **Per-scorer logging in adapter**: format is `"L1 (keyword) scored 'id': 0.500"` — stage ("L1"/"L2") + short label from `_scorer_label()` (uses `isinstance` checks, not class-name string manipulation).
- **Pipeline must always show content**: Every code path in `ShowContentCommand._run_pipeline` (including "no sources", "no new content", "empty after scoring") must return a list (possibly empty) so `execute()` calls the render/send step. Returning without rendering leaves the user with no response and no menu (Telegram).
- **Coordinator is now a pure initializer**: All pipeline logic lives in `ui/commands/__init__.py` (`ShowContentCommand._run_pipeline`, `_update_source_states`, `_process_feedback`). `Coordinator.run(commands)` simply calls `ui.loop(commands)`. Do not add pipeline methods back to Coordinator.

## Reference Docs

- `docs/architecture.md` — Module details and dependency graph
- `docs/flow.md` — Full pipeline and feedback loop description
- `docs/data.md` — Config and State schemas
- `docs/environment.md` — Runtime environment details
