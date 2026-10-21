"""舰队科技点数据。

缓存到 data_dir/tech_points.json；按舰种/科技分类分组，供筛选表使用。
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

from blhxwiki.utils.http_utils import get as http_get
from blhxwiki.parser.wiki_parser import BASE_URL, parse_html

TECH_URL = BASE_URL + quote("舰队科技")

RARITY_ORDER = ("海上传奇", "决战方案", "超稀有", "精锐", "稀有", "普通")


class TechPoints:
    def __init__(self, data_dir: str | Path) -> None:
        self.path = Path(data_dir) / "tech_points.json"
        self.ship_classes: list[str] = []
        self.tech_classes: list[str] = []
        self.data: dict[str, dict[str, list[list[str]]]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            self.ship_classes = [str(item) for item in payload.get("ship_classes", [])]
            self.tech_classes = [str(item) for item in payload.get("tech_classes", [])]
            self.data = payload.get("data", {})
        except (OSError, ValueError, TypeError):
            pass

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {
                    "ship_classes": self.ship_classes,
                    "tech_classes": self.tech_classes,
                    "data": self.data,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def rows(self, ship_class: str, tech_class: str) -> list[list[str]]:
        return self.data.get(ship_class, {}).get(tech_class, [])

    def ready(self) -> bool:
        return bool(self.data)

    async def refresh(self) -> bool:
        html = await http_get(TECH_URL)
        if not html:
            return False
        soup = parse_html(html)
        rows = soup.select("#CardSelectTr > tbody > tr")
        if not rows:
            return False

        entries: list[tuple[str, str, str, str, list[str]]] = []
        ship_classes: list[str] = []
        tech_classes: list[str] = []
        for row in rows:
            ship_class = row.get("data-param1", "").split(",")[0]
            if not ship_class:
                continue
            rarity = row.get("data-param2", "")
            obtain_class = row.get("data-param9", "")
            up120_class = row.get("data-param10", "")
            cells = row.select("td")
            if len(cells) < 10:
                continue
            name_cell = cells[1].select_one("a span")
            ship_name = name_cell.get_text(" ", strip=True) if name_cell is not None else ""
            item = [
                ship_name,
                cells[2].get_text(" ", strip=True),
                rarity,
                cells[8].get_text(" ", strip=True),
                cells[9].get_text(" ", strip=True),
            ]
            entries.append((ship_class, obtain_class, up120_class, "", item))
            if ship_class not in ship_classes:
                ship_classes.append(ship_class)
            for tech_class in (obtain_class, up120_class):
                if tech_class and tech_class not in tech_classes:
                    tech_classes.append(tech_class)

        data: dict[str, dict[str, list[list[str]]]] = {
            ship_class: {tech_class: [] for tech_class in tech_classes}
            for ship_class in ship_classes
        }
        for ship_class, obtain_class, up120_class, _, item in entries:
            if obtain_class == up120_class:
                if obtain_class in data[ship_class]:
                    data[ship_class][obtain_class].append(item)
                continue
            if obtain_class in data[ship_class]:
                data[ship_class][obtain_class].append(item)
            if up120_class in data[ship_class]:
                data[ship_class][up120_class].append(item)

        self.ship_classes = ship_classes
        self.tech_classes = tech_classes
        self.data = data
        self._save()
        return True


async def refresh_in_background(tech: TechPoints, logger=None) -> None:
    try:
        ok = await tech.refresh()
        if logger is not None:
            logger.info("科技点数据刷新%s", "成功" if ok else "失败")
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            logger.warning("科技点数据刷新异常: %s", exc)
