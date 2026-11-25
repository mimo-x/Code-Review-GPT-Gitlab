"""Exclude a change only on hard evidence; everything else is reviewed."""

from __future__ import annotations

import weakref
from pathlib import PurePosixPath

from review_core.intel.models import ChangeUnit

from .models import Exclusion

LOCK_FILES = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lockb",
        "bun.lock",
        "Cargo.lock",
        "poetry.lock",
        "Pipfile.lock",
        "uv.lock",
        "pdm.lock",
        "composer.lock",
        "Gemfile.lock",
        "go.sum",
        "flake.lock",
        "Podfile.lock",
        "Package.resolved",
        "packages.lock.json",
        "gradle.lockfile",
        "mix.lock",
        "pubspec.lock",
        "conan.lock",
    }
)
MINIFIED_SUFFIXES = (".min.js", ".min.mjs", ".min.css")
SOURCE_MAP_SUFFIXES = (".js.map", ".css.map")


def exclusion(intel, unit: ChangeUnit, change) -> Exclusion | None:
    path = unit.new_path or unit.old_path or ""
    name = PurePosixPath(path).name
    found = _reason(intel, unit, change, name)
    if found is None:
        return None
    reason, evidence = found
    return Exclusion(
        unit_id=unit.id,
        path=path,
        reason=reason,
        evidence=evidence,
        line_ids=tuple(line.id for line in unit.lines),
    )


def _reason(intel, unit, change, name):
    if change.binary:
        return "binary", "Git reports binary content"
    if name in LOCK_FILES:
        return "lock_file", f"dependency lock file {name}"
    lowered = name.lower()
    if lowered.endswith(MINIFIED_SUFFIXES):
        return "minified", f"minified asset suffix {lowered.rsplit('.', 2)[-2]}"
    if lowered.endswith(SOURCE_MAP_SUFFIXES):
        return "generated", "build source map"
    classification = unit.classification
    if classification and classification.kind == "generated":
        return "generated", "; ".join(classification.reasons) or "generated marker"
    if _format_only(intel, unit, change, classification.language if classification else None):
        return "format_only", "changed lines differ only in whitespace"
    return None


def _format_only(intel, unit, change, language) -> bool:
    """Whitespace-only text change AND identical syntax, with string literals kept verbatim.

    The text check alone is not enough: whitespace inside strings, and indentation in
    Python or YAML, carry meaning. Anything that cannot be parsed cleanly is reviewed.
    """
    if unit.metadata or not unit.lines or language is None:
        return False
    deleted = "".join(line.text for line in unit.lines if line.kind == "delete")
    added = "".join(line.text for line in unit.lines if line.kind == "add")
    if "".join(deleted.split()) != "".join(added.split()):
        return False
    if not (change.old_path and change.new_path):
        return False
    before, after = unit.base_symbol, unit.head_symbol
    if before and after:
        left = intel.normalize(intel.read_symbol(before.id, "base").text, language)
        right = intel.normalize(intel.read_symbol(after.id, "head").text, language)
        if left.complete and right.complete:
            return left.digest == right.digest
    # A symbol fragment may not parse alone; compare whole files instead (conservative:
    # any other change in the file keeps this unit in review).
    left = _file_syntax(intel, change.old_path, "base", language)
    right = _file_syntax(intel, change.new_path, "head", language)
    return left.complete and right.complete and left.digest == right.digest


# Per-intel cache: several units of one file compare the same two file versions.
_FILE_SYNTAX: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _file_syntax(intel, path: str, side: str, language: str):
    cache = _FILE_SYNTAX.setdefault(intel, {})
    key = (path, side, language)
    if key not in cache:
        cache[key] = intel.normalize(intel.workspace.read_file(path, side).text, language)
    return cache[key]
