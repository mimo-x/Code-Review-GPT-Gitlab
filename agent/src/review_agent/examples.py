"""Example library: real review comments on similar changes, shown while the investigator
lists its candidate concerns.

Cards come from human review threads of other repositories (never benchmark repositories):
the diff the reviewer saw, the comment, and its category. Retrieval is lexical (BM25 over
identifier sub-words of the changed lines), filtered by language and file role, then
diversified so the shown examples cover different kinds of concern.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from .files import file_role

LANGUAGES = {
    "c": "C", "h": "C", "cc": "C++", "cpp": "C++", "cxx": "C++", "hpp": "C++", "hh": "C++",
    "java": "Java", "kt": "Kotlin", "ts": "TypeScript", "tsx": "TypeScript", "js": "JavaScript",
    "jsx": "JavaScript", "mjs": "JavaScript", "py": "Python", "go": "Go", "rs": "Rust",
    "cs": "C#", "php": "PHP", "rb": "Ruby", "swift": "Swift", "scala": "Scala",
}
STOP = set("""a an the and or not of to in on for is are be with as at by this that it if else
return true false null none nil self this def function func fn let const var new import from
int string str void public private static final class struct use mod pub package include
""".split())
SUBWORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")
KINDS = [
    ("typo", r"typo|misspel|spelling|grammar"),
    ("docs", r"docstring|comment|documentation|\bdoc|readme|javadoc|jsdoc"),
    ("naming", r"\bname|naming|rename"),
    ("duplication", r"duplicat|repeated|reuse|\bdry\b"),
    ("hard-coded", r"hard-?coded|magic number|constant"),
    ("dead code", r"unused|dead code|redundant|unnecessary|no longer"),
    ("consistency", r"inconsisten|consistent"),
    ("messages", r"log|error message|message"),
    ("null/edge", r"\bnull|\bnil|none|empty|edge case|bound|overflow|negative"),
    ("errors", r"exception|error handling|\berr\b|throw|panic|catch"),
    ("concurrency", r"race|thread|lock|concurren|async|await"),
    ("resources", r"leak|close|dispose|cleanup|release"),
    ("tests", r"\btest"),
]


def language(path: str) -> str | None:
    return LANGUAGES.get(path.rsplit(".", 1)[-1].lower()) if "." in path else None


def kind(text: str) -> str:
    lower = text.lower()
    for name, pattern in KINDS:
        if re.search(pattern, lower):
            return name
    return "other"


def tokens(text: str) -> list[str]:
    out = []
    for word in SUBWORD.findall(text):
        word = word.lower()
        if len(word) > 2 and word not in STOP:
            out.append(word)
    return out


def hunk_terms(hunk: str) -> list[str]:
    """Changed lines count twice, context lines once."""
    terms = []
    for line in hunk.split("\n"):
        if line.startswith("@@"):
            continue
        weight = 2 if line[:1] in "+-" else 1
        terms += tokens(line[1:] if line[:1] in "+- " else line) * weight
    return terms


FEATURES = [
    ("doc", r"^\s*(//|#(?!include|define|if)|/\*|\*|\"\"\"|'\'\'|<!--)"),
    ("signature", r"\b(def|func|fn|function)\b|^\s*(public|private|protected|static|export)\b.*\("),
    ("string", r"\"[^\"]{3,}\"|'[^']{3,}'|`[^`]{3,}`"),
    ("error", r"\b(throw|raise|except|catch|panic|Err\(|err != nil|Error\(|Exception)"),
    ("loop", r"\b(for|while|forEach|map|filter|reduce)\b"),
    ("condition", r"\b(if|else|switch|case|match)\b|\?.*:"),
    ("import", r"^\s*(import|from \S+ import|#include|use |require\()"),
    ("log", r"\b(log|logger|print|println|printf|console\.|warn|debug)\b"),
    ("null", r"\b(null|nil|None|undefined|Optional|nullptr)\b|\?\."),
    ("async", r"\b(async|await|go |thread|Thread|lock|mutex|Mutex|atomic|channel|chan)\b"),
    ("test", r"\b(assert|expect|@Test|t\.Run|it\(|describe\()"),
    ("number", r"(?<![\w.])\d{2,}(?![\w.])"),
    ("return", r"\breturn\b"),
]


def change_features(hunk: str) -> set[str]:
    """Kinds of code on the changed lines (+/-), e.g. doc comments, signatures, errors."""
    found = set()
    for line in hunk.split("\n"):
        if line[:1] not in "+-" or line.startswith(("+++", "---")):
            continue
        body = line[1:]
        for name, pattern in FEATURES:
            if re.search(pattern, body):
                found.add(name)
    changed = [line[1:].strip() for line in hunk.split("\n") if line[:1] in "+-" and line[1:].strip()]
    if len(changed) >= 2 and len(set(changed)) and all(len(x) < 200 for x in changed):
        minus = [line[1:].strip() for line in hunk.split("\n") if line.startswith("-")]
        plus = [line[1:].strip() for line in hunk.split("\n") if line.startswith("+")]
        if minus and plus and len(minus) == len(plus):
            found.add("edit")  # lines rewritten in place (renames, wording, values)
    return found


def build(source: Path, target: Path, exclude_repos: set[str]) -> int:
    """Cards from refinement/comments.annotated.jsonl of a review-expansion dataset."""
    cards = []
    for line in source.open(encoding="utf-8"):
        row = json.loads(line)
        cls = row.get("classification") or {}
        if (row.get("in_reply_to_id") is not None or row.get("speaker_role") != "reviewer"
                or not cls.get("actionable") or cls.get("kind") not in ("issue", "improvement", "cosmetic")
                or cls.get("category") not in ("Defect", "Maintainability", "Performance", "Security")
                or not row.get("diff_hunk") or row["repo"].lower() in exclude_repos):
            continue
        body = re.sub(r"```.*?(```|$)", " ", row["body"], flags=re.S)  # prose only
        body = re.sub(r"\s+", " ", body).strip()
        if not 30 <= len(body) <= 600 or re.search(r"[\u3040-\u9fff]", body) or body.count("**") >= 2:
            continue  # short, long, non-English or bot-formatted
        hunk = "\n".join(line[:160] for line in row["diff_hunk"].split("\n")[-6:])
        signal = (row.get("automatic_signal") or {}).get("post_comment_edit_signal")
        cards.append({
            "id": row["id"], "repo": row["repo"], "path": row["path"],
            "language": row.get("language_group") or language(row["path"]),
            "role": file_role(row["path"]), "hunk": hunk, "body": body,
            "category": cls["category"], "kind": kind(body), "acted_on": signal == "changed",
            "terms": hunk_terms(hunk), "features": sorted(change_features(hunk)),
        })
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as out:
        for card in cards:
            out.write(json.dumps(card, ensure_ascii=False) + "\n")
    return len(cards)


class ExampleIndex:
    def __init__(self, cards: list[dict]):
        self.cards = cards
        self.df = Counter(t for c in cards for t in set(c["terms"]))
        self.avg = sum(len(c["terms"]) for c in cards) / max(len(cards), 1)
        self.n = len(cards)

    @classmethod
    def load(cls, path: Path) -> ExampleIndex:
        return cls([json.loads(line) for line in path.open(encoding="utf-8")])

    def _score(self, query: Counter, card: dict, k1: float = 1.2, b: float = 0.75) -> float:
        tf = Counter(card["terms"])
        size = len(card["terms"])
        score = 0.0
        for term, weight in query.items():
            if term not in tf:
                continue
            idf = math.log(1 + (self.n - self.df[term] + 0.5) / (self.df[term] + 0.5))
            score += weight * idf * tf[term] * (k1 + 1) / (tf[term] + k1 * (1 - b + b * size / self.avg))
        return score

    def search(self, path: str, hunk: str, k: int = 3, exclude: set | None = None,
               lexical: float = 0.5, structural: float = 1.0) -> list[dict]:
        """Top-k cards for a changed hunk: same language (and file role when possible),
        best BM25 first, at most one card per kind of concern and per repository."""
        lang, role = language(path), file_role(path)
        pool = [c for c in self.cards if c["language"] == lang and c["id"] not in (exclude or ())]
        if not pool:
            return []
        same_role = [c for c in pool if c["role"] == role]
        if len(same_role) >= 20:
            pool = same_role
        query = Counter(hunk_terms(hunk))
        features = change_features(hunk)
        lex = {c["id"]: self._score(query, c) for c in pool}
        top = max(lex.values()) or 1.0

        def score(card):
            other = set(card.get("features", ()))
            union = features | other
            jaccard = len(features & other) / len(union) if union else 0.0
            return lexical * lex[card["id"]] / top + structural * jaccard

        ranked = sorted(pool, key=lambda c: (-score(c), not c["acted_on"], c["id"]))
        chosen, kinds, repos = [], set(), set()
        for card in ranked:
            if card["kind"] in kinds or card["repo"] in repos:
                continue
            chosen.append(card)
            kinds.add(card["kind"])
            repos.add(card["repo"])
            if len(chosen) == k:
                break
        return chosen


def unit_hunk(unit) -> tuple[str, str]:
    """(path, diff text) of a changed unit, in the same +/-/space form as review diffs."""
    lines = []
    for line in unit.lines:
        mark = "+" if line.kind == "add" else "-" if line.kind == "delete" else " "
        lines.append(mark + line.text)
    return unit.new_path or unit.old_path, "\n".join(lines[:60])


def for_units(index: ExampleIndex, units: list, mode: str = "retrieved", k: int = 6,
              seed: str = "") -> list[dict]:
    """Up to k cards for an assignment: round-robin over its units, one new kind of concern
    per card. mode "random" draws cards of the same languages instead (a control)."""
    import random

    hunks = [unit_hunk(unit) for unit in units]
    hunks = [(path, text) for path, text in hunks if language(path)]
    if not hunks:
        return []
    chosen: list[dict] = []
    kinds: set[str] = set()
    if mode == "random":
        langs = {language(path) for path, _ in hunks}
        pool = [c for c in index.cards if c["language"] in langs]
        random.Random(seed).shuffle(pool)
        lists = [pool]
    else:
        lists = [index.search(path, text, k=k) for path, text in hunks]
    for rank in range(k):
        for ranked in lists:
            for card in ranked[rank:] if mode != "random" else ranked:
                if card["kind"] in kinds or any(c["id"] == card["id"] for c in chosen):
                    continue
                chosen.append(card)
                kinds.add(card["kind"])
                break
            if len(chosen) == k:
                return chosen
    return chosen


INTRO = (
    "Reviewers of similar changes in other projects wrote comments like these. Use them as "
    "angles to check this assignment's changes: add a candidate only when the same kind of "
    "problem really exists here; do not copy them."
)


def render(cards: list[dict], max_body: int = 300) -> str:
    parts = []
    for number, card in enumerate(cards, start=1):
        body = card["body"] if len(card["body"]) <= max_body else card["body"][:max_body].rsplit(" ", 1)[0] + " ..."
        parts.append(f"Example {number} ({card['language']}, {card['category'].lower()}):\n"
                     f"```diff\n{card['hunk']}\n```\nReviewer: {body}")
    return "\n\n".join(parts)
