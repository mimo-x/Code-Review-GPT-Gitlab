from __future__ import annotations

import ast
import fnmatch
import posixpath
import time
from pathlib import PurePosixPath

from review_core.common import Gap, QueryResult, ReviewCoreError, Shortfalls, source_lines

from .models import DefinitionCandidate, Reference
from .precise import precise_calls
from .resolvers import resolver_for
from .syntax import MEMBER_SEPARATORS, OUTLINE_LANGUAGES, walk

BOUND_LANGUAGES = {"python", "javascript", "jsx", "typescript", "tsx"}
# Files handed to a type-aware resolver for one definition lookup, besides the usage file.
MAX_TYPED_FILES = 200


def module_paths(
    intel, path: str, module: str, side: str, include_missing: str | None = None
) -> tuple[str, ...]:
    language = intel.classify_file(path, side).language
    folder = str(PurePosixPath(path).parent)
    tree = intel.workspace.tree(side)
    stems = []
    if language == "python":
        level = len(module) - len(module.lstrip("."))
        suffix = module[level:].replace(".", "/")
        if level:
            for _ in range(level - 1):
                folder = posixpath.dirname(folder)
            stems.append(posixpath.normpath(posixpath.join(folder, suffix)))
        else:
            stems.extend([suffix, "src/" + suffix])
            package_root = folder
            while posixpath.join(package_root, "__init__.py") in tree:
                parent = posixpath.dirname(package_root)
                if parent == package_root:
                    break
                package_root = parent
            if package_root != folder:
                stems.append(posixpath.normpath(posixpath.join(package_root, suffix)))
        endings = (".py", "/__init__.py", ".pyi")
    elif language in {"javascript", "jsx", "typescript", "tsx"} and module.startswith("."):
        stems.append(posixpath.normpath(posixpath.join(folder, module)))
        endings = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.js")
    else:
        return ()
    paths = {
        stem + ending
        for stem in stems
        for ending in endings
        if stem + ending in tree or stem + ending == include_missing
    }
    return tuple(sorted(paths))


def _visible(binding_scope: str, caller_scope: str) -> bool:
    return (
        not binding_scope
        or caller_scope == binding_scope
        or caller_scope.startswith(binding_scope + ".")
    )


def _shadowed(intel, path: str, side: str, name: str, line: int) -> bool:
    """Conservatively reject a strong binding if a parameter or assignment can replace it."""
    content = intel.workspace.read_file(path, side)
    language = intel.classify_file(path, side).language
    key = (content.blob_hash, language)
    index = intel._shadow_index.get(key)
    if index is None:
        builder = _python_bindings if language == "python" else _js_bindings
        index = intel._shadow_index[key] = builder(intel, content, language)
    if index is None:
        return True  # unparsable: never claim a strong binding
    file_names, scopes = index
    return name in file_names or any(
        start <= line <= end and name in names for start, end, names in scopes
    )


def _python_bindings(intel, content, language):
    """Module-level stores, and per function its parameters and local stores."""
    try:
        tree = ast.parse(content.text)
    except SyntaxError:
        return None

    def stores(scope) -> set[str]:
        found, stack = set(), list(ast.iter_child_nodes(scope))
        while stack:
            node = stack.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                found.add(node.id)
            stack.extend(ast.iter_child_nodes(node))
        return found

    scopes = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = node.args
            params = arguments.posonlyargs + arguments.args + arguments.kwonlyargs
            params += [arg for arg in (arguments.vararg, arguments.kwarg) if arg]
            names = {arg.arg for arg in params} | stores(node)
            scopes.append((node.lineno, node.end_lineno or node.lineno, frozenset(names)))
    return frozenset(stores(tree)), tuple(scopes)


JS_FUNCTION_KINDS = {
    "function_declaration",
    "function_expression",
    "arrow_function",
    "method_definition",
}
JS_BINDING_KINDS = {
    "variable_declarator",
    "assignment_expression",
    "augmented_assignment_expression",
}


