from __future__ import annotations

import ast
import importlib.metadata
import re
from collections import OrderedDict
from pathlib import PurePosixPath

from ast_grep_py import SgRoot

from review_core.common import Gap, GapError, stable_id
from review_core.storage import Store

from .models import NormalizedCode

EXTENSIONS = {
    ".py": "python",
    ".pyi": "python",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "jsx",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".go": "go",
    ".java": "java",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c++": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".h++": "cpp",
    ".ipp": "cpp",
    ".inl": "cpp",
    ".tcc": "cpp",
    ".mts": "typescript",
    ".cts": "typescript",
    ".cs": "csharp",
    ".php": "php",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".html": "html",
    ".css": "css",
    ".sh": "bash",
}
SYMBOL_KINDS = {
    "function_definition": "function",
    "function_declaration": "function",
    "function_item": "function",
    "method_definition": "method",
    "method_declaration": "method",
    "constructor_declaration": "method",
    "class_definition": "class",
    "class_declaration": "class",
    "class_specifier": "class",
    "interface_declaration": "interface",
    "struct_item": "struct",
    "struct_specifier": "struct",
    "enum_item": "enum",
    "enum_declaration": "enum",
    "trait_item": "trait",
    "impl_item": "impl",
    "type_spec": "type",
    "type_alias": "type",
    "type_alias_declaration": "type",
    "union_specifier": "struct",
    "annotation_type_declaration": "interface",
    "annotation_type_element_declaration": "method",
    "struct_declaration": "struct",
    "record_declaration": "class",
    "trait_declaration": "trait",
    "property_declaration": "property",
    "local_function_statement": "function",
}
OUTLINE_LANGUAGES = {
    "python",
    "javascript",
    "jsx",
    "typescript",
    "tsx",
    "go",
    "java",
    "rust",
    "c",
    "cpp",
    "csharp",
    "php",
}
CALL_KINDS = {
    "call",
    "call_expression",
    "method_invocation",
    "object_creation_expression",
    "invocation_expression",
    "function_call_expression",
    "member_call_expression",
    "nullsafe_member_call_expression",
    "scoped_call_expression",
}
# Data, markup and prose: no symbols are expected, so their absence is not an analysis gap.
DATA_LANGUAGES = {"json", "yaml", "css", "html"}
# Programming languages without a symbol extractor here: their absence is a real gap.
CODE_SUFFIXES = {
    ".svelte",
    ".vue",
    ".m",
    ".mm",
    ".rb",
    ".kt",
    ".kts",
    ".swift",
    ".scala",
    ".lua",
    ".ex",
    ".exs",
    ".dart",
    ".r",
    ".pl",
    ".pm",
    ".tcl",
    ".sql",
    ".groovy",
    ".gradle",
    ".ps1",
    ".zsh",
    ".fish",
    ".clj",
    ".erl",
    ".hs",
    ".ml",
    ".fs",
    ".jl",
    ".zig",
    ".nim",
    ".sol",
    ".cu",
    ".cuh",
    ".proto",
}
CALLEE_NAME_KINDS = {"name", "qualified_name", "identifier"}
MEMBER_SEPARATORS = re.compile(r"::|\?->|->|\.|\\")
# Zero-width tokens Tree-sitter inserts when it recovers from a missing delimiter.
MISSING_KINDS = {"(", ")", "[", "]", "{", "}", ":", ";", "identifier", "type_identifier"}
# A .h file is C++ when it uses constructs C does not have.
CPP_HEADER = re.compile(r"\b(?:class|namespace|template|public:|private:|protected:)\b|::")
IMPORT_KINDS = {
    "import_statement",
    "import_from_statement",
    "import_declaration",
    "use_declaration",
    "using_directive",
    "namespace_use_declaration",
}
SYNTAX_VERSION = "syntax-v11-" + importlib.metadata.version("ast-grep-py")


def walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children()))


def node_key(node):
    position = node.range()
    return node.kind(), position.start.index, position.end.index


def has_syntax_errors(root) -> bool:
    if root.find(kind="ERROR") is not None:
        return True
    # Tree-sitter also recovers with zero-width missing tokens, without an ERROR node.
    return any(_missing(node) for node in walk(root))


def _missing(node) -> bool:
    return node.kind() in MISSING_KINDS and node.is_leaf() and not node.text()


def language_for(path: str, text: str = "") -> str | None:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".h":
        return "cpp" if CPP_HEADER.search(text) else "c"
    language = EXTENSIONS.get(suffix)
    if language:
        return language
    first = text.splitlines()[0] if text else ""
    if first.startswith("#!"):
        for marker, name in (("python", "python"), ("node", "javascript"), ("bash", "bash")):
            if marker in first:
                return name
    return None


