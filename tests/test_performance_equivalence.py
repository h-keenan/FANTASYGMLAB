"""Golden/equivalence tests for the 2026-11 backend performance pass.

Every optimisation in docs/performance-audit-2026-11.md replaced a slow
implementation with a faster one that must return *identical* results. Each
test here keeps the original (slow) implementation inline as the oracle and
asserts the shipped code matches it exactly, on the same synthetic league
universes tests/test_drop_candidates.py uses.
"""

from __future__ import annotations

import copy

import pandas as pd
import pytest

import test_drop_candidates as tdc
from modules import drop_candidates as dc
from modules import trade_lineup_model as tlm
from modules import roster_value_model as rvm
from modules.frame_records import frame_records
from modules.trade_grade import healthy_equivalent_roster


# --- oracles: the pre-optimisation implementations, verbatim -------------------


def _legacy_row(rvc, player_id):
    match = rvc.frame[rvc.frame["player_id"].astype(str) == str(player_id)]
    return frame_records(match)[0] if not match.empty else None


def _legacy_evaluate_swap(rvc, drop_ids, add_rows=()):
    drop_set = {str(p) for p in drop_ids}
    before = rvc.frame
    keep = before[~before["player_id"].astype(str).isin(drop_set)]
    add_frame = pd.DataFrame(list(add_rows)) if add_rows else pd.DataFrame()
    after = pd.concat([keep, add_frame], ignore_index=True) if not add_frame.empty else keep
    send = [
        rvm._asset(pid, rvc.profiles[pid].name if pid in rvc.profiles else pid, rvc.healthy_value.get(pid, 0.0))
        for pid in drop_ids
    ]
    add_values = (
        healthy_equivalent_roster(add_frame, score_column=rvc.score_field, window=rvc.window)
        if not add_frame.empty
        else add_frame
    )
    add_value_by_id = {str(r["player_id"]): rvm._num(r.get(rvc.score_field)) for r in frame_records(add_values)}
    receive = [
        rvm._asset(str(r["player_id"]), rvm._text(r.get("name")), add_value_by_id.get(str(r["player_id"]), 0.0))
        for r in add_rows
    ]
    raw = sum(a["score"] for a in receive) - sum(a["score"] for a in send)
    result = tlm.evaluate_trade(
        before, after, rvc.model_ctx, send_assets=send, receive_assets=receive, raw_value_delta=raw,
        asset_value=lambda a: float(a.get("score") or 0.0),
    )
    result["raw_value_delta"] = round(raw)
    return result


# --- fixtures -------------------------------------------------------------------


def _league():
    roster = tdc._core() + [
        tdc._row("BN_WR", "WR", 700, ppg=4, age=30),
        tdc._row("BN_RB", "RB", 900, ppg=4, age=30),
        tdc._row("INJ_RB", "RB", 3000, ppg=9, status="Active", injury="Out", age=27),
        tdc._row("DOUBT_WR", "WR", 2600, ppg=8, injury="Doubtful", age=28),
        tdc._row("OLD_QB", "QB", 500, ppg=3, age=36),
    ]
    pool = tdc._pool(("WR", 1500, 9), ("RB", 1200, 8), ("TE", 900, 6), ("QB", 800, 7))
    # An injured free agent and one whose row carries an extra column the
    # roster frame lacks (forces the full-frame fallback path).
    pool.append(tdc._row("FA_INJ", "WR", 1100, ppg=8, injury="Questionable", age=25))
    pool.append(tdc._row("FA_EXTRA", "RB", 1000, ppg=7, age=25, brand_new_column=3.5))
    # A read field (proj_ppg) the roster frame lacks: kept rows would read NaN
    # after a concat, so the fast path must decline.
    pool.append(tdc._row("FA_PROJ", "WR", 1300, ppg=8, age=25, proj_ppg=12.5))
    return tdc._make(roster, pool, limit=len(roster))