def _js_bindings(intel, content, language):
    """Names assigned anywhere in the file, and per function its parameter names."""
    root = intel.syntax.root(content.blob_hash, language, content.text)
    assigned, scopes = set(), []
    for node in walk(root):
        kind = node.kind()
        if kind in JS_FUNCTION_KINDS:
            parameters = node.field("parameters") or node.field("parameter")
            if parameters:
                position = node.range()
                names = frozenset(
                    child.text() for child in walk(parameters) if child.kind() == "identifier"
                )
                scopes.append((position.start.line + 1, position.end.line + 1, names))
        elif kind in JS_BINDING_KINDS:
            target = node.field("name") or node.field("left")
            value = node.field("value")
            if value and value.kind() in {"arrow_function", "function_expression"}:
                continue
            if target:
                assigned.update(
                    child.text() for child in walk(target) if child.kind() == "identifier"
                )
    return frozenset(assigned), tuple(scopes)


NAME_BASES = {"same-file name candidate", "name match in repository"}
SELF_RECEIVERS = {"self", "this", "$this", "cls", "super"}
TYPE_KINDS = {"class", "interface", "struct", "trait", "impl", "enum"}
# Languages where obj.m() always calls a method (no module or namespace objects in play).
METHOD_ONLY_MEMBERS = {"java", "csharp", "cpp", "c", "php", "rust", "kotlin"}
# Languages where a bare f() can never call a method of another class.
BARE_IS_FREE = {"python", "javascript", "jsx", "typescript", "tsx", "go", "rust"}


def _shape_filter(intel, candidates, expression, side, from_path, local_scope):
    """Drop name matches the shape of the call rules out.

    self.m() / this.m() call methods, preferably of the enclosing class; Name.m() calls
    members of a class Name when there is one; obj.m() calls methods, not free functions;
    a bare f() calls free functions (or, in Java-like languages, the enclosing class's own
    methods). Import-bound and type-resolved candidates are never filtered.
    """
    named = {key: c for key, c in candidates.items() if c.basis in NAME_BASES}
    if not named:
        return candidates
    language = intel.classify_file(from_path, side).language
    parts = [part for part in MEMBER_SEPARATORS.split(expression) if part]
    receiver = parts[-2] if len(parts) > 1 else None
    qualified = "::" in expression
    enclosing_class = local_scope.rpartition(".")[0]

    kinds = {}

    def owner(candidate):
        """The class a candidate is a member of, or "" for free functions and classes."""
        symbol = candidate.symbol
        prefix = symbol.qualified_name.rpartition(".")[0]
        if not prefix or symbol.kind in TYPE_KINDS:
            return ""
        if symbol.parent_id is None:
            return prefix  # out-of-class definition such as C++ Foo::bar
        path = symbol.location.path
        if path not in kinds:
            kinds[path] = {s.id: s.kind for s in intel.outline(path, side).items}
        return prefix if kinds[path].get(symbol.parent_id) in TYPE_KINDS else ""

    keep = named
    if receiver in SELF_RECEIVERS:
        methods = {k: c for k, c in named.items() if owner(c)}
        own = {
            k: c
            for k, c in methods.items()
            if owner(c).split(".")[-1] == enclosing_class.split(".")[-1]
        }
        keep = own or methods
    elif receiver and (receiver[:1].isupper() or qualified):
        members = {k: c for k, c in named.items() if owner(c).split(".")[-1] == receiver}
        if members:
            keep = members
        elif not qualified and language in METHOD_ONLY_MEMBERS:
            keep = {k: c for k, c in named.items() if owner(c)}
    elif receiver:
        if language in METHOD_ONLY_MEMBERS or language in {
            "python",
            "javascript",
            "jsx",
            "typescript",
            "tsx",
        }:
            keep = {k: c for k, c in named.items() if owner(c)}
    else:
        free = {k: c for k, c in named.items() if not owner(c)}
        own = {
            k: c
            for k, c in named.items()
            if owner(c) and owner(c).split(".")[-1] == enclosing_class.split(".")[-1]
        }
        if language in BARE_IS_FREE:
            keep = free
        elif free or own:
            keep = {**free, **own}
    return {
        key: candidate
        for key, candidate in candidates.items()
        if candidate.basis not in NAME_BASES or key in keep
    }