def normalize(code: str, language: str | None) -> NormalizedCode:
    if language is None or len(code.encode("utf-8")) > 2_000_000:
        return NormalizedCode(
            digest=stable_id(code), tokens=(code,), precision="text", complete=False
        )
    try:
        root = SgRoot(code, language).root()
    except ValueError:
        return NormalizedCode(
            digest=stable_id(code), tokens=(code,), precision="text", complete=False
        )
    if has_syntax_errors(root):
        return NormalizedCode(
            digest=stable_id(code), tokens=(code,), precision="text", complete=False
        )
    tokens = syntax_tokens(root)
    return NormalizedCode(
        digest=stable_id([SYNTAX_VERSION, language, tokens]),
        tokens=tuple(tokens),
        precision="syntactic",
        complete=True,
    )


def syntax_tokens(root) -> list[str]:
    # Encode tree boundaries, not just leaf text: indentation changes can move statements.
    tokens = []
    stack = [(root, False)]
    while stack:
        node, closing = stack.pop()
        if "comment" in node.kind():
            continue
        if closing:
            tokens.append(")")
            continue
        kind = node.kind()
        tokens.append("(" + kind)
        if _literal(kind):
            # Whitespace inside a string literal is content, not formatting.
            tokens.extend((node.text(), ")"))
            continue
        children = node.children()
        if not children:
            tokens.append(node.text())
        stack.append((node, True))
        stack.extend((child, False) for child in reversed(children))
    return tokens


LITERAL_KINDS = frozenset({"character_literal", "char_literal", "rune_literal", "heredoc_body"})


C_TYPE_SPECIFIERS = {"class_specifier", "struct_specifier", "union_specifier", "enum_specifier"}
# Declarator wrappers whose inner declarator is a plain child, not a declarator field.
DECLARATOR_WRAPPERS = {
    "reference_declarator",
    "parenthesized_declarator",
    "attributed_declarator",
    "abstract_reference_declarator",
}


def _declarator_name(declarator):
    """The name inside a C/C++ declarator chain: pointer, reference, function, array..."""
    while declarator is not None:
        inner = declarator.field("declarator")
        if inner is None and declarator.kind() in DECLARATOR_WRAPPERS:
            inner = next((c for c in declarator.children() if c.is_named()), None)
        if inner is None:
            return declarator
        declarator = inner
    return None


def _strip_templates(expression: str) -> str:
    """Remove template argument lists: std::forward<Arg> -> std::forward."""
    out, depth = [], 0
    for index, char in enumerate(expression):
        if char == "<" and (
            depth or (index and (expression[index - 1].isalnum() or expression[index - 1] in "_>"))
        ):
            depth += 1
        elif char == ">" and depth and not (index and expression[index - 1] == "-"):
            depth -= 1
        elif not depth:
            out.append(char)
    return "".join(out) if depth == 0 else expression


def _subtract(ranges: list[list[int]], holes: list[list[int]]) -> list[list[int]]:
    """Line ranges minus the holes (both sorted and merged)."""
    out = []
    for start, end in ranges:
        for hole_start, hole_end in holes:
            if hole_end < start or hole_start > end:
                continue
            if hole_start > start:
                out.append([start, hole_start - 1])
            start = hole_end + 1
            if start > end:
                break
        if start <= end:
            out.append([start, end])
    return out


def _merged(ranges: list[list[int]]) -> list[list[int]]:
    """Error line ranges, sorted and merged where they overlap or touch."""
    merged = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _literal(kind: str) -> bool:
    return "string" in kind or "template" in kind or kind in LITERAL_KINDS


