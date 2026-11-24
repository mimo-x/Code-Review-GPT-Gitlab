"""审查范围：哪些文件要审查、哪些问题可以报告。

范围只约束"审查什么"，不约束"能读什么"。工作区始终保留完整代码，
引擎可以读取被排除的文件作为上下文，只是不能针对它们报告问题。
"""
from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase

from django.conf import settings

from apps.webhook.models import Project


@dataclass(frozen=True)
class ReviewScope:
    exclude_types: tuple[str, ...] = ()
    ignore_patterns: tuple[str, ...] = ()

    @classmethod
    def for_project(cls, project_id) -> "ReviewScope":
        """项目配置优先；项目未配置时使用全局配置。"""
        project = Project.objects.filter(project_id=project_id).first()
        exclude_types = project.exclude_file_types_list if project else None
        ignore_patterns = project.ignore_file_patterns_list if project else None
        return cls(
            exclude_types=_clean(exclude_types or settings.EXCLUDE_FILE_TYPES),
            ignore_patterns=_clean(ignore_patterns or settings.IGNORE_FILE_TYPES),
        )

    def allows(self, path: str) -> bool:
        if any(path.endswith(file_type) for file_type in self.exclude_types):
            return False
        return not any(_matches(path, pattern) for pattern in self.ignore_patterns)

    def split(self, changes: list[dict]) -> tuple[list[dict], tuple[str, ...]]:
        """返回要审查的变更和被排除的路径。"""
        included, skipped = [], []
        for change in changes:
            path = change.get("new_path") or change.get("old_path", "")
            if self.allows(path):
                included.append(change)
            else:
                skipped.append(path)
        return included, tuple(skipped)


def _clean(values) -> tuple[str, ...]:
    # 空字符串会匹配所有路径，必须去掉
    return tuple(text for text in (str(value).strip() for value in values) if text)


def _matches(path: str, pattern: str) -> bool:
    if any(char in pattern for char in "*?["):
        return fnmatchcase(path, pattern) or fnmatchcase(path.rsplit("/", 1)[-1], pattern)
    if pattern.startswith(".") and "/" not in pattern:
        # ".md" 是扩展名，".github" 是目录，都不能按子串匹配到 "parse.mdl.py"
        return path.endswith(pattern) or pattern in path.split("/")
    return pattern in path
