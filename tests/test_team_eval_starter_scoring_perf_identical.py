"""`_score_starter_weighted_roster` was rewritten to read positions once (perf
audit 2026-10); its output must stay identical to the original pandas-lookup
version. The reference below is that original selection logic."""

import random

import pandas as pd

from modules import team_eval


def _reference(df_team, lineup_settings=None, score_field="dynasty_score"):
    df = df_team.copy()
    df[score_field] = pd.to_numeric(df[score_field], errors="coerce").fillna(0)
    df = df.sort_values(score_field, ascending=False).reset_index(drop=True)
    slots = team_eval._lineup_slots(lineup_settings)
    used, starters = set(), []

    def pick(pos, limit):
        for idx in df.index[df["position"] == pos].tolist():
            if len([i for i in starters if df.loc[i, "position"] == pos]) >= limit:
                break
            if idx not in used:
                used.add(idx)
                starters.append(idx)

    for pos in ("QB", "RB", "WR", "TE"):
        pick(pos, slots[pos])
    pick("K", slots.get("K", 0))
    for eligible, name in ((["RB", "WR"], "WR/RB"), (["WR", "TE"], "REC_FLEX"), (["RB", "WR", "TE"], "FLEX"), (["QB", "RB", "WR", "TE"], "SUPER_FLEX")):
        cands = [i for i in df.index if df.loc[i, "position"] in eligible and i not in used]
        for i in cands[: slots.get(name, 0)]:
            used.add(i)
            starters.append(i)
    mask = df.index.isin(starters)
    bench = ~mask
    starter_score = float(df.loc[mask, score_field].sum())
    bench_score = float(df.loc[bench, score_field].nlargest(team_eval._bench_score_limit(lineup_settings)).sum()) * team_eval.BENCH_WEIGHT
    weighted = df[score_field].where(mask, df[score_field] * team_eval.BENCH_WEIGHT)

    def ps(pos):
        m = df["position"] == pos
        return float(weighted.loc[m].sum()) if m.any() else 0.0

    return {
        "total_score": starter_score + bench_score,
        "starter_score": starter_score,
        "bench_score": bench_score,
        "raw_roster_score": float(df[score_field].sum()),
        "qb_score": ps("QB"),
        "rb_score": ps("RB"),
        "wr_score": ps("WR"),
        "te_score": ps("TE"),
    }


def test_starter_weighted_score_matches_reference_selection():
    rng = random.Random(7)
    settings = [None, {"superflex_count": 1}, {"qb_count": 2, "rb_count": 3, "wr_count": 1, "te_count": 0, "flex_count": 2, "wrrb_flex_count": 1, "rec_flex_count": 1}]
    for trial in range(60):
        rows = [
            {"position": rng.choice(["QB", "RB", "WR", "TE", "K", "LB"]), "dynasty_score": rng.random() * 100}
            for _ in range(rng.randint(1, 28))
        ]
        df = pd.DataFrame(rows)
        if trial % 2:
            df["position"] = df["position"].astype("string[pyarrow]")
        for s in settings:
            assert team_eval._score_starter_weighted_roster(df, lineup_settings=s) == _reference(df, s)
