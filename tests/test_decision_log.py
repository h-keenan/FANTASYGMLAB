"""modules.decision_log: normalization, grading, track record, Pro gating, calibration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from modules import decision_log as dl


def _trade(outcome="yes", source="advice", net=30.0, per_week=7.5, conf="high", status="ready"):
    return {
        "outcome": outcome,
        "trade_summary": {"source": source, "confidence": conf},
        "result_summary": {"status": status, "production": {"net_points_ppr": net, "avg_net_per_week": per_week, "weeks_counted": 4}},
    }


def test_normalize_rejects_unknown_kind_action_and_blank_key():
    assert dl.normalize_decision(kind="nope", rec_key="k") is None
    assert dl.normalize_decision(kind="waiver_add", rec_key="") is None
    assert dl.normalize_decision(kind="waiver_add", rec_key="k", action="maybe") is None


def test_shown_ping_never_carries_action_so_upsert_cannot_downgrade():
    row = dl.normalize_decision(kind="waiver_add", rec_key="w:1", recommended_ids=["1"], alternative_ids=["2"])
    assert "action" not in row and "acted_at" not in row
    acted = dl.normalize_decision(kind="waiver_add", rec_key="w:1", action="accepted")
    assert acted["action"] == "accepted" and acted["acted_at"]


def _stats(pid, pts):
    return {pid: {"weekly": [{"week": w + 1, "fantasy_points_ppr": p} for w, p in enumerate(pts)]}}


def test_grade_right_wrong_even_and_insufficient():
    now = datetime(2026, 11, 1, tzinfo=timezone.utc)
    shown = (now - timedelta(days=28)).isoformat()
    row = {"shown_at": shown, "snapshot": {"recommended_ids": ["a"], "alternative_ids": ["b"]}}
    stats = {**_stats("a", [15, 15, 15, 15]), **_stats("b", [5, 5, 5, 5])}
    assert dl.grade_decision(row, stats, now=now)["outcome"] == "right"
    assert dl.grade_decision(row, {**_stats("a", [5] * 4), **_stats("b", [15] * 4)}, now=now)["outcome"] == "wrong"
    assert dl.grade_decision(row, {**_stats("a", [10] * 4), **_stats("b", [9] * 4)}, now=now)["outcome"] == "even"
    assert dl.grade_decision(row, {}, now=now)["status"] == "insufficient_data"
    no_alt = {"shown_at": shown, "snapshot": {"recommended_ids": ["a"]}}
    assert dl.grade_decision(no_alt, stats, now=now)["reason"] == "no_alternative"


def test_free_gets_basic_only_and_pro_gets_advanced():
    rows = [_trade(), _trade(net=-20, per_week=-5), _trade(outcome="no")]
    free = dl.build_track_record(rows, [], is_pro=False)
    assert free["advanced"] is None
    assert free["basic"]["trades_graded"] == 2
    assert free["basic"]["worked_out"] == 1 and free["basic"]["didnt_pan_out"] == 1
    assert free["basic"]["net_points_total"] == 10.0
    pro = dl.build_track_record(rows, [], is_pro=True)
    assert pro["advanced"]["advice"]["n"] == 2


def test_small_samples_never_claim_a_rate_or_a_gap():
    rows = [_trade(source="advice")] * 3 + [_trade(source="own", net=5, per_week=1.0)] * 3
    adv = dl.build_track_record(rows, [], is_pro=True)["advanced"]
    assert adv["advice"]["hit_rate"] is None
    assert adv["compare"]["verdict"] == "too_early"
    assert all(not b["supported"] for b in adv["calibration"].values())


def test_calibration_requires_min_sample_and_gap_needs_two_se():
    good = [_trade(net=30 + i, per_week=7.5, conf="high") for i in range(10)]
    bad_own = [_trade(source="own", net=-30 - i, per_week=-7.5) for i in range(8)]
    adv = dl.build_track_record(good + bad_own, [], is_pro=True)["advanced"]
    assert adv["calibration"]["high"]["supported"] is True
    assert adv["calibration"]["high"]["hit_rate"] == 1.0
    assert adv["compare"]["verdict"] == "advice_ahead"
    noisy_adv = [_trade(net=v, per_week=2.6 if v > 0 else -2.6) for v in (40, -35, 25, -30, 20, -15)]
    noisy_own = [_trade(source="own", net=v, per_week=2.6 if v > 0 else -2.6) for v in (38, -33, 22, -28, 18, -12)]
    assert dl.build_track_record(noisy_adv + noisy_own, [], is_pro=True)["advanced"]["compare"]["verdict"] == "within_noise"


def test_decision_rows_split_followed_vs_skipped():
    def drow(action, edge, outcome):
        return {"kind": "waiver_add", "action": action, "confidence": "medium",
                "result": {"status": "ready", "edge_pts": edge, "outcome": outcome}}

    rows = [drow("accepted", 20, "right"), drow("ignored", 18, "right"), drow("shown", 5, "right"),
            {"kind": "start_sit", "action": "opposite", "result": {"status": "insufficient_data"}}]
    adv = dl.build_track_record([], rows, is_pro=True)["advanced"]
    assert adv["followed"]["n"] == 1 and adv["skipped"]["n"] == 1
    assert adv["by_kind"]["waiver_add"]["n"] == 2
