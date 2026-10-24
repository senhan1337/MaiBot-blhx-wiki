"""资源文件名编码：中文名 → ASCII key（UTF-8 hex），避免 ZIP/跨平台文件名乱码。"""
from __future__ import annotations


def asset_key(name: str) -> str:
    return name.encode("utf-8").hex()