def _typed_definition(
    intel, name, target_name, side, from_path, line, column, timeout, path_glob="*"
):
    """Definitions from a type-aware resolver, or None to fall back to name matching."""
    language = intel.classify_file(from_path, side).language
    if not resolver_for(language):
        return None
    search = intel.workspace.search(target_name, side, timeout=timeout, words=True)
    extra = sorted({match.path for match in search.items})[:MAX_TYPED_FILES]
    site = {"line": line, "column": column, "name": target_name}
    bound, shortfalls = precise_calls(
        intel, side, {from_path: [site]}, extra_files=extra, timeout=max(timeout, 30)
    )
    symbols = bound.get((from_path, line, column))
    if symbols is None:
        return None
    symbols = tuple(s for s in symbols if fnmatch.fnmatchcase(s.location.path, path_glob))
    return QueryResult[DefinitionCandidate](
        items=tuple(
            DefinitionCandidate(symbol=symbol, confidence="bound", basis="type-aware resolution")
            for symbol in symbols
        ),
        scope=f"type-aware binding at {side}:{from_path}:{line}"
        + ("" if symbols else "; bound to no repository definition (external, local or field)"),
        searched_files=1 + len(extra),
        **shortfalls.fields(),
    )


def resolve(
    intel,
    name: str,
    side: str = "head",
    *,
    from_path: str | None = None,
    line: int | None = None,
    column: int = 0,
    path_glob: str = "*",
    max_files: int = 1000,
    timeout: float = 10,
    within: tuple[str, ...] | None = None,
    precise: bool = True,
) -> QueryResult[DefinitionCandidate]:
    """Definition candidates for a usage; within limits the name-match fallback to those
    paths instead of a repository-wide search (callers that only care about known files)."""
    started = time.monotonic()
    target_name = MEMBER_SEPARATORS.split(name)[-1]
    roots = name.split(".")
    candidates = {}
    found = Shortfalls()
    if precise and from_path and line:
        typed = _typed_definition(
            intel, name, target_name, side, from_path, line, column, timeout, path_glob
        )
        if typed is not None:
            return typed
        language = intel.classify_file(from_path, side).language
        if resolver_for(language):
            found.gaps.append(
                Gap(kind="name_only", detail=f"{language}: this call was not bound by type")
            )
    scanned = set()
    bound_targets = []
    local_scope = ""
    shadowed = True
    if from_path:
        try:
            parsed = intel.parsed(from_path, side)
            if parsed["language"] not in BOUND_LANGUAGES and not resolver_for(parsed["language"]):
                found.gaps.append(
                    Gap(
                        kind="name_only",
                        detail=f"{parsed['language']}: imports and calls are matched by name",
                    )
                )
            class_scopes = {
                symbol["qualified_name"]
                for symbol in parsed["symbols"]
                if symbol["kind"] == "class"
            }
            symbol = intel.enclosing_symbol(from_path, line, side, column) if line else None
            local_scope = symbol.qualified_name if symbol else ""
            if line and parsed["language"] in BOUND_LANGUAGES:
                shadowed = _shadowed(intel, from_path, side, roots[0], line)
            for binding in parsed["imports"]:
                if binding["local_name"] != roots[0] or not _visible(binding["scope"], local_scope):
                    continue
                if (
                    parsed["language"] == "python"
                    and binding["scope"] in class_scopes
                    and binding["scope"] != local_scope
                ):
                    continue
                imported = binding["imported_name"]
                imported_name = imported if len(roots) == 1 else target_name
                modules = module_paths(intel, from_path, binding["module"], side)
                if imported is None and len(roots) == 1:
                    continue
                if len(roots) > 1:
                    if imported is None:
                        prefix = binding["local_name"]
                        if (
                            parsed["language"] == "python"
                            and prefix == binding["module"].split(".")[0]
                        ):
                            prefix = binding["module"]
                        if ".".join(roots[:-1]) != prefix:
                            continue
                    elif parsed["language"] == "python" and len(roots) == 2:
                        module = binding["module"]
                        separator = "" if module.endswith(".") else "."
                        modules = module_paths(
                            intel, from_path, module + separator + imported, side
                        )
                    else:
                        continue
                for path in modules:
                    if not fnmatch.fnmatchcase(path, path_glob):
                        continue
                    result = intel.outline(path, side)
                    scanned.add(path)
                    found.absorb(result)
                    for definition in result.items:
                        if (
                            definition.name != imported_name
                            and imported_name not in definition.export_names
                        ) or definition.parent_id:
                            continue
                        is_bound = line is not None and not shadowed and len(modules) == 1
                        candidate = DefinitionCandidate(
                            symbol=definition,
                            confidence="bound" if is_bound else "candidate",
                            basis=f"import binding {binding['local_name']} from {binding['module']}",
                        )
                        candidates[definition.id] = candidate
                        if is_bound:
                            bound_targets.append(candidate)
            result = intel.outline(from_path, side)
            scanned.add(from_path)
            for definition in result.items:
                if definition.name != target_name or not fnmatch.fnmatchcase(from_path, path_glob):
                    continue
                parent = definition.qualified_name.rpartition(".")[0]
                lexical = _visible(parent, local_scope)
                if (
                    parsed["language"] == "python"
                    and parent in class_scopes
                    and parent != local_scope
                ):
                    lexical = False
                if definition.kind == "method":
                    lexical = False
                is_bound = line is not None and len(roots) == 1 and not shadowed and lexical
                candidate = DefinitionCandidate(
                    symbol=definition,
                    confidence="bound" if is_bound else "candidate",
                    basis="lexically visible definition"
                    if is_bound
                    else "same-file name candidate",
                )
                candidates[definition.id] = candidate
                if is_bound:
                    bound_targets.append(candidate)
        except ReviewCoreError as exc:
            found.error(exc, from_path)
    if len(bound_targets) == 1:
        return QueryResult[DefinitionCandidate](
            items=tuple(bound_targets),
            scope=f"binding at {side}:{from_path}:{line}",
            searched_files=len(scanned),
            **found.fields(),
        )
    if len(bound_targets) > 1:
        candidates = {
            key: candidate.model_copy(update={"confidence": "candidate"})
            for key, candidate in candidates.items()
        }
    if within is None:
        search = intel.workspace.search(target_name, side, path_glob, timeout=max(0.01, timeout))
        found.absorb(search)
        paths = sorted({item.path for item in search.items})
    else:
        tree = intel.workspace.tree(side)
        paths = sorted(
            path for path in set(within) if path in tree and fnmatch.fnmatchcase(path, path_glob)
        )
    for path in paths:
        if path in scanned:
            continue
        info = intel.classify_file(path, side)
        if info.unindexed and info.language in OUTLINE_LANGUAGES:
            # A skipped file may hold the definition: say so instead of reporting completeness.
            found.gaps.append(
                Gap(kind="unindexed", path=path, detail=f"definitions unknown: {info.unindexed}")
            )
            continue
        if not info.outline_available:
            continue
        if len(scanned) >= max_files or time.monotonic() - started >= timeout:
            found.limits.append(f"definition search budget ({max_files} files, {timeout:g}s)")
            break
        scanned.add(path)
        result = intel.outline(path, side)
        found.absorb(result)
        for definition in result.items:
            if definition.name == target_name and definition.id not in candidates:
                candidates[definition.id] = DefinitionCandidate(
                    symbol=definition,
                    confidence="candidate",
                    basis="name match in repository",
                )
    if from_path:
        candidates = _shape_filter(intel, candidates, name, side, from_path, local_scope)
    ordered = sorted(
        candidates.values(),
        key=lambda candidate: (
            candidate.symbol.location.path != from_path,
            not candidate.basis.startswith("import binding"),
            from_path is not None
            and PurePosixPath(candidate.symbol.location.path).parent
            != PurePosixPath(from_path).parent,
            candidate.symbol.location.path,
            candidate.symbol.location.start_line,
            candidate.symbol.id,
        ),
    )
    return QueryResult[DefinitionCandidate](
        items=tuple(ordered),
        **found.fields(),
        scope=f"definition candidates in supported languages for {name} on {side}; paths {path_glob}",
        searched_files=len(scanned),
    )


