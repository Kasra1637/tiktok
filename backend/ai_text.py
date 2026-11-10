"""Page-text extraction for app research.

Pure (stdlib only): HTML -> visible text plus title/meta/JSON-LD metadata
used when reading an app page. Split out of `ai_service` by flow;
`ai_service` re-exports these names so existing callers keep working.
"""
import json
import re


def strip_html_to_text(html: str) -> str:
    """Basic regex-based HTML-to-text stripper (no external HTML parsing dependency)."""
    import re

    # Remove script/style/head blocks entirely (including their content)
    text = re.sub(r"(?is)<(script|style|head|noscript)[^>]*>.*?</\1>", " ", html)
    # Replace common block-level tags with newlines to preserve some structure
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\s*/?>", "\n", text)
    # Strip all remaining tags
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    # Unescape common HTML entities
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&quot;": '"', "&#39;": "'", "&rsquo;": "'", "&ldquo;": '"', "&rdquo;": '"',
    }
    for ent, repl in entities.items():
        text = text.replace(ent, repl)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()
def _html_meta_descriptions(html: str) -> list:
    """
    content= of description/og:description/twitter:description meta tags.

    Parsed per-tag so attribute order does not matter (content-first tags
    are common on store listings). Returns [] on any markup surprise rather
    than half a tag.
    """
    found = []
    for tag in re.findall(r"(?is)<meta\b[^>]*>", html or ""):
        attrs = dict(
            (k.lower(), v)
            for k, v in re.findall(r"""(\w+)\s*=\s*["'](.*?)["']""", tag)
        )
        name = (attrs.get("name") or attrs.get("property") or "").strip().lower()
        if name in ("description", "og:description", "twitter:description"):
            content = (attrs.get("content") or "").strip()
            if content:
                found.append(content)
    return found
def _html_json_ld_strings(html: str, limit: int = 20) -> list:
    """
    Every string value inside JSON-LD blocks, in document order.

    Store listings and business sites carry their real description here even
    when the visible body is a client-rendered shell. Malformed blocks are
    skipped: one bad script tag must not poison the rest.
    """
    found = []
    for block in re.findall(
        r'''(?is)<script\b[^>]*type\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script>''',
        html or "",
    ):
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        stack = [data]
        while stack and len(found) < limit:
            node = stack.pop()
            if isinstance(node, dict):
                stack.extend(node.values())
            elif isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, str) and node.strip():
                found.append(node.strip())
    return found[:limit]
def _html_title(html: str) -> str:
    """The page <title>: stripped with <head> today, yet often the only words
    a script-rendered page serves to a plain fetch."""
    match = re.search(r"(?is)<title[^>]*>(.*?)</title>", html or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"(?s)<[^>]+>", " ", match.group(1))).strip()
def page_text_with_metadata(html: str) -> str:
    """
    Body text plus high-signal head metadata, highest-signal first.

    The plain stripper drops <head> entirely, so a store listing whose body
    is a client-rendered shell used to research as one heading plus nav —
    while its title, meta description and JSON-LD carried the actual product
    facts. This keeps the body primary (it stays the bulk) and prepends only
    what the body lacks: title, meta descriptions, JSON-LD strings, each
    once. A pure JS shell still yields almost nothing — honestly thin, and
    reported as such by the caller — rather than invented text.
    """
    import re

    body = strip_html_to_text(html)
    blocks = []
    title = _html_title(html)
    if title:
        blocks.append(title)
    blocks.extend(_html_meta_descriptions(html))
    blocks.extend(_html_json_ld_strings(html))
    if body.strip():
        blocks.append(body.strip())
    # Meta and JSON-LD routinely repeat the body's first paragraph; exact
    # duplicates would burn prompt budget twice for the same words.
    seen = set()
    unique = []
    for block in blocks:
        if block not in seen:
            seen.add(block)
            unique.append(block)
    return "\n\n".join(unique).strip()
