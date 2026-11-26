"""Deterministic checks of a finding's text against the code, applied when it is reported.

Each check either passes, repairs the text (the environment records the repair) or gives a
reason to reject the finding, so the model meets the rule inside the episode and the
trajectory keeps every change.
"""

from __future__ import annotations

import difflib
import re

TYPO = re.compile(r"\b(?:typos?|misspel\w*|spelling|spelled)\b", re.I)
_Q = r"[`'\"‘“]([A-Za-z_][\w.\-]{1,60})[`'\"’”]"
QUOTED = re.compile(_Q)
# "misspells 'method' as 'mehod'", "'method' is misspelled as 'mehod'": the last word is wrong
MISSPELLED_AS = re.compile(rf"misspel\w*\s+(?:{_Q}\s+)?as\s+{_Q}", re.I)
WORDS = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NEAR_CUTOFF = 0.8


def misspelled_word(text: str) -> str | None:
    """The word a typo comment calls misspelled: the first quoted word, unless the comment
    says "misspelled as X"."""
    match = MISSPELLED_AS.search(text)
    if match:
        return match.group(2)
    words = [w for w in QUOTED.findall(text) if len(w) >= 3]
    return words[0] if words else None


def _near(word: str, vocabulary: set[str]) -> tuple[str, float] | None:
    if "." in word or not vocabulary:
        return None
    found = difflib.get_close_matches(word, vocabulary, n=1, cutoff=NEAR_CUTOFF)
    if not found:
        return None
    return found[0], difflib.SequenceMatcher(None, word, found[0]).ratio()


def typo_check(text: str, head: str, base: str) -> tuple[str, str, str | None] | None:
    """For a comment about a typo: ("ok", word, None) when the word is in the new code;
    ("fixed", word, old) when only the old code has it (the pull request fixes it);
    ("corrected", word, actual) when the new code has a near spelling the model mis-copied;
    ("missing", word, None) when neither version has anything like it. None: not a typo
    comment, or no quoted word to check."""
    if not TYPO.search(text):
        return None
    word = misspelled_word(text)
    if not word:
        return None
    if word in head:
        return "ok", word, None
    if word in base:
        return "fixed", word, word
    others = {w for w in QUOTED.findall(text) if w != word}
    head_words = set(WORDS.findall(head)) - others
    base_only = set(WORDS.findall(base)) - set(WORDS.findall(head)) - others
    in_head, in_base = _near(word, head_words), _near(word, base_only)
    if in_base and (not in_head or in_base[1] > in_head[1]):
        return "fixed", word, in_base[0]
    if in_head:
        return "corrected", word, in_head[0]
    return "missing", word, None


def replace_word(text: str, old: str, new: str) -> str:
    return re.sub(rf"(?<![\w]){re.escape(old)}(?![\w])", new, text)


_ID = r"K\d+"
_IDS = rf"{_ID}(?:\s*/\s*{_ID})*"
# Only these shapes are cleaned: a leading label ("K3: ...", "[K3] ...", "K1 (high): ...",
# "K1/K2: ...", "K2 name ...") and a parenthesised id ("(K4)", "(K9/F2)").
ID_PREFIX = re.compile(
    rf"^\s*[\[(]?(?P<ids>{_IDS})[\])]?(?:\s*\((?:high|medium|low)\))?(?:\s*[:\-–—]\s*|\s+)"
)
ID_PAREN = re.compile(rf"\s*[\[(](?P<ids>{_IDS})(?:\s*/\s*F\d+)?[\])]")


def clean_ids(text: str, ids: set[str], source: str) -> tuple[str, list[str]]:
    """Remove our candidate ids from a title or description. Only ids this episode issued,
    never one that also occurs as a word in the code, and only in the shapes above."""

    def ours(group: str) -> list[str] | None:
        found = re.findall(_ID, group)
        if all(i in ids and not re.search(rf"(?<!\w){i}(?!\w)", source) for i in found):
            return found
        return None

    removed: list[str] = []
    match = ID_PREFIX.match(text)
    if match and ours(match.group("ids")) and text[match.end():].strip():
        removed += ours(match.group("ids"))
        rest = text[match.end():]
        text = rest[:1].upper() + rest[1:]

    def paren(m):
        found = ours(m.group("ids"))
        if not found:
            return m.group(0)
        removed.extend(found)
        return ""

    text = ID_PAREN.sub(paren, text)
    return text, removed


FIELD_LEAK = re.compile(
    r'["\']?\s*,\s*["\'](?:candidate|evidence|category|severity|condition|existing_code|path|'
    r'title|description|suggestion|line_hint|about_removal)["\']\s*:'
)


def cut_field_leak(text: str) -> str:
    """A description that swallowed the following JSON fields ('...", "candidate": "K3",
    "evidence": [...]'): keep the text before the leak."""
    match = FIELD_LEAK.search(text)
    if not match or not text[: match.start()].strip():
        return text
    return text[: match.start()].rstrip(" \"',")
