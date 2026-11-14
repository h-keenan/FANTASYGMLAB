# Sim realism audit 3: economy, markets, draft, season structure, exploits (2026-11)

Ask (coridian_): "do another deep realisticness audit". Scope: what audits 1-2 did not cover. Harness (committed, deterministic, real 2025 panel, never `data/players.db`):
`python -m modules.sim.calibration.economy_audit season|exploit|draft|market|wire|long` (+ `economy_audit_more.py`). Bots are paired: same seed = same snapshot, dice and AI,
so a bot and the baseline differ only by what the bot does; baseline = auto lineup + hole-filling wire. Live report that triggered the priority: the AI called
"Brissett + a 2027 R3 + R4 for Josh Allen" fair value (regression test below).

## Findings, severity ranked (audit first)

| # | Sev | Finding | Evidence (sim vs real/expected) | Status |
| --- | --- | --- | --- | --- |
| 1 | High | **Trade desk is farmable in dynasty.** Persona lenses disagree (a contender values a pick x0.76, a youth hoarder x1.32), a user can probe unlimited offers, and AIs accept up to 3-10 linear worth lost per deal | farmer bot **+2.54 wins/season (se 0.36, 60 seasons)**, stacker +1.60 (0.38), injured-star buyer +1.50 (0.41); gains grow to +3.5..+4.0 by season 5; each accepted deal gave the user +6..+26 asset value (2-4% of a 700 roster) | Fixed (econ_v 1): farmer +0.62 (0.37) / +0.88 (0.40 over 10 seasons), stacker +0.02, injured -0.73 |
| 2 | High | **Elite player for a mid starter plus late picks accepted as "fair value"** (reported: Brissett + R3 + R4 for Josh Allen). Causes: picks R2/R3 worth 1.4-1.5x the rookie they become; "now" worth had no replacement level (a body at a thin position was priced like production, though the wire gives it free); lineup "need" counted a free-agent-level player as an upgrade | pick value / rookie value by slot: 1.01 0.75, 1.06 0.83, 1.12 1.25, R2 1.44, R3 1.46 | Fixed (econ_v 1), regression test |
| 3 | High | **Pick curve disagrees with the rookies it produces** (geometric 70 x 0.945/slot vs the real generated curve 95 at 1.01, 66 at 1.06, 30 at 1.12, 12.5 at 2.12, 7.3 at 3.12). Buying top picks and selling R2/R3 is free value | `economy_audit draft` over 72 rookie drafts per league size (10/12/14 teams): the curve is the same for every size | Fixed: curve = measured rookie value (`picks.ROOKIE_SLOT_KNOTS`) |
| 4 | Medium | Injury discount: a player out for the whole season keeps 40% of his "now" value (cap 6 weeks / 60%); out 9+ weeks was valued 0.62 of healthy in dynasty, 0.51 in redraft. Redraft AIs overpay for season-ending injuries, dynasty buyers profit | `market`: worth ratio by weeks out 4-5: 0.71/0.62, 6-8: 0.61/0.51, 9+: 0.62/0.51 (dynasty/redraft) | Fixed: discount = share of the season missed; sellers anchor on the healthy price |
| 5 | Medium | Kicker sweetener: a K (base value 1.2) added to an offer moves the AI margin +7.5 (dynasty) / +9.2 (redraft), more than the accept threshold (5) | `market` probe | Fixed (free-agent cover in lineup need): +3.0 / +6.5; the rest is a real kicker-slot upgrade |
| 6 | Medium | Rookie hit rates too kind at the top, UDFA too rich | starter-level within 3 years (QB/TE top 12, RB/WR top 30): picks 1-6 **90%**, 7-12 76%, R2 35%, R3 20% (real R1 about 65-70%, R2 about 35%, R3 about 20%); undrafted rookies 10% over 8 ppg in year 1 (real 3-5%); every generated rookie plays 8+ games (93%) | Reported (player-model/generator change, PR2) |
| 7 | Medium | QB talent waves in 20-season dynasties: rank-12 QB ppg 15.5 (s1-5) -> 8-11 in seasons 10-15 in 2 of 4 seeds, QBs ranked 1-24 age 28 -> 32; recovers by s20 (world_v 1 halves it, does not remove it) | `economy_audit long` | Reported; belongs to the aging/retirement work |
| 8 | Medium | K and DEF weekly tails heavy: K sd 5.75 vs real 4.67, P(>=15) 13.4% vs 8.4%, P(>=20) 4.2% vs 1.6%; DEF sd 7.3 (cv .75), P(>=20) 7% vs about 2.5% (DEF real value is from memory, K from the panel) | `kvar` probe, 12 seeds | Reported (model change, PR2) |
| 9 | Low | Startup draft: the AI follows ADP tightly after round 4: mean |pick - ADP| 4.6-7 picks in rounds 4-10 (real mocks about 10-15); all 12 teams take a kicker in round 12 (the first round kickers are allowed) | `draft` | Reported |
| 10 | Low | Playoffs: higher seed wins 51% in the 12-team 6-seed bracket (n=1000 games; 52% over all shapes), 59% in 8-team; real about 55-60% | `season` 40 seeds x 8 shapes | Reported (parity is right: win% sd 0.147-0.158) |
| 11 | Low | No variance information: the public band is proportional to the mean, so "start by ceiling" picks the same lineup as by projection (0% difference); no opponent/matchup effect, so DEF/K streaming is worth exactly 0 (-0.05 wins, se 0.21) | `exploit` ceiling / streamer bots | Reported (realism gap, not an exploit) |
| 12 | Low | AI persona age preference is not expressed in dynasty trades: equal-value young-for-old swaps are accepted 34% vs old-for-young 33% (contenders 36/31, rebuilders 30/40: backwards) | `market` 6 seeds | Reported |
| 13 | Info | Harness caveat: the panel pool holds 33 QBs (1.0 per NFL team), so the QB wire is empty from week 7; not a product finding | `wire` | Noted |

