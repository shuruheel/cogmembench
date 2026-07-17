from __future__ import annotations

import re

TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def count_tokens(text: str) -> int:
    """Stable fallback accounting; providers may supply authoritative counts."""
    return len(TOKEN_RE.findall(text or ""))


def count_messages(messages: list[dict[str, object]]) -> int:
    total = 0
    for message in messages:
        total += 4 + count_tokens(str(message.get("content", "")))
    return total + 2