def _pool_rows(rvc):
    """Pool rows as the engine passes them: only FA_EXTRA carries the extra column."""

    out = {}
    for row in rvc.pool.to_dict("records"):
        if row["player_id"] != "FA_EXTRA":
            row.pop("brand_new_column", None)
        if row["player_id"] != "FA_PROJ":
            row.pop("proj_ppg", None)
        out[row["player_id"]] = row
    return out


def _swaps(rvc):
    by_id = _pool_rows(rvc)
    drops = ["BN_WR", "BN_RB", "INJ_RB", "DOUBT_WR", "OLD_QB", "NOT_ON_ROSTER"]
    cases = [([d], []) for d in drops]
    cases += [([d], [by_id[a]]) for d in drops for a in ("FA_WR0", "FA_RB1", "FA_INJ", "FA_EXTRA", "FA_PROJ", "FA_QB3")]
    cases += [(["BN_WR", "BN_RB"], [by_id["FA_WR0"], by_id["FA_TE2"]])]
    cases += [([], [by_id["FA_WR0"]])]
    # A duplicate: adding a player already on the roster must dedupe the same way.
    cases += [(["BN_WR"], [rvc.row("BN_RB")])]
    return cases


# --- tests ----------------------------------------------------------------------


def test_rvc_row_matches_the_scan_it_replaced_for_every_player_and_unknown_ids():
    rvc = _league()
    for pid in [*rvc.frame["player_id"].astype(str).tolist(), "missing", ""]:
        assert rvc.row(pid) == _legacy_row(rvc, pid), pid
        assert rvc.row(pid) == _legacy_row(rvc, pid)  # second call hits the index


def test_rvc_row_returns_a_private_copy_each_call():
    rvc = _league()
    first = rvc.row("QB1")
    first["name"] = "mutated"
    assert rvc.row("QB1")["name"] == "QB1"
    assert rvc.row("QB1") is not rvc.row("QB1")


def test_rvc_row_keeps_the_first_of_duplicate_ids_and_skips_missing_ids():
    rvc = _league()
    dup = rvc.frame.iloc[[0]].copy()
    dup["name"] = "second copy"
    nan_row = rvc.frame.iloc[[1]].copy()
    nan_row["player_id"] = None
    rvc.frame = pd.concat([rvc.frame, dup, nan_row], ignore_index=True)
    rvc._row_index = None
    first_id = str(rvc.frame.iloc[0]["player_id"])
    assert rvc.row(first_id) == _legacy_row(rvc, first_id)
    assert rvc.row(first_id)["name"] != "second copy"
    assert rvc.row("None") is None


def test_evaluate_swap_is_identical_to_the_full_frame_implementation():
    rvc = _league()
    checked = 0
    for drops, adds in _swaps(rvc):
        want = _legacy_evaluate_swap(rvc, drops, adds)
        got = rvm.evaluate_swap(rvc, drops, adds)
        assert got == want, (drops, [a["player_id"] for a in adds])
        checked += 1
    assert checked >= 30


def test_profile_swap_after_matches_profile_roster_of_the_concatenated_frame():
    rvc = _league()
    for drops, adds in _swaps(rvc):
        drop_set = {str(d) for d in drops}
        add_frame = pd.DataFrame(list(adds)) if adds else pd.DataFrame()
        keep = rvc.frame[~rvc.frame["player_id"].astype(str).isin(drop_set)]
        after = pd.concat([keep, add_frame], ignore_index=True) if not add_frame.empty else keep
        got = tlm.profile_swap_after(rvc.frame, drop_set, add_frame, rvc.model_ctx)
        if got is None:
            continue  # fallback path: caller profiles the full frame
        assert got == tlm.profile_roster(after, rvc.model_ctx), (drops, [a["player_id"] for a in adds])


