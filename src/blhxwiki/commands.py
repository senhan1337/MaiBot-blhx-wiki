"""命令入口与分发：wiki 查询、猜老婆、群开关。"""
from __future__ import annotations

import base64
import random
from typing import Any

from blhxwiki.config.config_data import PRIMARY_COMMANDS, TABLE_KEYWORDS, TABLE_LIST, VOICE_MAP
from blhxwiki.features import quiz, server, tech
from blhxwiki.models import QueryResult
from blhxwiki.parser.command_parser import RANK_NAMES, ParsedWikiCommand, parse_wiki_command
from blhxwiki.utils.cache import clear_cache
from blhxwiki.utils.text import extract_text, user_id_from_kwargs

CUODAO_KEYWORDS = ("锉刀", "锉宝", "挫刀", "小锉锉")
ADMIN_DENIED = "该命令仅限管理员使用喵（可在 config.toml 的 admin_users 中配置）"

VOICE_LIST = "目前支持查询的语音有：\n" + "、".join(sorted(set(VOICE_MAP)))


async def handle_wiki(plugin, **kwargs) -> tuple:
    stream_id = kwargs.get("stream_id")
    if not plugin.config.plugin.enabled:
        reply = "碧蓝航线 wiki 插件当前未启用。"
        await plugin.ctx.send.text(reply, stream_id)
        return True, reply, 2

    text = extract_text(kwargs)
    # 兼容宿主可能带 @ 前缀、或剥离了命令前缀的情况。
    lowered = text.lower()
    for prefix in PRIMARY_COMMANDS:
        index = lowered.find(prefix)
        if index >= 0:
            text = text[index:]
            break
    else:
        if text:
            text = "wiki " + text
    plugin.ctx.logger.info("blhx_wiki keys=%s text=%r", sorted(kwargs), text)

    parsed = parse_wiki_command(text, plugin.user_aliases)
    if parsed is None:
        image = plugin.renderer.help_image("help.png")
        result = QueryResult(images=[image]) if image else QueryResult(text=help_text(plugin))
    else:
        result = await dispatch(plugin, parsed, stream_id, user_id=user_id_from_kwargs(kwargs))

    await send(plugin, result, stream_id)
    return True, result.text or "[图片]", 2


async def dispatch(plugin, command: ParsedWikiCommand, stream_id: str, user_id: str = "") -> QueryResult:
    keyword = command.keyword
    query_type = command.query_type

    if keyword.lower() in ("help", "帮助", "指令"):
        image = plugin.renderer.help_image("help.png")
        return QueryResult(images=[image]) if image else QueryResult(text=help_text(plugin))

    if keyword == "clear":
        if not is_admin(plugin, user_id):
            return QueryResult(text=ADMIN_DENIED)
        removed = clear_cache(plugin.ctx.paths.runtime_dir)
        return QueryResult(text=f"缓存清除成功喵（删除 {removed} 个文件）")

    if keyword == "猜老婆":
        mode = query_type.lower()
        if mode in ("true", "false"):
            if not is_admin(plugin, user_id):
                return QueryResult(text=ADMIN_DENIED)
            plugin.settings.set_guess(stream_id, mode == "true")
            return QueryResult(text="设置成功喵")
        return await guess_wife(plugin, stream_id)

    if keyword in CUODAO_KEYWORDS:
        return cuodao(plugin)

    if keyword in TABLE_KEYWORDS:
        return QueryResult(text=TABLE_LIST)

    if query_type in ("语音", "[语音]"):
        image = plugin.renderer.help_image("voice.png")
        return QueryResult(images=[image]) if image else QueryResult(text=VOICE_LIST)

    if keyword == "服务器状态":
        return await server.handle_server_state(plugin, command)

    if keyword == "筛选":
        return await tech.handle_tech_filter(plugin, command)

    if keyword in RANK_NAMES:
        return await plugin.renderer.query_page(keyword, "", stream_id=stream_id)

    voice_key = VOICE_MAP.get(query_type)
    return await plugin.renderer.query_page(keyword, query_type or "属性", voice_key, stream_id)


