"""C/C++ call resolution with libclang, run as a helper process (see the package docstring).

There is usually no compile_commands.json, so flags are guessed: the language standard and
every exported directory that holds headers as an include path. Missing headers and macros
make this partial by nature: unresolved calls are reported as such, never guessed. Calls
link to definitions through clang USRs, since a call often sees only a header declaration.
"""

import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

HEADER_SUFFIXES = {".h", ".hh", ".hpp", ".hxx", ".h++", ".ipp", ".inl", ".tcc"}
CPP_HEADER = re.compile(r"\b(?:class|namespace|template|public:|private:|protected:)\b|::")
DEFINITION_KINDS = {
    "FUNCTION_DECL",
    "CXX_METHOD",
    "CONSTRUCTOR",
    "DESTRUCTOR",
    "FUNCTION_TEMPLATE",
    "CONVERSION_FUNCTION",
}
MAX_INCLUDE_DIRS = 4000


def system_includes(language: str) -> list[str]:
    """The host compiler's own search path (standard library, SDK), as -isystem flags.

    The libclang wheel ships no headers of its own; without this even <string> is missing
    and most C++ calls cannot bind. REVIEW_CORE_CXX picks the compiler to ask.
    """
    import shutil
    import subprocess

    candidates = [os.environ.get("REVIEW_CORE_CXX"), "clang++", "g++", "c++"]
    compiler = next((shutil.which(c) for c in candidates if c and shutil.which(c)), None)
    if compiler is None:
        return []
    try:
        result = subprocess.run(
            [compiler, "-E", "-x", language, "-", "-v"],
            input=b"",
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    flags, inside = [], False
    for line in result.stderr.decode("utf-8", "replace").splitlines():
        if line.startswith("#include <...> search starts here"):
            inside = True
        elif line.startswith("End of search list"):
            break
        elif inside:
            entry = line.strip()
            if entry.endswith("(framework directory)"):
                flags.append("-iframework" + entry.removesuffix("(framework directory)").strip())
            elif entry:
                flags.append("-isystem" + entry)
    return flags


def include_dirs(root: Path) -> list[str]:
    found = set()
    for directory, _, names in os.walk(root):
        if any(Path(name).suffix.lower() in HEADER_SUFFIXES for name in names):
            found.add(directory)
            # Also the parents, so includes like "Base/Foo.h" resolve from either level.
            parent = Path(directory).parent
            while parent != root.parent and str(parent).startswith(str(root)):
                found.add(str(parent))
                parent = parent.parent
    return sorted(found)[:MAX_INCLUDE_DIRS]


def language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".c":
        return "c"
    if suffix == ".h":
        try:
            text = path.read_text("utf-8", "replace")
        except OSError:
            return "c++"
        return "c++" if CPP_HEADER.search(text) else "c"
    return "c++"


def analyze(job):
    import clang.cindex as cindex

    root, rel, sites, includes, system = job
    path = Path(root) / rel
    lang = language(path)
    args = ["-x", lang, "-std=c++20" if lang == "c++" else "-std=c17", "-fsyntax-only"]
    args += ["-Wno-everything", "-ferror-limit=0", *(f"-I{d}" for d in includes)]
    args += system["c++" if lang == "c++" else "c"]
    options = 0x200 | 0x40 | 0x800 | 0x04  # keep going; skip bodies in the preamble only
    try:
        unit = cindex.Index.create().parse(str(path), args=args, options=options)
    except cindex.TranslationUnitLoadError:
        return rel, [], [], [f"clang could not parse {rel}"]
    wanted = {}
    for site in sites:
        wanted.setdefault(site["line"], []).append(site)
    calls = {}
    definitions = []
    main = str(path)
    for cursor in unit.cursor.walk_preorder():
        location = cursor.location
        if location.file is None or location.file.name != main:
            continue
        kind = cursor.kind.name
        if kind == "CALL_EXPR" and cursor.extent.start.line in wanted:
            calls.setdefault(cursor.extent.start.line, []).append(cursor)
        elif kind in DEFINITION_KINDS and cursor.is_definition():
            definitions.append(
                dict(path=rel, line=location.line, name=cursor.spelling, key=cursor.get_usr())
            )
    resolved = []
    for line, line_sites in wanted.items():
        for site in line_sites:
            targets, external = [], False
            for cursor in calls.get(line, []):
                if cursor.spelling != site["name"]:
                    continue
                reference = cursor.referenced
                if reference is None:
                    continue
                declaration = reference.get_definition() or reference
                file = declaration.location.file
                if file is None:
                    continue
                target = os.path.relpath(file.name, root)
                if target.startswith(".."):
                    external = True  # system or toolchain header
                    break
                targets.append(
                    dict(
                        path=target.replace(os.sep, "/"),
                        line=declaration.location.line,
                        name=reference.spelling,
                        key=reference.get_usr(),
                    )
                )
                break
            resolved.append(dict(site, targets=targets, external=external))
    return rel, resolved, definitions, []


def main() -> None:
    request = json.load(sys.stdin)
    root = Path(request["root"]).resolve()
    includes = include_dirs(root)
    by_file = {}
    for site in request["sites"]:
        by_file.setdefault(site["path"], []).append(site)
    system = {lang: system_includes(lang) for lang in ("c++", "c")}
    jobs = [(str(root), rel, by_file.get(rel, []), includes, system) for rel in request["files"]]
    response = {"sites": [], "definitions": [], "errors": []}
    workers = max(1, min(len(jobs), os.cpu_count() or 1))
    with ProcessPoolExecutor(workers) as pool:
        for _, sites, definitions, errors in pool.map(analyze, jobs):
            for site in sites:
                site.pop("name", None)
            response["sites"].extend(sites)
            response["definitions"].extend(definitions)
            response["errors"].extend(errors)
    json.dump(response, sys.stdout)


if __name__ == "__main__":
    main()
