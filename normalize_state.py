#!/usr/bin/env python3
"""Normalize interest keywords in state.sqlite using current lemmatization rules:

  - Removes skip words (from [scoring] skip in config.toml)
  - Lemmatizes Cyrillic words via pymorphy3 (e.g. идущий → идти)
  - Lemmatizes Latin words ≥4 chars via simplemma('en','sr') (e.g. attacks → attack)
  - Merges scores of words that collapse to the same lemma

Creates a backup at .tmp/state.sqlite.bak before any changes.
"""
import json
import shutil
import sqlite3
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "src"))

import pymorphy3
import simplemma

_morph = pymorphy3.MorphAnalyzer()
_TABLE = "state"


# ── normalization ──────────────────────────────────────────────────────────────

def _lemma(w: str, skip: set[str]) -> str | None:
    """Return lemma for a single keyword, or None if it should be dropped."""
    if w in skip:
        return None
    if any('\u0400' <= c <= '\u04ff' for c in w):
        parsed = _morph.parse(w)
        lemma = parsed[0].normal_form if parsed else w
    else:
        lemma = simplemma.lemmatize(w, ('en', 'hbs')) if len(w) >= 4 else w
    lemma = lemma.lower()
    return None if lemma in skip else lemma


def _normalize_dict(
    interests: dict[str, float],
    skip: set[str],
) -> tuple[dict[str, float], int, int, int]:
    """
    Normalize one keyword→score dict.

    Returns: (result, n_skip_removed, n_normalized, n_merged)
      n_skip_removed  — words dropped because they (or their lemma) were in skip
      n_normalized    — words whose form changed (but were not dropped)
      n_merged        — extra entries absorbed into an existing lemma
    """
    n_skip_removed = 0
    n_normalized = 0
    n_merged = 0
    result: dict[str, float] = {}

    for word, score in interests.items():
        w = word.lower()
        lemma = _lemma(w, skip)
        if lemma is None:
            n_skip_removed += 1
            continue
        if lemma != w:
            n_normalized += 1
        if lemma in result:
            n_merged += 1
        result[lemma] = result.get(lemma, 0.0) + score

    return result, n_skip_removed, n_normalized, n_merged


# ── config ─────────────────────────────────────────────────────────────────────

def _load_skip(config_path: Path) -> set[str]:
    with open(config_path, "rb") as f:
        cfg = tomllib.load(f)
    return set(cfg.get("scoring", {}).get("skip", []))


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    state_path = ROOT / (sys.argv[1] if len(sys.argv) > 1 else "state.sqlite")
    config_path = ROOT / "config.toml"

    if not state_path.exists():
        print(f"Error: {state_path} not found")
        sys.exit(1)

    # 1. Backup
    backup_dir = ROOT / ".tmp"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / "state.sqlite.bak"
    shutil.copy2(state_path, backup_path)
    print(f"Backup: {backup_path}")

    # 2. Skip list
    skip = _load_skip(config_path)
    print(f"Skip words in config: {len(skip)}\n")

    # 3. Read from backup
    conn_r = sqlite3.connect(str(backup_path))
    rows = dict(conn_r.execute(f"SELECT key, value FROM {_TABLE}").fetchall())
    conn_r.close()

    common_raw: dict[str, float] = json.loads(rows.get("common_keyword_interests", "{}"))
    category_raw: dict[str, dict[str, float]] = json.loads(rows.get("category_interests", "{}"))

    # 4. Normalize common interests
    common_new, com_skip, com_norm, com_merge = _normalize_dict(common_raw, skip)

    # 5. Normalize per-category interests
    cat_stats: dict[str, tuple[int, int, int, int]] = {}  # cat → (before, skip, norm, merge)
    category_new: dict[str, dict[str, float]] = {}
    for cat, cat_kw in category_raw.items():
        result, n_skip, n_norm, n_merge = _normalize_dict(cat_kw, skip)
        category_new[cat] = result
        cat_stats[cat] = (len(cat_kw), n_skip, n_norm, n_merge)

    # 6. Write to source state.sqlite
    conn_w = sqlite3.connect(str(state_path))
    conn_w.execute(
        f"INSERT OR REPLACE INTO {_TABLE} (key, value) VALUES (?, ?)",
        ("common_keyword_interests", json.dumps(common_new)),
    )
    conn_w.execute(
        f"INSERT OR REPLACE INTO {_TABLE} (key, value) VALUES (?, ?)",
        ("category_interests", json.dumps(category_new)),
    )
    conn_w.commit()
    conn_w.close()

    # 7. Stats
    total_cat_before = sum(v[0] for v in cat_stats.values())
    total_cat_skip   = sum(v[1] for v in cat_stats.values())
    total_cat_norm   = sum(v[2] for v in cat_stats.values())
    total_cat_merge  = sum(v[3] for v in cat_stats.values())
    total_cat_after  = sum(len(v) for v in category_new.values())

    grand_before = len(common_raw) + total_cat_before
    grand_skip   = com_skip + total_cat_skip
    grand_norm   = com_norm + total_cat_norm
    grand_merge  = com_merge + total_cat_merge
    grand_after  = len(common_new) + total_cat_after

    W = 34
    print("━" * W)
    print("  common_keyword_interests")
    print(f"    before:      {len(common_raw):>5}")
    print(f"    after:       {len(common_new):>5}")
    print(f"    skip removed:{com_skip:>5}")
    print(f"    normalized:  {com_norm:>5}")
    print(f"    merged:      {com_merge:>5}")

    for cat, (n_before, n_skip, n_norm, n_merge) in cat_stats.items():
        n_after = len(category_new[cat])
        print("━" * W)
        print(f"  category '{cat}'")
        print(f"    before:      {n_before:>5}")
        print(f"    after:       {n_after:>5}")
        print(f"    skip removed:{n_skip:>5}")
        print(f"    normalized:  {n_norm:>5}")
        print(f"    merged:      {n_merge:>5}")

    print("━" * W)
    print("  TOTAL")
    print(f"    before:      {grand_before:>5}")
    print(f"    after:       {grand_after:>5}")
    print(f"    skip removed:{grand_skip:>5}")
    print(f"    normalized:  {grand_norm:>5}")
    print(f"    merged:      {grand_merge:>5}")
    print("━" * W)
    print(f"\nDone — state.sqlite updated, backup at {backup_path}")


if __name__ == "__main__":
    main()