async def query_tool(plugin, keyword: str, query_type: str = "", **kwargs) -> dict:
    if not plugin.config.plugin.enabled:
        return {"success": False, "content": "碧蓝航线 wiki 插件当前未启用。"}
    result = await dispatch(
        plugin,
        ParsedWikiCommand(keyword=keyword, query_type=query_type, raw=keyword),
        kwargs.get("stream_id", ""),
        user_id=user_id_from_kwargs(kwargs),
    )
    # P2-13：结果直接发送到会话（图片不过模型，不占 token），LLM 只拿文字摘要。
    stream_id = kwargs.get("stream_id", "")
    if stream_id:
        await send(plugin, result, stream_id)
    return {"success": True, "content": result.text or "已发送查询结果图片。"}


async def guess_wife(plugin, stream_id: str) -> QueryResult:
    """wiki 猜老婆：开启一局；开关由 wiki 猜老婆 true/false 控制（admin_users）。"""
    if not plugin.config.plugin.enable_guess_wife or not plugin.settings.guess_enabled(stream_id):
        return QueryResult(text="本群未开启猜老婆功能喵")
    if stream_id in plugin.quizzes:
        return QueryResult(text="上一题还没回答正确哦~")
    return await quiz.start(plugin, stream_id)


async def handle_quiz_answer(plugin, **kwargs):
    return await quiz.handle_answer(plugin, **kwargs)


async def send(plugin, result: QueryResult, stream_id: str) -> None:
    if len(result.images) > 1:
        if not await send_forward(plugin, result.images, stream_id):
            for image in result.images:
                await plugin.ctx.send.image(base64.b64encode(image).decode("ascii"), stream_id)
    else:
        for image in result.images:
            await plugin.ctx.send.image(base64.b64encode(image).decode("ascii"), stream_id)
    if result.text:
        await plugin.ctx.send.text(result.text, stream_id)


async def send_forward(plugin, images: list[bytes], stream_id: str) -> bool:
    """多图合并转发；失败返回 False，由调用方回退逐张发送。"""
    segments = [
        {"type": "image", "content": base64.b64encode(image).decode("ascii")}
        for image in images
    ]
    for payload in ([{"segments": [segment]} for segment in segments], segments):
        try:
            await plugin.ctx.send.forward(payload, stream_id)
            return True
        except Exception as exc:  # noqa: BLE001
            plugin.ctx.logger.warning("合并转发失败: %s", exc)
    return False


def cuodao(plugin) -> QueryResult:
    path = plugin.assets_dir / "image" / "emoji" / f"cuodao_{random.randint(1, 4)}.jpg"
    if not path.exists():
        return QueryResult(text="锉刀图片缺失喵")
    return QueryResult(images=[path.read_bytes()])


def is_admin(plugin, user_id: str) -> bool:
    """敏感命令白名单校验：名单非空且包含该 QQ 号才放行。"""
    admins = [str(u) for u in plugin.config.plugin.admin_users]
    return bool(admins) and str(user_id) in admins


def help_text(plugin) -> str:
    return (
        "碧蓝航线 wiki MaiBot 插件命令：\n"
        "- wiki：显示帮助\n"
        "- wiki [舰娘]：查询舰娘基本属性，例如 wiki 拉菲\n"
        "- wiki [舰娘] 出处/皮肤/语音/科技点/配装/评价（大图/皮肤原图暂未实现）\n"
        "- wiki [装备]：查询装备，例如 wiki 533\n"
        "- wiki 榜单 / wiki [榜单名]，例如 wiki 装备一图榜\n"
        "- wiki 服务器状态 [国服/日服/国际服/繁中服]\n"
        "- 猜老婆\n"
        "支持无空格输入，例如 wiki拉菲皮肤"
    )
