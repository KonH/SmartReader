Run `git diff --staged` to see what is staged. Describe the changes concisely, then commit them with a clear commit message that reflects the intent of the changes (not just what files changed).

Before committing, run `git status` to identify any relevant unstaged files and stage them with `git add <file>`. For `.sh` scripts, always preserve execution rights using `git add --chmod=+x <file>` instead of plain `git add`.

Use this commit message format:
```
git commit -m "$(cat <<'EOF'
<message>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If nothing is staged and no relevant files are found, say so and stop — do not stage unrelated files automatically.
