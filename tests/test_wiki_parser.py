import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blhxwiki.parser.wiki_parser import normalize_keyword, search_names


def test_normalize_keyword() -> None:
    assert normalize_keyword("拉菲（改）") == "拉菲改"
    assert normalize_keyword("U-81") == "u81"
    assert normalize_keyword("  ") == ""


def test_search_names_contains_match() -> None:
    names = ["拉菲", "拉菲.改", "标枪"]
    hits = search_names("拉菲", names)
    assert "拉菲" in hits
    assert "标枪" not in hits


def test_search_names_no_match() -> None:
    assert search_names("拉菲皮", ["拉菲", "标枪"]) == []