def _candidate_paths(intel, target, side: str, path_glob: str, timeout: float):
    """Files that can refer to target: one word search for its names and module stem.

    Aliased imports still name the target or its module, so the prefilter keeps them;
    default and namespace imports are caught through the module stem.
    """
    stem = PurePosixPath(target.location.path).stem
    names = {target.name, *target.export_names, stem} - {"default", "index", "__init__", ""}
    search = intel.workspace.search(sorted(names), side, path_glob, timeout=timeout, words=True)
    paths = {match.path for match in search.items} | {target.location.path}
    return sorted(paths & intel.workspace.tree(side).keys()), search


def _same_symbol(symbol, target) -> bool:
    return symbol.id == target.id or (
        symbol.location.path == target.location.path
        and symbol.qualified_name == target.qualified_name
    )


def _typed_calls(intel, target, side, direction, paths, path_glob, timeout, found):
    """Batch-resolve the relevant calls of resolver languages in one helper run per language."""
    if target.location.side != side:
        return {}  # the target does not exist here (e.g. deleted): only names can find uses
    sites = {}
    for path in paths:
        if not fnmatch.fnmatchcase(path, path_glob):
            continue
        if not resolver_for(intel.classify_file(path, side).language):
            continue
        try:
            calls = intel.parsed(path, side)["calls"]
        except ReviewCoreError:
            continue
        if direction == "callers":
            calls = [call for call in calls if call["name"] == target.name]
        else:
            calls = [
                call
                for call in calls
                if (owner := intel.enclosing_symbol(path, call["line"], side, call["column"]))
                and owner.id == target.id
            ]
        if calls:
            sites[path] = calls
    if not sites:
        return {}
    extra = [*paths, target.location.path] if target.location.side == side else list(paths)
    bound, shortfalls = precise_calls(
        intel, side, sites, extra_files=extra[:MAX_TYPED_FILES], timeout=max(timeout, 30)
    )
    found.gaps.extend(shortfalls.gaps)
    found.issues.extend(shortfalls.issues)
    unbound = sum(
        1
        for path, calls in sites.items()
        for call in calls
        if bound.get((path, call["line"], call["column"])) is None
    )
    if unbound:
        total = sum(len(calls) for calls in sites.values())
        found.gaps.append(
            Gap(
                kind="name_only",
                detail=f"{unbound} of {total} call sites not bound by type, matched by name",
            )
        )
    return bound


