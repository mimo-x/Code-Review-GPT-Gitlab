from __future__ import annotations

import pytest

from review_core.common import ReviewCoreError
from review_core.intel import CodeIntel
from review_core.intel.resolvers import RESOLVERS, Resolver
from review_core.workspace import Workspace

AVAILABLE = {resolver.name: resolver.unavailable() is None for resolver in RESOLVERS}


def needs(name):
    return pytest.mark.skipif(not AVAILABLE[name], reason=f"{name} resolver toolchain missing")


def graph_for(repository, tmp_path, before, after):
    for path, text in before.items():
        repository.write(path, text)
    base = repository.commit()
    for path, text in after.items():
        repository.write(path, text)
    head = repository.commit()
    intel = CodeIntel(Workspace.create(repository.path, tmp_path / "state", "p", base, head))
    return intel, intel.change_graph()


def edges(intel, graph):
    units = {unit.id: unit for unit in graph.units}
    return {
        (units[r.source].label, units[r.target].label, r.confidence)
        for r in graph.relations
        if r.kind in {"call", "test_reference"}
    }


GO_A = 'package a\n\nimport "github.com/missing/dep"\n\nfunc Foo(x int) int { return x }\n\nfunc Bar() int { return dep.V() }\n'
GO_MAIN = 'package main\n\nimport (\n\t"fmt"\n\t"example.com/m/a"\n)\n\nfunc Println() {}\n\nfunc main() {\n\tfmt.Println(a.Foo(%d))\n}\n'


@needs("go")
def test_go_calls_bind_by_type_and_ignore_same_named_functions(repository, tmp_path):
    before = {"go.mod": "module example.com/m\n\ngo 1.22\n", "a/a.go": GO_A, "main.go": GO_MAIN % 1}
    after = {
        "a/a.go": GO_A.replace("return x }", "return x + 1 }"),
        "main.go": GO_MAIN.replace("func Println() {}", "func Println() { _ = 1 }") % 2,
    }
    intel, graph = graph_for(repository, tmp_path, before, after)
    found = edges(intel, graph)
    assert ("main.go::main", "a/a.go::Foo", "bound") in found
    # fmt.Println is the standard library's, not the changed local Println.
    assert not any(target == "main.go::Println" for _, target, _ in found)
    assert not any(gap.kind == "name_only" for gap in graph.gaps)
    definition = intel.resolve("a.Foo", from_path="main.go", line=11, column=13)
    assert [c.symbol.label for c in definition.items] == ["a/a.go::Foo"]
    assert definition.items[0].confidence == "bound"
    callers = intel.references("a/a.go::Foo")
    assert {(r.location.path, r.confidence) for r in callers.items} == {("main.go", "bound")}


JAVA_REPO = "package lib;\n\npublic class Repo {\n    public static Repo create() { return new Repo(); }\n    public int save(String s) { return %d; }\n}\n"
JAVA_MAIN = 'package app;\n\nimport lib.Repo;\nimport com.missing.Other;\n\npublic class Main {\n    int run(Other o) {\n        Repo r = Repo.create();\n        o.save("y");\n        return r.save("x") + %d;\n    }\n}\n'


@needs("java")
def test_java_calls_bind_through_spoon_without_dependencies(repository, tmp_path):
    before = {"src/lib/Repo.java": JAVA_REPO % 1, "src/app/Main.java": JAVA_MAIN % 1}
    after = {"src/lib/Repo.java": JAVA_REPO % 2, "src/app/Main.java": JAVA_MAIN % 2}
    intel, graph = graph_for(repository, tmp_path, before, after)
    found = edges(intel, graph)
    assert ("src/app/Main.java::Main.run", "src/lib/Repo.java::Repo.save", "bound") in found
    # o.save on an unresolvable type keeps only a name-level candidate.
    sites = {r.location.start_line: r.confidence for r in graph.relations if r.kind == "call"}
    assert sites == {10: "bound", 9: "candidate"}
    # The unbound site is reported, not passed off as complete.
    unbound = [g.detail for g in graph.gaps if g.kind == "name_only"]
    assert unbound == [
        f"java on {side}: 1 of 2 call sites not bound by type, matched by name"
        for side in ("base", "head")
    ]


CPP_H = "#pragma once\n#include <QString>\nnamespace base {\nclass Foo {\npublic:\n    int bar(int a);\n};\n}\n"
CPP_FOO = '#include "base/Foo.h"\nnamespace base {\nint Foo::bar(int a) { return a + %d; }\n}\n'
CPP_USE = '#include "base/Foo.h"\nint use(base::Foo* f) {\n    unknown_macro(1);\n    return f->bar(%d);\n}\n'


