"""Canonical tool calls: natural forms a small model writes, mapped onto our schemas.

The environment normalizes each call just before dispatching it. Only forms that fail as
written are rewritten, so a call that is valid as written is dispatched and shown exactly
as before; and only where the intent is plain:

  an array or object sent as a JSON string -> the decoded value (any tool, any such field)
  path on a tool that takes path_glob  -> path_glob (a file itself, a directory dir/**)
  a severity word as candidate priority -> high/medium/low (null: the default)
  update_finding withdrawing a K#       -> note_candidates dismissing it
  read_diff cluster with path/paths/unit -> without the cluster
  findings as a JSON string the model closed with extra brackets -> the array
  a tool name with tool-parser markup ("<note_candidates") -> the tool

The rewritten call is what later requests show and what training teaches; the model's own
output stays the step's response (trajectory.Step), so replays serve what it produced.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Collection
from functools import cache

from pydantic import ValidationError

from review_core.intel.tools import drop_empty

from . import repair
from .schemas import compact_schema

GLOB = re.compile(r"[*?\[]")
CANDIDATE = re.compile(r"K\d+")
PRIORITIES = ("high", "medium", "low")
PRIORITY_ALIASES = {"critical": "high", "major": "high", "minor": "low", "nit": "low"}
TYPO_PREFIX = 4  # "media" for medium: the first letters of one value
# a tool name with the start of parser markup: "<note_candidates", "code_search<parameter=x"
LEAKED_NAME = re.compile(r"<?([a-z_]+)\s*(?:<parameter=(\w+)>?)?")
CLOSING = re.compile(r"[\]}\s]+")
UNMAPPED = object()


def normalize(call: dict, tools: dict, candidates: Collection[str],
              files: Callable[[], Collection[str]]) -> dict:
    """The canonical form of one call, or the call itself when nothing applies. tools: the
    offered tools' argument models by name; candidates: the K# ids noted so far; files:
    the paths of both revisions (read only when a path is to be resolved)."""
    function = call.get("function") or {}
    name, raw = function.get("name"), function.get("arguments") or "{}"
    try:
        arguments = repair.loads(raw) if isinstance(raw, str) else raw
    except json.JSONDecodeError:
        return call
    if not isinstance(name, str) or not isinstance(arguments, dict):
        return call
    if name not in tools:
        tool = _leaked(name, arguments, tools)
        if tool is None:
            return call
        decoded = _json_strings(tools[tool], arguments)
        if decoded is None:
            return {**call, "function": {**function, "name": tool}}
        text = json.dumps(decoded, ensure_ascii=False) if isinstance(raw, str) else decoded
        return {**call, "function": {**function, "name": tool, "arguments": text}}
    model, canonical = tools[name], name
    decoded = _json_strings(model, arguments)
    arguments = arguments if decoded is None else decoded
    changed = None
    if name == "update_finding" and "note_candidates" in tools:
        changed = _dismissal(arguments, candidates)
        canonical = "note_candidates" if changed else name
    elif name == "note_candidates":
        changed = _priorities(arguments)
    elif name == "read_diff":
        changed = _one_scope(model, arguments)
    elif name == "report_finding":
        changed = _findings(arguments)
    elif "path_glob" in model.model_fields and "path" not in model.model_fields:
        changed = _path_glob(arguments, files)
    changed = decoded if changed is None else changed
    if changed is None:
        return call
    text = json.dumps(changed, ensure_ascii=False) if isinstance(raw, str) else changed
    return {**call, "function": {**function, "name": canonical, "arguments": text}}


@cache
def _structured_fields(model) -> dict[str, type]:
    """The model's fields whose schema type is an array or an object: list or dict."""
    properties = compact_schema(model.model_json_schema()).get("properties") or {}
    kinds = {"array": list, "object": dict}
    return {
        key: kinds[spec["type"]]
        for key, spec in properties.items()
        if isinstance(spec, dict) and spec.get("type") in kinds
    }


def _json_strings(model, arguments: dict) -> dict | None:
    """The arguments with each array or object field that was sent as a JSON string
    decoded, when the string parses to that type; None when there is none. A string that
    is not JSON, or parses to another type, is left for validation to reject."""
    out = None
    for key, kind in _structured_fields(model).items():
        value = arguments.get(key)
        if not isinstance(value, str) or value.strip()[:1] not in ("[", "{"):
            continue
        try:
            result = repair.loads(value.strip())
        except json.JSONDecodeError:
            continue
        if isinstance(result, kind):
            out = {**(out or arguments), key: result}
    return out