def references(
    intel,
    identifier: str,
    side: str = "head",
    *,
    symbol_side: str | None = None,
    direction: str = "callers",
    scope: str = "all",
    path_glob: str = "*",
    max_files: int = 1000,
    timeout: float = 10,
) -> QueryResult[Reference]:
    if direction not in {"callers", "callees", "importers"} or scope not in {"all", "tests"}:
        raise ReviewCoreError("Invalid reference direction or scope")
    target = intel.symbol(identifier, symbol_side or side)
    matches = []
    found = Shortfalls()
    started = time.monotonic()
    scanned = 0
    if direction == "callees":
        if target.location.side != side:
            raise ReviewCoreError("Callee query must read the symbol on its own side")
        paths = [target.location.path]
    else:
        paths, search = _candidate_paths(intel, target, side, path_glob, timeout)
        found.absorb(search)
    typed = {}
    if direction != "importers":
        typed = _typed_calls(intel, target, side, direction, paths, path_glob, timeout, found)
    for path in paths:
        if not fnmatch.fnmatchcase(path, path_glob):
            continue
        info = intel.classify_file(path, side)
        if scope == "tests" and info.kind != "test":
            continue
        if scanned >= max_files or time.monotonic() - started >= timeout:
            found.limits.append(f"reference search budget ({max_files} files, {timeout:g}s)")
            break
        scanned += 1
        try:
            parsed = intel.parsed(path, side)
            content = source_lines(intel.workspace.read_file(path, side).text)
        except ReviewCoreError as exc:
            if info.kind in {"source", "test", "other"}:
                fallback = intel.workspace.search(
                    target.name, side, path, timeout=max(0.01, timeout), words=True
                )
                found.absorb(fallback)
                if fallback.items and intel.expects_symbols(path, side):
                    # Only a code file that mentions the target makes the gap matter.
                    found.error(exc, path)
                for match in fallback.items:
                    matches.append(
                        Reference(
                            location=intel.location(path, match.line, side),
                            context=match.text,
                            target_id=target.id,
                            relation="text",
                            confidence="candidate",
                            basis="text fallback; binding and call syntax are unknown",
                        )
                    )
            continue
        language = parsed["language"]
        if language not in BOUND_LANGUAGES and not resolver_for(language):
            found.gaps.append(
                Gap(kind="name_only", detail=f"{language}: imports and calls are matched by name")
            )
        if direction == "importers":
            for binding in parsed["imports"]:
                modules = module_paths(
                    intel, path, binding["module"], side, include_missing=target.location.path
                )
                if target.location.path in modules:
                    matches.append(
                        Reference(
                            location=intel.location(path, binding["line"], side),
                            context=content[binding["line"] - 1],
                            target_id=target.id,
                            relation="import",
                            confidence="bound"
                            if len(modules) == 1
                            and target.location.path in intel.workspace.tree(side)
                            else "candidate",
                            basis=f"module import {binding['module']}",
                        )
                    )
            continue
        imported_names = {
            binding["local_name"]
            for binding in parsed["imports"]
            if binding["imported_name"] == target.name
            or binding["imported_name"] in target.export_names
        }
        for call in parsed["calls"]:
            owner = intel.enclosing_symbol(path, call["line"], side, call["column"])
            if direction == "callees" and (owner is None or owner.id != target.id):
                continue
            if direction == "callers" and call["name"] not in imported_names | {target.name}:
                continue
            bound = typed.get((path, call["line"], call["column"]))
            if bound is not None:
                # Type-aware: a caller is kept only if the call binds to the target itself.
                for symbol in bound:
                    if direction == "callers" and not _same_symbol(symbol, target):
                        continue
                    matches.append(
                        Reference(
                            location=intel.location(path, call["line"], side, call["column"]),
                            context=content[call["line"] - 1],
                            target_id=symbol.id,
                            relation="call",
                            confidence="bound",
                            basis="type-aware resolution",
                        )
                    )
                continue
            result = resolve(
                intel,
                call["expression"],
                side,
                from_path=path,
                line=call["line"],
                column=call["column"],
                max_files=max_files,
                timeout=max(0.01, timeout - (time.monotonic() - started)),
                # A caller only needs to know whether the call binds to the target.
                within=None if direction == "callees" else (target.location.path, path),
                precise=False,
            )
            found.absorb(result)
            if direction == "callees":
                definitions = result.items or (None,)
            else:
                definitions = tuple(
                    candidate
                    for candidate in result.items
                    if candidate.symbol.location.path == target.location.path
                    and candidate.symbol.qualified_name == target.qualified_name
                )
                if not definitions and not any(
                    candidate.confidence == "bound" for candidate in result.items
                ):
                    definitions = (None,)
            for definition in definitions:
                matches.append(
                    Reference(
                        location=intel.location(path, call["line"], side, call["column"]),
                        context=content[call["line"] - 1],
                        target_id=definition.symbol.id
                        if definition
                        else (target.id if direction == "callers" else None),
                        relation="call",
                        confidence=definition.confidence if definition else "candidate",
                        basis=definition.basis
                        if definition
                        else "name/alias match; target is unresolved",
                    )
                )
    return QueryResult[Reference](
        items=tuple(matches),
        searched_files=scanned,
        scope=f"{direction} candidates, {side}:{path_glob}, scope={scope}",
        precision="mixed" if any(match.relation == "text" for match in matches) else "syntactic",
        **found.fields(),
    )
