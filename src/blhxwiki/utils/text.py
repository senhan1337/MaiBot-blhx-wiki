"""文本提取、配置索引加载与 URL 辅助。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from blhxwiki.parser.wiki_parser import normalize_keyword


def text_from(value: Any) -> str:
    """从字符串 / dict / 消息对象 / 消息段列表里尽力取出纯文本。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return join_segments(value)
    if isinstance(value, dict):
        for key in ("raw_message", "text", "content", "plain_text"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        for key in ("message", "segments", "raw_message"):
            segments = value.get(key)
            if isinstance(segments, list):
                text = join_segments(segments)
                if text:
                    return text
        return ""
    for attr in ("raw_message", "text", "content", "plain_text"):
        inner = getattr(value, attr, None)
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
    segments = getattr(value, "message", None)
    if isinstance(segments, list):
        return join_segments(segments)
    return ""


def join_segments(segments: list[Any]) -> str:
    parts: list[str] = []
    for segment in segments:
        if isinstance(segment, str):
            parts.append(segment)
            continue
        if not isinstance(segment, dict):
            data = getattr(segment, "data", None) or getattr(segment, "DATA", None)
            if isinstance(data, str):
                parts.append(data)
            elif isinstance(data, dict):
                text = data.get("text") or data.get("content") or data.get("TEXT")
                if isinstance(text, str):
                    parts.append(text)
            continue
        data = segment.get("data") or segment.get("DATA")
        if isinstance(data, str):
            parts.append(data)
        elif isinstance(data, dict):
            text = data.get("text") or data.get("content") or data.get("TEXT")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def extract_text(kwargs: dict[str, Any]) -> str:
    for key in ("raw_message", "message", "content", "text"):
        text = text_from(kwargs.get(key))
        if text:
            return text
    groups = kwargs.get("matched_groups")
    if isinstance(groups, dict):
        args = groups.get("args")
        if isinstance(args, str) and args.strip():
            return "wiki" + args
    return ""


def hook_message_text(message: Any, kwargs: dict[str, Any]) -> str:
    """Hook 消息文本：优先 processed_plain_text，其次消息段列表。"""
    if isinstance(message, dict):
        for key in ("processed_plain_text", "raw_message"):
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    text = text_from(message)
    if text:
        return text
    return text_from(kwargs.get("raw_message"))


def load_aliases(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key).lower(): str(value) for key, value in payload.items()}


def load_index(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {str(key): str(value) for key, value in payload.items()}


def pick_direct(results: list[str], keyword: str) -> str | None:
    normalized = normalize_keyword(keyword)
    if not normalized:
        return None
    for title in results:
        if normalize_keyword(title) == normalized:
            return title
    for title in results:
        if normalize_keyword(title).startswith(normalized):
            return title
    return None


def original_image_url(url: str) -> str:
    """把 wiki 缩略图 URL 还原成原图 URL。"""
    if "/thumb/" not in url:
        return url
    match = re.match(r"^(.*)/thumb/(.*?)/\d+px-[^/]+(\.[A-Za-z0-9]+)$", url)
    if match:
        return f"{match.group(1)}/{match.group(2)}{match.group(3)}"
    return url.replace("/thumb/", "/")
