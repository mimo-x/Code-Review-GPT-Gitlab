"""Path classification shared by the example library and the post-filter."""

from __future__ import annotations

import re


def file_role(path: str) -> str:
    lower = path.lower()
    if re.search(r"(^|/)(tests?|__tests__|spec)/|_test\.|\.test\.|\.spec\.|test_[^/]*$|tests?\.[a-z]+$", lower):
        return "test"
    if re.search(r"\.(md|rst|txt|adoc)$", lower):
        return "doc"
    if re.search(r"\.(json|ya?ml|toml|ini|cfg|xml|gradle|properties)$|cmakelists", lower):
        return "config"
    return "source"
