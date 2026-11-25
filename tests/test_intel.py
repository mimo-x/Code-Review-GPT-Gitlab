from __future__ import annotations

import re
from collections import Counter

import pytest

from review_core.intel import CodeIntel
from review_core.intel.resolvers import resolver_for
from review_core.intel.syntax import normalize
from review_core.intel.tools import Tools
from review_core.workspace import Workspace


def test_outline_nested_symbols_decorators_and_unicode(repository, tmp_path):
    source = "@decorator\ndef 中文(x):\n    return x\n\ndef next_fn():\n    return 2\n\nclass C:\n    def get(self):\n        return next_fn()\n"
    repository.write("sample.py", source)
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    symbols = intel.outline("sample.py").items
    assert [symbol.qualified_name for symbol in symbols] == ["中文", "next_fn", "C", "C.get"]
    assert symbols[0].signature == "@decorator\ndef 中文(x):"
    assert symbols[0].location.start_line == 1
    assert intel.enclosing_symbol("sample.py", 9).qualified_name == "C.get"
    assert intel.read_symbol("sample.py::中文").text.startswith("@decorator")


@pytest.mark.parametrize(
    ("path", "source", "expected"),
    [
        (
            "a.ts",
            "export class C { get(x: number): number { return x; } }\nexport const f = (x: number) => x;",
            ["C", "C.get", "f"],
        ),
        ("a.js", "export function f(x) { return x; }", ["f"]),
        ("a.go", 'package a\nfunc (u *User) Get(x int) string { return "ok" }', ["User.Get"]),
        ("A.java", 'class A { public String get(int x) { return "ok"; } }', ["A", "A.get"]),
        ("a.rs", "fn fetch(x: i32) -> i32 { x }", ["fetch"]),
        ("a.c", "int fetch(int x) { return x; }", ["fetch"]),
    ],
)
def test_real_parsers_extract_symbols(repository, tmp_path, path, source, expected):
    repository.write(path, source)
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.outline(path)
    assert result.complete, result.issues
    assert [symbol.qualified_name for symbol in result.items] == expected


def test_alias_references_and_test_relationships(reviewed):
    _, _, intel = reviewed
    definitions = intel.resolve("fetch", from_path="api.py", line=4, column=11)
    assert len(definitions.items) == 1
    assert definitions.items[0].confidence == "bound"
    assert definitions.items[0].symbol.name == "get_user"
    references = intel.references("users.py::get_user")
    assert {ref.location.path for ref in references.items} == {"api.py", "tests/test_users.py"}
    tests = intel.references("users.py::get_user", scope="tests")
    assert {ref.location.path for ref in tests.items} == {"tests/test_users.py"}
    graph = intel.change_graph()
    assert graph.complete
    assert any(
        edge.kind == "test_reference" and edge.confidence == "bound" for edge in graph.relations
    )
    assert all(edge.location.side in {"base", "head"} for edge in graph.relations if edge.location)


