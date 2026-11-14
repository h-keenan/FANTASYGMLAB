# Fantasy Sim: hidden-value oracles in user-facing helpers (2026-11-14)

Follow-up to `2026-11-sim-letter-grades.md`. Letter grades hide the number, but a helper that *acts* on the hidden value is the same tell with a
button on it (coridian_: "I just try to get as many high value players and it seems to work out well, so value is a back-end tell").
This audit lists every user-facing helper, recommendation and auto action in `modules/sim` and its web + app clients, classifies the input
it uses, and moves the hidden-value ones to public information behind `settings.hint_v` 1 (new games only; a save without `hint_v` replays and
behaves exactly as before). API: `docs/fantasy-sim-api.md` ("Public-information helpers"). Code: `game_draft.choose_public`,
`game_dynasty._public_rookie`, `TradeDesk.user_cost`, `game_home._trade_weight`.

## Audit table

| Helper / surface | Input before | Class | hint_v 1 |
|---|---|---|---|
| Draft hint ("Best available for your need") and its one-tap "Draft X" button (`best_for_user`, `draft_view.hint`) | `p.value` + need bonus | hidden | public: ADP, need, bye overlap, shown grade tie-break; `why` names it |
| "Auto-pick the rest" (`POST /draft/auto`, `auto_for_user`) | same function as the hint | hidden | same public rule |
| Rookie draft auto-pick (`POST /offseason/rookie-draft/auto`, `choose_rookie(human=True)`) | `ev.worth(USER_PARAMS)` (dynasty value, age horizon) | hidden | public: rookie ADP, thin-position bump, shown grade tie-break |
| Trade counter: which asset is asked for (`build_counter` ranks by user cost) | `ev.worth(USER_PARAMS)` | hidden | public cost (ADP; pick by round); candidate set from the AI's own wants only |
| Trade counter `counter_delta.user_net_change` | hidden net, sent as -1/0/+1 | hidden, but direction only; a counter never pays the user more, so it is always "worse for you" and carries no information | unchanged; net computed from the public cost |
| Trade verdict accept / counter / decline and its reason code | AI's private valuation | the opponent's own decision (fine: it is the sim's AI, a black box to probe like a real leaguemate) | unchanged |
| Trade fairness language | none exists: the sim never says "you overpay" or shows a delta | n/a | n/a |
| Home "trade spotlight" centerpiece (`game_home`) | `p.value` | hidden | public projection |
| Draft recap team grade tie-break (`draft_recap` depth) | sum of `p.value` | hidden (0.02 weight, tie-break) | public projection |
| Auto-lineup, lineup suggestions, bye alerts | `ev.proj` / `ros_mean` (projection, results blend) | public | unchanged |
| Waiver suggestions (Home) and the free-agent list | lineup gain from `ros_mean` / `proj` | public | unchanged |
| Queue | the user's own order | public | unchanged |
| Player lists, sorts, board | shown grade, ADP, projection | public (since letter grades) | unchanged |
| Notifications, review, history, simto | no value reads (grep of `.value` / `worth` in `game_notifications`, `game_review`, `game_history`, `game_simto`) | public | unchanged |
| AI-initiated trade offers to you (`find_deal(to_user=True)`) | joint utility with the user's neutral-lens value; an offer is never below a user floor | hidden, but opponent behaviour, not a button | unchanged (see "What remains") |
| AI drafts, waivers, lineups, block offers, rookie picks | hidden value / own params | the opponent's own decisions | unchanged |

## Does the hidden value even help? (draft bots, 12 teams, 12t PPR, 36 seeds, auto lineup, explicit model id)

Same harness as the grade audit (`python -m modules.sim.calibration.grade_report bots --seeds 36`). Baseline = ADP + roster-need legality.

| Bot | wins | PF | vs baseline wins (se) | vs baseline PF (se) |
|---|---|---|---|---|
| ADP + need legality (public baseline) | 6.06 | 1370 | baseline | baseline |
| highest shown grade | 4.44 | 1216 | -1.61 (0.45) | -154 (29) |
| grade within 12 ADP spots | 5.42 | 1292 | -0.64 (0.47) | -78 (28) |
| old hint / Auto-pick (hidden value + need), hint_v 0 | 6.75 | 1411 | +0.69 (0.35) | +40 (23) |
| **hidden value alone, no need weighting** | 6.19 | 1371 | **+0.14 (0.10)** | **+0 (2)** |
| **new hint / Auto-pick (public), hint_v 1** | 6.69 | 1412 | +0.64 (0.41) | +42 (21) |
| new rule, need only (no bye penalty) | 6.67 | 1412 | +0.61 (0.39) | +42 (21) |
| new rule, bye penalty only (no need) | 6.33 | 1376 | +0.28 (0.22) | +6 (8) |

Findings:

- **The hidden number was not what made the old hint strong.** Drafting by the hidden value alone is indistinguishable from drafting by ADP
  (+0.14 wins, +0 PF): in this pool the value and ADP orders nearly coincide. The old hint's +0.7 wins came from its *positional need
  weighting* (it takes a WR or QB over a fifth RB, and fills open starter slots), which is a public strategy.
- The new public hint reproduces that edge from public inputs (+0.64 wins, +42 PF, 1.5 to 2 sigma, the same as the oracle's +0.69 / +40). So
  the oracle is closed in the sense that matters (the hint reads no hidden field, and a scrambled-values test proves it), but the hint is
  still a good drafter, because "ADP, filled needs, spread byes" is a good strategy. That is the helper working, not a leak; it cannot be made
  weaker without making it worse than a naive ADP board. The lever, if it is judged too strong: `game_draft.NEED_SPOTS` (0.8; set 0 to get the
  plain ADP baseline, +0.0 wins).
- **Not absurd**: mean reach (pick number minus ADP) is -6.5 (it takes players after their ADP, like the baseline's -6.6; the old oracle was
  -5.1); the largest reach in a draft is 0.6 ADP spots on average (oracle 10.5, grade-greedy 40); QB 2.6, RB 3.7, WR 4.1, TE 2.6, one K, no DEF, K
  in round 12 as the rules require.
- Grade-greedy stays a trap (-1.6 wins), as before.

Caveat: 36 seeds, one pool; a +0.6 wins difference is about 1.5 sigma. The directional claim "hidden value alone adds nothing, need
weighting is the edge" is solid (0.14 +/- 0.10 vs 0.61 +/- 0.39 and PF 0 vs 42).

## Tests

`tests/test_sim_hint_v.py`: settings serialization (absent when 0, old dict loads as 0); hint_v 0 hint equals the old `choose_pick`; with
hint_v 1, picking on a board whose hidden values are scrambled gives identical picks (grades pinned: they are the shown quantity); hint
response carries no value / overall / rank / market field; hint == what Auto-pick takes == the Draft button; queue wins; not absurd (reach <
40, K/DEF counts, full roster); replay determinism; rookie auto-pick and counter-ask cost and spotlight weight independent of the hidden
value; old saves keep "Best available for your need". The pre-existing old-save golden digests (`OLD_SAVE_DIGEST`, ai_v 0, model-version
goldens, `limit_v` 0 golden, dynasty v2 goldens) now strip `hint_v` like the other post-save flags; seeded-world engine/dynasty test
harnesses default to `hint_v` 0.

## What remains

- **AI-initiated offers** (`find_deal(to_user=True)`) are accepted against a neutral-lens user floor, so "accept an AI offer" is mildly
  favourable by the hidden value. It is the opponent's behaviour rather than a button, and changing it changes what AI teams propose
  (a world change that needs its own gate and a bot study: accept-all-offers vs never). Not measured here.
- The accept/decline answer for a trade you propose is the AI's private valuation. Probing it with offers is the same information channel a
  real leaguemate gives. If it matters, the gate-able mitigation is noise on
  the AI's threshold (already present: `noise(partner)`).
- ADP, the preseason projection (which tracks the hidden rating at 0.845 vs 0.842 Spearman to ROS ppg) and ros_mean remain public numbers.
- Position-relative grades, rookie ranges and the pool tables derive from the hidden value by design (noisy, 12 bands).
