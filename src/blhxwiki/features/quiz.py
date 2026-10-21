"""猜老婆小游戏：出题、状态机与答案拦截。"""
from __future__ import annotations

import asyncio
import io
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from blhxwiki.models import QueryResult
from blhxwiki.utils.text import hook_message_text

QUIZ_TIMEOUT = 30.0
QUIZ_SIZE = 6
QUIZ_WRONG = (" 回答错误哦~", " 差一点就对了(｀・ω・´)", " 不对哦(｡･ω･｡)", " 没有答对哦(=´ω｀=)")
QUIZ_RIGHT = " 回答正确φ(>ω<*)"


@dataclass(slots=True)
class Quiz:
    choices: dict[str, str]
    answer: str
    stream_id: str


async def start(plugin, stream_id: str) -> QueryResult:
    images = _images(plugin)
    if len(images) < QUIZ_SIZE:
        return QueryResult(text="本地没有足够的舰娘图片喵（先查询几次舰娘或使用 /wikiconfig 下载头像）")

    picks = random.sample(images, QUIZ_SIZE)
    letters = [chr(ord("A") + index) for index in range(QUIZ_SIZE)]
    choices = {letter: name for letter, (_, name) in zip(letters, picks)}
    answer_letter = random.choice(letters)
    answer_path = picks[letters.index(answer_letter)][0]
    plugin.quizzes[stream_id] = Quiz(choices=choices, answer=answer_letter, stream_id=stream_id)
    asyncio.create_task(_timeout(plugin, stream_id))

    options = "\n".join(f"{letter}. {name}" for letter, name in choices.items())
    image = _crop(answer_path)
    return QueryResult(text=options, images=[image] if image else [])


def _images(plugin) -> list[tuple[Path, str]]:
    images: list[tuple[Path, str]] = []
    ship_dir = Path(plugin.ctx.paths.runtime_dir) / "ship"
    if ship_dir.is_dir():
        images.extend(
            (path, path.stem)
            for path in ship_dir.iterdir()
            if path.suffix.lower() in (".png", ".jpg", ".jpeg")
        )
    return images


async def _timeout(plugin, stream_id: str) -> None:
    await asyncio.sleep(QUIZ_TIMEOUT)
    quiz = plugin.quizzes.pop(stream_id, None)
    if quiz is not None:
        await plugin.ctx.send.text(f"回答超时~，正确答案是{quiz.answer}哒！", stream_id)


def _crop(path: Path, size: int = 200) -> bytes | None:
    """从立绘/头像随机裁一块，尽量避开透明区域。"""
    from PIL import Image

    try:
        with Image.open(path) as source:
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
    if quiz is not None or text in ("A", "B", "C", "D", "E", "F"):
        plugin.ctx.logger.info(
            "quiz_hook keys=%s msg_keys=%s stream_id=%r text=%r active=%s",
            sorted(kwargs),
            sorted(message) if isinstance(message, dict) else type(message).__name__,
            stream_id,
            text,
            quiz is not None,
        )
    if quiz is None or text not in quiz.choices:
        return {"action": "continue", "modified_kwargs": kwargs}

    if text == quiz.answer:
        plugin.quizzes.pop(stream_id, None)
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
