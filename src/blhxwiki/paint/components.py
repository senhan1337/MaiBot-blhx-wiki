"""装备卡、特殊兵装卡、配装图、关卡图、科技点表（Pillow 绘制）。

只依赖 Pillow，复用 drawing.py 的 AssetLoader 与文本工具。
"""
from __future__ import annotations

import io
import os
from typing import Any, Mapping

from PIL import Image, ImageDraw

from blhxwiki.paint.drawing import AssetLoader, _center_text, _wrap_chars

MAP_EQUIP_USE = [
    "驱逐", "轻巡", "重巡", "超巡", "战巡", "战列", "轻航", "航母",
    "航战", "潜母", "重炮", "潜艇", "维修", "运输", "风帆",
]


def _line_height(draw: ImageDraw.ImageDraw, font: Any) -> int:
    box = draw.textbbox((0, 0), "国Ag", font=font)
    return max(1, box[3] - box[1])


def _fade(image: Image.Image) -> Image.Image:
    faded = image.copy()
    faded.putalpha(faded.getchannel("A").point(lambda value: value // 2))
    return faded


def _to_png(image: Image.Image) -> io.BytesIO:
    output = io.BytesIO()
    image.convert("RGB").save(output, "PNG")
    output.seek(0)
    return output


def _hex_color(value: str) -> tuple[int, int, int]:
    try:
        text = str(value).lstrip("#")
        if len(text) == 3:
            text = "".join(char * 2 for char in text)
        return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))
    except (ValueError, IndexError):
        return (255, 255, 255)


