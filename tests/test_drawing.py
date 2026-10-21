import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PIL import Image

from blhxwiki.paint.drawing import generate_build_result_image, generate_ship_card


def test_generate_ship_card_returns_png() -> None:
    result = generate_ship_card({
        "name": "拉菲", "code": "DD-459", "rarity": "超稀有", "camp": "白鹰", "type": "驱逐",
        "attributes": {"naijiu": "2345", "paoji": "88", "leiji": "420", "hangsu": "45"},
        "time": "00:27:00", "normal_from": "2-1、2-2、3-1、3-2、3-3",
        "skills": [{"name": "所罗门的战神", "detail": "炮击时有概率提升自身属性。"}],
    })
    assert isinstance(result, io.BytesIO)
    image = Image.open(result)
    assert image.format == "PNG"
    assert image.size == (1280, 720)


def test_generate_build_result_returns_png() -> None:
    result = generate_build_result_image([{"name": "拉菲", "rarity": "SSR"}])
    image = Image.open(result)
    assert image.format == "PNG"
    assert image.size == (840, 380)


def test_ship_card_uses_bundled_assets() -> None:
    """资源已随插件分发：卡片不应是纯色空白。"""
    result = generate_ship_card({
        "name": "拉菲", "rarity": "超稀有", "camp": "白鹰", "type": "驱逐",
        "attributes": {"naijiu": "2345", "paoji": "88"},
    })
    image = Image.open(result).convert("RGB")
    colors = image.getcolors(maxcolors=2_000_000)
    assert colors is not None
    assert len(colors) > 10_000
