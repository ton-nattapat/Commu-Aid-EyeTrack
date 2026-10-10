import pytest

pytest.importorskip("PySide6")

from commu_aid.ui import theme  # noqa: E402


def test_content_area_keeps_margins():
    left, top, w, h = theme.content_area(120, 100)
    assert left == 120 and left + w == theme.CANVAS_W - 120
    assert top + h == theme.CANVAS_H - 100


def test_margins_are_clamped_so_keys_stay_large():
    _, _, w, h = theme.content_area(1000, 1000)
    assert (w - 9 * theme.GAP) / 10 >= theme.MIN_TARGET  # keyboard: 10 keys across
    assert (h - 4 * theme.KEY_GAP) / 5 >= theme.MIN_TARGET  # keyboard: 5 rows
    assert theme.content_area(-5, -5)[0] == 0
