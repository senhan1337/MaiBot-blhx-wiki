"""服务器状态查询。"""
from __future__ import annotations

from blhxwiki.models import QueryResult
from blhxwiki.paint.drawing import generate_server_state_image
from blhxwiki.parser.command_parser import ParsedWikiCommand
from blhxwiki.utils.server_state import REGION_NAMES, get_server_states


async def handle_server_state(plugin, command: ParsedWikiCommand) -> QueryResult:
    region_name = command.query_type or "国服"
    region = REGION_NAMES.get(region_name)
    if region is None:
        return QueryResult(text=f"未找到该区服喵，可选：{'/'.join(REGION_NAMES)}")

    states = await get_server_states(region)
    if not states:
        return QueryResult(text="服务器状态查询失败：该区服网关无响应，请稍后再试喵")

    image = generate_server_state_image(
        [
            {"name": state.name, "region": region_name, "maintenance": state.state == 1}
            for state in states
        ],
        assets_dir=plugin.assets_dir,
    )
    return QueryResult(images=[image.getvalue()])
