"""舰队科技筛选表。"""
from __future__ import annotations

from blhxwiki.models import QueryResult
from blhxwiki.paint.components import generate_tech_table
from blhxwiki.parser.command_parser import ParsedWikiCommand


async def handle_tech_filter(plugin, command: ParsedWikiCommand) -> QueryResult:
    args = command.args or []
    if len(args) < 4:
        return QueryResult(text="格式：wiki 筛选 [舰种] [科技分类] [页码]\n例如：wiki 筛选 驱逐 耐久 1")
    ship_class, tech_class = args[1], args[2]
    try:
        page = int(args[3])
    except ValueError:
        page = 1

    if not plugin.tech.ready():
        await plugin.tech.refresh()
    if not plugin.tech.ready():
        return QueryResult(text="科技点数据尚未就绪，请稍后再试喵")
    if ship_class not in plugin.tech.ship_classes:
        return QueryResult(text=f"没有这个舰种喵，可选：{'/'.join(plugin.tech.ship_classes)}")
    if tech_class not in plugin.tech.tech_classes:
        return QueryResult(text=f"没有这个科技分类喵，可选：{'/'.join(plugin.tech.tech_classes)}")

    rows = plugin.tech.rows(ship_class, tech_class)
    if not rows:
        return QueryResult(text="没有找到对应的科技点数据喵")
    try:
        image = generate_tech_table(rows, page, assets_dir=plugin.assets_dir)
    except ValueError as exc:
        return QueryResult(text=str(exc))
    return QueryResult(images=[image.getvalue()])
