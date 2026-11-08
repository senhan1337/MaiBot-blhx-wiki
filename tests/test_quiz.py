import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from blhxwiki.features.quiz import _pick_candidates


def test_pick_candidates_no_duplicates() -> None:
    picks = _pick_candidates(["a", "b", "c", "d", "e"], 3)
    assert len(picks) == 3
    assert len(set(picks)) == 3
    assert set(picks) <= {"a", "b", "c", "d", "e"}


def test_pick_candidates_small_pool_returns_all() -> None:
    assert _pick_candidates(["a", "b"], 5) == ["a", "b"]


def test_pick_candidates_skips_empty_names() -> None:
    assert _pick_candidates(["", "a", "b"], 5) == ["a", "b"]
