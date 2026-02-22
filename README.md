# SmartReader

SmartReader is a personalized content aggregation system that reads from multiple sources (RSS, Telegram), scores articles based on your interests, summarizes the most relevant ones using AI, and continuously improves its relevance ranking through your feedback.

---

## How It Works

Content is fetched from configured sources, filtered and ranked by a keyword-based scoring engine, summarized via the OpenAI API, then presented through a terminal or Telegram interface. User feedback on shown items feeds back into the interest model, making each run more relevant than the last.

```
Ask / Cron ──► Read sources ──► Score (L1) ──► Select Top N ──► Summarize ──► Score (L2) ──► Show ──► Feedback
                                     ▲                                                                      │
                                     └────────────────────── Interests ◄──────────────────────────────────┘
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | System modules, abstractions, implementations, and dependencies |
| [Flow](docs/flow.md) | End-to-end processing pipeline and feedback loop |
| [Data](docs/data.md) | Config and State data structures and schemas |
| [Tools](docs/tools.md) | Planning, development, and debug tooling |
| [Environment](docs/environment.md) | Runtime and development environment setup |

---

## Key Concepts

**Callback convention** — Every async operation uses a callback with `success<bool>` and `error<string>`.

**Two-level scoring** — Content is scored twice: a fast keyword pass before summarization (Level 1) to filter the bulk, and a refined pass on the summarized text (Level 2) for final ranking.

**Pluggable interfaces** — UI, Input, Config, State, and Scoring are all defined as abstractions with swappable implementations, making it straightforward to add new sources or storage backends.

**Interest model** — Keyword interest scores are maintained at both a global (common) and per-category level, updated continuously from user feedback.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Language | Python (venv) |
| Configuration | TOML |
| State storage | SQLite (with optional encryption) |
| Summarization | OpenAI API |
| UI options | Terminal, Telegram |
| Input sources | RSS, Telegram |
| Version control | git + lazygit |
