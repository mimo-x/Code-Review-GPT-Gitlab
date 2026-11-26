"""Shape of text lines, so data-like content can be folded instead of sent whole."""

from __future__ import annotations

from collections.abc import Iterable

from review_core.common import Record


class TextShape(Record):
    chars: int
    longest_line: int
    # Characters that sit in lines longer than the line limit.
    long_line_chars: int
    letter_share: float


def shape(lines: Iterable[str], max_line_chars: int) -> TextShape:
    chars = longest = long_chars = letters = 0
    for line in lines:
        body = line.rstrip("\r\n")
        size = len(body)
        chars += size
        longest = max(longest, size)
        if size > max_line_chars:
            long_chars += size
        letters += sum(character.isalpha() for character in body)
    return TextShape(
        chars=chars,
        longest_line=longest,
        long_line_chars=long_chars,
        letter_share=round(letters / chars, 3) if chars else 0.0,
    )


def describe(text: str) -> str:
    letters = sum(character.isalpha() for character in text)
    share = round(100 * letters / len(text)) if text else 0
    return f"{len(text)} chars, {share}% letters"


def fold(line: str, limit: int, offset: int = 0, hint: str | None = None) -> str:
    """Show at most limit characters of one line, starting at offset, and say what is hidden."""
    body = line.rstrip("\r\n")
    if offset == 0 and len(body) <= limit:
        return body
    shown = body[offset : offset + limit]
    before = f"[{offset} chars before] " if offset else ""
    rest = body[offset + limit :]
    if not rest:
        return before + shown
    note = f"+{len(rest)} chars folded: {describe(body)}"
    return f"{before}{shown} [{note}{'; ' + hint if hint else ''}]"
