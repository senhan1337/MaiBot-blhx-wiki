import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blhxwiki.parser.command_parser import parse_wiki_command


def test_parse_ship_query() -> None:
    cmd = parse_wiki_command("wiki 拉菲")
    assert cmd is not None
    assert cmd.keyword == "拉菲"
    assert cmd.query_type == ""
    assert cmd.args == ["拉菲"]


def test_parse_ship_with_type() -> None:
    cmd = parse_wiki_command("wiki 拉菲 皮肤")
    assert cmd is not None
    assert cmd.keyword == "拉菲"
    assert cmd.query_type == "皮肤"


def test_parse_case_insensitive() -> None:
    cmd = parse_wiki_command("WIKI 拉菲")
    assert cmd is not None
    assert cmd.keyword == "拉菲"


def test_bare_wiki_returns_none() -> None:
    assert parse_wiki_command("wiki") is None
    assert parse_wiki_command("") is None
    assert parse_wiki_command("wiki   ") is None


def test_non_wiki_returns_none() -> None:
    assert parse_wiki_command("hello 拉菲") is None


def test_extra_spaces_collapsed() -> None:
    cmd = parse_wiki_command("wiki   拉菲    皮肤")
    assert cmd is not None
    assert cmd.keyword == "拉菲"
    assert cmd.query_type == "皮肤"


def test_only_wiki_primary_command() -> None:
    for text in (".wiki 拉菲", "/wiki 拉菲", "yls 拉菲"):
        assert parse_wiki_command(text) is None, text


def test_auto_split_without_spaces() -> None:
    cmd = parse_wiki_command("wiki拉菲皮肤")
    assert cmd is not None
    assert cmd.keyword == "拉菲"
    assert cmd.query_type == "皮肤"
    assert cmd.auto_split is True


def test_auto_split_prefers_longer_command() -> None:
    cmd = parse_wiki_command("wiki拉菲皮肤原图")
    assert cmd is not None
    assert cmd.keyword == "拉菲"
    assert cmd.query_type == "皮肤原图"


def test_alias_replacement() -> None:
    cmd = parse_wiki_command("wiki 金坷垃")
    assert cmd is not None
    assert cmd.keyword == "圣地亚哥"


def test_user_aliases_override_builtin() -> None:
    cmd = parse_wiki_command("wiki 老婆", {"老婆": "拉菲"})
    assert cmd is not None
    assert cmd.keyword == "拉菲"


def test_auto_split_alias() -> None:
    cmd = parse_wiki_command("wiki金坷垃皮肤")
    assert cmd is not None
    assert cmd.keyword == "圣地亚哥"
    assert cmd.query_type == "皮肤"
