# Project Constitution

Non-negotiable architectural principles. The `/plan` command checks these before finalising any plan.

## Module Abstraction

- **Every top-level module (UI, Input, Config, State, Scoring, Summarize, Secrets) is an interface with swappable implementations.** No module's implementation detail (Telegram, RSS, TOML, SQLite, OpenAI API, etc.) may leak into the Main Coordinator or into another module; all cross-module access goes through the module's abstraction interface.

## Callback Convention

- **Every async operation uses a callback with `success<bool>` and `error<string>`.** No exceptions-as-control-flow across module boundaries, no bare return-value success signaling; this keeps every module's error handling uniform and composable by the Main Coordinator.

## Two-Level Scoring

- **Content is scored before summarization (Level 1, keyword pass) and again after (Level 2, refined pass).** Do not collapse the two passes or run expensive summarization before the Level 1 filter narrows the set; Level 1 exists specifically to bound how much gets sent to Summarize.

## Interest Model

- **Interest scores are maintained at both a global (common) and per-category level, updated only from user feedback.** No hardcoded or externally-seeded interest weights outside the feedback update path.

## Secrets

- **All credentials and API keys are read through the Secrets abstraction.** No direct `os.environ` access (or equivalent) from UI, Input, Config, State, Scoring, or Summarize; only the Secrets module's implementation touches the underlying source.

## Planning Discipline

- **Plan before implement.** No code or config-schema changes without an approved plan file; this prevents scope drift and keeps the git history reviewable.

## Specification Discipline

- **Spec before plan for feature work.** Feature additions must start with a `/specify` pass that captures intent and acceptance criteria; purely technical tasks (refactors, dependency upgrades, infra) may skip the spec and go straight to `/plan`.

## File Organisation

- **`docs/specs/<index>_<name>/` for all new plans, spec-backed or not.** A technical-only plan (refactor, infra) still gets a `docs/specs/<index>_<name>/plan.md`, simply with no `spec.md` alongside it. The numeric index always increments; no two plans or specs share a prefix.

## Python Code Style

- **Python (venv-managed), TOML for config, SQLite for state.** No swapping the config format or state engine outside an approved plan; no dependency additions that duplicate an existing module's role (e.g. a second HTTP/RSS library, a second summarization provider) without updating `docs/architecture.md`.
