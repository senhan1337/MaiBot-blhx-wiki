import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blhxwiki.features.server import _display_servers
from blhxwiki.utils.server_state import ServerState, visible_servers


def test_visible_filters_placeholder_state() -> None:
    servers = [
        ServerState("官服甲", 1, 1, "官服"),
        ServerState("未开放", 99, 31, "官服"),
        ServerState("正常", 0, 2, "iOS"),
    ]
    assert [s.name for s in visible_servers(servers)] == ["官服甲", "正常"]


def test_display_cn_uses_platform_sections() -> None:
    states = [
        ServerState("莱茵演习", 1, 1, "官服"),
        ServerState("夏威夷", 0, 1, "iOS"),
        ServerState("皇家巡游", 0, 1, "渠道服"),
    ]
    rows = _display_servers(states, "国服")
    assert [r["region"] for r in rows] == ["官服", "iOS", "渠道服"]


def test_display_maintenance_mapping() -> None:
    states = [ServerState("维护中", 1, 1, "官服"), ServerState("正常", 0, 2, "官服")]
    rows = _display_servers(states, "国服")
    assert [r["maintenance"] for r in rows] == [True, False]


def test_display_foreign_region_single_section() -> None:
    states = [ServerState("ブレスト", 0, 1, "")]
    rows = _display_servers(states, "日服")
    assert rows[0]["region"] == "日服"