def test_swap_fast_path_is_used_for_ordinary_adds_and_declines_when_columns_differ():
    rvc = _league()
    pool = _pool_rows(rvc)
    ordinary = pd.DataFrame([pool["FA_WR0"]])
    assert tlm.profile_swap_after(rvc.frame, {"BN_WR"}, ordinary, rvc.model_ctx) is not None
    unread_extra = pd.DataFrame([pool["FA_EXTRA"]])  # a column the model never reads: still fast
    assert tlm.profile_swap_after(rvc.frame, {"BN_WR"}, unread_extra, rvc.model_ctx) is not None
    read_extra = pd.DataFrame([pool["FA_PROJ"]])  # a column the model reads and the roster frame lacks
    assert tlm.profile_swap_after(rvc.frame, {"BN_WR"}, read_extra, rvc.model_ctx) is None


def test_drop_engine_outputs_are_unchanged():
    """End-to-end over the engine that calls row()/evaluate_swap thousands of times."""

    rvc = _league()
    pool = _pool_rows(rvc)
    got = [
        dc.suggest_drop_for_add(rvc, pool[a], untouchable=set(), usage={}) for a in ("FA_WR0", "FA_RB1", "FA_QB3")
    ]
    rvc_ref = _league()
    original_row, original_swap = type(rvc_ref).row, rvm.evaluate_swap
    try:
        type(rvc_ref).row = lambda self, pid: _legacy_row(self, pid)
        rvm.evaluate_swap = _legacy_evaluate_swap
        pool_ref = _pool_rows(rvc_ref)
        want = [
            dc.suggest_drop_for_add(rvc_ref, pool_ref[a], untouchable=set(), usage={}) for a in ("FA_WR0", "FA_RB1", "FA_QB3")
        ]
    finally:
        type(rvc_ref).row = original_row
        rvm.evaluate_swap = original_swap
    assert got == want


def test_frame_records_dtype_classification_is_cached_and_stable():
    frame = pd.DataFrame({"a": [1.0, 2.0], "b": ["x", None], "c": [True, False], "d": pd.to_datetime(["2026-01-01"] * 2)})
    assert frame_records(frame) == frame.to_dict("records")  # slow dtype (datetime) falls back
    assert frame_records(frame[["a", "b", "c"]]) == frame[["a", "b", "c"]].to_dict("records")
    assert frame_records(frame[["a", "b", "c"]]) == frame[["a", "b", "c"]].to_dict("records")  # cached kinds


def test_swap_cache_serves_equal_independent_results_and_never_conflates_rows():
    rvc = _league()
    pool = _pool_rows(rvc)
    first = rvm.evaluate_swap(rvc, ["BN_WR"], [pool["FA_WR0"]])
    assert rvc.swap_cache, "a plain-scalar swap should be memoized"
    again = rvm.evaluate_swap(rvc, ["BN_WR"], [dict(pool["FA_WR0"])])  # new dict, same content
    assert again == first == _legacy_evaluate_swap(rvc, ["BN_WR"], [pool["FA_WR0"]])
    again["trade_score"] = -1  # callers decorate results: must not leak into the cache
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [pool["FA_WR0"]]) == first
    # Same player id, different content (a changed projection) is a different swap.
    changed = {**pool["FA_WR0"], "ppg": 30.0, "value_score": 9000}
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [changed]) == _legacy_evaluate_swap(rvc, ["BN_WR"], [changed])
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [changed]) != first
    # Different drop, same add.
    assert rvm.evaluate_swap(rvc, ["BN_RB"], [pool["FA_WR0"]]) == _legacy_evaluate_swap(rvc, ["BN_RB"], [pool["FA_WR0"]])


def test_swap_with_non_scalar_cells_is_not_memoized():
    rvc = _league()
    row = {**_pool_rows(rvc)["FA_WR0"], "notes": ["a", "b"]}
    assert rvm._swap_key(["BN_WR"], [row]) is None
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [row]) == _legacy_evaluate_swap(rvc, ["BN_WR"], [row])
    assert not rvc.swap_cache


def test_aged_profiles_are_memoized_without_changing_values():
    rvc = _league()
    for p in rvc.profiles.values():
        for years in (1, 2, 3):
            tlm._AGED_CACHE.clear()
            fresh = tlm._aged(p, years)
            assert tlm._aged(p, years) is tlm._aged(p, years)
            assert tlm._aged(p, years) == fresh