def generate_equip_card(data: Mapping[str, Any], assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """装备属性卡，布局对齐 EquipAttrComponent。"""
    loader = AssetLoader(assets_dir)
    width = 576
    tab = 15
    font_title = loader.font(30)
    font_body = loader.font(24)
    font_small = loader.font(20)
    canvas = Image.new("RGBA", (width, 5000), (100, 100, 100, 200))
    draw = ImageDraw.Draw(canvas, "RGBA")

    title_h = _line_height(draw, font_title) + 6
    draw.rectangle((0, 0, width, title_h), fill=(0, 0, 0, 127))
    _center_text(draw, (0, 0, width, title_h), data.get("name", ""), font_title, (255, 255, 255, 255))
    y = title_h

    level_icon = loader.image(f"image/icon/equip/level_{data.get('level', 1)}.png")
    canvas.alpha_composite(level_icon, ((width - level_icon.width) // 2, y))
    y += level_icon.height + 5

    pic = loader.image(data.get("pic", ""), (128, 128))
    canvas.alpha_composite(pic, ((width - 128) // 2, max(0, y - 180)))
    tno_icon = loader.image(f"image/icon/equip/T{data.get('tno', 0)}.png", (32, 45))
    canvas.alpha_composite(tno_icon, (512, max(0, y - 201)))

    type_color = (0, 0, 255, 255) if data.get("type") in ("设备", "货物", "唯一设备") else (255, 0, 0, 255)
    draw.rectangle((20, y - 80, 120, y - 50), fill=type_color)
    _center_text(draw, (20, y - 80, 120, y - 50), data.get("type", ""), font_small, (255, 255, 255, 255))
    draw.rectangle((20, y - 40, 120, y - 10), fill=(100, 100, 100, 200))
    _center_text(draw, (20, y - 40, 120, y - 10), data.get("tag", ""), font_small, (255, 255, 255, 255))

    y = _draw_equip_attrs(canvas, draw, data.get("attr", ""), font_body, width, tab, y)

    draw.rectangle((tab, y, width - tab, y + 152), fill=(0, 0, 0, 127))
    y += 8
    _draw_equip_use(canvas, draw, loader, data.get("use", {}), tab, y)
    y += 3 * 48 + tab
    return _to_png(canvas.crop((0, 0, width, min(y, 5000))))


def generate_special_equip_card(data: Mapping[str, Any], assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """特殊兵装卡，布局对齐 SpecialEquipComponent。"""
    loader = AssetLoader(assets_dir)
    width = 576
    tab = 15
    font_title = loader.font(30)
    font_body = loader.font(24)
    font_small = loader.font(20)
    canvas = Image.new("RGBA", (width, 5000), (100, 100, 100, 200))
    draw = ImageDraw.Draw(canvas, "RGBA")

    title_h = _line_height(draw, font_title) + 6
    draw.rectangle((0, 0, width, title_h), fill=(0, 0, 0, 127))
    _center_text(draw, (0, 0, width, title_h), data.get("name", ""), font_title, (255, 255, 255, 255))
    y = title_h

    level_icon = loader.image(f"image/icon/equip/level_{data.get('level', 1)}.png")
    canvas.alpha_composite(level_icon, ((width - level_icon.width) // 2, y))
    y += level_icon.height + 5

    pic = loader.image(data.get("pic", ""), (128, 128))
    canvas.alpha_composite(pic, ((width - 128) // 2, max(0, y - 180)))
    tno_icon = loader.image(f"image/icon/equip/T{data.get('tno', 0)}.png", (32, 45))
    canvas.alpha_composite(tno_icon, (512, max(0, y - 201)))

    owner = data.get("owner", "")
    if owner:
        draw.rectangle((20, y - 80, 120, y - 50), fill=(100, 100, 100, 200))
        _center_text(draw, (20, y - 80, 120, y - 50), owner, font_small, (255, 255, 255, 255))
        draw.rectangle((20, y - 40, 120, y - 10), fill=(255, 0, 0, 255))
        _center_text(draw, (20, y - 40, 120, y - 10), "专属兵装", font_small, (255, 255, 255, 255))

    y = _draw_equip_attrs(canvas, draw, data.get("attr", ""), font_body, width, tab, y)

    use_icon = loader.image("image/icon/equip/use.png")
    canvas.alpha_composite(use_icon, (tab, y))
    y += 8
    _draw_equip_use(canvas, draw, loader, data.get("use", {}), tab, y, marker=False)
    y += 3 * 48 + tab
    return _to_png(canvas.crop((0, 0, width, min(y, 5000))))


def _draw_equip_attrs(canvas, draw, attr_text: str, font, width: int, tab: int, y: int) -> int:
    line_h = _line_height(draw, font)
    for raw in (attr_text or "").split("\n"):
        if not raw:
            continue
        parts = raw.split(":", 1)
        label = parts[0]
        value = parts[1] if len(parts) > 1 else " "
        if raw.startswith("\t描述"):
            lines = _wrap_chars(draw, value, font, width - 2 * tab - 40)
            height = line_h * len(lines) + 6
            draw.rectangle((tab, y, width - tab, y + height), fill=(0, 0, 0, 127))
            for index, line in enumerate(lines):
                draw.text((tab + 20, y + 3 + index * line_h), line, font=font, fill=(0, 255, 0, 255))
            y += height
        else:
            indent = 1
            while label.startswith("\t"):
                label = label[1:]
                indent += 1
            box_w = width - (indent + 1) * tab
            height = line_h + 6
            draw.rectangle((tab * indent, y, tab * indent + box_w, y + height), fill=(0, 0, 0, 127))
            draw.text((tab * indent + 15, y + 3), label, font=font, fill=(255, 255, 255, 255))
            if value.strip():
                value_w = draw.textlength(value, font=font)
                draw.text((int(tab * indent + box_w - 15 - value_w), y + 3), value, font=font, fill=(255, 255, 0, 255))
            y += height
        y += 4
    return y


def _draw_equip_use(canvas, draw, loader, use: Mapping[str, int], tab: int, y: int, marker: bool = True) -> None:
    main_icon = loader.image("image/icon/equip/main.png", (18, 14), (1, 1))
    sub_icon = loader.image("image/icon/equip/sub.png", (18, 14), (1, 1))
    for index, ship_type in enumerate(MAP_EQUIP_USE):
        icon = loader.image(f"image/icon/equip/use_{index + 1}.png")
        column, row = index % 5, index // 5
        x = tab + 26 + column * 104
        top = y + row * 48
        if ship_type in use:
            canvas.alpha_composite(icon, (x, top))
            if marker and use[ship_type] in (1, 2):
                badge = main_icon if use[ship_type] == 1 else sub_icon
                canvas.alpha_composite(badge, (x - 6, top - 6))
        else:
            canvas.alpha_composite(_fade(icon), (x, top))


def generate_ship_equip_image(data: Mapping[str, Any], assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """配装推荐图：6 列标签 + 特殊配装。图片字段需为本地路径。"""
    loader = AssetLoader(assets_dir)
    label_w, label_h, margin = 350, 50, 10
    width = 6 * label_w + 7 * margin
    height = 4000
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = loader.font(20)
    line_h = _line_height(draw, font)

    title = "萌新可以不看文字，直接按表中顺序，以此寻找有的装备，就可以随便用。另外，除设备外灰色背景代表下半段装备比上半部分低一档，每半段装备差距不大"
    y = 10
    for line in _wrap_chars(draw, title, font, width - 20):
        draw.text((10, y), line, font=font, fill=(0, 0, 0, 255))
        y += line_h

    box_x = margin
    for column in data.get("equip_lists", []):
        if not column:
            box_x += margin + label_w
            continue
        box_y = 40
        for row_index, cell in enumerate(column):
            draw.rectangle((box_x, box_y, box_x + label_w, box_y + label_h), fill=tuple(cell.get("bg_color", (255, 255, 255))))
            text = str(cell.get("text", "") or " ")
            fill = tuple(cell.get("font_color", (0, 0, 0)))
            if row_index == 0:
                text_w = draw.textlength(text, font=font)
                draw.text((int(box_x + (label_w - text_w) / 2), box_y + 10), text, font=font, fill=fill)
            else:
                draw.text((box_x + 4, box_y + 10), text, font=font, fill=fill)
                icon_x = box_x + label_w
                for pic in cell.get("pics", []):
                    icon = loader.image(pic, (40, 40), (40, 40))
                    canvas.alpha_composite(icon, (icon_x - 40, box_y + 5))
                    icon_x -= 43
            box_y += label_h
        box_x += margin + label_w

    box_y = max(box_y, 40)
    for special in data.get("special_equips", []):
        box_y += 8
        draw.line((margin, box_y, width - margin, box_y), fill=(64, 64, 64, 255), width=1)
        box_y += 2
        draw.text((margin, box_y + 10), "特殊配装", font=font, fill=(0, 0, 0, 255))
        draw.text((width - 300 + 10, box_y + 10), f"推荐人：{special.get('recommender', '')}", font=font, fill=(0, 0, 0, 255))

        icon_x = 100
        last_start = icon_x
        for icon in special.get("list", []):
            name = icon.get("name", "")
            url = icon.get("url", "")
            if name != "红叉叉图标":
                text_w = draw.textlength(name, font=font)
                if icon_x + 46 + text_w > width - 300:
                    icon_x = 100
                    box_y += 42
                last_start = icon_x
                image = loader.image(url, (40, 40), (40, 40))
                canvas.alpha_composite(image, (icon_x, box_y))
                icon_x += 43
                draw.text((icon_x, box_y + (40 - line_h) // 2), name, font=font, fill=(0, 0, 0, 255))
                icon_x = int(icon_x + text_w + 3)
            else:
                image = loader.image(url, (40, 40), (40, 40))
                canvas.alpha_composite(image, (last_start, box_y))
                draw.line((last_start + 43, box_y + 18, icon_x - 3, box_y + 18), fill=(255, 0, 0, 255), width=4)
        box_y += 42
        draw.text((margin, box_y + 10), "推荐理由", font=font, fill=(0, 0, 0, 255))
        for line in _wrap_chars(draw, str(special.get("msg", "")), font, width - 300 + 200):
            draw.text((100, box_y), line, font=font, fill=(0, 0, 0, 255))
            box_y += line_h

    return _to_png(canvas.crop((0, 0, width, min(box_y + 10, height))))


def generate_stage_image(data: Mapping[str, Any], assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """关卡信息图：标签值行 + BOSS + 地图 + 掉落表。"""
    loader = AssetLoader(assets_dir)
    width, height = 1280, 3000
    start_label, start_value, end_value = 20, 170, 710
    margin = 5
    font = loader.font(24)
    font_small = loader.font(20)
    canvas = Image.new("RGBA", (width, height), (64, 64, 64, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    line_h = _line_height(draw, font)
    y = 20

    def line() -> None:
        nonlocal y
        draw.line((start_label, y, end_value, y), fill=(255, 255, 255, 255), width=1)
        y += 1

    def label_value(label: str, value: str) -> None:
        nonlocal y
        box_h = line_h + margin * 2
        draw.rectangle((start_label, y, end_value, y + box_h), fill=(50, 50, 50, 127))
        draw.text((start_value + 2, y + margin), str(value), font=font, fill=(255, 255, 255, 255))
        _center_text(draw, (start_label, y, start_value, y + box_h), label, font, (255, 255, 255, 255))
        y += box_h
        line()

    draw.rectangle((start_label, y, end_value, y + 40), fill=(50, 50, 50, 127))
    _center_text(draw, (start_label, y, end_value, y + 40), data.get("name", ""), loader.font(40), (255, 255, 255, 255))
    y += 40
    line()

    label_value("旗舰刷新", data.get("times_min", ""))
    label_value("敌舰等级", data.get("level", ""))
    label_value("敌舰经验", data.get("exp", ""))

    boss_h = margin
    for part in [part for part in str(data.get("boss", "")).split("|||") if part]:
        lines = _wrap_chars(draw, part, font, end_value - start_value)
        text_h = line_h * len(lines)
        draw.rectangle((start_label, y + boss_h - margin, end_value, y + boss_h + text_h + margin), fill=(100, 100, 100, 50))
        for index, text_line in enumerate(lines):
            draw.text((start_value + 2, y + boss_h + index * line_h), text_line, font=font, fill=(255, 255, 255, 255))
        boss_h += text_h + margin
    _center_text(draw, (start_label, y, start_value, y + boss_h), "BOSS", font, (255, 255, 255, 255))
    y += boss_h
    line()

    label_value("BOSS等级", data.get("boss_level", ""))
    label_value("BOSS经验", data.get("boss_exp", ""))
    label_value("油耗上限", data.get("cost_limit", ""))
    y += 2
    draw.text((start_label, y), "*彩蛋掉落暂时不显示", font=loader.font(16), fill=(255, 255, 255, 255))
    y += 20

    stage_pic = loader.image(data.get("pic", ""), fallback=(1, 1))
    if stage_pic.width > 1:
        target_w = width - end_value - 40
        target_h = int(stage_pic.height / stage_pic.width * target_w)
        canvas.alpha_composite(stage_pic.resize((target_w, target_h), Image.Resampling.LANCZOS), (end_value + 20, 20))
        y = max(y, target_h + 20)
    y += 20

    start_drop, end_drop = 120, 1260
    for drop_line in data.get("drop_lines", []):
        items = [item for item in drop_line.get("items", []) if item.get("name")]
        if not items:
            continue
        y += margin
        row_h = 40 + margin * 2
        draw.rectangle((start_label, y, end_drop, y + row_h), fill=(100, 100, 100, 50))
        x = start_drop
        for item in items:
            name = str(item.get("name", ""))
            color = _hex_color(item.get("color", "#ffffff"))
            name_w = draw.textlength(name, font=font_small)
            if x + 44 + name_w > end_drop:
                y += 40 + margin
                row_h += 40 + margin
                draw.rectangle((start_label, y, end_drop, y + 40 + margin * 2), fill=(100, 100, 100, 50))
                x = start_drop
            icon = loader.image(item.get("pic", ""), (40, 40), (40, 40))
            canvas.alpha_composite(icon, (x, y))
            x += 42
            draw.text((x, y + 10), name, font=font_small, fill=color)
            x = int(x + name_w + 2)
        y += 40 + margin
        _center_text(draw, (start_label, y - row_h, start_drop, y), drop_line.get("label", ""), font, (255, 255, 255, 255))
        draw.line((start_label, y, end_drop, y), fill=(255, 255, 255, 255), width=1)

    return _to_png(canvas.crop((0, 0, width, min(y + 20, height))))


def generate_tech_table(rows: list[list[str]], page: int = 1, assets_dir: str | os.PathLike[str] | None = None) -> io.BytesIO:
    """科技点筛选表：1200x600，每页 10 行。"""
    loader = AssetLoader(assets_dir)
    width, height, per_page = 1200, 600, 10
    start = max(0, (max(1, page) - 1) * per_page)
    page_rows = rows[start:start + per_page]
    if not page_rows:
        raise ValueError("没有更多数据了喵")

    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas, "RGBA")
    font = loader.font(20)
    columns = max(len(row) for row in page_rows)
    cell_w = width // columns
    cell_h = height // len(page_rows)

    rarity_colors = {
        "海上传奇": (238, 73, 76),
        "决战方案": (204, 0, 102),
        "超稀有": (204, 0, 102),
        "精锐": (128, 0, 255),
        "稀有": (0, 0, 255),
        "普通": (0, 0, 0),
    }

    for index in range(len(page_rows) + 1):
        draw.line((0, index * cell_h, width, index * cell_h), fill=(0, 0, 0, 255))
    for index in range(columns + 1):
        draw.line((index * cell_w, 0, index * cell_w, height), fill=(0, 0, 0, 255))

    for row_index, row in enumerate(page_rows):
        for column_index, value in enumerate(row):
            fill = (0, 0, 0)
            if column_index == 0 and len(row) > 2:
                fill = rarity_colors.get(row[2], (0, 0, 0))
            _center_text(
                draw,
                (column_index * cell_w, row_index * cell_h, (column_index + 1) * cell_w, (row_index + 1) * cell_h),
                value,
                font,
                fill,
            )
    return _to_png(canvas)
