from modules import launch_analytics


def test_ad_attribution_props_are_allowlisted_and_click_id_keeps_case_and_length():
    long_id = "Cj0KCQiA" + "x" * 150
    clean = launch_analytics._safe_props(
        {
            "utm_source": "meta",
            "utm_content": "video-a",
            "utm_term": "dynasty",
            "click_id": "fbclid",
            "click_id_value": long_id,
            "not_allowed": "x",
        }
    )
    assert clean["utm_content"] == "video-a"
    assert clean["utm_term"] == "dynasty"
    assert clean["click_id_value"] == long_id  # case preserved, within the 200 cap
    assert "not_allowed" not in clean


def test_click_id_value_is_capped_and_other_strings_keep_120_limit():
    clean = launch_analytics._safe_props({"click_id_value": "a" * 500, "utm_source": "b" * 500})
    assert len(clean["click_id_value"]) == 200
    assert len(clean["utm_source"]) == 120
