from commu_aid.targets import distance_to_rect, pick_target

A = ("a", (0, 0, 100, 100))
B = ("b", (136, 0, 100, 100))  # 36 px gap to the right of A


def test_inside_picks_that_button():
    assert pick_target(50, 50, [A, B], snap_px=40) == "a"
    assert pick_target(150, 50, [A, B], snap_px=0) == "b"


def test_gap_snaps_to_nearest_button():
    assert pick_target(110, 50, [A, B], snap_px=40) == "a"
    assert pick_target(126, 50, [A, B], snap_px=40) == "b"


def test_past_the_edge_snaps_within_range_only():
    assert pick_target(50, 130, [A, B], snap_px=40) == "a"  # 30 px below A
    assert pick_target(50, 150, [A, B], snap_px=40) is None  # 50 px below A
    assert pick_target(110, 50, [A, B], snap_px=0) is None  # snapping off: gaps choose nothing


def test_distance_to_corner():
    assert distance_to_rect(103, 104, (0, 0, 100, 100)) == 5
