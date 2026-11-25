"""Python call resolution with Jedi, run as a helper process (see the package docstring).

Jedi infers types statically (no code is executed) and follows imports inside the exported
repository; calls into packages that are not exported stay unresolved or external.
"""

import json
import re
import sys
from pathlib import Path


def name_column(line: str, column: int, name: str) -> int | None:
    """Column of the called name at or after the call start (calls start at the receiver)."""
    match = re.compile(rf"\b{re.escape(name)}\s*\(").search(line, column)
    if match is None:
        match = re.compile(rf"\b{re.escape(name)}\b").search(line, column)
    return match.start() if match else None


def main() -> None:
    import jedi

    request = json.load(sys.stdin)
    root = Path(request["root"]).resolve()
    project = jedi.Project(
        root,
        added_sys_path=[str(root), str(root / "src")],
        smart_sys_path=False,
        load_unsafe_extensions=False,
    )
    by_file = {}
    for site in request["sites"]:
        by_file.setdefault(site["path"], []).append(site)
    out = {"sites": [], "definitions": [], "errors": []}
    for rel, sites in by_file.items():
        path = root / rel
        try:
            code = path.read_text("utf-8")
            script = jedi.Script(code, path=path, project=project)
        except Exception as exc:  # unreadable or unparsable: every site stays unresolved
            out["errors"].append(f"{rel}: {type(exc).__name__}")
            script, code = None, ""
        lines = code.split("\n")
        for site in sites:
            result = dict(
                path=site["path"],
                line=site["line"],
                column=site["column"],
                targets=[],
                external=False,
            )
            if script is not None and site["line"] <= len(lines):
                column = name_column(lines[site["line"] - 1], site["column"], site["name"])
                if column is not None:
                    try:
                        names = script.goto(site["line"], column, follow_imports=True)
                    except Exception:
                        names = []
                    for name in names:
                        module = name.module_path
                        if module is None or name.line is None:
                            result["external"] = True
                            continue
                        try:
                            target = Path(module).resolve().relative_to(root).as_posix()
                        except ValueError:
                            result["external"] = True  # standard library or site-packages
                            continue
                        result["targets"].append(
                            dict(
                                path=target,
                                line=name.line,
                                name=name.name,
                                key=f"{target}:{name.line}",
                            )
                        )
                    if result["targets"]:
                        result["external"] = False
            out["sites"].append(result)
    json.dump(out, sys.stdout)


if __name__ == "__main__":
    main()
