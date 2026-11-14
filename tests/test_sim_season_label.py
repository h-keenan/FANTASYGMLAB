"""One season label everywhere: S3 2028 (presentation only; stored events keep plain numbers)."""

from modules.sim.season_label import season_label, season_label_for_year


def test_labels():
    assert season_label(3, 2028) == "S3 2028"
    assert season_label(1, None) == "S1"
    assert season_label(None, 2028) == "2028"
    assert season_label(None, None) == ""
    assert season_label_for_year(2028, 2026) == "S3 2028"
    assert season_label_for_year(2028, 0) == "2028"
    assert season_label_for_year(None, 2026) == ""
