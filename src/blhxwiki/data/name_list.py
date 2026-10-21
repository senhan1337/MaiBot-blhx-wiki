"""名称列表与数据更新。

缓存到 data_dir/names.json；启动时后台刷新，失败保留旧数据。
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from pathlib import Path
from urllib.parse import quote, urljoin

from blhxwiki.utils.http_utils import get as http_get
from blhxwiki.parser.wiki_parser import BASE_URL, parse_html

SHIP_LIST_URL = BASE_URL + quote("舰娘图鉴")
EQUIP_LIST_URL = BASE_URL + quote("装备")
BUILD_SIM_URL = BASE_URL + quote("建造模拟器")
CACHE_TTL = 7 * 24 * 3600


class NameList:
    """舰娘/装备名称列表，用于模糊搜索与自动分词校验。"""

    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "names.json"
        self.ships: list[str] = []
        self.equips: list[str] = []
        self.icons: dict[str, str] = {}
        self.updated_at = 0.0
        self._load()

    @property
    def all(self) -> list[str]:
        return self.ships + self.equips

    def icon_url(self, name: str) -> str | None:
        return self.icons.get(name)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.ships = [str(item) for item in payload.get("ships", [])]
            self.equips = [str(item) for item in payload.get("equips", [])]
            self.icons = {str(k): str(v) for k, v in payload.get("icons", {}).items()}
            self.updated_at = float(payload.get("updated_at", 0))
        except (OSError, ValueError, TypeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "ships": self.ships,
                    "equips": self.equips,
                    "icons": self.icons,
                    "updated_at": self.updated_at,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def stale(self) -> bool:
        return not self.ships or time.time() - self.updated_at > CACHE_TTL

    async def refresh(self, force: bool = False) -> bool:
        """刷新名称列表、头像映射与常驻池；成功返回 True。"""
        if not force and not self.stale():
            return True

        ships = await _fetch_ship_names()
        equips = await _fetch_equip_names()
        icons = await _fetch_icon_map()
        if ships:
            self.ships = ships
        if equips:
            self.equips = equips
        if icons:
            self.icons = icons
        if ships or equips or icons:
            self.updated_at = time.time()
            self._save()

        return bool(ships or equips)


async def _fetch_ship_names() -> list[str]:
    html = await http_get(SHIP_LIST_URL)
    if not html:
        return []
    soup = parse_html(html)
    container = soup.select_one("div#CardSelectTr")
    if container is None:
        return []
    names = []
    for span in container.select("span.jntj-4"):
        for link in span.select("a"):
            title = link.get("title", "")
            if title:
                names.append(title.replace(" ", "_").lower())
    return names


async def _fetch_equip_names() -> list[str]:
    html = await http_get(EQUIP_LIST_URL)
    if not html:
        return []
    soup = parse_html(html)
    container = soup.select_one("div.panel-body.tab-content")
    if container is None:
        return []
    names = []
    for link in container.select("a"):
        title = link.get("title", "")
        if title:
            names.append(title.replace(" ", "_").lower())
    return names


async def _fetch_icon_map() -> dict[str, str]:
    """舰娘头像映射：名称 → 原图 URL。"""
    html = await http_get(SHIP_LIST_URL)
    if not html:
        return {}
    soup = parse_html(html)
    container = soup.select_one("div#CardSelectTr")
    if container is None:
        return {}
    icons: dict[str, str] = {}
    for img in container.select("img"):
        src = img.get("src", "")
        name = img.get("alt", "").replace("头像.jpg", "")
        if not name or name.startswith("舰娘头像") or not src:
            continue
        url = src.replace("/thumb", "")
        url = re.split(r"/60px", url)[0]
        icons[name] = urljoin(BASE_URL, url)
    return icons


async def refresh_in_background(names: NameList, logger=None) -> None:
    """on_load 中调用：不阻塞加载，失败只记日志。"""
    try:
        ok = await names.refresh()
        if logger is not None:
            logger.info("名称列表刷新%s（舰娘 %d / 装备 %d）", "成功" if ok else "失败", len(names.ships), len(names.equips))
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            logger.warning("名称列表刷新异常: %s", exc)


def create_background_task(names: NameList, logger=None) -> asyncio.Task:
    return asyncio.create_task(refresh_in_background(names, logger))