def _leaked(name: str, arguments: dict, tools: dict) -> str | None:
    """The tool a leaked name means, when the call is valid for it as it stands; not when
    the markup names a parameter that is missing (the parser lost its value)."""
    match = LEAKED_NAME.fullmatch(name.strip())
    if not match or match.group(1) not in tools:
        return None
    if match.group(2) and match.group(2) not in arguments:
        return None
    model = tools[match.group(1)]
    decoded = {key: repair.decoded(value, [], key) for key, value in arguments.items()}
    try:
        model.model_validate(drop_empty(model, decoded))
    except ValidationError:
        return None
    return match.group(1)


def _glob(value: str, files: Callable[[], Collection[str]]) -> str | None:
    value = value.strip()
    if not value:
        return "*"
    if GLOB.search(value):
        return value
    paths = files()
    if value in paths:
        return value
    folder = value.rstrip("/")
    if folder and any(path.startswith(folder + "/") for path in paths):
        return folder + "/**"
    return None  # no such file or directory: left as it is


def _path_glob(arguments: dict, files) -> dict | None:
    value = arguments.get("path")
    if not isinstance(value, str):
        return None
    glob = _glob(value, files)
    rest = {key: item for key, item in arguments.items() if key != "path"}
    if glob is None or rest.get("path_glob") not in (None, "", "*", glob):
        return None
    if glob != "*":  # "*" or "": anywhere, the default
        rest["path_glob"] = glob
    return rest


def _priority(value):
    if value is None:
        return None
    if not isinstance(value, str):
        return UNMAPPED
    key = value.strip().lower()
    if key in PRIORITIES or key in PRIORITY_ALIASES:
        return PRIORITY_ALIASES.get(key, key)
    near = [c for c in PRIORITIES if len(c) >= TYPO_PREFIX and key[:TYPO_PREFIX] == c[:TYPO_PREFIX]]
    return near[0] if len(near) == 1 else UNMAPPED


def _priorities(arguments: dict) -> dict | None:
    add = repair.decoded(arguments.get("add"), [], "add")
    if not isinstance(add, list):
        return None
    items, changed = [], False
    for item in add:
        if isinstance(item, dict) and "priority" in item and item["priority"] not in PRIORITIES:
            value = _priority(item["priority"])
            if value is UNMAPPED:
                return None
            item = {key: v for key, v in item.items() if key != "priority" or value}
            if value:
                item["priority"] = value
            changed = True
        items.append(item)
    return {**arguments, "add": items} if changed else None


def _yes(value) -> bool:
    return value is True or (isinstance(value, str) and value.strip().lower() == "true")


def _dismissal(arguments: dict, candidates: Collection[str]) -> dict | None:
    key = arguments.get("id")
    key = key.strip() if isinstance(key, str) else None
    if not key or not CANDIDATE.fullmatch(key) or key not in candidates:
        return None
    dismiss = arguments.get("dismiss")
    said = dismiss.strip() if isinstance(dismiss, str) else ""
    stated = said if said.lower() not in ("", "true", "false") else ""  # dismiss: "reason"
    if not (_yes(arguments.get("withdraw")) or _yes(dismiss) or stated):
        return None
    reason = arguments.get("reason")
    reason = reason.strip() if isinstance(reason, str) and reason.strip() else stated
    if not reason:
        return {"dismiss": [key]}
    return {"dismiss": [reason if reason.startswith(f"{key}:") else f"{key}: {reason}"]}


def _one_scope(model, arguments: dict) -> dict | None:
    given = drop_empty(model, arguments)
    if given.get("cluster") is None or all(given.get(k) is None for k in ("path", "paths", "unit")):
        return None
    return {key: value for key, value in arguments.items() if key != "cluster"}


def _findings(arguments: dict) -> dict | None:
    text = arguments.get("findings")
    if not isinstance(text, str):
        return None
    text = text.strip()
    try:
        repair.loads(text)
        return None  # decoded as it is (repair)
    except json.JSONDecodeError:
        pass
    try:
        value, end = json.JSONDecoder(strict=False).raw_decode(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list) or not CLOSING.fullmatch(text[end:]):
        return None
    return {**arguments, "findings": value}
