"""modules.verdict_assumptions + modules.verdict_feedback (pure helpers)."""

from modules import trade_grade, verdict_assumptions, verdict_feedback

SETTINGS = {
    "qb_format": "Superflex",
    "scoring_format": "Half-PPR",
    "te_premium": True,
    "_sources": {"qb_format": "Sleeper", "scoring_format": "Sleeper", "te_premium": "Sleeper"},
}


def _build(**overrides):
    kwargs = {"lens": "Dynasty", "settings": SETTINGS, "strategy": "contender"}
    kwargs.update(overrides)
    return verdict_assumptions.build_verdict_assumptions(**kwargs)


def test_assumptions_name_format_lens_posture_and_source():
    result = _build()
    assert result["line"].startswith("Assumed: Superflex, Half-PPR, TE premium, Dynasty values, Contender posture;")
    items = {item["key"]: item["value"] for item in result["items"]}
    assert items["format"] == "Superflex, Half-PPR, TE premium (from your league settings)"
    assert items["lens"] == "Dynasty"
    assert items["posture"] == "Contender"


def test_assumptions_say_values_only_without_a_lineup_model_and_projections_with_one():
    assert "values only, no weekly projections" in _build()["line"]
    modeled = _build(lineup_model={"basis_counts": {"projection": 12, "season_average": 3, "value_estimate": 0}})
    assert "lineup impact from weekly projections, season averages" in modeled["line"]
    assert "value-derived" not in modeled["line"]


def test_injury_defaults_come_from_the_engine_constants():
    text = {item["key"]: item["value"] for item in _build()["items"]}["injury"]
    for key in ("questionable", "doubtful", "out", "ir"):
        assert f"{trade_grade.INJURY_STATUS_DEFAULT_WEEKS[key]:g}" in text
    assert "not from return dates" in text


def test_undetected_settings_are_labelled_as_defaults():
    result = _build(settings={"qb_format": "1QB", "scoring_format": "PPR", "te_premium": False, "_sources": {}})
    assert "defaults (settings not detected)" in {i["key"]: i["value"] for i in result["items"]}["format"]


def test_keeper_and_pick_assumptions_only_when_they_apply():
    keys = {item["key"] for item in _build(keeper_adjusted=True, has_picks=True)["items"]}
    assert {"keepers", "picks"} <= keys
    assert not {"keepers", "picks"} & {item["key"] for item in _build()["items"]}


def _row(**overrides):
    kwargs = dict(
        user_id="user-123", reason="values_off", surface="trade_analyzer", platform="ios", league_id="L1",
        lens="Dynasty", strategy="retool", send_ids=["a", "a", "b"], receive_ids=["c"], verdict_label="ACCEPT",
        confidence="High", value_delta="-379.04", assumptions_line="Assumed: x", environ={},
    )
    kwargs.update(overrides)
    return verdict_feedback.build_feedback_row(**kwargs)


def test_feedback_row_is_anonymous_and_free_text_free():
    row = _row()
    assert row["user_id"] is None and row["email"] == "" and row["message"] == "" and row["can_contact"] is False
    assert row["feedback_type"] == "bad_verdict" and row["category"] == "values_off"
    context = row["context"]
    assert context["send_ids"] == ["a", "b"] and context["value_delta"] == -379.0
    assert "user-123" not in str(row)


def test_account_hash_is_stable_per_account_salted_and_not_the_id():
    assert verdict_feedback.account_hash("u1", environ={}) == verdict_feedback.account_hash("u1", environ={})
    assert verdict_feedback.account_hash("u1", environ={}) != verdict_feedback.account_hash("u2", environ={})
    salted = verdict_feedback.account_hash("u1", environ={verdict_feedback.HASH_SALT_ENV: "pepper"})
    assert salted != verdict_feedback.account_hash("u1", environ={})
    assert len(salted) == 16 and "u1" not in salted


def test_feedback_rejects_unknown_reason_or_surface_and_caps_lists():
    assert _row(reason="my email is x@y.com") is None
    assert _row(surface="nowhere") is None
    assert len(_row(send_ids=[str(i) for i in range(50)])["context"]["send_ids"]) == verdict_feedback.MAX_IDS
    assert _row(platform="toaster")["context"]["platform"] == "unknown"


def test_client_reason_keys_match_the_server_list():
    """Web and app share web-next/src/lib/verdictTrust.ts's reason list; it must equal REASONS."""
    import re
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "web-next/src/lib/verdictTrust.ts").read_text()
    block = text[text.index("VERDICT_FEEDBACK_REASONS") : text.index("] as const")]
    pairs = re.findall(r'key: "([a-z_]+)", label: "([^"]+)"', block)
    assert dict(pairs) == verdict_feedback.REASONS