# --- player_quick_view percentiles ------------------------------------------------


def _legacy_percentile_from_values(values, positions):
    from modules.player_quick_view import PERCENTILE_MIN_POOL

    pool_sizes = values.groupby(positions).transform(lambda s: int(s.notna().sum()))
    ranks = values.groupby(positions).rank(pct=True)
    return pd.Series(
        [
            int(min(100, max(1, round(float(p) * 100)))) if not pd.isna(p) and n >= PERCENTILE_MIN_POOL else None
            for p, n in zip(ranks, pool_sizes)
        ],
        index=values.index,
        dtype=object,
    )


@pytest.mark.parametrize("seed", range(6))
def test_vectorized_percentiles_match_the_per_group_lambda_version(seed):
    import numpy as np

    from modules.player_quick_view import _percentile_from_values

    rng = np.random.default_rng(seed)
    n = int(rng.integers(1, 400))
    values = pd.Series(np.where(rng.random(n) < 0.25, np.nan, np.round(rng.random(n) * 20, int(rng.integers(0, 3)))))
    values.index = rng.permutation(n) + 10  # non-default, non-sorted index
    positions = pd.Series(rng.choice(["QB", "RB", "WR", "TE", "K", "DEF"], size=n, p=[0.05, 0.3, 0.4, 0.2, 0.03, 0.02]), index=values.index)
    positions = positions.where(rng.random(n) > 0.03, None)  # some missing positions
    want = _legacy_percentile_from_values(values, positions)
    got = _percentile_from_values(values, positions)
    assert list(got.index) == list(want.index)
    assert got.tolist() == want.tolist()
    assert all(v is None or type(v) is int for v in got.tolist())


def test_vectorized_percentiles_handle_empty_and_all_missing():
    from modules.player_quick_view import _percentile_from_values

    empty = pd.Series([], dtype="float64")
    assert _percentile_from_values(empty, pd.Series([], dtype=object)).tolist() == []
    nan = pd.Series([float("nan")] * 12)
    pos = pd.Series(["WR"] * 12)
    assert _percentile_from_values(nan, pos).tolist() == _legacy_percentile_from_values(nan, pos).tolist() == [None] * 12


# --- news identity scan -----------------------------------------------------------


def _legacy_index_matches(text, index):
    from modules import news_signal

    matches = []
    for normalized_name, player_id in index.items():
        normalized = str(normalized_name or "").strip()
        pid = str(player_id or "").strip()
        if normalized and pid and news_signal.contains_phrase(text, normalized):
            matches.append((normalized, pid))
    return matches


def test_phrase_index_matches_equals_the_contains_phrase_loop():
    import random

    from modules import news_signal

    rng = random.Random(7)
    first = ["josh", "ja'marr", "amon-ra", "a.j.", "cj", "de'von", "tank", "kyle", "bo", "d.k.", "lamar", "jalen", "mike"]
    last = ["allen", "chase", "st. brown", "brown", "stroud", "achane", "jackson", "hurts", "evans", "nacua", "o'dell"]
    names = {f"{rng.choice(first)} {rng.choice(last)}": str(i) for i in range(400)}
    names.update({"  tank  ": "900", "": "901", "bo": "", "ward": "902", "al": "903", "  Mixed Case ": "904", None: "905"})
    pieces = list(names)[:60] + ["the", "reported", "Sunday", "bo", "ward", "al", "tankard", "towards", "ALLEN", "Josh  Allen", "ja'marr chase!", "amon-ra st. brown."]
    for _ in range(300):
        text = " ".join(rng.choice(pieces) or "" for _ in range(rng.randint(0, 25)))
        if rng.random() < 0.2:
            text = text.upper()
        assert news_signal.phrase_index_matches(text, names) == _legacy_index_matches(text, names), text
    for text in ("", None, 5):
        assert news_signal.phrase_index_matches(text, names) == _legacy_index_matches(text, names)


