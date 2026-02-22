Before anything else, run tests:
```
PYTHONPATH=src python -m pytest tests/ -v
```
If any tests fail, stop and report — do not stage or commit.

Run `git status` to see the full working tree state, then `git diff --staged` to inspect what is already staged.

Stage all relevant changed and untracked files with `git add <file>`. For `.sh` scripts, always preserve execution rights using `git add --chmod=+x <file>` instead of plain `git add`.

Describe the changes concisely, then commit with a clear message that reflects the intent of the changes (not just what files changed).

Use this commit message format:
```
git commit -m "$(cat <<'EOF'
<message>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If nothing is staged and no relevant files are found, say so and stop — do not stage unrelated files automatically.
