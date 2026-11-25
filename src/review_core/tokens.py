from __future__ import annotations

from functools import lru_cache

import tiktoken


class TokenCounter:
    """Deterministic token measurement shared by every layer that sizes model-facing text."""

    def __init__(self, encoding: str = "cl100k_base"):
        self.encoding = _encoding(encoding)

    def count(self, value: str) -> int:
        return len(self.encoding.encode(value, disallowed_special=()))

    def prefix(self, text: str, limit: int) -> str:
        if self.count(text) <= limit:
            return text
        low, high = 0, len(text)
        while low < high:
            middle = (low + high + 1) // 2
            if self.count(text[:middle]) <= limit:
                low = middle
            else:
                high = middle - 1
        return text[:low]


@lru_cache(maxsize=4)
def _encoding(name: str):
    return tiktoken.get_encoding(name)
