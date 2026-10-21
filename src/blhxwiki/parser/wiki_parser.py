"""wiki 页面解析。

解析结果用 dict 返回，展示层（plugin.py）负责渲染成文本/图片。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

BASE_URL = "https://wiki.biligame.com/blhx/"
SEARCH_URL = BASE_URL + "index.php?search="

EQUIP_TYPES = ("鱼雷", "防空炮", "舰炮", "设备", "舰载机", "导弹")
CAMPS = (
    "白鹰", "皇家", "重樱", "铁血", "东煌", "哔哩哔哩", "撒丁帝国",
    "北方联合", "自由鸢尾", "维希教廷",
)
RARITY_LEVELS = {
    "海上传奇": 5, "超稀有": 4, "精锐": 3, "稀有": 2, "普通": 1,
    "最高方案": 24, "决战方案": 25,
}


def parse_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def detect_page_type(soup: BeautifulSoup) -> str | None:
    """按页面结构判断类型。"""
    h1 = soup.select_one("h1#firstHeading")
    heading = h1.get_text(" ", strip=True) if h1 else ""

    if heading == "搜索结果":
        return "search"

    home = soup.select_one("a[title='首页']")
    if home is not None:
        sibling = home.find_next_sibling()
        title = sibling.get("title", "") if sibling is not None else ""
        if title == "舰娘图鉴":
            return "ship"
        if title in EQUIP_TYPES:
            return "equip"
        if title == "特殊兵装":
            return "special_equip"

    if re.search("[榜表]", heading):
        return "table"
    categories = soup.select_one("div#mw-normal-catlinks")
    if categories is not None and "关卡图鉴" in categories.get_text(" ", strip=True):
        return "level"
    return None


def parse_page(
    html: str, keyword: str, query_type: str = "", voice_key: str | None = None
) -> dict[str, Any] | None:
    """解析一个 wiki 页面；无法识别时返回 None。"""
    soup = parse_html(html)
    page_type = detect_page_type(soup)
    if page_type is None:
        return None

    if page_type == "search":
        return {"type": "search", "data": {"results": parse_search_results(soup, keyword)}}
    if page_type == "ship":
        return parse_ship(soup, query_type, voice_key)
    if page_type == "equip":
        return parse_equip(soup, query_type)
    if page_type == "special_equip":
        return {"type": "special_equip", "data": parse_special_equip(soup)}
    if page_type == "table":
        return {"type": "rank", "data": {"images": parse_rank_images(soup, keyword)}}
    if page_type == "level":
        return {"type": "level", "data": parse_level(soup)}
    return None


# ----------------------------------------------------------------------
# 舰娘
# ----------------------------------------------------------------------
def parse_ship(soup: BeautifulSoup, query_type: str, voice_key: str | None) -> dict[str, Any]:
    for big in soup.select("big b"):
        if "这是某人挖的一个坑" in big.get_text(" ", strip=True):
            return {"type": "text", "data": {"text": "是还没有实装的舰娘呢"}}

    attr = parse_ship_attr(soup)
    if voice_key is not None:
        return {"type": "voice", "data": {"url": parse_voice(soup, voice_key)}}
    if not query_type or query_type in ("属性", "基本信息", "基本"):
        return {"type": "ship_attr", "data": attr}
    if query_type in ("出处", "建造", "来源", "获得途径"):
        return {"type": "ship_source", "data": attr}
    if query_type in ("皮肤", "换装"):
        return {"type": "images", "data": {"images": parse_ship_skins(soup)}}
    if query_type in ("语音",):
        return {"type": "voice", "data": {"url": parse_voice(soup, voice_key)}}
    if query_type in ("科技点", "科技", "舰队科技"):
        return {"type": "text", "data": {"text": parse_ship_tech(soup, attr.get("name", ""))}}
    if query_type == "评价":
        return {"type": "text", "data": {"text": parse_ship_evaluate(soup)}}
    if query_type in ("装备", "出装", "配装"):
        return {"type": "ship_equip", "data": parse_ship_equip(soup)}
    if query_type in ("原皮", "大图", "皮肤原图", "皮肤大图", "婚皮原图", "婚皮大图", "婚纱原图", "婚纱大图"):
        return {"type": "local_image", "data": {"name": attr.get("name", ""), "kind": query_type}}
    if query_type in ("改造", "改"):
        return {"type": "text", "data": {"text": "改造解析暂未迁移喵"}}
    return {"type": "ship_attr", "data": attr}


def parse_ship_attr(soup: BeautifulSoup) -> dict[str, Any]:
    general = soup.select("table.wikitable.sv-general")
    if not general:
        raise ValueError("未找到舰娘通用表")
    rows = general[0].select("tr")

    name_bits = [b.get_text(" ", strip=True) for b in rows[0].select("b")]
    result: dict[str, Any] = {
        "name": "",
        "code": "",
        "type": rows[1].select("td")[4].get_text(" ", strip=True) if len(rows[1].select("td")) > 4 else "",
        "rarity": "",
        "camp": "",
        "time": "",
        "normal_from": "",
        "active_from": "",
        "file_from": "",
        "other_from": "",
        "active": "",
        "pic": "",
        "can_upgrade": bool(soup.select_one("span#改造详情")),
        "attributes": {},
        "skills": [],
        "equip_detail": [],
    }

    rarity = rows[2].select_one("span#PNrarity")
    result["rarity"] = rarity.get_text(" ", strip=True) if rarity else ""
    camp_cells = rows[2].select("td")
    result["camp"] = camp_cells[3].get_text(" ", strip=True) if len(camp_cells) > 3 else ""

    for row in rows[3:]:
        cells = row.select("td")
        if len(cells) < 2:
            continue
        # 页面里标签常被拆成“建造 时间”“普通 掉落点”，去掉空白再匹配。
        label = re.sub(r"\s+", "", cells[0].get_text(" ", strip=True))
        value = cells[1].get_text(" ", strip=True)
        if "建造时间" in label:
            result["time"] = value
        elif "普通掉落点" in label:
            result["normal_from"] = value
        elif "活动掉落点" in label:
            result["active_from"] = value
        elif "档案掉落点" in label:
            result["file_from"] = value
        elif "相关活动" in label:
            result["active"] = value
        elif "其他途径" in label:
            result["other_from"] = value
    if result["time"]:
        result["time"] = result["time"].replace("活动", f"{result['active']}活动")

    if result["can_upgrade"]:
        span = soup.select_one("span#改造详情")
        sibling = span.parent.find_next_sibling() if span and span.parent else None
        if sibling is not None:
            cell = sibling.select_one("td")
            if cell is not None:
                result["type"] = cell.get_text(" ", strip=True).split(" ")[-1]

    index = 0
    if name_bits and result["camp"] in CAMPS and "μ" not in name_bits[0]:
        index += 1
    name = name_bits[index] if index < len(name_bits) else ""
    if result["can_upgrade"]:
        name += ".改"
    index += 1
    if index < len(name_bits) - 2:
        name += name_bits[index].replace("·META", "")
        index += 1
    code = name_bits[index] if index < len(name_bits) else ""
    if name == "HMS Little Cheshire":
        name, code = "小柴郡", "HMS Little Cheshire"
    result["name"] = name
    result["code"] = code

    content_box = soup.select("div.Contentbox2")
    if content_box:
        divs = content_box[0].select("div")
        try:
            target = divs[-2] if result["can_upgrade"] and len(divs) >= 2 else divs[0]
            img = target.select_one("img")
            result["pic"] = urljoin(BASE_URL, img.get("src", "")) if img else ""
        except IndexError:
            result["pic"] = ""

    result["attributes"] = _parse_ship_attributes(soup)
    result["skills"] = _parse_skills(soup, result["can_upgrade"])
    result["equip_detail"] = _parse_equip_efficiency(soup, result["can_upgrade"])
    return result


def _parse_ship_attributes(soup: BeautifulSoup) -> dict[str, str]:
    tables = soup.select("table.wikitable.sv-performance")
    if len(tables) < 2:
        return {}
    rows = tables[1].select("tr")
    cells: list[Any] = []
    for row in rows[1:8]:
        cells.extend(row.select("td"))

    key_map = {
        "耐久": "naijiu", "装甲": "zhuangjia", "装填": "zhuangtian", "炮击": "paoji",
        "雷击": "leiji", "机动": "jidong", "防空": "fangkong", "航空": "hangkong",
        "命中": "mingzhong", "反潜": "fanqian", "幸运": "xingyun", "消耗": "xiaohao",
        "航速": "hangsu", "氧气": "yangqi", "弹药量": "danyao",
    }
    attributes: dict[str, str] = {}
    for index, cell in enumerate(cells):
        label = cell.get_text(" ", strip=True)
        if label in key_map and index + 1 < len(cells):
            attributes[key_map[label]] = _attribute_value(cells[index + 1])
    return attributes


def _attribute_value(cell: Any) -> str:
    tj = cell.select_one("span.tjmode1")
    if tj is not None:
        value = tj.get_text(" ", strip=True).split("→")[-1]
        if value.startswith("{") or not value:
            tj0 = cell.select_one("span.tjmode0")
            value = tj0.get_text(" ", strip=True).split("→")[-1] if tj0 else ""
        return value
    return cell.get_text(" ", strip=True).split("→")[-1]


def _parse_skills(soup: BeautifulSoup, can_upgrade: bool) -> list[dict[str, str]]:
    tables = soup.select("table.wikitable.sv-skill")
    if not tables:
        return []
    skills: list[dict[str, str]] = []
    for row in tables[0].select("tr")[2 if can_upgrade else 1:]:
        classes = row.get("class", [])
        hidden = row.get("style") == "display:none"
        # 隐藏行只有改造后技能（tjmode1）才保留。
        if hidden and not (can_upgrade and "tjmode1" in classes):
            continue
        cells = row.select("td")
        if len(cells) < 2:
            continue
        detail = cells[1].get_text(" ", strip=True)
        tabs = cells[1].select("div.resp-tab-content")
        if len(tabs) >= 2:
            detail = tabs[0].get_text(" ", strip=True)
        name = cells[0].get_text(" ", strip=True)
        if "（天运拟合" in detail:
            name += "+"
            detail = detail.split("+：")[-1]
        img = cells[0].select_one("img")
        skills.append({
            "name": name,
            "pic": urljoin(BASE_URL, img.get("src", "")) if img else "",
            "detail": detail,
        })
    return skills


def _parse_equip_efficiency(soup: BeautifulSoup, can_upgrade: bool) -> list[dict[str, str]]:
    tables = soup.select("table.wikitable.sv-equipment")
    if not tables:
        return []
    rows = tables[0].select("tr")
    details = [{"index": "槽位", "name": "装备类型", "efficiency": "效率", "count": "武器数", "prefill_count": "预装填数"}]
    keys = ("index", "name", "efficiency", "count", "prefill_count")
    for offset in range(2, 5):
        index = offset + (1 if can_upgrade else 0)
        if index >= len(rows):
            continue
        cells = rows[index].select("td")
        if len(cells) < 5:
            continue
        item = {}
        for position, key in enumerate(keys):
            span = cells[position].select_one("span.tjmode1")
            item[key] = span.get_text(" ", strip=True) if span else cells[position].get_text(" ", strip=True)
        details.append(item)
    return details


def parse_ship_skins(soup: BeautifulSoup) -> list[str]:
    content_box = soup.select("div.Contentbox2")
    if not content_box:
        return []
    images = []
    for img in content_box[0].select("img")[1:]:
        src = img.get("src", "")
        if src:
            images.append(urljoin(BASE_URL, src))
    return images


def parse_voice(soup: BeautifulSoup, voice_key: str | None) -> str | None:
    if not voice_key:
        return None
    links = []
    for row in soup.select("table.table-ShipWordsTable tr"):
        if row.get("data-key") == voice_key:
            for link in row.select("a"):
                href = link.get("href", "")
                if href:
                    links.append(urljoin(BASE_URL, href))
    if not links:
        return None
    import random
    return random.choice(links)


def parse_ship_tech(soup: BeautifulSoup, name: str) -> str:
    tables = soup.select("table.wikitable.sv-category")
    if not tables:
        return "没有找到科技点数据喵"
    rows = tables[0].select("tr")

    def find(prefix: str):
        for row in rows:
            cells = row.select("td")
            if cells and cells[0].get_text(" ", strip=True).startswith(prefix):
                return row
        return None

    def cell(row, index: int) -> str:
        cells = row.select("td") if row is not None else []
        return cells[index].get_text(" ", strip=True) if len(cells) > index else ""

    def bonus(row) -> str:
        cells = row.select("td") if row is not None else []
        return cells[-1].get_text(" ", strip=True) if cells else "-"

    obtain = find("获得")
    full = find("满星")
    level120 = find("Lv.120") or find("120")
    if obtain is None:
        return "没有找到科技点数据喵"

    point = cell(obtain, 1)
    if point == "+":
        return "该舰娘不提供科技点哦~"
    return (
        f"{name}\n"
        f"获取时科技点{point}\n"
        f"满星时科技点{cell(full, 1)}\n"
        f"120级时科技点{cell(level120, 1)}\n"
        f"属性加成:\n"
        f"获取时 {bonus(obtain)}\n"
        f"120级时 {bonus(level120)}"
    )


def parse_ship_evaluate(soup: BeautifulSoup) -> str:
    tables = soup.select("table.wikitable.sv-remark")
    if not tables:
        return "还没有人对该舰娘评价哦~"
    rows = tables[0].select("tr")
    if len(rows) < 2:
        return "还没有人对该舰娘评价哦~"
    text = rows[1].get_text("\n", strip=True)
    return text or "还没有人对该舰娘评价哦~"


def parse_ship_equip(soup: BeautifulSoup) -> dict[str, Any]:
    """配装推荐：结构化返回（对齐 ShipEquipData）。

    wiki 改版后配装行是最后一个 div.row，每列一个 div（内含 1 张表）。
    """
    rows = soup.select("div.row")
    table_columns: list[Any] = []
    for row in reversed(rows):
        columns = [
            child
            for child in row.children
            if hasattr(child, "find_all") and len(child.find_all("table", recursive=False)) == 1
        ]
        if len(columns) >= 4:
            table_columns = columns
            break

    equip_lists: list[list[dict[str, Any]]] = []
    for column_node in table_columns:
        table = column_node.find("table", recursive=False)
        if table is None:
            continue
        column: list[dict[str, Any]] = []
        for row in table.select("tbody tr"):
            cell = row.select_one("td")
            if cell is None:
                continue
            style = cell.get("style", "")
            bg_color = (255, 255, 255)
            font_color = (0, 0, 0)
            match = re.search(r"background:(#[^;]+)", style)
            if match:
                bg_color = _hex_to_rgb(match.group(1))
            if "color:red" in style:
                font_color = (255, 0, 0)
            pics = []
            for img in cell.select("img"):
                src = img.get("src", "").replace("30px", "60px")
                if src:
                    pics.append(urljoin(BASE_URL, src))
            column.append(
                {
                    "text": cell.get_text(" ", strip=True),
                    "pics": pics,
                    "bg_color": bg_color,
                    "font_color": font_color,
                }
            )
        equip_lists.append(column)

    special_equips: list[dict[str, Any]] = []
    for panel in soup.select('[class*="pverecommend"]'):
        icons = [
            {
                "name": img.get("alt", "").split(".")[0],
                "url": urljoin(BASE_URL, img.get("src", "")),
            }
            for img in panel.select("img")
        ]
        cells = panel.select("td")
        special_equips.append(
            {
                "list": icons,
                "msg": cells[-1].get_text(" ", strip=True) if cells else "",
                "recommender": cells[-2].get_text(" ", strip=True) if len(cells) >= 2 else "",
            }
        )
    return {"equip_lists": equip_lists, "special_equips": special_equips}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    try:
        text = value.lstrip("#")
        if len(text) == 3:
            text = "".join(char * 2 for char in text)
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except (ValueError, IndexError):
        return (255, 255, 255)


# ----------------------------------------------------------------------
# 装备
# ----------------------------------------------------------------------
def parse_equip(soup: BeautifulSoup, query_type: str) -> dict[str, Any]:
    if query_type in ("出处", "建造", "来源", "获得途径"):
        return {"type": "equip_source", "data": parse_equip_source(soup)}
    return {"type": "equip_attr", "data": parse_equip_attr(soup)}


def parse_equip_attr(soup: BeautifulSoup) -> dict[str, Any]:
    equip = soup.select("ul.equip")
    if not equip:
        raise ValueError("未找到装备信息")
    items = equip[0].find_all("li", recursive=False)
    style = items[0].get("style", "")
    level_map = {
        "text-align:center;font-size:1.2em;background:#dbdcdf": 1,
        "text-align:center;font-size:1.2em;background:#1bb7eb": 2,
        "text-align:center;font-size:1.2em;background:#ae90ef": 3,
        "text-align:center;font-size:1.2em;background:#f9f593": 4,
        "text-align:center;font-size:1.2em;background:linear-gradient(135deg,#59AE6A,#48AE96,#60D9EC,#65A5D5,#9491E0,#C382A4)": 5,
    }
    divs = items[1].select("div")
    bold = items[1].select("b")
    tno = 0
    if bold:
        text = bold[-1].get_text(" ", strip=True)
        if len(text) > 1 and text[1].isdigit():
            tno = int(text[1])
    img = items[1].select_one("img")

    attr_lines: list[str] = []
    for item in items[2:-1]:
        attr_lines.extend(_flatten_equip_attr(item, 0))

    use = _parse_equip_use(items[-1])

    return {
        "name": items[0].get_text(" ", strip=True),
        "type": divs[0].get_text(" ", strip=True) if divs else "",
        "tag": divs[1].get_text(" ", strip=True) if len(divs) > 1 else "",
        "level": level_map.get(style, 1),
        "tno": tno,
        "pic": urljoin(BASE_URL, img.get("src", "")) if img else "",
        "attr": "\n".join(attr_lines),
        "use": use,
        "use_text": "、".join(use),
    }


def _parse_equip_use(node: Any) -> dict[str, int]:
    """解析适用舰种：0=普通，1=主武器，2=副武器。"""
    use: dict[str, int] = {}
    cells = node.select("td")
    if not cells:
        return use
    for cell in cells[0].children:
        if not hasattr(cell, "get"):
            continue
        classes = " ".join(cell.get("class", []))
        if "notAppShipType" in classes:
            continue
        text = cell.get_text(" ", strip=True).replace("主", "").replace("副", "")
        sup = cell.select_one("sup")
        if sup is not None:
            use[text] = 1 if "mainAppShipType" in " ".join(sup.get("class", [])) else 2
        else:
            use[text] = 0
    return use


def _flatten_equip_attr(node: Any, depth: int) -> list[str]:
    if not hasattr(node, "children"):
        return []
    if getattr(node, "name", None) == "table":
        rows = node.select("tr")
        if rows:
            cells = rows[0].select("td, th")
            left = cells[0].get_text(" ", strip=True) if cells else ""
            right = cells[1].get_text(" ", strip=True) if len(cells) > 1 else ""
            return ["\t" * depth + f"{left}:{right}"]
        return []
    if getattr(node, "name", None) in ("li", "ul"):
        lines: list[str] = []
        for child in node.children:
            lines.extend(_flatten_equip_attr(child, depth + (1 if node.name == "ul" else 0)))
        return lines
    lines = []
    for child in node.children:
        lines.extend(_flatten_equip_attr(child, depth))
    return lines


def parse_equip_source(soup: BeautifulSoup) -> dict[str, Any]:
    equip = soup.select("ul.equip")
    items = equip[0].find_all("li", recursive=False) if equip else []
    name = items[0].get_text(" ", strip=True) if items else ""
    img = items[1].select_one("img") if len(items) > 1 else None
    tables = soup.select("table.table.table-bordered")
    from_text = piece_text = ""
    if tables:
        headers = tables[0].select("th")
        cells = tables[0].select("td")
        for index, header in enumerate(headers):
            label = header.get_text(" ", strip=True).replace("\n", "")
            if index >= len(cells):
                break
            if label == "整装获取":
                from_text = cells[index].get_text("\n", strip=True)
            elif label == "图纸获取":
                piece_text = cells[index].get_text("\n", strip=True)
    camp = soup.select("li.active")
    return {
        "name": name,
        "pic": urljoin(BASE_URL, img.get("src", "")) if img else "",
        "camp": camp[-1].get_text(" ", strip=True) if camp else "",
        "from": from_text or "无",
        "piece": piece_text or "无",
    }


def parse_special_equip(soup: BeautifulSoup) -> dict[str, Any]:
    equip = soup.select("ul.equip")
    if not equip:
        raise ValueError("未找到特殊兵装信息")
    items = equip[0].find_all("li", recursive=False)
    style = items[0].get("style", "")
    level_map = {
        "text-align:center;font-size:1.2em;background:#dbdcdf": 1,
        "text-align:center;font-size:1.2em;background:#1bb7eb": 2,
        "text-align:center;font-size:1.2em;background:#ae90ef": 3,
        "text-align:center;font-size:1.2em;background:#f9f593": 4,
        "text-align:center;font-size:1.2em;background:linear-gradient(135deg,#59AE6A,#48AE96,#60D9EC,#65A5D5,#9491E0,#C382A4)": 5,
    }
    bold = items[1].select("b")
    tno = 0
    if bold:
        text = bold[-1].get_text(" ", strip=True)
        if len(text) > 1 and text[1].isdigit():
            tno = int(text[1])
    img = items[1].select_one("img")
    attr_lines: list[str] = []
    for item in items[2:-1]:
        attr_lines.extend(_flatten_equip_attr(item, 0))
    owner = soup.select_one("span.AF")
    use = _parse_equip_use(items[-1])
    return {
        "name": items[0].get_text(" ", strip=True),
        "owner": owner.get_text(" ", strip=True) if owner else "",
        "level": level_map.get(style, 1),
        "tno": tno,
        "pic": urljoin(BASE_URL, img.get("src", "")) if img else "",
        "attr": "\n".join(attr_lines),
        "use": use,
        "use_text": "、".join(use),
    }


# ----------------------------------------------------------------------
# 榜单 / 关卡 / 搜索
# ----------------------------------------------------------------------
def parse_rank_images(soup: BeautifulSoup, keyword: str) -> list[str]:
    images: list[str] = []
    # 装备一图榜等页面：正文图片在 div.noresize 内。
    for img in soup.select("div.noresize img"):
        src = img.get("src", "")
        if src:
            images.append(urljoin(BASE_URL, src))
    if not images:
        for img in soup.select("div.center img"):
            src = img.get("src", "")
            if src:
                images.append(urljoin(BASE_URL, src))
    if not images:
        span = soup.select_one(f"span#{keyword}") or soup.select_one("span[id]")
        if span is not None and span.parent is not None:
            sibling = span.parent.find_next_sibling()
            if sibling is not None:
                for img in sibling.select("img"):
                    src = img.get("src", "")
                    if src:
                        images.append(urljoin(BASE_URL, re.split(r"/\d*px-", src)[0]))
    return images


def parse_level(soup: BeautifulSoup) -> dict[str, Any]:
    tables = soup.select("table.wikitable")
    if not tables:
        return {"text": "没有找到关卡信息喵"}
    rows = tables[0].select("tr")
    heading = soup.select_one("h1#firstHeading")
    name = heading.get_text(" ", strip=True) if heading is not None else ""
    level = exp = boss = boss_level = boss_exp = cost_limit = times_min = ""
    for row in rows:
        if "display:none" in row.get("style", ""):
            continue
        label = row.select_one("th")
        label_text = label.get_text(" ", strip=True) if label else ""
        cells = row.select("td")
        if "敌舰等级" in label_text and cells:
            parts = cells[0].get_text(" ", strip=True).split(" ：")
            level = parts[0]
            images = row.select("td img")
            exp = " ".join(
                f"{img.get('alt', '').split('.')[0]}:{parts[index + 1] if index + 1 < len(parts) else ''}"
                for index, img in enumerate(images)
            )
        elif "BOSS位置" in label_text and cells:
            parts = cells[0].get_text("\n", strip=True).split("\n")
            if len(parts) >= 3:
                boss = " / ".join(parts[1:-2])
                boss_level = parts[-2]
                boss_exp = parts[-1].split("：")[-1]
        elif "油耗上限" in label_text and cells:
            cost_limit = cells[0].get_text(" ", strip=True)
        elif "旗舰刷新" in label_text and cells:
            times_min = cells[0].get_text(" ", strip=True)

    pic = ""
    if len(tables) >= 2:
        image = tables[1].select_one("img")
        if image is not None:
            pic = urljoin(BASE_URL, image.get("src", ""))

    drop_lines: list[dict[str, Any]] = []
    drop_tables = soup.select("table.table-DropList")
    if drop_tables:
        for row in drop_tables[0].select("tr"):
            label_cell = row.select_one("th")
            label = label_cell.get_text(" ", strip=True) if label_cell is not None else ""
            items = []
            cells = row.select("td")
            if cells:
                for span in cells[0].select("span.xtb-image"):
                    image = span.select_one("img")
                    nowrap = span.select_one("span.nowrap")
                    color = "#ffffff"
                    if nowrap is None:
                        item_name = span.get_text(" ", strip=True)
                    else:
                        link = span.select_one("a")
                        short = span.select_one("span.AF")
                        title = link.get("title", "") if link is not None else ""
                        short_text = short.get_text(" ", strip=True) if short is not None else ""
                        match = re.search(r"color:([^;]+)", nowrap.get("style", ""))
                        if match:
                            color = match.group(1).strip()
                        item_name = title if title == short_text or not short_text else f"{short_text}({title})"
                    items.append(
                        {
                            "pic": urljoin(BASE_URL, image.get("src", "")) if image is not None else "",
                            "name": item_name,
                            "color": color,
                        }
                    )
            drop_lines.append({"label": label, "items": items})

    return {
        "name": name,
        "level": level,
        "exp": exp,
        "boss": boss,
        "boss_level": boss_level,
        "boss_exp": boss_exp,
        "cost_limit": cost_limit or "该关卡没有油耗上限喵",
        "times_min": times_min,
        "pic": pic,
        "drop_lines": drop_lines,
    }


def parse_search_results(soup: BeautifulSoup, keyword: str) -> list[str]:
    results: list[str] = []
    normalized = normalize_keyword(keyword)
    for div in soup.select("div.searchresults div.mw-search-result-heading"):
        link = div.find("a")
        title = link.get("title", "") if link else ""
        if title and (not normalized or normalized in normalize_keyword(title)):
            results.append(title)
    return results


# ----------------------------------------------------------------------
# 模糊搜索
# ----------------------------------------------------------------------
def normalize_keyword(value: str) -> str:
    return "".join(
        ch for ch in (value or "").lower()
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fa5"
    )


def _contains_ordered(source: str, target: str) -> bool:
    index = 0
    for char in source:
        if index < len(target) and char == target[index]:
            index += 1
    return index == len(target)


def search_names(keyword: str, names: list[str]) -> list[str]:
    normalized = normalize_keyword(keyword)
    if not normalized:
        return []
    hits = [name for name in names if normalized in normalize_keyword(name)]
    if hits:
        return hits
    return [name for name in names if _contains_ordered(normalize_keyword(name), normalized)]


def build_page_url(title: str) -> str:
    return BASE_URL + quote(title, safe="")
