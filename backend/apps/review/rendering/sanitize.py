"""清洗模型写的文本：这些内容受 MR 影响，不能让它触发 GitLab 或 IM 的行为。"""
from __future__ import annotations

import re

_QUICK_ACTION = re.compile(r"^([ \t>]*)/(?=[A-Za-z])", re.MULTILINE)
_MENTION = re.compile(r"(?<![\w.+/-])@(?=[\w.-])")
_LAYOUT_TAG = re.compile(r"<(/?)(details|summary)\b", re.IGNORECASE)
_ZERO_WIDTH_SPACE = "​"


def sanitize(text: str) -> str:
    """转义 GitLab 快捷命令和 @提及，并防止文本破坏折叠区结构。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = _QUICK_ACTION.sub(r"\1\\/", text)
    text = _MENTION.sub(f"@{_ZERO_WIDTH_SPACE}", text)
    return _LAYOUT_TAG.sub(r"&lt;\1\2", text)


def single_line(text: str) -> str:
    return " ".join(sanitize(text).split())


def table_cell(text: str) -> str:
    return single_line(text).replace("|", "\\|")


def code_span(text: str) -> str:
    """路径可能来自模型：压成一行并去掉反引号，防止跳出行内代码。"""
    return f"`{' '.join(text.replace('`', '').split())}`".replace("|", "\\|")


def plain_message(text: str) -> str:
    """IM 消息用：去掉可能被渠道解析成指令或卡片标签的字符。"""
    return single_line(text).replace("<", "＜").replace(">", "＞").replace("```", "")

