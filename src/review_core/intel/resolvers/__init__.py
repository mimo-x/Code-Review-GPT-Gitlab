"""External, type-aware call resolution for languages Tree-sitter can only match by name.

Each resolver is an optional helper process speaking one JSON protocol:

    request  {"root": dir, "files": [rel], "sites": [{"path", "line", "column", "name"}]}
    response {"sites": [{"path", "line", "column", "targets": [{"path", "line", "name",
              "key"}]}], "definitions": [{"path", "line", "name", "key"}], "errors": [...]}

`line` is 1-based and `column` 0-based, as in Code Intel. A target is a declaration; when
a language separates declarations from definitions (C++), `key` links a target to the
definitions listed in `definitions`. Core code depends only on this protocol: a missing
toolchain disables the resolver and analysis falls back to name matching, reported as a
gap rather than an error.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from functools import cache
from pathlib import Path

from filelock import FileLock

from review_core.common import Record, ReviewCoreError

HERE = Path(__file__).parent
MAX_JAVA_CONTEXT = 800
JAVA_IMPORT = re.compile(r"^\s*import\s+(static\s+)?([\w.]+?)(\.\*)?\s*;", re.MULTILINE)
HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".h++", ".ipp", ".inl", ".tcc"}


class Site(Record):
    path: str
    line: int
    column: int
    name: str


class Target(Record):
    path: str
    line: int
    name: str
    key: str


class Resolved(Record):
    path: str
    line: int
    column: int
    targets: tuple[Target, ...] = ()
    # Bound, but to a declaration outside the repository (standard library, system headers).
    external: bool = False


class Resolution(Record):
    sites: tuple[Resolved, ...] = ()
    definitions: tuple[Target, ...] = ()
    errors: tuple[str, ...] = ()


def cache_dir() -> Path:
    root = Path(os.environ.get("REVIEW_CORE_CACHE") or Path.home() / ".cache" / "review-core")
    root.mkdir(parents=True, exist_ok=True)
    return root


class Resolver:
    name: str
    languages: frozenset[str]
    # Bumped when the helper's output changes, so cached resolutions are not reused.
    version: str

    def unavailable(self) -> str | None:
        """Why this resolver cannot run here, or None when it can."""
        raise NotImplementedError

    def context(self, tree: list[str], files: list[str], read) -> list[str]:
        """Extra files to analyze with the requested ones, so their types are known.

        read(path) returns a file's text on the analyzed revision.
        """
        return []

    def export_paths(self, tree: list[str], files: list[str]) -> list[str]:
        """Files the helper needs on disk besides the requested ones."""
        return list(files)

    def command(self) -> list[str]:
        raise NotImplementedError

    def environment(self) -> dict[str, str]:
        return {"PATH": os.defpath, "HOME": str(cache_dir()), "LC_ALL": "C"}

    def run(self, root: Path, files: list[str], sites: list[Site], timeout: float) -> Resolution:
        request = {
            "root": str(root),
            "files": sorted(set(files)),
            "sites": [site.model_dump() for site in sites],
        }
        try:
            process = subprocess.run(
                self.command(),
                input=json.dumps(request).encode(),
                capture_output=True,
                env=self.environment(),
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ReviewCoreError(f"{self.name} resolver exceeded {timeout:g}s") from exc
        if process.returncode:
            detail = process.stderr.decode("utf-8", "replace").strip().splitlines()
            raise ReviewCoreError(
                f"{self.name} resolver failed (exit {process.returncode})"
                + (f": {detail[-1][:200]}" if detail else "")
            )
        payload = json.loads(process.stdout)
        return Resolution(
            sites=tuple(Resolved.model_validate(item) for item in payload.get("sites") or ()),
            definitions=tuple(
                Target.model_validate(item) for item in payload.get("definitions") or ()
            ),
            errors=tuple(payload.get("errors") or ()),
        )


def _build(name: str, sources: list[Path], build) -> Path:
    """Build a helper once per source digest, under a lock, into the cache directory."""
    digest = hashlib.sha256(b"".join(path.read_bytes() for path in sources)).hexdigest()[:16]
    output = cache_dir() / "build" / f"{name}-{digest}"
    marker = output / ".built"
    if marker.exists():
        return output
    output.mkdir(parents=True, exist_ok=True)
    with FileLock(str(output) + ".lock"):
        if not marker.exists():
            build(output)
            marker.touch()
    return output


def _executable(environment: str, *candidates: str) -> str | None:
    explicit = os.environ.get(environment)
    if explicit:
        return explicit if Path(explicit).exists() else None
    for candidate in candidates:
        found = shutil.which(candidate) if "/" not in candidate else candidate
        if found and Path(found).exists():
            return found
    return None


class GoResolver(Resolver):
    name = "go"
    languages = frozenset({"go"})
    version = "go-v1"

    def go(self) -> str | None:
        return _executable("REVIEW_CORE_GO", "go", "/opt/homebrew/bin/go", "/usr/local/go/bin/go")

    def unavailable(self) -> str | None:
        return None if self.go() else "Go toolchain not found (set REVIEW_CORE_GO)"

    def export_paths(self, tree: list[str], files: list[str]) -> list[str]:
        # Packages are type-checked from source, so every package must be on disk.
        return [
            path
            for path in tree
            if (path.endswith(".go") or path.endswith("/go.mod") or path == "go.mod")
            and "/testdata/" not in f"/{path}"
        ]

    def environment(self) -> dict[str, str]:
        root = cache_dir()
        go = Path(self.go()).resolve()
        return {
            **super().environment(),
            "PATH": f"{go.parent}{os.pathsep}{os.defpath}",
            "GOCACHE": str(root / "gocache"),
            "GOPATH": str(root / "gopath"),
            "GOFLAGS": "-mod=mod",
            "GOPROXY": "off",
            "GOTOOLCHAIN": "local",
            "GOWORK": "off",
            "CGO_ENABLED": "0",
        }

    def command(self) -> list[str]:
        source = HERE / "go" / "main.go"

        def build(output: Path) -> None:
            subprocess.run(
                [self.go(), "build", "-o", str(output / "resolve"), str(source)],
                check=True,
                capture_output=True,
                env=self.environment(),
                timeout=300,
            )

        return [str(_build("go", [source], build) / "resolve")]


class JavaResolver(Resolver):
    name = "java"
    languages = frozenset({"java"})
    version = "java-v3"

    def java(self) -> str | None:
        home = os.environ.get("JAVA_HOME")
        candidates = [f"{home}/bin/java"] if home else []
        candidates += sorted(str(p) for p in Path("/opt/homebrew/opt").glob("openjdk*/bin/java"))
        candidates += sorted(str(p) for p in Path("/usr/lib/jvm").glob("*/bin/java"))
        found = _executable("REVIEW_CORE_JAVA", *candidates, "java")
        if found and _works(found):
            return found
        return None

    def spoon(self) -> Path | None:
        explicit = os.environ.get("REVIEW_CORE_SPOON_JAR")
        if explicit:
            return Path(explicit) if Path(explicit).exists() else None
        jars = sorted((cache_dir() / "spoon").glob("spoon-core-*-jar-with-dependencies.jar"))
        return jars[-1] if jars else None

    def context(self, tree: list[str], files: list[str], read) -> list[str]:
        """Imported types first (their sources declare the callees), then same-package files."""
        sources = [path for path in tree if path.endswith(".java")]
        by_suffix = {}
        for path in sources:
            by_suffix.setdefault(path.split("/java/")[-1], []).append(path)
        imported = []
        for file in files:
            try:
                text = read(file)
            except Exception:
                continue
            for _, name, star in JAVA_IMPORT.findall(text):
                parts = name.split(".")
                if star:
                    package = "/".join(parts) + "/"
                    imported += [
                        p
                        for p in sources
                        if p.split("/java/")[-1].startswith(package)
                        and "/" not in p.split("/java/")[-1][len(package) :]
                    ][:20]
                    continue
                # import a.b.C, import a.b.C.Inner, import static a.b.C.member
                for cut in range(len(parts), 1, -1):
                    hits = by_suffix.get("/".join(parts[:cut]) + ".java")
                    if hits:
                        imported += hits[:2]
                        break
        directories = {str(Path(path).parent) for path in files}
        siblings = [path for path in sources if str(Path(path).parent) in directories]
        return list(dict.fromkeys([*imported, *siblings]))[:MAX_JAVA_CONTEXT]

    def unavailable(self) -> str | None:
        if not self.java():
            return "Java 17+ runtime not found (set REVIEW_CORE_JAVA or JAVA_HOME)"
        if not self.spoon():
            return "Spoon jar not found (set REVIEW_CORE_SPOON_JAR)"
        return None

    def command(self) -> list[str]:
        source = HERE / "java" / "Resolve.java"
        javac = str(Path(self.java()).with_name("javac"))
        spoon = str(self.spoon())

        def build(output: Path) -> None:
            subprocess.run(
                [javac, "-cp", spoon, "-d", str(output), str(source)],
                check=True,
                capture_output=True,
                timeout=300,
            )

        classes = _build("java", [source], build)
        return [
            self.java(),
            "-Xss8m",
            "-Xmx2g",
            "-cp",
            f"{classes}{os.pathsep}{spoon}",
            "Resolve",
        ]


class CppResolver(Resolver):
    name = "cpp"
    languages = frozenset({"c", "cpp"})
    version = "cpp-v2"

    def unavailable(self) -> str | None:
        return (
            None if _libclang() else "libclang Python bindings not installed (pip install libclang)"
        )

    def export_paths(self, tree: list[str], files: list[str]) -> list[str]:
        # Headers anywhere in the repository can be included.
        return [*files, *(path for path in tree if Path(path).suffix.lower() in HEADER_SUFFIXES)]

    def command(self) -> list[str]:
        return [sys.executable, "-I", str(HERE / "cpp.py")]


JS_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")


class TypeScriptResolver(Resolver):
    name = "typescript"
    languages = frozenset({"javascript", "jsx", "typescript", "tsx"})
    version = "typescript-v2"

    def node(self) -> str | None:
        return _executable("REVIEW_CORE_NODE", "node", "/opt/homebrew/bin/node", "/usr/bin/node")

    def typescript(self) -> Path | None:
        explicit = os.environ.get("REVIEW_CORE_TYPESCRIPT")
        if explicit:
            return Path(explicit) if Path(explicit).exists() else None
        package = cache_dir() / "node" / "node_modules" / "typescript"
        return package if (package / "lib" / "typescript.js").exists() else None

    def unavailable(self) -> str | None:
        if not self.node():
            return "Node.js not found (set REVIEW_CORE_NODE)"
        if not self.typescript():
            return "TypeScript package not found (set REVIEW_CORE_TYPESCRIPT)"
        return None

    def export_paths(self, tree: list[str], files: list[str]) -> list[str]:
        # The program follows imports, so every first-party source and config may be read.
        return [
            path
            for path in tree
            if "node_modules/" not in f"/{path}"
            and (
                path.endswith(JS_SUFFIXES)
                or Path(path).name in {"package.json", "tsconfig.json", "jsconfig.json"}
                or (Path(path).name.startswith("tsconfig") and path.endswith(".json"))
            )
        ]

    def environment(self) -> dict[str, str]:
        return {**super().environment(), "REVIEW_CORE_TYPESCRIPT": str(self.typescript())}

    def command(self) -> list[str]:
        return [self.node(), "--max-old-space-size=4096", str(HERE / "ts" / "resolve.js")]


class JediResolver(Resolver):
    name = "python-jedi"
    languages = frozenset({"python"})
    version = "jedi-v1"

    def unavailable(self) -> str | None:
        try:
            import jedi  # noqa: F401
        except ImportError:
            return "Jedi not installed (pip install jedi)"
        return None

    def export_paths(self, tree: list[str], files: list[str]) -> list[str]:
        # Imports are followed, so every first-party module may be read.
        return [path for path in tree if path.endswith((".py", ".pyi"))]

    def command(self) -> list[str]:
        return [sys.executable, "-I", str(HERE / "python_jedi.py")]


class PyreflyResolver(JediResolver):
    name = "python-pyrefly"
    version = "pyrefly-v4"

    def pyrefly(self) -> str | None:
        local = Path(sys.executable).with_name("pyrefly")
        return _executable("REVIEW_CORE_PYREFLY", str(local), "pyrefly")

    def unavailable(self) -> str | None:
        return None if self.pyrefly() else "Pyrefly not installed (pip install pyrefly)"

    def environment(self) -> dict[str, str]:
        return {**super().environment(), "REVIEW_CORE_PYREFLY": self.pyrefly()}

    def command(self) -> list[str]:
        return [sys.executable, "-I", str(HERE / "python_pyrefly.py")]


@cache
def _works(java: str) -> bool:
    try:
        result = subprocess.run([java, "-version"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


@cache
def _libclang() -> bool:
    try:
        import clang.cindex as cindex

        cindex.Index.create()
    except Exception:
        return False
    return True


# Pyrefly first: on the bench it bound 33% of Python calls (Jedi 25%) in 0.4s per case
# (Jedi 21s); REVIEW_CORE_PYTHON_RESOLVER=jedi selects Jedi instead.
RESOLVERS: tuple[Resolver, ...] = (
    GoResolver(),
    JavaResolver(),
    CppResolver(),
    TypeScriptResolver(),
    PyreflyResolver(),
    JediResolver(),
)


@cache
def _available(resolver: Resolver) -> bool:
    return resolver.unavailable() is None


def resolver_for(language: str | None) -> Resolver | None:
    """The available resolver for a language, or None (then name matching applies).

    REVIEW_CORE_RESOLVERS=off disables all of them, for ablations and minimal installs.
    """
    if os.environ.get("REVIEW_CORE_RESOLVERS", "on") == "off":
        return None
    preferred = os.environ.get("REVIEW_CORE_PYTHON_RESOLVER", "pyrefly")
    for resolver in RESOLVERS:
        if language == "python" and not resolver.name.endswith(preferred):
            continue
        if language in resolver.languages and _available(resolver):
            return resolver
    return None