@needs("cpp")
def test_cpp_calls_reach_out_of_class_definitions_through_usrs(repository, tmp_path):
    before = {"include/base/Foo.h": CPP_H, "src/Foo.cpp": CPP_FOO % 1, "src/use.cpp": CPP_USE % 1}
    after = {"src/Foo.cpp": CPP_FOO % 2, "src/use.cpp": CPP_USE % 2}
    intel, graph = graph_for(repository, tmp_path, before, after)
    assert ("src/use.cpp::use", "src/Foo.cpp::Foo.bar", "bound") in edges(intel, graph)


def test_without_resolvers_calls_fall_back_to_names_and_say_so(repository, tmp_path, monkeypatch):
    monkeypatch.setenv("REVIEW_CORE_RESOLVERS", "off")
    before = {"go.mod": "module example.com/m\n", "a/a.go": GO_A, "main.go": GO_MAIN % 1}
    after = {"a/a.go": GO_A.replace("return x }", "return x + 1 }"), "main.go": GO_MAIN % 2}
    intel, graph = graph_for(repository, tmp_path, before, after)
    assert ("main.go::main", "a/a.go::Foo", "candidate") in edges(intel, graph)
    assert any(gap.kind == "name_only" for gap in graph.gaps)


@needs("go")
def test_a_failing_resolver_is_a_gap_and_names_still_apply(repository, tmp_path, monkeypatch):
    def broken(self, *args, **kwargs):
        raise ReviewCoreError(f"{self.name} resolver failed (exit 2)")

    monkeypatch.setattr(Resolver, "run", broken)
    before = {"go.mod": "module example.com/m\n", "a/a.go": GO_A, "main.go": GO_MAIN % 1}
    after = {"a/a.go": GO_A.replace("return x }", "return x + 1 }"), "main.go": GO_MAIN % 2}
    intel, graph = graph_for(repository, tmp_path, before, after)
    assert ("main.go::main", "a/a.go::Foo", "candidate") in edges(intel, graph)
    assert any(gap.kind == "resolver_failed" for gap in graph.gaps)


TS_USERS = "export function getUser(id: number) { return id; }\nexport default function (x: number) { return x; }\n"
TS_API = (
    'import {getUser as fetch} from "./users";\nimport anon from "./users";\n'
    "export function api(id: number) { return fetch(id) + anon(%d); }\n"
    "export function other(fetch: Function) { return fetch(1); }\n"
    "class Tool { check() { return 1; } run() { return this.check(); } }\n"
)


@needs("typescript")
def test_typescript_aliases_defaults_this_and_shadowing_bind_by_type(repository, tmp_path):
    before = {"users.ts": TS_USERS, "api.ts": TS_API % 1}
    after = {"users.ts": TS_USERS.replace("return id;", "return id + 1;"), "api.ts": TS_API % 2}
    intel, graph = graph_for(repository, tmp_path, before, after)
    found = edges(intel, graph)
    assert ("api.ts::api", "users.ts::getUser", "bound") in found
    shadowed = intel.resolve("fetch", from_path="api.ts", line=4, column=47)
    assert shadowed.items == ()  # the parameter, not the import
    own = intel.resolve("this.check", from_path="api.ts", line=5, column=50)
    assert [c.symbol.qualified_name for c in own.items] == ["Tool.check"]
    anon = intel.resolve("anon", from_path="api.ts", line=3, column=55)
    assert [c.symbol.name for c in anon.items] == ["default"]


PY_USERS = "class Repo:\n    def save(self):\n        return %d\n\ndef make():\n    return Repo()\n"
PY_API = (
    "from users import make as build\n\ndef api():\n    repo = build()\n    return repo.save()\n"
)


@needs("python-pyrefly")
def test_python_calls_bind_through_pyrefly(repository, tmp_path):
    before = {"users.py": PY_USERS % 1, "api.py": PY_API}
    after = {"users.py": PY_USERS % 2, "api.py": PY_API + "\n# touched\n"}
    intel, graph = graph_for(repository, tmp_path, before, after)
    definition = intel.resolve("repo.save", from_path="api.py", line=5, column=11)
    assert [c.symbol.qualified_name for c in definition.items] == ["Repo.save"]
    assert definition.items[0].confidence == "bound"
    built = intel.resolve("build", from_path="api.py", line=4, column=11)
    assert [c.symbol.qualified_name for c in built.items] == ["make"]