class Syntax:
    def __init__(self, store: Store):
        self.store = store
        self._roots = OrderedDict()

    def root(self, blob_hash: str, language: str, text: str):
        if len(text.encode("utf-8")) > 2_000_000:
            raise GapError(
                Gap(
                    kind="unindexed", detail="exceeds the 2 MB syntax parsing limit; use text tools"
                )
            )
        key = (blob_hash, language)
        if key not in self._roots:
            self._roots[key] = SgRoot(text, language).root()
            if len(self._roots) > 16:
                self._roots.popitem(last=False)
        self._roots.move_to_end(key)
        return self._roots[key]

    def parse(self, blob_hash: str, language: str, text: str) -> dict:
        key = stable_id([SYNTAX_VERSION, blob_hash, language])
        cached = self.store.get("syntax", key)
        if cached is not None:
            if "gap" in cached:
                raise GapError(Gap.model_validate(cached["gap"]))
            return cached
        if language not in OUTLINE_LANGUAGES:
            raise GapError(Gap(kind="unsupported", detail=f"no symbol extractor for {language}"))
        root = self.root(blob_hash, language, text)
        symbols, calls, imports, errors, recovered = [], [], [], [], []
        classes = set()
        # Depth-first with the enclosing scope carried along. Inside an ERROR node only
        # well-formed definitions are trusted: Tree-sitter often wraps the rest of a file in
        # one ERROR after a construct it does not know, yet keeps intact functions inside.
        stack = [(root, "", False)]
        while stack:
            node, parent_scope, broken = stack.pop()
            node_kind = node.kind()
            position = node.range()
            if node_kind == "ERROR" or _missing(node):
                errors.append([position.start.line + 1, position.end.line + 1])
                broken = True
            elif broken and node_kind in SYMBOL_KINDS and not has_syntax_errors(node):
                broken = False
                recovered.append([position.start.line + 1, position.end.line + 1])
            scope = parent_scope
            if not broken:
                symbol = self._symbol(node, language, parent_scope, classes, symbols)
                if symbol:
                    symbols.append(symbol)
                    scope = symbol["qualified_name"]
                    if symbol["kind"] in {"class", "interface", "struct", "trait"}:
                        classes.add(scope)
                call = self._call(node, parent_scope) if node_kind in CALL_KINDS else None
                if call:
                    calls.append(call)
                if node_kind in IMPORT_KINDS:
                    imports.extend(self._imports(node, language, parent_scope))
            stack.extend((child, scope, broken) for child in reversed(node.children()))
        result = dict(
            symbols=symbols,
            calls=calls,
            imports=imports,
            language=language,
            errors=_subtract(_merged(errors), _merged(recovered)),
        )
        self.store.put("syntax", key, result)
        return result

    @staticmethod
    def _symbol(node, language: str, parent_scope: str, classes: set, symbols: list) -> dict | None:
        node_kind = node.kind()
        kind = SYMBOL_KINDS.get(node_kind)
        name_node = node.field("name")
        anonymous_default = False
        if node_kind in ("arrow_function", "function_expression", "generator_function"):
            parent = node.parent()
            if parent and parent.kind() in (
                "variable_declarator",
                "pair",
                "public_field_definition",
            ):
                name_node = parent.field("name") or parent.field("key")
                kind = "function"
            elif parent and parent.kind() == "export_statement":
                kind = "function"
                anonymous_default = True
        qualifiers = []
        if kind and language in ("c", "cpp") and node_kind in C_TYPE_SPECIFIERS:
            if node.field("body") is None:
                return None  # `struct foo *p` refers to a type, it does not define one
            parent = node.parent()
            if name_node is None and parent is not None and parent.kind() == "type_definition":
                name_node = parent.field("declarator")  # typedef struct { ... } Name;
        if kind and name_node is None and language in ("c", "cpp"):
            name_node = _declarator_name(node.field("declarator"))
        if kind and name_node is not None and language in ("c", "cpp"):
            # Out-of-class definitions (Foo::bar, class A::B) are named in their scope.
            while name_node is not None and name_node.kind() == "qualified_identifier":
                if name_node.field("scope"):
                    qualifiers.append(name_node.field("scope").text())
                name_node = name_node.field("name")
        if node_kind == "impl_item":
            name_node = node.field("type")
        if not kind or not (name_node or anonymous_default):
            return None
        position = node.range()
        name = name_node.text() if name_node else "default"
        prefix = ".".join(part for part in (parent_scope, *qualifiers) if part)
        receiver = node.field("receiver")
        if receiver:
            types = receiver.find_all(kind="type_identifier")
            if types:
                prefix = types[-1].text()
        qualified = f"{prefix}.{name}" if prefix else name
        body = node.field("body")
        signature = node.text()
        if body:
            signature = node.text()[: body.range().start.index - position.start.index].rstrip()
        container = node.parent()
        start_line = position.start.line + 1
        start_column = position.start.column
        if container and container.kind() == "decorated_definition":
            start_line = container.range().start.line + 1
            start_column = container.range().start.column
            signature = container.text().split(node.text(), 1)[0] + signature
        visibility = "unknown"
        export_names = []
        head = signature.split("(", 1)[0]
        if language == "python":
            visibility = "private" if name.startswith("_") else "public"
            if parent_scope in classes and kind == "function":
                kind = "method"
        elif language == "go":
            visibility = "public" if name[:1].isupper() else "private"
        elif language in {"javascript", "jsx", "typescript", "tsx"}:
            exported = any(a.kind() == "export_statement" for a in node.ancestors())
            visibility = "public" if exported else "unknown"
            if exported and not parent_scope:
                wrapper = next(a for a in node.ancestors() if a.kind() == "export_statement")
                is_default = any(child.kind() == "default" for child in wrapper.children())
                export_names = ["default" if is_default else name]
            if "private " in signature or name.startswith("#"):
                visibility = "private"
        elif language == "java":
            if "private " in head:
                visibility = "private"
            elif "public " in head or "protected " in head:
                visibility = "public"
        elif language == "csharp":
            if "private " in head:
                visibility = "private"
            elif any(word in head for word in ("public ", "protected ", "internal ")):
                visibility = "public"
            elif kind in {"method", "property"} and parent_scope:
                visibility = "private"  # C# members default to private
        elif language == "php":
            visibility = "private" if "private " in head else "public"
        return dict(
            name=name,
            qualified_name=qualified,
            kind=kind,
            signature=signature,
            visibility=visibility,
            parent=parent_scope,
            body_hash=stable_id(syntax_tokens(body)) if body else stable_id(None),
            export_names=export_names,
            start_line=start_line,
            start_column=start_column,
            end_line=position.end.line + (1 if position.end.column else 0),
            end_column=position.end.column,
        )

    @staticmethod
    def _call(node, scope: str) -> dict | None:
        node_kind = node.kind()
        function = node.field("function") or node.field("name") or node.field("type")
        if function is None and node_kind == "object_creation_expression":
            function = next(
                (child for child in node.children() if child.kind() in CALLEE_NAME_KINDS), None
            )
        if function is None:
            return None
        expression = _strip_templates(function.text())
        receiver = node.field("object") or node.field("scope")
        if receiver is not None and node.field("function") is None:
            # Java method_invocation, PHP member/scoped calls: receiver and name are separate.
            expression = receiver.text() + "." + expression
        name = MEMBER_SEPARATORS.split(expression)[-1].strip()
        if not name:
            return None
        position = node.range()
        return dict(
            name=name,
            expression=expression,
            line=position.start.line + 1,
            column=position.start.column,
            scope=scope,
        )

    @staticmethod
    def _imports(node, language: str, scope: str) -> list[dict]:
        line = node.range().start.line + 1
        result = []
        if language == "python":
            try:
                statement = ast.parse(node.text()).body[0]
            except SyntaxError:
                return []
            if isinstance(statement, ast.ImportFrom):
                module = "." * statement.level + (statement.module or "")
                for alias in statement.names:
                    result.append(
                        dict(
                            local_name=alias.asname or alias.name,
                            module=module,
                            imported_name=alias.name,
                            line=line,
                            scope=scope,
                        )
                    )
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    result.append(
                        dict(
                            local_name=alias.asname or alias.name.split(".")[0],
                            module=alias.name,
                            imported_name=None,
                            line=line,
                            scope=scope,
                        )
                    )
        elif language in {"javascript", "jsx", "typescript", "tsx"}:
            source = node.field("source")
            if source is None:
                return []
            module = source.text()[1:-1]
            for child in walk(node):
                if child.kind() == "import_specifier":
                    name = child.field("name")
                    alias = child.field("alias") or name
                    if name and alias:
                        result.append(
                            dict(
                                local_name=alias.text(),
                                module=module,
                                imported_name=name.text(),
                                line=line,
                                scope=scope,
                            )
                        )
                elif child.kind() == "namespace_import":
                    names = child.find_all(kind="identifier")
                    if names:
                        result.append(
                            dict(
                                local_name=names[-1].text(),
                                module=module,
                                imported_name=None,
                                line=line,
                                scope=scope,
                            )
                        )
                elif child.kind() == "import_clause":
                    for name in child.children():
                        if name.kind() == "identifier":
                            result.append(
                                dict(
                                    local_name=name.text(),
                                    module=module,
                                    imported_name="default",
                                    line=line,
                                    scope=scope,
                                )
                            )
            if not result:
                result.append(
                    dict(local_name="", module=module, imported_name=None, line=line, scope=scope)
                )
        else:
            # Keep module imports as syntactic candidates without inventing language resolution.
            result.append(
                dict(local_name="", module=node.text(), imported_name=None, line=line, scope=scope)
            )
        return result
