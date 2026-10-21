"""插件内部通用数据结构。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class QueryResult:
    """一次查询的结果：文本、图片或两者兼有。"""

    text: str = ""
    images: list[bytes] = field(default_factory=list)
