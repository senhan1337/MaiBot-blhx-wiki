"""自定义回复，持久化到 data_dir/replies.json。"""
from __future__ import annotations

import json
from pathlib import Path


class Replies:
    """指令 → 回复文本。"""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "replies.json"
        self.data: dict[str, str] = {}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data = {str(k).lower(): str(v) for k, v in loaded.items()}
            except (OSError, ValueError):
                pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def get(self, command: str) -> str | None:
        return self.data.get(command.lower())

    def set(self, command: str, content: str, *, overwrite: bool = False) -> bool:
        key = command.lower()
        if key in self.data and not overwrite:
            return False
        self.data[key] = content
        self._save()
        return True

    def delete(self, command: str) -> bool:
        if self.data.pop(command.lower(), None) is None:
            return False
        self._save()
        return True

    def commands(self) -> list[str]:
        return sorted(self.data)