Checked and fine (no action): redraft trade/waiver farming (lineup trader +0.44 se 0.27; churner +0.16 se 0.25; farmer/stacker -0.4..-0.8), superflex QB hoarding (+0.07 se 0.13, 40 seeds),
K/DEF streaming, schedule (fresh round robin each season, max 2 repeats, opponent-strength sd 1%), seeding/tiebreakers/reseeding, bracket pairings, weekly team score sd 21 (12 teams),
week-1 to last-week score drift -9%, pythagorean correlation 0.85, AI-AI trade volume (dynasty 10.7 per league-season about 1.8 per team, redraft 3.7), tanking (not dominant: -4.1 wins in year 1,
about break-even by year 5 with the old trade desk, -0.6 per season after econ_v 1), free-agent depth by week (best FA RB 7.0 / WR 9.7 / TE 6.4 at week 2, 6.9 core free agents over 8 ppg, falling to 1.2 by week 8).

## Fix (econ_v 1, new games; `GameSettings.econ_v`, serialized only when non-zero)

1. **Consensus anchor** (`TradeDesk.below_market`): the AI also refuses a deal that loses more than 2 + 5% of what it gives + half its persona noise in the league's neutral lens
   (`USER_PARAMS`), the same lens that already protects the user from AI offers. Sellers anchor on the healthy price. Reason shown: "too lopsided" (`fair_floor`); counters must clear it;
   AI offers to the user must clear it too (the AI never gifts value either).
2. **Pick curve** = the rookie it becomes (`picks.pick_market_value_v2`); unknown slots use the round average.
3. **Replacement level**: "now" worth is production over the free-agent level (mean of the best 3 healthy free agents, 1 for K/DEF); the scale is re-derived so the top-24 keep their value.
4. **Free-agent cover**: every lineup a trade is judged by includes the wire (a player no better than the wire adds no "need").
5. **Injury discount** = share of the season missed (redraft: whole value; dynasty: "now" half plus a 15% sliver of the long-run half).

### Before / after (paired bots, dynasty, 12 teams, 12 seeds x 5 seasons = 60 seasons; wins/season minus baseline, se)

| bot | before | econ_v 1 |
| --- | --- | --- |
| farmer (1-1, 2-1, 1-2 asset trades) | +2.54 (0.36) | +0.62 (0.37) |
| stacker (asset trades) | +1.60 (0.38) | +0.02 (0.27) |
| injured-star buyer | +1.50 (0.41) | -0.73 (0.42) |
| pick hoarder | +0.82 (0.32) | +0.37 (0.29) |
| tank 2 seasons then buy back | +0.34 (0.47) (-4.1 in year 1) | -0.62 (0.36) |
| waiver churner | +0.41 (0.27) | +0.58 (0.31), unchanged by this work |
| lineup trader | +0.03 (0.12) | -0.13 (0.20) |

10 seasons (6 seeds, econ_v 1): farmer +0.88 (0.40), stacker -0.22, injured -0.25. Side effects: AI-AI trades 10.7 -> 9.5 (dynasty), 3.7 -> 2.7 (redraft) per league-season;
kicker sweetener margin 7.5 -> 3.0. Residual: the farmer still wins about +0.6..0.9 a season (season 5 up to +3 in one run): the AIs' convex star premium vs linear lineup scoring; left as skill edge.

### Existing saves
`econ_v` absent = byte-identical replay (golden digests with trade verdicts pinned in `tests/test_sim_econ_v.py`, captured on main before the change). A save can opt in with
`POST /v1/sim/games/{id}/fair-trades`: one `econ_upgrade` event sets `state.econ_up`, in force from that event on (the log before it replays as before; replay == resume tested; the flag is out of
the digest while 0). `home.flags.fair_trades` tells the client whether it is on. Client opt-in button (web + app) is not in this PR.

### Remaining (PR2)
Rookie hit rates / UDFA (6), QB wave (7, with the aging work), K/DEF tails (8), draft adherence and the kicker run (9), no persona age preference in dynasty (12).
