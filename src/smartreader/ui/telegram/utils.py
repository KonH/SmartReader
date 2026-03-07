"""Pure helper functions for Telegram UI — no side effects, no state."""
from __future__ import annotations

import re


def escape_md(text: str) -> str:
    """Escape Markdown special chars for Telegram MarkdownV1."""
    for ch in ("*", "_", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def html_escape(text: str) -> str:
    """Escape text for embedding inside an HTML parse_mode message."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def md_to_html(text: str) -> str:
    """HTML-escape arbitrary text then convert common Markdown patterns to HTML tags.

    Order matters: HTML-escape first so that '<' / '>' in the source text don't
    collide with the tags we insert afterwards.
    Handles: [text](url) links, **bold**, `inline code`.
    Single-star italic is intentionally skipped to avoid false positives.
    """
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # [link text](https://...) → <a href="...">link text</a>  (full, well-formed links)
    text = re.sub(r'\[([^\]\n]+)\]\((https?://[^\)\s]+)\)', r'<a href="\2">\1</a>', text)
    # Truncated/unclosed [text](https://... without closing ) → just show link text
    text = re.sub(r'\[([^\]\n]+)\]\(https?://[^\)\s]*', r'\1', text)
    # **bold** → <b>bold</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    # Strip remaining unmatched ** (e.g. unclosed bold markers from channel authors)
    text = text.replace('**', '')
    # `code` → <code>code</code>
    text = re.sub(r'`([^`\n]+)`', r'<code>\1</code>', text)
    return text


def normalize_telegram_id(raw: str) -> str:
    """For t.me links, extract the channel username; otherwise return as-is."""
    m = re.match(r'^(?:https?://)?t\.me/([^/?#]+)', raw.strip())
    return m.group(1) if m else raw.strip()


def normalize_source_name(external_id: str) -> str:
    """Derive a clean config-key name from an external ID or URL."""
    s = external_id.strip()
    s = re.sub(r'^https?://', '', s)
    s = re.sub(r'^www\.', '', s, flags=re.I)
    parts = [p for p in s.split('/') if p]
    if not parts:
        return 'source'

    _SKIP = {'rss', 'feed', 'feeds', 'atom', 'news', 'index', 'latest', 'all'}
    _TLDS = {'com', 'net', 'org', 'io', 'co', 'uk', 'de', 'ru', 'me', 'tv', 'app', 'dev'}
    _PFXS = {'www', 'feeds', 'rss', 'feed', 'news', 'media'}

    candidates: list[str] = []
    for p in parts[1:]:
        p = re.sub(r'\.(rss|xml|atom|json|feed|html?)$', '', p, flags=re.I)
        p = re.sub(r'[-_]?(rss|feed|atom)$', '', p, flags=re.I)
        if p and p.lower() not in _SKIP:
            candidates.append(p)

    if candidates:
        base = candidates[-1]
    else:
        domain_parts = parts[0].split('.')
        significant = [p for p in domain_parts
                       if p.lower() not in _TLDS and p.lower() not in _PFXS]
        base = significant[-1] if significant else domain_parts[0]

    base = re.sub(r'[^a-z0-9]+', '_', base.lower())
    return base.strip('_') or 'source'


def username(sender: object) -> str:
    u = getattr(sender, "username", None)
    return str(u) if u else str(getattr(sender, "id", "unknown"))
