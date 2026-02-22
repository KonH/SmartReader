# Environment

This document describes the development and runtime environment for SmartReader.

---

## Global Environment

These tools apply across the entire project, outside any specific prototype environment.

| Tool | Purpose |
|------|---------|
| **git** | Version control system for tracking code changes and collaboration |
| **venv** | Python virtual environment for dependency isolation |

---

## Prototype 1

The initial prototype environment runs on the following stack:

| Component | Details |
|-----------|---------|
| **WSL** | Windows Subsystem for Linux — provides a Linux runtime on Windows for development |
| **SQLite** | Lightweight embedded database used for local state persistence |

> **Note:** Prototype 1 is self-contained within WSL, with SQLite handling all local data storage needs.
