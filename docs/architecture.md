# Architecture

This document describes the software architecture of the SmartReader system.

---

## Overview

SmartReader is coordinated by a central **Main Coordinator** which orchestrates all top-level modules. Every callback follows the convention:

> `callback` always has `success<bool>` and `error<string>`.

The system is composed of six primary modules: **UI**, **Input**, **Config**, **State**, **Scoring**, and **Summarize**. All modules interact with a shared **Secrets** module for credential management.

---

## Main Coordinator

The entry point of the application. It initializes and connects all subsystems, passing configuration and callbacks down the dependency tree.

---

## UI

The user-facing interface layer.

**Abstraction interface:**
- `initialize(params, callback)`
- `waitTrigger(callback<params>)`
- `showContentList(content[], callback)`
- `receiveScore(id, score)`
- `terminate()`

**Implementations (One of):**
- `terminal` — Command-line interface
- `Telegram` — Telegram bot interface

---

## Input

Responsible for reading content from external sources.

**Abstraction interface:**
- `readSources(startTs, type, id, callback)`

**Implementations (Any of):**
- `RSS` — Reads articles from RSS feeds
- `Telegram` — Reads messages from Telegram channels

---

## Config

Handles loading and persisting application configuration.

**Abstraction interface:**
- `load(params, callback)`
- `readValue(key, callback<dict>)`
- `writeValue(key, callback)`
- `save(callback)`

**Implementation:**
- `TOML` — Configuration stored in TOML file format

---

## State

Manages persistent application state, including source tracking and user interests.

**Abstraction interface:**
- Inherits the Config abstraction interface

**Implementation chain:**
- `Encryption` *(optional layer)* — Wraps the storage layer with encryption
- `SQLite` — Underlying storage engine

---

## Scoring

Scores content items based on user interests and configured keyword weights.

**Abstraction interface:**
- `initialize(callback)`
- `score(content, effortLevel, callback<score>)`

**Implementation:**
- `KeywordScoring` — Scores content using keyword matching against interest profiles

---

## Summarize

Generates natural-language summaries of content items.

**Abstraction interface:**
- `initialize(callback)`
- `summarize(content, callback<content>)`

**Implementation:**
- `OpenAI API` — Uses OpenAI's language models to produce summaries

---

## Secrets

Provides secure access to credentials and API keys required by other modules.

**Abstraction interface:**
- `initialize(params, callback)`
- `readValue(key, callback<string>)`

**Implementation:**
- `Environment` — Reads secrets from environment variables

---

## Module Dependency Summary

| Module | Depends On |
|--------|-----------|
| Main Coordinator | UI, Input, Config, State, Scoring, Summarize |
| UI | Secrets |
| Input | Secrets |
| Config | Secrets, TOML |
| State | Config (inherits), Encryption, SQLite, Secrets |
| Scoring | Secrets, KeywordScoring |
| Summarize | Secrets, OpenAI API |
