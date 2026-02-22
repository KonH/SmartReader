# Data

This document describes the data structures used by SmartReader for configuration and runtime state.

---

## Config

Stored as a **TOML** file. Contains source definitions and scoring parameters.

### `[scoring][keyword]`

Controls how keyword-based scoring weights content items.

| Field | Description |
|-------|-------------|
| `common_weight` | Weight applied to keywords shared across all sources/categories |
| `category_weight` | Weight applied to keywords specific to a source category |

### `[sources]`

Defines the list of content sources to monitor. Each source entry is named and has the following fields:

| Field | Required | Description |
|-------|----------|-------------|
| `type` | ✅ Yes | Source type — determines how content is fetched (e.g. `rss`, `telegram`) |
| `externalId` | No | External identifier for the source (e.g. channel ID, feed URL) |
| `category` | No | Category label used for category-level interest scoring |
| `custom` | No | Any additional custom metadata for the source |

**Example structure:**
```toml
[sources]

[[sources.name]]
type = "rss"
externalId = "https://example.com/feed"
category = "tech"
```

---

## State

Stored as a **SQLite** database using a **key = value\<json\>** pattern. Tracks per-source reading progress and user interest scores.

### Keys

| Key | Value Type | Description |
|-----|-----------|-------------|
| `sourceStates` | `sourceId[]` | List of all known source IDs |
| `source_<sourceId>` | `sourceState` | Per-source state object containing `active` (bool) and `lastReadTs` (timestamp) |
| `common_keyword_interests` | `dict<keyword, score>` | Global keyword interest scores shared across all sources |
| `category_interests` | `dict<category, dict<keyword, score>>` | Per-category keyword interest scores |

### `sourceState` Object

| Field | Type | Description |
|-------|------|-------------|
| `active` | `bool` | Whether the source is currently enabled |
| `lastReadTs` | `timestamp` | The timestamp of the last successfully read item from this source |

---

## Interest Scoring Model

Interests are maintained at two levels:

- **Common** (`common_keyword_interests`): Cross-source keyword relevance, updated from user feedback regardless of source.
- **Category** (`category_interests`): Per-category keyword relevance, allowing finer-grained personalization when sources are grouped by topic.

Both levels feed into the **Scoring (Level 1)** step of the processing pipeline.
