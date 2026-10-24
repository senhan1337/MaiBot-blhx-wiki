"""碧蓝航线舰娘卡片绘制。

仅使用 Pillow；不依赖 MaiBot，便于单元测试。
"""
from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from blhxwiki.utils.naming import asset_key


# 硬编码布局/颜色集中于此，避免散落在绘制逻辑中。
SHIP_CARD_LAYOUT: dict[str, Any] = {
    "canvas": {"width": 1280, "height": 720},
    "camp_icon": {"x": 0, "y": 0, "width": 160, "height": 160},
    "title": {"x": 150, "y": 5},
    "type_icon": {"x": 164, "y": 30, "width": 60, "height": 60},  # 194 - 30
    "name": {"center_x": 340, "y": 40, "font_size": 20},
    "code": {"center_x": 340, "y": 71, "font_size": 12},
    "ship_fallback": {"x": 50, "y": 0, "width": 525, "height": 788},
    "attribute_box": {"x": 680, "y": 20, "width": 570, "base_height": 190},
    "attribute_cell": {"icon_width": 30, "height": 30, "value_width": 147, "gap": 10, "row_gap": 5, "columns": 3},
    "attribute_padding": {"left": 2, "top": 2},
    "skill": {"width": 570, "font_size": 16, "icon_width": 80, "padding": 3, "text_padding_x": 10, "border": 1},
    "flow": {"box_top_padding": 10, "attribute_after_gap": 40, "safe_bottom": 710, "canvas_bottom": 720},
    "bottom": {"label_width": 100, "line_height": 30, "grid_x": [70, 270, 370, 470, 570], "center_y_offset": 2, "rows": 4, "fallback_x": 50},
    "text_component": {"baseline_divisor": 1.4, "line_padding": 0},
    "draw_result": {"width": 840, "height": 380, "start_x": 50, "start_y": 50, "item_width": 90, "item_height": 90, "step_x": 130, "second_row_y": 200, "border": 3, "text_gap": 5},
    "colors": {
        "white": (255, 255, 255, 255), "yellow": (255, 255, 0, 255),
        "icon_bg": (0, 0, 0, 127), "attribute_bg": (50, 50, 50, 127),
        "box_bg": (100, 100, 100, 50),
    },
    "fonts": {"default_path": "fonts/SourceHanSans.ttf", "name_size": 20, "code_size": 12, "attribute_size": 20, "skill_size": 16},
    "rounded_rectangles": {},  # 原 ShipAttr/DrawResult 绘制代码没有圆角矩形
    "z_index": ["rarity_background", "ship_art", "camp_icon", "title", "type_icon", "name", "code", "attribute_box"],
}

RARITY_COLORS = {
    "UR": (255, 0, 0, 255), "SSR": (235, 208, 127, 255),
    "SR": (131, 7, 255, 255), "R": (27, 183, 235, 255), "N": (219, 220, 223, 255),
}
RARITY_LEVELS = {"海上传奇": 5, "超稀有": 4, "精锐": 3, "稀有": 2, "普通": 1, "最高方案": 24, "决战方案": 25}
ATTR_NAMES = ["耐久", "装甲", "装填", "炮击", "雷击", "机动", "防空", "航空", "命中", "反潜", "氧气", "弹药量", "航速", "幸运", "消耗"]
ATTR_KEYS = ["naijiu", "zhuangjia", "zhuangtian", "paoji", "leiji", "jidong", "fangkong", "hangkong", "mingzhong", "fanqian", "yangqi", "danyao", "hangsu", "xingyun", "xiaohao"]


