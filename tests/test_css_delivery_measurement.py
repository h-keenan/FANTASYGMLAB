from scripts.measure_css_delivery import _distribution, _style_elements


class _Markdown:
    def __init__(self, value):
        self.value = value


class _Application:
    markdown = [
        _Markdown("<style>.safe{color:red}</style>"),
        _Markdown("ordinary page content"),
        _Markdown("  <STYLE>.other{display:grid}</STYLE>"),
    ]


def test_style_element_measurement_records_only_hash_size_and_position():
    result = _style_elements(_Application())

    assert [item["css_ordinal"] for item in result] == [1, 2]
    assert [item["element_ordinal"] for item in result] == [1, 3]
    assert all(len(item["sha256"]) == 64 for item in result)
    assert all(item["utf8_bytes"] > 0 for item in result)
    assert "safe" not in repr(result)
    assert "color:red" not in repr(result)


def test_distribution_handles_empty_and_directional_small_samples():
    assert _distribution([]) is None
    assert _distribution([1.0, 2.0, 3.0]) == {
        "min": 1.0,
        "mean": 2.0,
        "median": 2.0,
        "directional_p95": 3.0,
        "max": 3.0,
    }
