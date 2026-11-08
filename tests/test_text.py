import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blhxwiki.utils.text import user_id_from_kwargs


def test_direct_user_id() -> None:
    assert user_id_from_kwargs({"user_id": "123"}) == "123"


def test_message_fallback() -> None:
    kwargs = {"message": {"user_info": {"user_id": "456"}}}
    assert user_id_from_kwargs(kwargs) == "456"


def test_missing_returns_empty() -> None:
    assert user_id_from_kwargs({}) == ""
    assert user_id_from_kwargs({"message": {}}) == ""
    assert user_id_from_kwargs({"message": {"user_info": {}}}) == ""


def test_direct_takes_priority() -> None:
    kwargs = {"user_id": "123", "message": {"user_info": {"user_id": "456"}}}
    assert user_id_from_kwargs(kwargs) == "123"