def _default_assets_root() -> Path:
    """向上查找插件根（含 _manifest.json），返回其 assets 目录。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "_manifest.json").exists():
            return parent / "assets"
    return Path(__file__).resolve().parents[3] / "assets"


class AssetLoader:
    """从可配置 assets 根目录加载图片/字体；支持绝对路径和相对路径。"""
    def __init__(self, assets_dir: str | os.PathLike[str] | None = None):
        self.root = Path(assets_dir).expanduser() if assets_dir else _default_assets_root()

    def resolve(self, path: str | os.PathLike[str]) -> Path:
        p = Path(path).expanduser()
        return p if p.is_absolute() else self.root / p

    def image(self, path: str | os.PathLike[str], size: tuple[int, int] | None = None, fallback: tuple[int, int] = (1, 1)) -> Image.Image:
        p = self.resolve(path)
        try:
            image = Image.open(p).convert("RGBA")
        except (FileNotFoundError, OSError):
            image = Image.new("RGBA", size or fallback, (0, 0, 0, 0))
        return image.resize(size, Image.Resampling.LANCZOS) if size else image

    def font(self, size: int, path: str | os.PathLike[str] | None = None) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        candidates = []
        if path:
            candidates.append(path)
        default = SHIP_CARD_LAYOUT["fonts"].get("default_path") or ""
        if default:
            candidates.append(default)
        candidates.extend(("fonts/SourceHanSans.ttf", "思源黑体.ttf"))
        for candidate in candidates:
            try:
                return ImageFont.truetype(str(self.resolve(candidate)), size)
            except OSError:
                continue
        # ZIP 解压可能把中文文件名弄乱；直接扫描 assets 下的字体文件兜底。
        for pattern in ("fonts/*.ttf", "fonts/*.ttc", "*.ttf", "*.ttc"):
            for font_path in sorted(self.root.glob(pattern)):
                try:
                    return ImageFont.truetype(str(font_path), size)
                except OSError:
                    continue
        for name in ("msyh.ttc", "Microsoft YaHei.ttf", "NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: Any, font: Any, fill: tuple[int, ...], anchor: str | None = None) -> None:
    draw.text(xy, str(value or ""), font=font, fill=fill, anchor=anchor)


def _center_text(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], value: Any, font: Any, fill: tuple[int, ...]) -> None:
    x0, y0, x1, y1 = box
    _text(draw, ((x0 + x1) // 2, (y0 + y1) // 2), value, font, fill, "mm")


def _wrap_chars(draw: ImageDraw.ImageDraw, text: str, font: Any, max_width: int) -> list[str]:
    """按原 TextComponent 的逐字符方式换行。"""
    lines: list[str] = []
    current = ""
    for char in text or " ":
        if char == "\n":
            lines.append(current or " "); current = ""; continue
        candidate = current + char
        if current and draw.textlength(candidate, font=font) > max_width:
            lines.append(current); current = char
        else:
            current = candidate
    lines.append(current or " ")
    return lines


def _skill_metrics(draw: ImageDraw.ImageDraw, loader: AssetLoader, skill: Mapping[str, Any], font_path: Any) -> tuple[Any, list[str], int, int]:
    cfg = SHIP_CARD_LAYOUT["skill"]; font = loader.font(cfg["font_size"], font_path)
    text_width = cfg["width"] - cfg["icon_width"] - 2 * cfg["padding"] - 2 * cfg["text_padding_x"]
    detail = f"{skill.get('name', '')} {skill.get('detail', '')}".strip()
    lines = _wrap_chars(draw, detail, font, text_width)
    bbox = draw.textbbox((0, 0), "国Ag", font=font); line_height = max(1, bbox[3] - bbox[1])
    height = max(cfg["icon_width"], 2 * cfg["padding"] + line_height * len(lines))
    return font, lines, line_height, height


def _draw_skill(canvas: Image.Image, loader: AssetLoader, skill: Mapping[str, Any], x: int, y: int, font_path: Any) -> int:
    cfg = SHIP_CARD_LAYOUT["skill"]; colors = SHIP_CARD_LAYOUT["colors"]
    draw = ImageDraw.Draw(canvas, "RGBA")
    font, lines, line_height, height = _skill_metrics(draw, loader, skill, font_path)
    draw.rectangle((x, y, x + cfg["width"], y + height), fill=colors["attribute_bg"], outline=colors["white"], width=cfg["border"])
    icon_y = y + (height - cfg["icon_width"]) // 2
    canvas.alpha_composite(loader.image(skill.get("pic", "skill/placeholder.png"), (cfg["icon_width"], cfg["icon_width"])), (x + cfg["padding"], icon_y))
    text_x = x + cfg["padding"] + cfg["icon_width"] + cfg["text_padding_x"]
    text_y = y + (height - line_height * len(lines)) // 2
    for index, line in enumerate(lines):
        _text(draw, (text_x, text_y + index * line_height), line, font, colors["white"])
    # 黄色技能名覆盖在详情文本相同起点。
    _text(draw, (text_x, text_y), skill.get("name", ""), font, colors["yellow"])
    return height


def _source_lines(data: Mapping[str, Any]) -> list[str]:
    result: list[str] = []
    normal = str(data.get("normal_from", ""))
    if normal:
        parts = normal.split("、"); result.append(",".join(parts[:4]) + ("等" if len(parts) > 4 else ""))
    active = str(data.get("active_from", "")); file_from = str(data.get("file_from", ""))
    if active and not file_from: result.append(active.split(" ")[-1])
    if file_from: result.append(file_from.split(" ")[-1])
    other = str(data.get("other_from", ""))
    for value in other.replace(" ", "、").split("、"):
        if value and any(word in value for word in ("兑换", "科研", "奖励", "META", "彩蛋", "开发船坞")): result.append(value)
    return result


def generate_ship_card(ship_data: dict) -> io.BytesIO:
    """生成舰娘详情卡片，返回 seek(0) 的 PNG BytesIO。

    ship_data 常用字段：name、code、level/rarity、camp、type、pic、attributes。
    attributes 可为字典（键使用 ATTR_KEYS 或中文名），也兼容原始字段名。
    可选 ``assets_dir`` 和 ``font_path`` 用于覆盖资源路径。
    """
    data: Mapping[str, Any] = ship_data
    layout = SHIP_CARD_LAYOUT
    loader = AssetLoader(data.get("assets_dir"))
    w, h = layout["canvas"]["width"], layout["canvas"]["height"]
    canvas = Image.new("RGBA", (w, h), (30, 30, 40, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    rarity_name = str(data.get("rarity", data.get("level", "普通")))
    rarity = RARITY_LEVELS.get(rarity_name)
    if rarity is None:
        try:
            rarity = int(data.get("rarity_code", 1))
        except (TypeError, ValueError):
            rarity = 1
    if data.get("camp") in ("", "META-???"): data = dict(data); data["camp"] = "余烬"
    if data.get("camp") == "余烬": rarity += 10
    if data.get("can_upgrade"): rarity += 1

    # Z 顺序：背景 -> 立绘 -> 阵营 -> 标题 -> 舰种 -> 文字 -> 属性框。
    canvas.alpha_composite(loader.image(f"image/icon/rarity/bg_{rarity}.png", (w, h), (w, h)))
    ship_path = data.get("pic", "ship/placeholder.png")
    ship = loader.image(ship_path, (layout["ship_fallback"]["width"], layout["ship_fallback"]["height"]), (525, 788))
    canvas.alpha_composite(ship, (layout["ship_fallback"]["x"], layout["ship_fallback"]["y"]))
    # 阵营图标：缺失（如新阵营“飓风”）时回退到“其他联动”图标，避免图标丢失。
    camp_name = data.get("camp", "其他联动")
    camp_icon = loader.root / "image" / "icon" / "camp" / f"{asset_key(camp_name)}.png"
    if not camp_icon.exists():
        camp_icon = loader.root / "image" / "icon" / "camp" / f"{asset_key('其他联动')}.png"
    canvas.alpha_composite(loader.image(str(camp_icon), (160, 160)), (0, 0))
    canvas.alpha_composite(loader.image("image/icon/ship/title.png"), (150, 5))
    canvas.alpha_composite(loader.image(f"image/icon/ship/{asset_key(data.get('type', '其他'))}.png", (60, 60)), (164, 30))

    font_path = data.get("font_path")
    _center_text(draw, (0, 40, 680, 40 + 30), data.get("name", "未知舰娘"), loader.font(20, font_path), layout["colors"]["white"])
    _center_text(draw, (0, 71, 680, 71 + 20), data.get("code", ""), loader.font(12, font_path), layout["colors"]["white"])

    box = layout["attribute_box"]; x, y = box["x"], box["y"]
    attrs = data.get("attributes", {})
    if not isinstance(attrs, Mapping): attrs = {}
    skills = [skill for skill in (data.get("skills", data.get("skill", [])) or []) if isinstance(skill, Mapping)]
    skill_height = sum(_skill_metrics(draw, loader, skill, font_path)[3] for skill in skills)
    draw.rectangle((x, y, x + box["width"], y + box["base_height"] + skill_height), fill=layout["colors"]["box_bg"], outline=layout["colors"]["white"])
    cell = layout["attribute_cell"]
    y += layout["flow"]["box_top_padding"]; count = 0; current_x = x + layout["flow"]["box_top_padding"]
    for i, key in enumerate(ATTR_KEYS):
        value = attrs.get(key, attrs.get(ATTR_NAMES[i], data.get(key, "")))
        if value in (None, ""): continue
        draw.rectangle((current_x, y, current_x + 30, y + 30), fill=layout["colors"]["icon_bg"])
        canvas.alpha_composite(loader.image(f"image/icon/ship/attr_{i + 1}.png", (30, 30)), (current_x, y))
        draw.rectangle((current_x + 30, y, current_x + 30 + 147, y + 30), fill=layout["colors"]["attribute_bg"])
        _text(draw, (current_x + 32, y + 2), ATTR_NAMES[i], loader.font(20, font_path), layout["colors"]["white"])
        _text(draw, (current_x + 30 + 147 - 2, y + 2), str(value).split("→")[-1], loader.font(20, font_path), layout["colors"]["yellow"], "ra")
        current_x += 30 + 147 + 10; count += 1
        if count == 3: count = 0; current_x = x + 10; y += 35

    y += layout["flow"]["attribute_after_gap"]
    for skill in data.get("skills", data.get("skill", [])) or []:
        if isinstance(skill, Mapping): y += _draw_skill(canvas, loader, skill, x, y, font_path)

    # 空间不足时把建造时间/出处区域移到左下角。
    body_font = loader.font(20, font_path); source_lines = _source_lines(data)
    text_bbox = draw.textbbox((0, 0), "建造时间", font=body_font)
    text_height = max(1, text_bbox[3] - text_bbox[1])
    source_height = text_height * len(source_lines)
    bottom_x = x
    if source_height + text_height + y > layout["flow"]["safe_bottom"]:
        bottom_x = layout["bottom"]["fallback_x"]
        y = layout["flow"]["safe_bottom"] - source_height - text_height
    label_width = layout["bottom"]["label_width"]
    draw.rectangle((bottom_x, y, bottom_x + box["width"], y + text_height), fill=layout["colors"]["attribute_bg"], outline=layout["colors"]["white"])
    draw.line((bottom_x + label_width, y, bottom_x + label_width, y + text_height), fill=layout["colors"]["white"])
    _center_text(draw, (bottom_x, y, bottom_x + label_width, y + text_height), "建造时间", body_font, layout["colors"]["white"])
    _center_text(draw, (bottom_x + label_width, y, bottom_x + box["width"], y + text_height), data.get("time", ""), body_font, layout["colors"]["white"])
    y += text_height
    if source_lines:
        draw.rectangle((bottom_x, y, bottom_x + box["width"], y + source_height), fill=layout["colors"]["attribute_bg"], outline=layout["colors"]["white"])
        draw.line((bottom_x + label_width, y, bottom_x + label_width, y + source_height), fill=layout["colors"]["white"])
        _center_text(draw, (bottom_x, y, bottom_x + label_width, y + source_height), "其他途径", body_font, layout["colors"]["white"])
        for index, line in enumerate(source_lines):
            _center_text(draw, (bottom_x + label_width, y + index * text_height, bottom_x + box["width"], y + (index + 1) * text_height), line, body_font, layout["colors"]["white"])
        y += source_height

    # 武器效率表固定 4 行，按列坐标与回流规则绘制。
    equip_details = data.get("equip_detail", []) or []
    if data.get("show_equip_efficiency", True) and equip_details:
        line_height = layout["bottom"]["line_height"]; rows = layout["bottom"]["rows"]
        if bottom_x == layout["bottom"]["fallback_x"]: y -= source_height + text_height + line_height * rows
        elif y + line_height * rows > layout["flow"]["canvas_bottom"]:
            bottom_x = layout["bottom"]["fallback_x"]; y = layout["flow"]["safe_bottom"] - line_height * rows
        columns = [0] + layout["bottom"]["grid_x"]
        draw.rectangle((bottom_x, y, bottom_x + box["width"], y + line_height * rows), fill=layout["colors"]["attribute_bg"], outline=layout["colors"]["white"])
        for row in range(rows + 1): draw.line((bottom_x, y + row * line_height, bottom_x + box["width"], y + row * line_height), fill=layout["colors"]["white"])
        for col in layout["bottom"]["grid_x"]: draw.line((bottom_x + col, y, bottom_x + col, y + line_height * rows), fill=layout["colors"]["white"])
        keys = ("index", "name", "efficiency", "count", "prefill_count")
        for row, detail in enumerate(equip_details[:rows]):
            for col, key in enumerate(keys):
                _center_text(draw, (bottom_x + columns[col], y + row * line_height, bottom_x + columns[col + 1], y + (row + 1) * line_height), detail.get(key, ""), body_font, layout["colors"]["white"])

    output = io.BytesIO(); canvas.convert("RGB").save(output, "PNG"); output.seek(0); return output


def generate_build_result_image(results: list[dict], assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """迁移 DrawResultComponent 的模拟建造结果图；results 含 rarity/name/pic。"""
    cfg = SHIP_CARD_LAYOUT["draw_result"]; loader = AssetLoader(assets_dir)
    image = loader.image("image/icon/ship/draw_bg.png", (cfg["width"], cfg["height"]), (cfg["width"], cfg["height"]))
    draw = ImageDraw.Draw(image, "RGBA")
    x, y = cfg["start_x"], cfg["start_y"]
    for item in results:
        color = RARITY_COLORS.get(str(item.get("rarity", "N")).upper(), RARITY_COLORS["N"])
        draw.rectangle((x - 3, y - 3, x + 93, y + 93), fill=color)
        image.alpha_composite(loader.image(item.get("pic", "ship/other_r.png"), (90, 90)), (x, y))
        text_font = loader.font(20)
        bbox = draw.textbbox((0, 0), str(item.get("name", "未知")), font=text_font)
        tw = bbox[2] - bbox[0]
        draw.rectangle((x + (90 - tw) // 2 - 2, y + 95, x + (90 + tw) // 2 + 2, y + 125), fill=(0, 0, 0, 127))
        _center_text(draw, (x, y + 95, x + 90, y + 125), item.get("name", "未知"), text_font, color)
        x += cfg["step_x"]
        if x > 800:
            x = cfg["start_x"] + cfg["step_x"]
            y = cfg["second_row_y"]
    output = io.BytesIO(); image.convert("RGB").save(output, "PNG"); output.seek(0); return output


def generate_server_state_image(
    servers: list[dict],
    assets_dir: str | os.PathLike[str] | None = None,
) -> io.BytesIO:
    """服务器状态图。

    servers: [{"name": str, "region": str, "maintenance": bool}]，region 用中文区服名。
    """
    loader = AssetLoader(assets_dir)
    font_time = loader.font(24)
    font_title = loader.font(30)
    font_body = loader.font(24)

    region_order = ("国服", "日服", "国际服", "繁中服")
    grouped = {region: [s for s in servers if s.get("region") == region] for region in region_order}
    grouped = {region: items for region, items in grouped.items() if items}

    outer, gap, section_pad = 28, 12, 20
    card_w, card_h = 260, 44
    columns = 3
    section_w = section_pad * 2 + card_w * columns + gap * (columns - 1)

    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    time_text = _now_text()
    time_h = measure.textbbox((0, 0), time_text, font=font_time)[3]
    title_h = measure.textbbox((0, 0), "国服", font=font_title)[3]

    def section_height(count: int) -> int:
        rows = (count + columns - 1) // columns
        return 16 + title_h + 12 + rows * card_h + (rows - 1) * gap + 16

    heights = [section_height(len(items)) for items in grouped.values()]
    width = max(outer * 2 + section_w, outer * 2 + measure.textbbox((0, 0), time_text, font=font_time)[2] + 40)
    height = outer * 2 + time_h + 18 + sum(heights) + gap * max(0, len(heights) - 1)

    image = Image.new("RGB", (width, height), (245, 247, 250))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.text(((width - measure.textbbox((0, 0), time_text, font=font_time)[2]) // 2, outer), time_text, font=font_time, fill=(33, 37, 41))

    top = outer + time_h + 18
    for (region, items), section_h in zip(grouped.items(), heights):
        left = (width - section_w) // 2
        draw.rounded_rectangle((left, top, left + section_w, top + section_h), radius=20, fill=(235, 239, 244), outline=(214, 220, 228))
        draw.text((left + section_pad, top + 16), region, font=font_title, fill=(33, 37, 41))
        start_y = top + 16 + title_h + 12
        for index, item in enumerate(items):
            row, col = divmod(index, columns)
            x = left + section_pad + col * (card_w + gap)
            y = start_y + row * (card_h + gap)
            draw.rounded_rectangle((x, y, x + card_w, y + card_h), radius=14, fill=(255, 255, 255), outline=(220, 224, 230))
            draw.text((x + 16, y + (card_h - measure.textbbox((0, 0), item["name"], font=font_body)[3]) // 2), item["name"], font=font_body, fill=(33, 37, 41))
            color = (220, 53, 69) if item.get("maintenance") else (25, 135, 84)
            draw.rectangle((x + card_w - 34, y + (card_h - 18) // 2, x + card_w - 16, y + (card_h + 18) // 2), fill=color)
        top += section_h + gap

    output = io.BytesIO(); image.save(output, "PNG"); output.seek(0); return output


def _now_text() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