# --- healthy_equivalent_roster ------------------------------------------------------


def _legacy_healthy_equivalent_roster(df, *, score_column, window):
    from modules.trade_grade import _number, estimate_injury_absence, healthy_restore_factor

    if df is None or df.empty or "player_id" not in df.columns:
        return df
    status = df["status"] if "status" in df.columns else pd.Series("", index=df.index)
    injury = df["injury_status"] if "injury_status" in df.columns else pd.Series("", index=df.index)
    body = df["injury_body_part"] if "injury_body_part" in df.columns else pd.Series("", index=df.index)
    notes = df["injury_notes"] if "injury_notes" in df.columns else pd.Series("", index=df.index)
    mask = []
    for s, i, b, n in zip(status.tolist(), injury.tolist(), body.tolist(), notes.tolist()):
        mask.append(estimate_injury_absence(s, i, body_part=b, notes=n, window=window) is not None)
    if not any(mask):
        return df
    out = df.copy()
    flagged = pd.Series(mask, index=out.index)
    if score_column in out.columns:
        restored = []
        for idx, row in out.loc[flagged].iterrows():
            factor = healthy_restore_factor(row.to_dict(), score_column)
            value = _number(row.get(score_column), 0.0)
            restored.append(value / factor if factor > 0 else value)
        out[score_column] = pd.to_numeric(out[score_column], errors="coerce").astype("float64")
        out.loc[flagged, score_column] = restored
    if "status" in out.columns:
        out.loc[flagged, "status"] = "Active"
    if "injury_status" in out.columns:
        out.loc[flagged, "injury_status"] = ""
    return out


@pytest.mark.parametrize("variant", ["plain", "risk", "risk_lens"])
@pytest.mark.parametrize("score_column", ["dynasty_score", "value_score", "rebuild_score"])
def test_healthy_equivalent_roster_matches_the_iterrows_version(variant, score_column):
    rvc = _league()
    frame = rvc.frame.copy()
    frame["rebuild_score"] = frame["dynasty_score"] * 0.9
    if variant != "plain":
        n = len(frame)
        frame["risk_multiplier"] = [0.8 + 0.01 * (i % 15) for i in range(n)]
        frame["search_rank"] = [None if i % 6 == 0 else i * 3 for i in range(n)]
        frame["team"] = ["KC", "BUF", "", "SF", "DAL"][: 1] * n
        frame.loc[frame.index[::7], "team"] = ""
    if variant == "risk_lens":
        frame["league_settings_multiplier"] = 1.05
    for col in ("injury_body_part", "injury_notes"):
        frame[col] = [("knee" if col == "injury_body_part" else "ACL surgery") if i % 4 == 0 else None for i in range(len(frame))]
    got = healthy_equivalent_roster(frame, score_column=score_column, window=tdc.WINDOW)
    want = _legacy_healthy_equivalent_roster(frame, score_column=score_column, window=tdc.WINDOW)
    pd.testing.assert_frame_equal(got, want)
    assert (got[score_column] != frame[score_column]).any() or variant == "plain"


# --- profile_roster column narrowing --------------------------------------------------


class _RecordingRow(dict):
    reads: set = set()

    def get(self, key, default=None):
        _RecordingRow.reads.add(key)
        return super().get(key, default)

    def __getitem__(self, key):
        _RecordingRow.reads.add(key)
        return super().__getitem__(key)


def test_profile_roster_reads_only_the_declared_columns(monkeypatch):
    """Guards ``_PROFILE_ROW_COLUMNS``: if profile_roster ever reads another row field this fails."""

    rvc = _league()
    frame = rvc.frame.copy()
    for col in ("injury_body_part", "injury_notes", "proj_ppg", "proj_sd", "proj_scoring_applied"):
        frame[col] = None
    frame["proj_ppg"] = 10.0
    frame["proj_scoring_applied"] = True
    _RecordingRow.reads = set()
    ctx = rvc.model_ctx
    # Hand the recorder the FULL-width rows (bypassing the narrowing) and see what is read.
    full_rows = [_RecordingRow(r) for r in frame.to_dict("records")]
    monkeypatch.setattr(tlm, "frame_records", lambda f: full_rows)
    tlm.profile_roster(frame, ctx)
    assert _RecordingRow.reads <= (tlm._PROFILE_ROW_COLUMNS | {ctx.score_column}), _RecordingRow.reads


