"""Python call resolution with Pyrefly's language server (textDocument/definition)."""

import ast
import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

sys.path.insert(0, str(Path(__file__).parent))
from python_jedi import name_column  # noqa: E402


class Client:
    def __init__(self, command, root):
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=root,
        )
        self.next_id = 0
        self.lock = threading.Lock()

    def send(self, payload):
        body = json.dumps(payload).encode()
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode() + body)
        self.process.stdin.flush()

    def read(self):
        length = 0
        while True:
            line = self.process.stdout.readline()
            if not line:
                raise EOFError
            if line in (b"\r\n", b"\n"):
                break
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":")[1])
        return json.loads(self.process.stdout.read(length))

    def request(self, method, params):
        self.next_id += 1
        ident = self.next_id
        self.send({"jsonrpc": "2.0", "id": ident, "method": method, "params": params})
        while True:
            message = self.read()
            if message.get("id") == ident and "method" not in message:
                return message.get("result")
            if "method" in message and "id" in message:  # server request: answer null
                self.send({"jsonrpc": "2.0", "id": message["id"], "result": None})

    def notify(self, method, params):
        self.send({"jsonrpc": "2.0", "method": method, "params": params})


MAX_ROOTS = 64
_IMPORTS: dict[Path, list[tuple[int, int]]] = {}
_TEXT: dict[Path, list[str]] = {}


def declared_name(path: Path, span: dict) -> str | None:
    """The identifier the definition range points at, as written in the source."""
    if path not in _TEXT:
        try:
            _TEXT[path] = path.read_text("utf-8", "replace").split("\n")
        except OSError:
            _TEXT[path] = []
    lines = _TEXT[path]
    start, end = span["start"], span["end"]
    if start["line"] != end["line"] or start["line"] >= len(lines):
        return None
    text = lines[start["line"]][start["character"] : end["character"]]
    return text if text.isidentifier() else None


def in_import(path: Path, line: int) -> bool:
    """Whether line falls inside an import statement of path."""
    if path not in _IMPORTS:
        spans = []
        try:
            tree = ast.parse(path.read_text("utf-8", "replace"))
            spans = [
                (node.lineno, node.end_lineno or node.lineno)
                for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
        except (OSError, SyntaxError, ValueError):
            pass
        _IMPORTS[path] = spans
    return any(start <= line <= end for start, end in _IMPORTS[path])


def source_roots(root: Path) -> list[str]:
    """Directories that hold top-level packages: the parent of every outermost package."""
    roots = {".", "src"}
    for directory, names, files in os.walk(root):
        names[:] = [n for n in names if not n.startswith(".") and n != "node_modules"]
        here = Path(directory)
        if "__init__.py" in files and not (here.parent / "__init__.py").exists():
            roots.add(here.parent.relative_to(root).as_posix() or ".")
        if len(roots) >= MAX_ROOTS:
            break
    return sorted(roots)


def configure(root: Path) -> None:
    """Search the repository's own source roots only: no interpreter, no site-packages."""
    config = root / "pyrefly.toml"
    if config.exists():
        return
    paths = ", ".join(json.dumps(path) for path in source_roots(root))
    temporary = config.with_name(f".pyrefly.toml.{os.getpid()}")
    temporary.write_text(
        f"search-path = [{paths}]\nsite-package-path = []\nskip-interpreter-query = true\n"
    )
    os.replace(temporary, config)


def main() -> None:
    request = json.load(sys.stdin)
    root = Path(request["root"]).resolve()
    configure(root)
    pyrefly = os.environ.get("REVIEW_CORE_PYREFLY") or "pyrefly"
    client = Client([pyrefly, "lsp"], root)
    client.request(
        "initialize",
        {
            "processId": os.getpid(),
            "rootUri": root.as_uri(),
            "capabilities": {},
            "workspaceFolders": [{"uri": root.as_uri(), "name": "root"}],
        },
    )
    client.notify("initialized", {})
    out = {"sites": [], "definitions": [], "errors": []}
    by_file = {}
    for site in request["sites"]:
        by_file.setdefault(site["path"], []).append(site)
    for rel, sites in by_file.items():
        path = root / rel
        code = path.read_text("utf-8", "replace")
        uri = path.as_uri()
        client.notify(
            "textDocument/didOpen",
            {"textDocument": {"uri": uri, "languageId": "python", "version": 1, "text": code}},
        )
        lines = code.split("\n")
        for site in sites:
            result = dict(
                path=site["path"],
                line=site["line"],
                column=site["column"],
                targets=[],
                external=False,
            )
            column = (
                name_column(lines[site["line"] - 1], site["column"], site["name"])
                if site["line"] <= len(lines)
                else None
            )
            if column is not None:
                found = (
                    client.request(
                        "textDocument/definition",
                        {
                            "textDocument": {"uri": uri},
                            "position": {"line": site["line"] - 1, "character": column},
                        },
                    )
                    or []
                )
                if isinstance(found, dict):
                    found = [found]
                for location in found:
                    target_uri = location.get("uri") or location.get("targetUri")
                    span = location.get("range") or location.get("targetSelectionRange")
                    target = Path(unquote(urlparse(target_uri).path)).resolve()
                    try:
                        rel_target = target.relative_to(root).as_posix()
                    except ValueError:
                        result["external"] = True
                        continue
                    line = span["start"]["line"] + 1
                    declared = declared_name(target, span) or site["name"]
                    if in_import(target, line):
                        # Definition stopped at an import of a module outside the repository.
                        result["external"] = True
                        continue
                    result["targets"].append(
                        dict(
                            path=rel_target,
                            line=line,
                            name=declared,
                            key=f"{rel_target}:{line}",
                        )
                    )
                if result["targets"]:
                    result["external"] = False
            out["sites"].append(result)
        client.notify("textDocument/didClose", {"textDocument": {"uri": uri}})
    try:
        client.request("shutdown", None)
        client.notify("exit", None)
    except Exception:
        pass
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
