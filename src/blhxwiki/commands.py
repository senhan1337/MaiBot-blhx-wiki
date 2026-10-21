"""命令入口与分发：wiki 查询、猜老婆、自定义回复、群开关。"""
from __future__ import annotations

import base64
import random
from typing import Any

from blhxwiki.config.config_data import PRIMARY_COMMANDS, TABLE_KEYWORDS, TABLE_LIST, VOICE_MAP
from blhxwiki.features import quiz, server, tech
from blhxwiki.models import QueryResult
from blhxwiki.parser.command_parser import RANK_NAMES, ParsedWikiCommand, parse_wiki_command
from blhxwiki.utils.cache import clear_cache
from blhxwiki.utils.text import extract_text

CUODAO_KEYWORDS = ("锉刀", "锉宝", "挫刀", "小锉锉")

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
        result = await dispatch(plugin, parsed, stream_id)

    await send(plugin, result, stream_id)
    return True, result.text or "[图片]", 2


async def dispatch(plugin, command: ParsedWikiCommand, stream_id: str) -> QueryResult:
    keyword = command.keyword
    query_type = command.query_type

    if keyword.lower() in ("help", "帮助", "指令"):
        image = plugin.renderer.help_image("help.png")
        return QueryResult(images=[image]) if image else QueryResult(text=help_text(plugin))

    if keyword == "clear":
        removed = clear_cache(plugin.ctx.paths.runtime_dir)
        return QueryResult(text=f"缓存清除成功喵（删除 {removed} 个文件）")

    reply = plugin.replies.get(keyword)
    if reply is not None:
        return QueryResult(text=reply)

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
    )
    return {"success": True, "content": result.text or "已生成图片。"}


async def handle_guess_wife(plugin, **kwargs) -> tuple:
    stream_id = kwargs.get("stream_id")
    if not plugin.config.plugin.enabled or not plugin.config.plugin.enable_guess_wife or not plugin.settings.guess_enabled(stream_id):
        reply = "本群未开启猜老婆功能喵"
        await plugin.ctx.send.text(reply, stream_id)
        return True, reply, 2
    if stream_id in plugin.quizzes:
        reply = "上一题还没回答正确哦~"
        await plugin.ctx.send.text(reply, stream_id)
        return True, reply, 2
    result = await quiz.start(plugin, stream_id)
    await send(plugin, result, stream_id)
    return True, result.text or "[图片]", 2


async def handle_quiz_answer(plugin, **kwargs):
    return await quiz.handle_answer(plugin, **kwargs)


async def handle_reply(plugin, **kwargs) -> tuple:
    stream_id = kwargs.get("stream_id")
    groups = kwargs.get("matched_groups", {})
    action = (groups.get("action") or "").lower()
    command = (groups.get("command") or "").strip()
    content = (groups.get("content") or "").strip()

    if action == "list":
        commands = plugin.replies.commands()
        reply = "现有自动回复指令：\n" + "\n".join(commands) if commands else "还没有设置自动回复指令喵"
    elif action == "delete":
        reply = "删除成功喵" if plugin.replies.delete(command) else "还没有该指令喵"
    elif action in ("set", "reset"):
        if not command or not content:
            reply = "格式：/reply set [指令] [回复]"
        else:
            ok = plugin.replies.set(command, content, overwrite=action == "reset")
            reply = "设置成功喵" if ok else "该指令已存在，覆盖请用 /reply reset"
    else:
        reply = "格式：/reply set|reset|delete|list"

    await plugin.ctx.send.text(reply, stream_id)
    return True, reply, 2


async def handle_config(plugin, **kwargs) -> tuple:
    stream_id = kwargs.get("stream_id")
    groups = kwargs.get("matched_groups", {})
    action = groups.get("action") or ""
    enabled = (groups.get("value") or "true").lower() == "true"

    if action == "clear":
        removed = clear_cache(plugin.ctx.paths.runtime_dir)
        reply = f"缓存清除成功喵（删除 {removed} 个文件）"
    elif action == "猜老婆":
        plugin.settings.set_guess(stream_id, enabled)
        reply = "设置成功喵"
    else:
        reply = "不支持的配置项喵"

    await plugin.ctx.send.text(reply, stream_id)
    return True, reply, 2


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


def help_text(plugin) -> str:
    return (
        "碧蓝航线 wiki MaiBot 插件命令：\n"
        "- wiki：显示帮助\n"
        "- wiki [舰娘]：查询舰娘基本属性，例如 wiki 拉菲\n"
        "- wiki [舰娘] 出处/皮肤/大图/皮肤原图/语音/科技点/配装/评价\n"
        "- wiki [装备]：查询装备，例如 wiki 533\n"
        "- wiki 榜单 / wiki [榜单名]，例如 wiki 装备一图榜\n"
        "- wiki 服务器状态 [国服/日服/国际服/繁中服]\n"
        "- 猜老婆\n"
        "支持无空格输入，例如 wiki拉菲皮肤"
    )