def test_profile_roster_is_unchanged_by_dropping_unread_columns():
    rvc = _league()
    frame = rvc.frame.copy()
    frame["proj_ppg"] = [None if i % 3 == 0 else 8.0 + i for i in range(len(frame))]
    frame["injury_body_part"] = ["knee" if i % 5 == 0 else None for i in range(len(frame))]
    noisy = frame.copy()
    noisy["unrelated_a"] = "x"
    noisy["unrelated_b"] = range(len(frame))
    assert tlm.profile_roster(noisy, rvc.model_ctx) == tlm.profile_roster(frame, rvc.model_ctx)
    expected_full = _legacy_profile_roster(noisy, rvc.model_ctx)
    assert tlm.profile_roster(noisy, rvc.model_ctx) == expected_full


def _legacy_profile_roster(df, ctx):
    """profile_roster over the FULL-width conversion (the pre-narrowing behaviour)."""

    original = tlm._PROFILE_ROW_COLUMNS
    try:
        tlm._PROFILE_ROW_COLUMNS = frozenset(df.columns)
        return tlm.profile_roster(df, ctx)
    finally:
        tlm._PROFILE_ROW_COLUMNS = original


def test_active_rows_and_build_context_values_ignore_unread_columns():
    rvc = _league()
    base = rvc.all_players.copy()
    noisy = base.copy()
    noisy["unrelated"] = "x"
    for col in ("ppg", "games_played", "receptions"):
        assert col in noisy.columns
    scoring = rvc.model_ctx.scoring
    assert tlm._active_rows(noisy, "dynasty_score", scoring) == tlm._active_rows(base, "dynasty_score", scoring)
    # Reference: the full-width conversion.
    full = {pos: [] for pos in tlm.SCORED_POSITIONS}
    for row in frame_records(base):
        pos = tlm._text(row.get("position")).upper()
        if pos not in full:
            continue
        games = tlm._num(row.get("games_played"), 0.0) or 0.0
        ppg = tlm._num(row.get("ppg"))
        value = tlm._num(row.get("dynasty_score"))
        if ppg is None or value is None or games < 3 or value <= 0:
            continue
        full[pos].append((value, tlm._league_scored(ppg, row, pos, scoring)))
    for pos in full:
        full[pos].sort(key=lambda item: -item[0])
    assert tlm._active_rows(base, "dynasty_score", scoring) == full


def test_swap_accepts_series_rows_like_the_callers_that_pass_iterrows_rows():
    rvc = _league()
    row = pd.Series(_pool_rows(rvc)["FA_WR0"])
    assert rvm._swap_key(["BN_WR"], [row]) is not None
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [row]) == _legacy_evaluate_swap(rvc, ["BN_WR"], [row])
    assert rvm.evaluate_swap(rvc, ["BN_WR"], [row]) == rvm.evaluate_swap(rvc, ["BN_WR"], [dict(row)])


def test_phrase_index_prep_cache_follows_content_not_identity():
    from modules import news_signal

    index = {"josh allen": "1", "tank dell": "2"}
    text = "Josh Allen and Tank Dell"
    assert news_signal.phrase_index_matches(text, index) == [("josh allen", "1"), ("tank dell", "2")]
    index["tank dell"] = "9"  # mutated in place: same object, new content
    assert news_signal.phrase_index_matches(text, index) == [("josh allen", "1"), ("tank dell", "9")]
    index.pop("josh allen")
    assert news_signal.phrase_index_matches(text, index) == [("tank dell", "9")]
    assert news_signal.phrase_index_matches(text, {}) == []
