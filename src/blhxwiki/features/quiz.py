"""猜老婆小游戏：出题、状态机与答案拦截。

立绘每局从 wiki 动态抓取（内存裁切后即弃，不落盘），wiki clear / 清缓存不影响。
"""
from __future__ import annotations

import asyncio
import io
import random
import time
from dataclasses import dataclass
from urllib.parse import urljoin
from typing import Any

from blhxwiki.models import QueryResult
from blhxwiki.parser.wiki_parser import BASE_URL, build_page_url, parse_html
from blhxwiki.utils.http_utils import get as http_get, get_bytes
from blhxwiki.utils.text import hook_message_text

QUIZ_TIMEOUT = 30.0
QUIZ_SIZE = 6
QUIZ_TRIES = 3  # 答案立绘并行候选数：占坑页/无图/网络失败时换人重试
QUIZ_WRONG = (" 回答错误哦~", " 差一点就对了(｀・ω・´)", " 不对哦(｡･ω･｡)", " 没有答对哦(=´ω｀=)")
QUIZ_RIGHT = " 回答正确φ(>ω<*)"


@dataclass(slots=True)
class Quiz:
    choices: dict[str, str]
    answer: str
    stream_id: str
    deadline: float  # 单调时钟到期时间；所有清理动作必须核对同一局，防止旧任务误清新一局


async def start(plugin, stream_id: str) -> QueryResult:
    names = list(plugin.names.ships or [])
    if len(names) < QUIZ_SIZE:
        return QueryResult(text="舰娘名单尚未就绪，请稍后再试喵")

    answer_name, art = await _fetch_answer_art(plugin, names)
    if art is None:
        return QueryResult(text="舰娘图片获取失败喵，请检查网络后重试")

    wrong = random.sample([n for n in names if n != answer_name], QUIZ_SIZE - 1)
    picks = [answer_name] + wrong
    random.shuffle(picks)
    letters = [chr(ord("A") + index) for index in range(QUIZ_SIZE)]
    choices = {letter: name for letter, name in zip(letters, picks)}
    answer_letter = next(letter for letter, name in choices.items() if name == answer_name)
    quiz = Quiz(
        choices=choices, answer=answer_letter, stream_id=stream_id,
        deadline=time.monotonic() + QUIZ_TIMEOUT,
    )
    plugin.quizzes[stream_id] = quiz
    asyncio.create_task(_timeout(plugin, stream_id, quiz.deadline))

    options = "\n".join(f"{letter}. {name}" for letter, name in choices.items())
    image = _crop(art)
    return QueryResult(text=options, images=[image] if image else [])


def _pick_candidates(names: list[str], count: int) -> list[str]:
    """抽 count 个不重复候选名（答案 + 备选），纯函数便于测试。"""
    pool = [n for n in names if n]
    if len(pool) <= count:
        return pool
    return random.sample(pool, count)


async def _fetch_answer_art(plugin, names: list[str]) -> tuple[str, bytes | None]:
    """抽一个舰娘当答案并抓它的立绘；失败换人重试（并行候选，先到先用）。"""
    candidates = _pick_candidates(names, QUIZ_TRIES)
    results = await asyncio.gather(*(_fetch_ship_art(plugin, name) for name in candidates))
    for name, art in results:
        if art:
            return name, art
    return (candidates[0] if candidates else ""), None


async def _fetch_ship_art(plugin, name: str) -> tuple[str, bytes | None]:
    """抓一个舰娘页的立绘缩略图；占坑页/无图/网络失败返回 (name, None)。"""
    try:
        html = await http_get(build_page_url(name), timeout=plugin.renderer.timeout)
        if not html:
            return name, None
        img = parse_html(html).select_one("div.Contentbox2 img")
        src = img.get("src", "") if img is not None else ""
        if not src:
            return name, None
        art = await get_bytes(urljoin(BASE_URL, src), timeout=plugin.renderer.timeout)
        return name, art or None
    except Exception:  # noqa: BLE001
        return name, None


async def _timeout(plugin, stream_id: str, deadline: float) -> None:
    await asyncio.sleep(max(0.0, deadline - time.monotonic()))
    quiz = plugin.quizzes.get(stream_id)
    # 核对同一局：答对已清场、或已开出新一局时不发旧答案（否则「超时秒到」）
    if quiz is not None and quiz.deadline == deadline and plugin.quizzes.pop(stream_id, None) is quiz:
        await plugin.ctx.send.text(f"回答超时~，正确答案是{quiz.answer}哒！", stream_id)


def _crop(data: bytes, size: int = 150) -> bytes | None:
    """从立绘随机裁一块，尽量避开透明区域。"""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGBA")
    except Exception:  # noqa: BLE001
        return None
    if image.width < size or image.height < size:
        image = image.resize(
            (max(size, image.width), max(size, image.height)), Image.Resampling.LANCZOS
        )

    piece = image.crop((0, 0, size, size))
    for _ in range(20):
        left = random.randrange(0, image.width - size + 1)
        top = random.randrange(0, image.height - size + 1)
        piece = image.crop((left, top, left + size, top + size))
        transparent = sum(1 for value in piece.getchannel("A").getdata() if value == 0)
        if transparent < size * size // 2:
            break
    output = io.BytesIO()
    piece.save(output, "PNG")
    return output.getvalue()


async def handle_answer(plugin, **kwargs):
    """拦截 A-F 答案；命中当前群的猜老婆题目时回复并中止消息链。"""
    message = kwargs.get("message", {}) or {}
    stream_id = _stream_id(message, kwargs)
    text = hook_message_text(message, kwargs).upper()
    quiz = plugin.quizzes.get(stream_id)
    if quiz is None:
        return {"action": "continue", "modified_kwargs": kwargs}
    if time.monotonic() > quiz.deadline:
        # 到期兜底：后台定时器在空闲期可能滞后，靠消息流量及时收尾并放行本条消息
        if plugin.quizzes.pop(stream_id, None) is quiz:
            await plugin.ctx.send.text(f"回答超时~，正确答案是{quiz.answer}哒！", stream_id)
        return {"action": "continue", "modified_kwargs": kwargs}
    if text not in quiz.choices:
        return {"action": "continue", "modified_kwargs": kwargs}

    if text == quiz.answer:
        # 核对同一局再清场，答对与超时任务并发时只发一条结果
        if plugin.quizzes.pop(stream_id, None) is quiz:
            await plugin.ctx.send.text(QUIZ_RIGHT, stream_id)
    else:
        await plugin.ctx.send.text(random.choice(QUIZ_WRONG), stream_id)
    return {"action": "abort"}


def _stream_id(message: Any, kwargs: dict[str, Any]) -> str:
    sources: list[Any] = [message, kwargs]
    chat = message.get("chat") if isinstance(message, dict) else None
    if chat is not None:
        sources.append(chat)
    for source in sources:
        if not isinstance(source, dict):
            continue
        for key in ("stream_id", "chat_id", "session_id"):
            value = source.get(key)
            if isinstance(value, str) and value:
                return value
    return ""
