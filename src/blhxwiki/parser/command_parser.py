"""wiki 命令解析与参数归一化。

指令格式：
- 一级指令别名：wiki / .wiki / /wiki / yls（大小写不敏感）
- 标准格式：``wiki [目标] ([子命令])``
- 自动分词：``wiki拉菲皮肤`` → 拉菲 / 皮肤
- 别名替换：``金坷垃`` → ``圣地亚哥``

不依赖 MaiBot SDK，便于单元测试。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from blhxwiki.config.config_data import ALIASES, PRIMARY_COMMANDS, SECONDARY_COMMANDS

# 所有二级指令别名（属性/皮肤/出处/语音关键词……）
ALL_SECONDARY = frozenset(
    alias for group in SECONDARY_COMMANDS.values() for alias in group
)

# 具体榜单名。
RANK_NAMES = frozenset({
    "PVE用舰船综合性能强度榜", "舰娘一图榜",
    "装备一图榜",
    "认知觉醒推荐榜", "觉醒榜",
    "萌新入坑推荐榜", "萌新榜",
    "兑换装备推荐榜", "兑换榜",
    "装备研发推荐榜", "研发榜",
    "改造舰船推荐榜", "改造榜",
    "井号打捞表", "打捞表",
})


@dataclass(slots=True)
class ParsedWikiCommand:
    """从聊天文本中解析出的 wiki 查询请求。"""

    keyword: str
    query_type: str = ""  # 空串表示用户未显式指定子命令
    raw: str = ""
    auto_split: bool = False
    args: list[str] = field(default_factory=list)  # 完整分词参数（含一级指令）


def parse_wiki_command(
    text: str, user_aliases: dict[str, str] | None = None
) -> ParsedWikiCommand | None:
    """解析 ``wiki [目标] ([子命令])``；只发 ``wiki`` 时返回 None（触发帮助）。

    ``user_aliases`` 对应用户自定义别名，优先级高于内置别名。
    """
    aliases = _merged_aliases(user_aliases)
    normalized = re.sub(r"\s+", " ", (text or "").strip())
    if not normalized:
        return None

    lowered = normalized.lower()
    prefix = None
    for candidate in PRIMARY_COMMANDS:
        if lowered == candidate:
            return None
        if lowered.startswith(candidate + " "):
            prefix = candidate
            break

    if prefix is None:
        # 无空格形式：wiki拉菲皮肤 / yls拉菲
        return phrase_command(normalized, user_aliases)

    args = normalized[len(prefix):].strip().split(" ")
    if not args or not args[0]:
        return None

    keyword = args[0]
    return ParsedWikiCommand(
        keyword=aliases.get(keyword.lower(), keyword),
        query_type=args[1] if len(args) >= 2 else "",
        raw=text,
        args=args,
    )


def phrase_command(
    text: str, user_aliases: dict[str, str] | None = None
) -> ParsedWikiCommand | None:
    """自动分词：去掉空格后剥离一级指令，再按二级指令切分目标。"""
    aliases = _merged_aliases(user_aliases)
    compact = re.sub(r"\s+", "", (text or "").lower())
    prefix = next((p for p in PRIMARY_COMMANDS if compact.startswith(p)), None)
    if prefix is None:
        return None

    rest = compact[len(prefix):]
    if not rest:
        return None

    if rest in aliases:
        return ParsedWikiCommand(keyword=aliases[rest], raw=text, auto_split=True)

    # 长词优先，避免「皮肤原图」被「皮肤」抢先切分。
    for alias in sorted(ALL_SECONDARY, key=len, reverse=True):
        if rest.endswith(alias) and len(rest) > len(alias):
            keyword = rest[: -len(alias)]
            return ParsedWikiCommand(
                keyword=aliases.get(keyword, keyword),
                query_type=alias,
                raw=text,
                auto_split=True,
            )
        # 前缀切分限制至少 2 字，避免「改」「大」这类单字误切。
        if len(alias) >= 2 and rest.startswith(alias) and len(rest) > len(alias) + 1:
            keyword = rest[len(alias):]
            return ParsedWikiCommand(
                keyword=aliases.get(keyword, keyword),
                query_type=alias,
                raw=text,
                auto_split=True,
            )

    return ParsedWikiCommand(keyword=aliases.get(rest, rest), raw=text, auto_split=True)


def _merged_aliases(user_aliases: dict[str, str] | None) -> dict[str, str]:
    """内置别名 + 用户自定义别名（用户优先）。"""
    if not user_aliases:
        return ALIASES
    merged = dict(ALIASES)
    merged.update({str(key).lower(): str(value) for key, value in user_aliases.items()})
    return merged


