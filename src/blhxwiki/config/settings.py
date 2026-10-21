"""群级开关与插件设置，持久化到 data_dir/settings.json。"""
from __future__ import annotations

import json
from pathlib import Path


class Settings:
    """按 stream_id 记录猜老婆开关。"""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "settings.json"
        self.data: dict[str, list[str]] = {"guess_ban": []}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for key in self.data:
                    if isinstance(loaded.get(key), list):
                        self.data[key] = [str(item) for item in loaded[key]]
            except (OSError, ValueError):
                pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def guess_enabled(self, stream_id: str) -> bool:
        return stream_id not in self.data["guess_ban"]

    def set_guess(self, stream_id: str, enabled: bool) -> None:
        self._update("guess_ban", stream_id, add=not enabled)

    def _update(self, key: str, stream_id: str, *, add: bool) -> None:
        values = self.data[key]
        if add and stream_id not in values:
            values.append(stream_id)
        elif not add and stream_id in values:
            values.remove(stream_id)
        self._save()
