Run `git diff --staged` to see what is staged. Describe the changes concisely, then commit them with a clear commit message that reflects the intent of the changes (not just what files changed).

Use this commit message format:
```
git commit -m "$(cat <<'EOF'
<message>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

If nothing is staged, say so and stop — do not stage anything automatically.
