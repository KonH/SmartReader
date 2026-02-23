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
Ask / Cron ──► Read sources ──► Score (L1) ──► Select Top N ──► Summarize ──► Score (L2) ──► Show ──► Feedback
                                     ▲                                                                      │
                                     └──────────────────── Interests ◄───────────────────────────────────┘
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
- **Domain types**: `src/smartreader/types/content.py` (`Content`), `types/params.py` (`UIParams`, `TriggerParams`, `ConfigParams`, `SecretsParams`), `types/values.py` (`StateValue`).
- **Pluggable abstractions**: UI, Input, Config, State, and Scoring are defined as abstract interfaces with swappable implementations. New sources or storage backends should follow this pattern.
- **Two-level interest model**: Interests are stored at both global (`common_keyword_interests`) and per-category (`category_interests`) granularity. Both feed into L1 scoring.

## Config Schema (TOML)

```toml
[common]
initial_days_scan_interval = 7  # days to scan back on first run per source

[scoring.keyword]
common_weight = <float>
category_weight = <float>

[sources]
[[sources.<name>]]
type = "rss"          # or "telegram"
externalId = "..."    # feed URL or channel ID
category = "..."      # optional, used for category-level interest scoring
custom = {}           # optional extra metadata
```

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
Input:     readSources(startTs, type, id, cb)
Config:    load(params, cb) | readValue(key, cb<dict>) | writeValue(key, cb) | save(cb)
State:     inherits Config interface
Scoring:   initialize(cb) | score(content, effortLevel, cb<score>)
Summarize: initialize(cb) | summarize(content, cb<content>)
Secrets:   initialize(params, cb) | readValue(key, cb<string>)
```

## Reference Docs

- `docs/architecture.md` — Module details and dependency graph
- `docs/flow.md` — Full pipeline and feedback loop description
- `docs/data.md` — Config and State schemas
- `docs/environment.md` — Runtime environment details
