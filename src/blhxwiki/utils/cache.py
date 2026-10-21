"""运行时缓存上限管理：超过上限时按修改时间删除最旧文件。"""
from __future__ import annotations

from pathlib import Path


def clear_cache(root: str | Path) -> int:
    """删除运行时目录下的全部文件；返回删除数量。"""
    directory = Path(root)
    if not directory.is_dir():
        return 0
    removed = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            path.unlink()
        except OSError:
            continue
        removed += 1
    return removed


def enforce_cache_limit(root: str | Path, max_mb: int) -> int:
    """删除最旧缓存直到总量不超过 max_mb；返回删除的文件数。"""
    if max_mb <= 0:
        return 0
    directory = Path(root)
    if not directory.is_dir():
        return 0

    max_bytes = max_mb * 1024 * 1024
    entries: list[tuple[float, int, Path]] = []
    total = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((stat.st_mtime, stat.st_size, path))
        total += stat.st_size

    if total <= max_bytes:
        return 0

    removed = 0
    for _, size, path in sorted(entries):
        try:
            path.unlink()
        except OSError:
            continue
        removed += 1
        total -= size
        if total <= max_bytes:
            break
    return removed