def test_shadowed_import_remains_candidate(repository, tmp_path, monkeypatch):
    repository.write("users.py", "def get_user(id):\n    return id\n")
    repository.write(
        "api.py", "from users import get_user\ndef api(get_user):\n    return get_user(3)\n"
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    if resolver_for("python"):
        # A type checker sees the parameter: the call binds to no repository definition.
        typed = intel.resolve("get_user", from_path="api.py", line=3, column=11)
        assert typed.items == () and "local" in typed.scope
    monkeypatch.setenv("REVIEW_CORE_RESOLVERS", "off")
    result = CodeIntel(intel.workspace).resolve("get_user", from_path="api.py", line=3, column=11)
    assert result.items
    assert all(item.confidence == "candidate" for item in result.items)


def test_deleted_symbol_can_be_searched_on_head(repository, tmp_path):
    repository.write("users.py", "def get_user(id):\n    return id\n")
    repository.write("api.py", "from users import get_user\ndef api():\n    return get_user(3)\n")
    base = repository.commit()
    (repository.path / "users.py").unlink()
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    result = intel.references("users.py::get_user", symbol_side="base", side="head")
    assert len(result.items) == 1
    assert result.items[0].confidence == "candidate"
    importers = intel.references(
        "users.py::get_user", symbol_side="base", side="head", direction="importers"
    )
    assert len(importers.items) == 1


def test_change_ownership_uses_changed_lines_not_hunk_context(repository, tmp_path):
    repository.write("a.py", "def first():\n    return 1\n\ndef second():\n    return 2\n")
    base = repository.commit()
    repository.write("a.py", "def first():\n    return 3\n\ndef second():\n    return 2\n")
    repository.write("unknown.xyz", "changed contents\n")
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    intel = CodeIntel(workspace)
    units = intel.changed_symbols()
    assert any(unit.head_symbol and unit.head_symbol.name == "first" for unit in units)
    assert not any(unit.head_symbol and unit.head_symbol.name == "second" for unit in units)
    assert any(unit.new_path == "unknown.xyz" and unit.precision == "text" for unit in units)
    expected = Counter(
        line.id
        for change in workspace.snapshot.changes
        for hunk in change.hunks
        for line in hunk.lines
        if line.kind != "context"
    )
    assert Counter(line.id for unit in units for line in unit.lines) == expected


def test_ast_normalization_preserves_indentation_and_strings():
    first = "if ok:\n    call()\nfinish()\n"
    formatted = "if ok:  # comment\n    call( )\nfinish()\n"
    different = "if ok:\n    call()\n    finish()\n"
    assert normalize(first, "python").digest == normalize(formatted, "python").digest
    assert normalize(first, "python").digest != normalize(different, "python").digest
    assert normalize('x="a b"', "python").digest != normalize('x="ab"', "python").digest


def test_structural_search_real_ast_and_errors(reviewed):
    _, _, intel = reviewed
    result = intel.structural_match("get_user($ARG)", "python")
    assert len(result.items) == 1
    assert result.items[0].bindings["ARG"] == "None"
    response = Tools(intel).call("structural_search", pattern={"nonsense": "x"}, language="python")
    assert response.error
    assert not response.complete


def test_tools_bound_output_persist_evidence_and_mark_changes(reviewed):
    _, workspace, intel = reviewed
    tools = Tools(intel, max_output_tokens=512)
    response = tools.call("read_symbol", identifier="users.py::get_user")
    assert tools.counter.count(response.text) <= 512
    evidence = workspace.store.get("evidence-v1", response.evidence_id)
    assert evidence["snapshot_id"] == workspace.snapshot.id
    assert tools.evidence(response.evidence_id[:12]) == evidence
    response = Tools(intel).call("read_symbol", identifier="users.py::get_user")
    assert "* L2 " in response.text and response.text.endswith(response.evidence_id[:12])


def test_relocation_does_not_mark_deleted_code_resolved(reviewed):
    _, workspace, intel = reviewed
    old = intel.location("api.py", 4, "base")
    snippet = workspace.read_file("api.py", "base", 4, 4).text
    result = intel.relocate(old, snippet)
    assert result.status == "candidate"
    assert "requires investigation" in result.basis
    assert "resolved" not in type(result).model_fields


def test_typescript_import_binding_and_shadowing(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_CORE_RESOLVERS", "off")  # the name-based fallback itself
    repository.write("users.ts", "export function getUser(id: number) { return id; }\n")
    repository.write(
        "api.ts",
        'import {getUser as fetch} from "./users";\nexport function api(id: number) { return fetch(id); }\nexport function other(fetch: Function) { return fetch(1); }\n',
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    bound = intel.resolve("fetch", from_path="api.ts", line=2, column=40)
    assert len(bound.items) == 1
    assert bound.items[0].confidence == "bound"
    shadowed = intel.resolve("fetch", from_path="api.ts", line=3, column=48)
    assert shadowed.items
    assert all(candidate.confidence == "candidate" for candidate in shadowed.items)


def test_module_qualifier_must_match_import_binding(repository, tmp_path):
    repository.write("pkg/users.py", "def get_user(id):\n    return id\n")
    repository.write("api.py", "import pkg.users\ndef api():\n    return pkg.other.get_user(3)\n")
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.resolve("pkg.other.get_user", from_path="api.py", line=3, column=11)
    assert all(candidate.confidence == "candidate" for candidate in result.items)


def test_signature_only_change_is_not_body_change(repository, tmp_path):
    repository.write("a.py", "def f(x):\n    return x\n")
    base = repository.commit()
    repository.write("a.py", "def f(x=1):\n    return x\n")
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    assert intel.changed_symbols()[0].kinds == ("signature_changed",)


def test_generated_file_classification_uses_snapshot_attributes(repository, tmp_path):
    repository.write("a.py", "def f():\n    return 1\n")
    repository.write(".gitattributes", "a.py linguist-generated\n")
    sha = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", sha, sha)
    repository.write(".gitattributes", "a.py -linguist-generated\n")
    assert CodeIntel(workspace).classify_file("a.py").kind == "generated"


def test_inline_methods_keep_common_changed_container(repository, tmp_path):
    repository.write("a.ts", "class A { a() { return 1; } b() { return 2; } }\n")
    base = repository.commit()
    repository.write("a.ts", "class A { a() { return 1; } b() { return 3; } }\n")
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    units = intel.changed_symbols()
    assert len(units) == 1
    assert units[0].head_symbol.qualified_name == "A"
    assert intel.enclosing_symbol("a.ts", 1, column=43).qualified_name == "A.b"


@pytest.mark.parametrize(
    "declaration",
    [
        "export default function getUser(id: number) { return id; }",
        "export default function(id: number) { return id; }",
        "export default (id: number) => id;",
    ],
)
def test_typescript_default_exports_resolve_to_actual_definition(repository, tmp_path, declaration):
    repository.write("users.ts", declaration)
    repository.write(
        "api.ts", 'import fetch from "./users";\nexport function api() { return fetch(1); }\n'
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.resolve("fetch", from_path="api.ts", line=2, column=30)
    assert len(result.items) == 1
    assert result.items[0].confidence == "bound"
    assert result.items[0].symbol.export_names == ("default",)


def test_missing_delimiter_recovery_is_reported_as_incomplete(repository, tmp_path):
    repository.write("a.ts", "function f() { return 1;")
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.outline("a.ts")
    assert not result.complete
    assert result.gaps[0].kind == "syntax_error"
    matches = intel.structural_match("return $X", "typescript")
    assert not matches.complete


def test_structural_search_reports_budget_exhaustion(reviewed):
    result = reviewed[2].structural_match("return $X", "python", max_files=1)
    assert not result.complete
    assert result.searched_files == 1


def test_compare_symbol_keeps_rename_pairing_as_candidate(repository, tmp_path):
    before = "def fetch_user(id):\n    value = id + 1\n    return value\n"
    after = before.replace("fetch_user", "load_user")
    repository.write("users.py", before)
    base = repository.commit()
    repository.write("users.py", after)
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    result = Tools(intel).call("compare_symbol", identifier="users.py::load_user")
    assert not result.error
    candidate = result.items[0]["pairing_candidates"][0]
    assert candidate["confidence"] == "candidate"
    assert "-def fetch_user" in candidate["diff"]
    assert "+def load_user" in candidate["diff"]


def test_callees_and_module_importers(reviewed):
    _, _, intel = reviewed
    result = intel.references("api.py::api", direction="callees")
    target = intel.symbol("users.py::get_user")
    assert any(reference.target_id == target.id for reference in result.items)
    result = intel.references("users.py::get_user", direction="importers")
    assert {reference.location.path for reference in result.items} == {
        "api.py",
        "tests/test_users.py",
    }


def test_new_file_metadata_does_not_duplicate_source_diff(repository, tmp_path):
    base = repository.commit()
    repository.write("new.py", "def f():\n    return 1\n")
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    units = intel.changed_symbols()
    assert len(units) == 1
    assert units[0].metadata
    assert "return 1" not in units[0].metadata
    assert "metadata_changed" in units[0].kinds


def test_moved_snippet_is_a_candidate_without_confirmed_lineage(repository, tmp_path):
    source = "def f():\n    return 1\n"
    repository.write("before.py", source)
    base = repository.commit()
    repository.git("mv", "before.py", "after.py")
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    intel = CodeIntel(workspace)
    location = intel.location("before.py", 2, "base")
    result = intel.relocate(location, workspace.read_file("before.py", "base", 2, 2).text)
    assert result.status == "candidate"
    assert result.locations[0].path == "after.py"


def test_symbol_handles_survive_process_restart_without_repository_index(reviewed, monkeypatch):
    _, workspace, intel = reviewed
    identifier = intel.outline("users.py").items[0].id
    restarted = CodeIntel(workspace)
    paths = []
    original = restarted.parsed

    def tracked(path, side="head"):
        paths.append(path)
        return original(path, side)

    monkeypatch.setattr(restarted, "parsed", tracked)
    assert restarted.read_symbol(identifier).text.startswith("def get_user")
    assert paths == ["users.py"]


def test_definition_path_filter_applies_to_imported_candidates(reviewed):
    result = reviewed[2].resolve("fetch", from_path="api.py", line=4, path_glob="tests/*")
    assert all(candidate.symbol.location.path.startswith("tests/") for candidate in result.items)


def test_python_class_import_is_not_a_method_lexical_binding(repository, tmp_path):
    repository.write("users.py", "def get_user(id):\n    return id\n")
    repository.write(
        "api.py",
        "class C:\n    from users import get_user\n    def api(self):\n        return get_user(1)\n",
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.resolve("get_user", from_path="api.py", line=4, column=15)
    assert all(candidate.confidence == "candidate" for candidate in result.items)


def test_python_package_root_can_be_nested_under_backend(repository, tmp_path):
    repository.write("backend/apps/__init__.py", "")
    repository.write("backend/apps/users.py", "def get_user(id):\n    return id\n")
    repository.write(
        "backend/apps/api.py",
        "from apps.users import get_user\ndef api():\n    return get_user(1)\n",
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    result = intel.resolve("get_user", from_path="backend/apps/api.py", line=3, column=11)
    assert len(result.items) == 1
    assert result.items[0].confidence == "bound"
    assert result.items[0].symbol.location.path == "backend/apps/users.py"


def test_module_hunks_are_separate_and_calls_keep_the_correct_owner(repository, tmp_path):
    padding = "".join(f"padding_{i} = {i}\n" for i in range(15))
    before = (
        "def first(x):\n    return x\n\ndef second(x):\n    return x\n\nfirst(1)\n"
        + padding
        + "second(1)\n"
    )
    repository.write("module.py", before)
    base = repository.commit()
    repository.write("module.py", before.replace("return x", "return x + 1").replace("(1)", "(2)"))
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "module", base, head))
    graph = intel.change_graph()
    modules = [
        unit for unit in graph.units if unit.base_symbol is None and unit.head_symbol is None
    ]
    assert len(modules) == 2
    for module in modules:
        names = {
            target.head_symbol.name
            for edge in graph.relations
            if edge.source == module.id and edge.kind == "call" and edge.confidence == "bound"
            for target in graph.units
            if target.id == edge.target
        }
        expected = "first" if any("first(" in line.text for line in module.lines) else "second"
        assert names == {expected}


def test_files_over_the_index_limit_stay_reviewable_as_text(repository, tmp_path):
    repository.write("big.py", "def f():\n    return 1\n" * 10)
    repository.write("small.py", "def g():\n    return 1\n")
    base = repository.commit()
    repository.write("big.py", "def f():\n    return 2\n" * 10)
    repository.write("small.py", "def g():\n    return 2\n")
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    intel = CodeIntel(workspace, max_index_bytes=100)
    info = intel.classify_file("big.py")
    assert info.unindexed and info.size == 220
    assert not info.parser_available and not info.outline_available
    assert intel.outline("big.py").gaps[0].kind == "unindexed"
    assert intel.classify_file("small.py").outline_available
    units = intel.changed_symbols()
    assert {unit.precision for unit in units if unit.new_path == "big.py"} == {"text"}
    structural = intel.structural_match("return $X", "python")
    assert structural.searched_files == 1
    assert not structural.complete and structural.gaps[0].kind == "unindexed"
    definition = intel.resolve("f", "head")
    assert not definition.complete
    assert any(gap.path == "big.py" for gap in definition.gaps)
    response = Tools(intel).call("find_definition", name="g")
    assert response.error is None and response.items
    partial = Tools(intel).call("structural_search", pattern="return $X", language="python")
    assert "PARTIAL (unindexed 1): unindexed: big.py" in partial.text
    assert partial.total is None and "small.py:2" in partial.text


def test_tool_bugs_become_errors_not_crashes(reviewed, monkeypatch):
    _, _, intel = reviewed

    def broken(*args, **kwargs):
        raise KeyError("boom")

    monkeypatch.setattr(intel, "outline", broken)
    result = Tools(intel).call("outline", path="users.py")
    assert result.error.startswith("internal tool error (KeyError)")
    assert "ERROR: internal tool error" in result.text


def test_tools_fold_long_lines_page_them_and_keep_full_evidence(repository, tmp_path):
    vector = "VECTOR = [" + ", ".join(f"{i}.5" for i in range(1500)) + "]"
    repository.write("data.py", "x = 1\n")
    base = repository.commit()
    repository.write("data.py", f"x = 1\n{vector}\n")
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    tools = Tools(CodeIntel(workspace), max_line_chars=500)
    first = tools.call("read_file", path="data.py")
    assert "  L1 x = 1\n* L2 VECTOR = [0.5" in first.text
    assert "chars folded" in first.text and "char_offset=500" in first.text
    assert len(first.text) < 1000
    evidence = workspace.store.get("evidence-v1", first.evidence_id)
    assert vector in evidence["result"]["items"][0]["text"]
    second = tools.call("read_file", path="data.py", start_line=2, end_line=2, char_offset=500)
    assert "* L2 [500 chars before] " in second.text
    assert vector[500:1000] in second.text
    diff = tools.call("read_diff", path="data.py")
    assert "patch" not in diff.items[0]
    assert "+L2 VECTOR" in diff.text and "chars folded" in diff.text and len(diff.text) < 1200
    hit = tools.call("code_search", pattern="VECTOR")
    assert "data.py:2: VECTOR" in hit.text and "chars folded" in hit.text


def test_an_oversized_hunk_pages_by_line(repository, tmp_path):
    rows = [f"ROW_{i} = [" + ", ".join(f"{j}.5" for j in range(300)) + "]\n" for i in range(60)]
    repository.write("rows.py", "x = 1\n")
    base = repository.commit()
    repository.write("rows.py", "x = 1\n" + "".join(rows))
    head = repository.commit()
    workspace = Workspace.create(repository.path, tmp_path / "state", "p", base, head)
    tools = Tools(CodeIntel(workspace))
    first = tools.call("read_diff", path="rows.py")
    assert tools.counter.count(first.text) <= tools.max_output_tokens
    cut = re.search(r"continue with offset=0 line_offset=(\d+)", first.text)
    assert cut and "+L2 ROW_0" in first.text
    second = tools.call("read_diff", path="rows.py", line_offset=int(cut.group(1)))
    assert f"(from hunk line {int(cut.group(1)) + 1})" in second.text
    assert f"+L{int(cut.group(1)) + 1} ROW_" in second.text


def test_graph_time_budget_keeps_cheap_edges_and_is_cached(reviewed):
    _, workspace, _ = reviewed
    intel = CodeIntel(workspace, graph_timeout=0)
    graph = intel.change_graph()
    assert not graph.complete
    assert any("time budget" in limit for limit in graph.limits)
    assert not any(relation.kind in {"call", "test_reference"} for relation in graph.relations)
    assert any(relation.kind == "import" for relation in graph.relations)
    assert intel.change_graph() is graph
    assert CodeIntel(workspace).change_graph().complete


def test_csharp_php_and_cpp_outlines_and_calls(repository, tmp_path):
    repository.write(
        "User.cs",
        "namespace App {\n  public class User {\n    public static int Add(int a) { return Helper.Sum(a); }\n"
        "    void Hidden() { }\n    public string Name { get; set; }\n  }\n}\n",
    )
    repository.write(
        "Controller.php",
        "<?php\nclass Controller {\n  public function show($id) { return User::find($id)->load(); }\n"
        "  private function helper() { $this->go(); }\n}\nfunction top($a) { return helper2($a); }\n",
    )
    repository.write(
        "foo.cpp",
        "void Foo::bar(int a) { baz(); ptr->run(); ns::util::f(); }\nint A::B::c() { return 1; }\n",
    )
    repository.write("plain.h", "struct point { int x; };\nint area(struct point p);\n")
    repository.write("klass.h", "namespace n { class K { void m(); }; }\n")
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    cs = {s.qualified_name: s for s in intel.outline("User.cs").items}
    assert {"User", "User.Add", "User.Hidden", "User.Name"} <= cs.keys()
    assert cs["User.Add"].visibility == "public" and cs["User.Hidden"].visibility == "private"
    assert cs["User.Name"].kind == "property"
    php = {s.qualified_name: s for s in intel.outline("Controller.php").items}
    assert {"Controller", "Controller.show", "Controller.helper", "top"} <= php.keys()
    assert php["Controller.helper"].visibility == "private"
    php_calls = {call["expression"] for call in intel.parsed("Controller.php")["calls"]}
    assert {"User.find", "User::find($id).load", "$this.go", "helper2"} <= php_calls
    cpp = {s.qualified_name: s for s in intel.outline("foo.cpp").items}
    assert {"Foo.bar", "A.B.c"} <= cpp.keys() and cpp["Foo.bar"].name == "bar"
    cpp_calls = {call["name"] for call in intel.parsed("foo.cpp")["calls"]}
    assert cpp_calls == {"baz", "run", "f"}
    assert intel.classify_file("plain.h").language == "c"
    assert intel.classify_file("klass.h").language == "cpp"


def test_partial_parse_keeps_symbols_outside_error_regions(repository, tmp_path):
    source = (
        "def good():\n    return 1\n\ndef broken(:\n    pass\n\ndef also_good():\n    return 2\n"
    )
    repository.write("m.py", "def good():\n    return 0\n\ndef also_good():\n    return 0\n")
    base = repository.commit()
    repository.write("m.py", source)
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    outline = intel.outline("m.py")
    names = {symbol.name for symbol in outline.items}
    assert {"good", "also_good"} <= names
    assert outline.gaps[0].kind == "syntax_error" and "L4" in outline.gaps[0].detail
    units = [unit for unit in intel.changed_symbols() if unit.new_path == "m.py"]
    labels = {unit.head_symbol.name for unit in units if unit.head_symbol}
    assert {"good", "also_good"} <= labels
    assert any(unit.head_symbol is None for unit in units)  # the broken lines stay as a hunk
    assert all(unit.precision == "mixed" for unit in units)


def test_data_and_prose_files_are_text_not_gaps(repository, tmp_path):
    repository.write("config.json", '{"a": 1}\n')
    repository.write("README.md", "hello\n")
    repository.write("App.svelte", "<script>let a = 1;</script>\n")
    repository.write("lib.py", "def f():\n    return 1\n")
    base = repository.commit()
    repository.write("config.json", '{"a": 2}\n')
    repository.write("README.md", "hello world\n")
    repository.write("App.svelte", "<script>let a = 2;</script>\n")
    repository.write("lib.py", "def f():\n    return 2\n")
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    units = {unit.new_path: unit for unit in intel.changed_symbols()}
    assert units["config.json"].gaps == () and units["config.json"].precision == "text"
    assert units["README.md"].gaps == () and units["README.md"].kinds == ("file",)
    assert units["App.svelte"].gaps[0].kind == "unsupported"
    graph = intel.change_graph()
    assert {gap.path for gap in graph.gaps} == {"App.svelte"}


def test_definitions_inside_an_error_region_are_recovered(repository, tmp_path):
    source = (
        "namespace n {\n"
        "void g( {\n"
        "int good(int v) { return v + 1; }\n"
        "struct S { int f() { return 2; } };\n"
        "}\n"
    )
    repository.write("x.cpp", source)
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    outline = intel.outline("x.cpp")
    assert {"good", "S", "f"} <= {symbol.name for symbol in outline.items}
    assert outline.gaps and outline.gaps[0].kind == "syntax_error"
    # Recovered definitions are not error lines; the broken line still is.
    errors = intel.syntax_errors("x.cpp")
    assert not any(a <= 3 <= b for a, b in errors) and any(a <= 2 <= b for a, b in errors)


def test_c_type_references_typedefs_and_reference_returns(repository, tmp_path):
    repository.write(
        "a.c",
        "typedef struct { int a; } Info;\nstruct point { int x; };\nvoid f(struct point p) {}\n",
    )
    repository.write("b.cpp", "class Q { T & get() { return x; } };\nclass A::B { };\n")
    repository.write("c.go", "package p\ntype A = B\n")
    repository.write("D.java", "@interface Scope { String value(); }\n")
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    names = lambda path: [(s.qualified_name, s.kind) for s in intel.outline(path).items]  # noqa: E731
    assert names("a.c") == [("Info", "struct"), ("point", "struct"), ("f", "function")]
    assert ("Q.get", "function") in names("b.cpp") and ("A.B", "class") in names("b.cpp")
    assert names("c.go") == [("A", "type")]
    assert names("D.java") == [("Scope", "interface"), ("Scope.value", "method")]


def test_name_fallback_respects_the_shape_of_the_call(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_CORE_RESOLVERS", "off")
    repository.write(
        "a.py",
        "def run():\n    return 0\n\n"
        "class Tool:\n    def run(self):\n        return 1\n    def go(self):\n        return self.run()\n\n"
        "class Other:\n    def run(self):\n        return 2\n\n"
        "def outer():\n    def helper():\n        return 3\n    return helper() + run()\n\n"
        "def use(obj):\n    return obj.run()\n",
    )
    sha = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", sha, sha))
    names = lambda result: sorted(c.symbol.qualified_name for c in result.items)  # noqa: E731
    assert names(intel.resolve("self.run", from_path="a.py", line=8, column=15)) == ["Tool.run"]
    assert names(intel.resolve("obj.run", from_path="a.py", line=19, column=11)) == [
        "Other.run",
        "Tool.run",
    ]
    assert names(intel.resolve("run", from_path="a.py", line=16, column=22)) == ["run"]
    assert "outer.helper" in names(intel.resolve("helper", from_path="a.py", line=16, column=11))


def test_find_file_regex_search_and_multi_path_diff(reviewed):
    _, _, intel = reviewed
    tools = Tools(intel)
    found = tools.call("find_file", query="USERS")
    assert [item["path"] for item in found.items] == ["tests/test_users.py", "users.py"]
    exact = tools.call("find_file", query="USERS", case_sensitive=True)
    assert exact.items == () and not exact.error
    regex = tools.call("code_search", pattern=r"get_user\(None\)|is None", regex=True)
    assert {item["path"] for item in regex.items} == {"users.py", "tests/test_users.py"}
    excluded = tools.call(
        "code_search", pattern="IS NONE", case_sensitive=False, exclude_glob="tests/*"
    )
    assert {item["path"] for item in excluded.items} == {"users.py"}
    bad = tools.call("code_search", pattern="(", regex=True)
    assert bad.error and "Invalid search pattern" in bad.error
    both = tools.call("read_diff", paths=["users.py", "api.py"])
    assert {item["new_path"] for item in both.items} == {"users.py", "api.py"}
    assert both.complete
    partial = tools.call("read_diff", paths=["users.py", "nope.py"])
    assert {item["new_path"] for item in partial.items} == {"users.py"}
    assert "no diff for nope.py" in partial.text and "api.py" in partial.text
    missing = tools.call("read_diff", path="nope.py")
    assert missing.error and "files with diffs" in missing.error
    clash = tools.call("read_diff", path="users.py", paths=["api.py"])
    assert clash.error
