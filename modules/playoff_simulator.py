"""Monte Carlo rest-of-season playoff-odds simulation.

Built entirely on real inputs already fetched/computed elsewhere in this
app — never an invented schedule or strength metric:

- **Schedule**: ``modules.sleeper.get_matchups`` (grouped by ``matchup_id``
  per week) for both the weeks already played (to calibrate the win-
  probability model below against this league's own real results) and the
  weeks still to come (the actual remaining matchup pairings to simulate).
  A future week Sleeper hasn't published pairings for yet is simply left
  out of the simulated schedule rather than invented.
- **Team strength**: ``modules.league_rankings``'s real Roster Power
  ``power_score`` (same number the Teams screen/Team Rankings board show)
  is the only team-strength signal — never a new valuation metric.
- **Current record/tiebreakers**: ``modules.league_standings``'s real
  wins/losses/ties/points-for/points-against, the same fields and the same
  tiebreak order (wins desc, win% desc, points-for desc, points-against
  asc, team name asc) the Standings board already uses.
- **Format**: the real ``playoff_teams``/``playoff_week_start`` league
  settings ``modules.league_standings``/``modules.gm_plan`` already read —
  never an assumed bracket size.

## Win-probability model

Each remaining matchup's win probability is a **single-parameter logistic
function of the two teams' real Roster Power ``power_score`` differential**,
z-scored against this league's own power_score spread so the model is
scale-free:

    p(team A beats team B) = sigmoid(slope * (z_A - z_B))

No intercept: there is no "home field"/first-mover edge between two
fantasy rosters, so a symmetric model (``p(A beats B) == 1 - p(B beats
A)``) is the honest shape, not an extra free parameter to fit.

``slope`` is fit by maximum likelihood against this league's own
season-to-date real results (every completed matchup this season: higher-
power_score team's z-differential vs. whether it actually won) whenever
there are enough completed games to do that safely (see
``MIN_GAMES_TO_FIT``); small-sample MLE for a single logistic parameter is
numerically stable (one Newton-Raphson update per iteration, clamped to
avoid runaway separation — see ``MAX_FIT_SLOPE``), so no second
regularization mechanism is needed, INCLUDING when this season's completed
games so far are perfectly (or near-perfectly) one-sided — e.g., every
completed game has gone the way the power-score gap implied. An
unclamped MLE genuinely diverges toward an infinite slope in that case
(there is no counterexample to pull it back toward a finite estimate), but
``MAX_FIT_SLOPE`` already exists specifically to stop that divergence at a
strong-but-finite, explicitly documented effect size instead of letting it
run away — so a real fit is still used there rather than discarded for the
context-free default, as long as ``MIN_GAMES_TO_FIT`` games have been
played. Below that games threshold (e.g., the first couple of weeks of a
season) there is not enough same-season signal yet to fit anything
honestly, so a **documented default slope of 1.0** is used instead — the
"standard logistic" shape where a one-standard-deviation power_score edge
is ~73% to win and a two-standard-deviation edge is ~88%, a modest,
commonly-used effect size in sports win-probability models, not a
precision claim. As the season progresses, real completed games
accumulate and the model re-calibrates itself to this specific league
automatically (recomputed fresh on every cache-TTL refresh — see
``compute_playoff_odds_cached``).

## Why not simulate individual player scores

``modules.player_projections`` has real per-player point/low/high bands,
which could in principle be summed per starting lineup into a team-level
score distribution per week. That is the more "statistically honest" path
the task brief flags as worth considering, but it was judged out of scope
here: it would mean running a defense-adjusted weekly projection for every
rostered player on every team for every remaining week of the season on
every cache refresh (a full-roster, full-schedule pass, not the single
per-player/per-week lookup that screen does today), which is a much
heavier on-demand computation for a feature whose only external output is
a single percentage per team. The logistic-on-Power-Rank model gets the
same essential signal (who's more likely to win a given week) from data
this app already computes for free, stays fast enough to run from a cold
cache on a live API request, and is no less honest about what it is
(explicitly documented, league-calibrated, not a false-precision claim).

## Tiebreakers inside the simulation

A trial's standings are ordered by *simulated* final win total first, but
ties within a trial are broken by each team's **real, already-accumulated**
points-for (desc) / points-against (asc) / team name (asc) — the exact
fields and order ``league_standings.build_league_standings_bundle`` uses.
This simulation does not generate a plausible future point total for
each simulated matchup (only an outcome), so it cannot build a fully
simulated points-for figure to break ties with; using today's real
points-for as a stable proxy tiebreaker avoids inventing one. This is a
deliberate, documented scope trade-off, not an oversight.

## Clinching / elimination

"Clinched" and "eliminated" are claims about every possible outcome, so they
are NOT read off the sampled probability (3,000 trials cannot tell a 0.02%
path from an impossible one). They come from an exact, conservative bound:
each team's final wins lie in ``[wins, wins + remaining games]``, ties on
wins count as unresolved, and with divisions the bound also accounts for
division winners being seeded above wildcards. A team that is neither
certified keeps a sampled probability clamped to ``[0.05, 99.95]`` so a
number never reads as certainty it does not have. When no games remain the
standings are deterministic and the sampled result is exact.
"""

from __future__ import annotations

import time
from typing import Any, Mapping, Sequence

import numpy as np

from modules import league_rankings, league_recaps, league_standings, redis_cache, sleeper

# Logistic-regression (no intercept) fit of win probability on z-scored
# power_score differential needs enough same-season games to be more
# trustworthy than the documented default slope below. Requiring at least
# two completed games per team (and a hard floor of 12) means a 10-team
# league needs ~Week 3 before it starts trusting its own fit over the
# default — early enough to matter, late enough that a handful of
# upset/chalk results from Week 1 alone can't swing it.
MIN_GAMES_TO_FIT = 12

# Used when there isn't enough same-season data to fit a slope yet (see
# module docstring): sigmoid(1 SD) ~= 73.1%, sigmoid(2 SD) ~= 88.1%. A
# modest, explicitly-labeled default effect size — not a claim about this
# specific league.
DEFAULT_SLOPE = 1.0

# Keeps Newton-Raphson from diverging under near-perfect separation in a
# small sample (e.g., every observed upset this season happened to go the
# same direction) — the fit saturates at a strong-but-finite effect size
# instead of running away to an arbitrarily large one.
MAX_FIT_SLOPE = 6.0


def _sigmoid(x: np.ndarray) -> np.ndarray:
    # Clip avoids overflow warnings in exp() for very large |x| — result is
    # already ~0/1 at that point so clamping the input changes nothing
    # observable.
    return 1.0 / (1.0 + np.exp(-np.clip(x, -50.0, 50.0)))


def fit_win_probability_slope(
    z_differentials: Sequence[float],
    outcomes: Sequence[int],
    *,
    min_games: int = MIN_GAMES_TO_FIT,
    default_slope: float = DEFAULT_SLOPE,
    max_slope: float = MAX_FIT_SLOPE,
    iterations: int = 25,
) -> tuple[float, bool, int]:
    """Fit the single logistic slope parameter by maximum likelihood.

    ``z_differentials[i]`` is (z of team A's power_score - z of team B's
    power_score) for one real, completed game this season; ``outcomes[i]``
    is 1 if team A won that game, 0 if team B won. Returns
    ``(slope, fitted, n_games)`` — ``fitted`` is False (and ``slope`` is
    ``default_slope``) only when there are fewer than ``min_games`` usable
    results; that is the one case where a same-season fit genuinely isn't
    trustworthy yet.

    A completed-games sample that is perfectly (or near-perfectly)
    one-sided — every game this season has gone the way the power-score
    gap implied, so ``outcomes`` is all-1 or all-0 — is deliberately NOT
    special-cased here anymore: an unclamped MLE would diverge toward an
    infinite slope in that case, but the Newton-Raphson loop below clamps
    every step to ``max_slope`` (see ``MAX_FIT_SLOPE``'s module-level
    comment), so it already saturates at a strong-but-finite, explicitly
    documented effect size instead of running away. That clamped result is
    real, bounded signal from this league's own games — strictly more
    informative than silently discarding it for the context-free
    ``default_slope`` once ``min_games`` really have been played.
    """

    x = np.asarray(z_differentials, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    n_games = int(x.shape[0])
    if n_games < min_games:
        return default_slope, False, n_games

    slope = default_slope
    for _ in range(iterations):
        p = _sigmoid(slope * x)
        gradient = float(np.sum(x * (y - p)))
        hessian = float(-np.sum(x * x * p * (1.0 - p)))
        if hessian == 0.0:
            break
        step = gradient / hessian
        slope -= step
        slope = float(np.clip(slope, -max_slope, max_slope))
        if abs(step) < 1e-6:
            break
    return slope, True, n_games


def _tiebreak_rank(
    *,
    points_for: np.ndarray,
    points_against: np.ndarray,
    team_names: Sequence[str],
) -> np.ndarray:
    """Real, static tiebreak order (best=0) — see module docstring."""

    n = points_for.shape[0]
    # lexsort sorts by the LAST key primary; name asc is weakest, then
    # points_against asc, then points_for desc is the strongest tiebreaker.
    order = np.lexsort((
        list(team_names),
        points_against,
        -points_for,
    ))
    rank = np.empty(n, dtype=int)
    rank[order] = np.arange(n)
    return rank


# A team that is not mathematically eliminated/clinched never reports exactly
# 0 or 100: sampling 3,000 trials cannot distinguish "1 in 5,000" from "never".
UNCERTAIN_PROBABILITY_FLOOR = 0.05


def _certified_clinch_elimination(
    *,
    floor_wins: np.ndarray,
    remaining: np.ndarray,
    playoff_teams: int,
    divisions: Sequence[int | None] | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Exact (conservative) clinched / eliminated flags per team.

    Every team's final win total lies in ``[floor, floor + remaining]``.
    Ties on wins are treated as unresolved (the points tiebreak is not known
    in advance), so only strict separation certifies anything.

    * Eliminated: at least ``playoff_teams`` other teams already have more
      wins than this team can possibly reach, AND (with divisions) the team
      cannot win its own division, since division winners are seeded ahead of
      every wildcard.
    * Clinched: fewer than ``playoff_teams`` other teams can still reach this
      team's current wins, counting one extra seed for every other division
      (a division winner can out-seed a wildcard on fewer wins).
    """

    n = len(floor_wins)
    ceiling = floor_wins + remaining
    clinched = np.zeros(n, dtype=bool)
    eliminated = np.zeros(n, dtype=bool)
    if n == 0 or playoff_teams <= 0:
        return clinched, eliminated
    division_ids = list(divisions) if divisions is not None else None
    other_divisions = 0
    if division_ids is not None:
        other_divisions = len({d for d in division_ids if d})
    for i in range(n):
        others = [j for j in range(n) if j != i]
        ahead_for_sure = sum(1 for j in others if floor_wins[j] > ceiling[i])
        can_catch = sum(1 for j in others if ceiling[j] >= floor_wins[i])
        can_win_division = False
        extra_seeds = 0
        if division_ids is not None and division_ids[i]:
            mates = [j for j in others if division_ids[j] == division_ids[i]]
            can_win_division = all(ceiling[i] >= floor_wins[j] for j in mates)
            extra_seeds = max(0, other_divisions - 1)
        elif division_ids is not None:
            extra_seeds = other_divisions
        if ahead_for_sure >= playoff_teams and not can_win_division:
            eliminated[i] = True
        if can_catch + extra_seeds < playoff_teams:
            clinched[i] = True
    return clinched, eliminated


def _bracket_slots(size: int) -> list[int]:
    """Standard single-elimination seed order for a power-of-two bracket:
    adjacent entries meet in round one (8 -> 1,8,4,5,2,7,3,6)."""

    slots = [1]
    while len(slots) < size:
        total = len(slots) * 2 + 1
        slots = [x for seed in slots for x in (seed, total - seed)]
    return slots


def playoff_bracket_format(
    settings: Mapping[str, Any] | None, playoff_teams: int, *, playoffs_started: bool = False
) -> dict[str, Any]:
    """Whether this league's playoff format is known well enough to simulate a
    title run, from the real Sleeper settings only.

    Supported: single-elimination, one week per round, fixed or re-seeded
    bracket (``playoff_seed_type`` 0/1), top seeds getting byes when
    ``playoff_teams`` is not a power of two. Anything else (two-week rounds, a
    non-standard ``playoff_type``) is reported unavailable with a reason code
    rather than approximated. Returns ``{"available", "reason", "reseed"}``.
    """

    settings = settings or {}

    def unavailable(reason: str) -> dict[str, Any]:
        return {"available": False, "reason": reason, "reseed": False}

    if playoff_teams < 2:
        return unavailable("no_playoff_format")
    if playoffs_started:
        return unavailable("playoffs_underway")
    if _safe_int(settings.get("playoff_type")) != 0 or _safe_int(settings.get("playoff_round_type")) != 0:
        return unavailable("unsupported_playoff_format")
    seed_type = _safe_int(settings.get("playoff_seed_type"))
    if seed_type not in (0, 1):
        return unavailable("unsupported_playoff_format")
    return {"available": True, "reason": "", "reseed": seed_type == 1}


def simulate_title_odds(
    *,
    seed_order: np.ndarray,
    z: np.ndarray,
    slope: float,
    playoff_teams: int,
    reseed: bool,
    rng: np.random.Generator,
) -> np.ndarray:
    """Per-team championship probability (0-100) from the simulated seeds.

    ``seed_order[t, k]`` is the team index holding seed ``k + 1`` in trial
    ``t`` (the same standings the playoff odds use). Each playoff game is won
    with the same logistic Roster-Power model as the regular season. Byes go
    to the top seeds when the field is not a power of two.
    """

    n_trials, n = seed_order.shape
    field = min(playoff_teams, n)
    titles = np.zeros(n, dtype=float)
    if field < 2:
        return titles
    size = 1
    while size < field:
        size *= 2
    slots = _bracket_slots(size)
    draws = rng.random(size=(n_trials, field - 1))
    diff = z[:, None] - z[None, :]
    win_prob = 1.0 / (1.0 + np.exp(-slope * diff))
    for t in range(n_trials):
        team_of = seed_order[t]
        current: list[tuple[int, int] | None] = [
            (seed, int(team_of[seed - 1])) if seed <= field else None for seed in slots
        ]
        game = 0
        first_round = True
        while len(current) > 1:
            if reseed and not first_round:
                live = sorted(x for x in current if x is not None)
                current = [live[i // 2] if i % 2 == 0 else live[-(i // 2) - 1] for i in range(len(live))]
            first_round = False
            nxt: list[tuple[int, int] | None] = []
            for i in range(0, len(current), 2):
                a, b = current[i], current[i + 1]
                if a is None or b is None:
                    nxt.append(a if b is None else b)
                    continue
                a_wins = draws[t, game] < win_prob[a[1], b[1]]
                game += 1
                nxt.append(a if a_wins else b)
            current = nxt
        champion = current[0]
        if champion is not None:
            titles[champion[1]] += 1.0
    return titles / n_trials * 100.0


def simulate_playoff_odds(
    *,
    roster_ids: Sequence[str],
    power_scores: Sequence[float],
    current_wins: Sequence[float],
    current_losses: Sequence[float],
    current_ties: Sequence[float],
    points_for: Sequence[float],
    points_against: Sequence[float],
    team_names: Sequence[str],
    completed_games: Sequence[tuple[str, str, str]],
    remaining_games: Sequence[tuple[str, str]],
    playoff_teams: int,
    n_trials: int = 3000,
    rng: np.random.Generator | None = None,
    remaining_weeks: Sequence[Sequence[tuple[str, str]]] | None = None,
    league_median: bool = False,
    divisions: Sequence[int | None] | None = None,
    title_bracket: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure Monte Carlo simulation — no network/IO, fully unit-testable.

    ``completed_games`` is ``(roster_a, roster_b, winner_roster_id)`` for
    every real, decided game this season (used only to calibrate the win-
    probability slope — see ``fit_win_probability_slope``). ``winner`` must
    be one of the two roster ids; skip ties before calling (fantasy ties
    are vanishingly rare with decimal scoring and are not modeled).
    Median scoring (``league_median`` + ``remaining_weeks``): Sleeper's
    ``settings.league_average_match = 1`` also credits every team a win or
    loss each week against the league median score. Verified against live
    leagues: roster ``settings.wins/losses`` already include those results, so
    the current record needs no adjustment; only the remaining weeks do.
    ``remaining_weeks`` is the per-week pairing lists; each week the sim draws
    a weekly score per team (``a * z + N(0, 1)`` with ``a`` chosen so the
    pairwise win probability matches the logistic slope), decides the
    head-to-head games from those scores, and credits a median win to every
    team scoring above the median of that week's participants.

    Divisions (``divisions`` = per-team division id or None): Sleeper seeds
    division winners above all wildcard teams (verified against the live
    playoff brackets of divisional leagues), then everyone else by record.

    ``remaining_games`` is ``(roster_a, roster_b)`` for every real
    not-yet-played matchup still on the schedule — one call simulates the
    whole remaining season across all weeks at once (win totals are
    additive and week order doesn't affect final standings, so there is no
    need to simulate week-by-week).

    Returns a dict keyed by roster_id with ``playoff_probability`` (0-100),
    ``median_final_wins``/``median_final_losses``, ``median_seed``
    (1-indexed), ``clinched``/``eliminated`` (exactly True only when the
    probability is exactly 100/0 — see module docstring), plus top-level
    ``slope``, ``slope_fitted``, ``games_used_for_fit``, ``trials``.
    """

    rng = rng if rng is not None else np.random.default_rng()
    n = len(roster_ids)
    index_of = {rid: i for i, rid in enumerate(roster_ids)}

    power = np.asarray(power_scores, dtype=float)
    mean_power = float(power.mean()) if n else 0.0
    std_power = float(power.std()) if n else 0.0
    z = (power - mean_power) / std_power if std_power > 0 else np.zeros(n)

    fit_x: list[float] = []
    fit_y: list[float] = []
    for roster_a, roster_b, winner in completed_games:
        if roster_a not in index_of or roster_b not in index_of:
            continue
        ia, ib = index_of[roster_a], index_of[roster_b]
        if winner not in (roster_a, roster_b):
            continue
        fit_x.append(float(z[ia] - z[ib]))
        fit_y.append(1.0 if winner == roster_a else 0.0)

    slope, fitted, games_used = fit_win_probability_slope(fit_x, fit_y)

    pair_indices: list[tuple[int, int]] = []
    pair_probs: list[float] = []
    for roster_a, roster_b in remaining_games:
        if roster_a not in index_of or roster_b not in index_of:
            continue
        ia, ib = index_of[roster_a], index_of[roster_b]
        pair_indices.append((ia, ib))
        pair_probs.append(float(_sigmoid(slope * (z[ia] - z[ib]))))

    wins_arr = np.asarray(current_wins, dtype=float)
    losses_arr = np.asarray(current_losses, dtype=float)
    ties_arr = np.asarray(current_ties, dtype=float)
    points_for_arr = np.asarray(points_for, dtype=float)
    points_against_arr = np.asarray(points_against, dtype=float)
    remaining_games_count = np.zeros(n, dtype=int)
    for ia, ib in pair_indices:
        remaining_games_count[ia] += 1
        remaining_games_count[ib] += 1

    win_equiv_base = wins_arr + 0.5 * ties_arr
    static_tiebreak = (
        _tiebreak_rank(points_for=points_for_arr, points_against=points_against_arr, team_names=team_names)
        if n
        else np.zeros(0, dtype=int)
    )

    n_games = len(pair_indices)
    wins_added = np.zeros((n_trials, n), dtype=int)
    if league_median and remaining_weeks:
        # score = a*z + N(0,1);  P(A>B) = Phi(a*dz/sqrt2) ~= sigmoid(slope*dz)
        # using sigmoid(x) ~= Phi(x/1.702)  =>  a = sqrt(2)*slope/1.702.
        a_coef = float(np.sqrt(2.0) * slope / 1.702)
        pair_indices = []
        remaining_games_count = np.zeros(n, dtype=int)
        for week_pairs in remaining_weeks:
            week_idx = [
                (index_of[ra], index_of[rb])
                for ra, rb in week_pairs
                if ra in index_of and rb in index_of
            ]
            if not week_idx:
                continue
            scores = a_coef * z[None, :] + rng.standard_normal(size=(n_trials, n))
            participants = sorted({i for pair in week_idx for i in pair})
            median = np.median(scores[:, participants], axis=1)
            for ia, ib in week_idx:
                pair_indices.append((ia, ib))
                outcome = scores[:, ia] > scores[:, ib]
                wins_added[:, ia] += outcome
                wins_added[:, ib] += ~outcome
                remaining_games_count[ia] += 1
                remaining_games_count[ib] += 1
            for i in participants:
                wins_added[:, i] += scores[:, i] > median
                remaining_games_count[i] += 1
    elif n_games:
        probs = np.asarray(pair_probs, dtype=float)
        draws = rng.random(size=(n_trials, n_games))
        a_wins = draws < probs[None, :]
        for g, (ia, ib) in enumerate(pair_indices):
            outcome = a_wins[:, g]
            wins_added[:, ia] += outcome
            wins_added[:, ib] += ~outcome

    final_wins = wins_arr[None, :] + wins_added
    final_win_equiv = win_equiv_base[None, :] + wins_added

    # Combined per-trial sort key: win total dominates (scaled comfortably
    # above the static tiebreak's 0..n-1 range), static real tiebreak
    # settles ties. Lower key = better.
    sort_key = -(final_win_equiv * (n + 1)) + static_tiebreak[None, :]
    if divisions is not None:
        # Division winners (best sort_key inside each division) are seeded
        # above every other team: shift them below all non-winners' keys.
        division_ids = list(divisions)
        winner_bonus = np.zeros((n_trials, n), dtype=float)
        big = float((final_win_equiv.max() + 2) * (n + 1) + n)
        for division in {d for d in division_ids if d}:
            members = [i for i, d in enumerate(division_ids) if d == division]
            best = np.argmin(sort_key[:, members], axis=1)
            winner_bonus[np.arange(n_trials), np.asarray(members)[best]] = big
        sort_key = sort_key - winner_bonus
    order = np.argsort(sort_key, axis=1)
    ranks = np.empty_like(order)
    trial_idx = np.arange(n_trials)[:, None]
    ranks[trial_idx, order] = np.arange(n)[None, :] + 1

    made_playoffs = ranks <= playoff_teams

    # Title odds run after every other draw so enabling them never shifts the
    # random numbers the playoff odds use (baseline/scenario stay comparable).
    title_odds: np.ndarray | None = None
    if title_bracket and title_bracket.get("available") and n >= 2:
        title_odds = simulate_title_odds(
            seed_order=order,
            z=z,
            slope=slope,
            playoff_teams=playoff_teams,
            reseed=bool(title_bracket.get("reseed")),
            rng=rng,
        )

    # With nothing left to play every trial is identical, so the simulated
    # standings (including the points tiebreak and division seeding) are
    # exact. Otherwise only the conservative bound may claim certainty.
    season_decided = not bool(np.any(remaining_games_count))
    if season_decided:
        clinched_flags = made_playoffs.all(axis=0)
        eliminated_flags = ~made_playoffs.any(axis=0)
    else:
        clinched_flags, eliminated_flags = _certified_clinch_elimination(
            floor_wins=win_equiv_base,
            remaining=remaining_games_count,
            playoff_teams=playoff_teams,
            divisions=divisions,
        )

    results: dict[str, Any] = {}
    for rid in roster_ids:
        i = index_of[rid]
        probability = float(made_playoffs[:, i].mean() * 100.0)
        # "Clinched"/"eliminated" are claims about every possible outcome, so
        # they come from the exact bound above, never from a sampled 0%/100%
        # (a team with a real 0.02% path samples to 0 in 3,000 trials). A
        # sampled extreme that is not certified is nudged off the boundary so
        # the number can never read as a certainty it does not have.
        if bool(clinched_flags[i]):
            probability = 100.0
        elif bool(eliminated_flags[i]):
            probability = 0.0
        elif season_decided:
            pass
        else:
            probability = min(max(probability, UNCERTAIN_PROBABILITY_FLOOR), 100.0 - UNCERTAIN_PROBABILITY_FLOOR)
        results[rid] = {
            "playoff_probability": probability,
            "median_final_wins": float(np.median(final_wins[:, i])),
            "median_final_losses": float(losses_arr[i] + remaining_games_count[i] - np.median(wins_added[:, i])),
            "median_seed": int(np.median(ranks[:, i])),
            "remaining_games": int(remaining_games_count[i]),
            "clinched": bool(clinched_flags[i]),
            "eliminated": bool(eliminated_flags[i]),
        }
        if title_odds is not None:
            # A team that cannot make the field cannot win the title: exact,
            # not sampled, so an eliminated team reads 0 rather than noise.
            results[rid]["title_probability"] = 0.0 if bool(eliminated_flags[i]) else float(title_odds[i])

    return {
        "teams": results,
        "slope": slope,
        "slope_fitted": fitted,
        "games_used_for_fit": games_used,
        "trials": n_trials,
    }


# ---------------------------------------------------------------------------
# Real-data assembly (network/IO). Everything above this line is pure and
# directly unit-tested; everything below wires it to this app's real Sleeper
# data and real caching conventions. Default trial count: 3,000. At ~70
# remaining matchups in a typical 12-team/10-week-remaining league that's
# ~210k Bernoulli draws plus a handful of vectorized numpy ops — comfortably
# sub-100ms, well inside an on-demand API request, while keeping each team's
# probability estimate's Monte Carlo standard error under ~1 point (binomial
# SE at p=0.5 is sqrt(0.25/3000) ~= 0.9%). Raising this would sharpen
# borderline-team estimates marginally at a roughly linear compute cost;
# 3,000 was chosen as the smallest trial count that keeps noise comfortably
# below the 1%-rounding granularity the UI displays results at.
DEFAULT_TRIALS = 3000

# Same live-time-bucket idiom as league_rankings.LEAGUE_RANKINGS_FRAME_TTL_SECONDS
# and modules.sleeper's own caches, but a much longer window: this is a
# rest-of-season outlook, not a live score, so re-running a few-thousand-trial
# simulation on every page load (every Dashboard/League Rankings open within
# the same hour) would be wasted work for a number that can only change when
# new real games get played — which happens at most once a week. Three hours
# keeps it fresh across a single viewing session while still collapsing many
# requests from many users checking a shared league's odds down to roughly
# one real simulation run every few hours.
PLAYOFF_ODDS_TTL_SECONDS = 10800


def _playoff_odds_cache_bucket() -> int:
    return int(time.time() // PLAYOFF_ODDS_TTL_SECONDS)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


def _roster_id_str(value: object) -> str:
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return str(value) if value is not None else ""


def _group_remaining_week_pairs(matchups: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Real pairings for a not-yet-decided week — just who plays whom."""

    groups: dict[Any, list[str]] = {}
    for entry in matchups or []:
        matchup_id = entry.get("matchup_id")
        if matchup_id is None:
            continue  # Sleeper's own "bye this week" marker.
        roster_id = _roster_id_str(entry.get("roster_id"))
        if not roster_id:
            continue
        groups.setdefault(matchup_id, []).append(roster_id)
    return [(members[0], members[1]) for members in groups.values() if len(members) == 2]


def _group_completed_week_games(matchups: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Real decided-game winners for an already-played week.

    Skips a pairing Sleeper hasn't scored yet (points missing on either
    side) and skips an exact tie (vanishingly rare with decimal scoring,
    and this model has no "tie" outcome — see module docstring).
    """

    groups: dict[Any, list[dict[str, Any]]] = {}
    for entry in matchups or []:
        matchup_id = entry.get("matchup_id")
        if matchup_id is None:
            continue
        groups.setdefault(matchup_id, []).append(entry)

    games: list[tuple[str, str, str]] = []
    for members in groups.values():
        if len(members) != 2:
            continue
        a, b = members
        roster_a = _roster_id_str(a.get("roster_id"))
        roster_b = _roster_id_str(b.get("roster_id"))
        if not roster_a or not roster_b:
            continue
        try:
            points_a = float(a.get("points") or 0.0)
            points_b = float(b.get("points") or 0.0)
        except (TypeError, ValueError):
            continue
        if points_a <= 0.0 and points_b <= 0.0:
            continue  # Not actually played yet despite having a matchup_id.
        if points_a == points_b:
            continue  # Tie — not modeled (see docstring).
        winner = roster_a if points_a > points_b else roster_b
        games.append((roster_a, roster_b, winner))
    return games


def build_league_playoff_odds(
    league_id: str,
    *,
    lens: str = "Dynasty",
    players_db_path: str,
    n_trials: int = DEFAULT_TRIALS,
    rng: np.random.Generator | None = None,
    power_overrides: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Assemble real league data and run the Monte Carlo simulation.

    ``power_overrides`` (roster_id -> power_score) swaps in a hypothetical
    Roster Power for specific teams (the Games what-if); nothing else about the
    run changes, so a baseline and a scenario built with equally seeded ``rng``
    differ only by that input.

    Returns ``{"ok": True, "reason": "", ...}`` with simulation output on
    success, or ``{"ok": True, "reason": <code>, ...}`` (same not-ready
    contract as the other `/v1/leagues/{id}/...` endpoints) when the real
    data needed isn't available yet: ``"offseason"`` (no real results yet),
    ``"no_playoff_format"`` (league has no configured playoff_teams
    setting), ``"no_rankings_data"`` (Roster Power can't be computed — same
    gate /team-rankings uses).
    """

    league = sleeper.get_league(league_id)
    if not league:
        return {"ok": True, "reason": "unavailable", "teams": []}

    rosters = sleeper.get_rosters(league_id)
    roster_profiles = sleeper.get_league_roster_profiles(league_id)
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if rankings_frame.empty:
        return {"ok": True, "reason": "no_rankings_data", "teams": []}

    standings_bundle = league_standings.build_league_standings_bundle(
        rosters=rosters,
        roster_profiles=roster_profiles,
        league=league,
        team_frame=rankings_frame,
    )
    if not standings_bundle.get("available"):
        reason = "offseason" if standings_bundle.get("empty_reason") == "offseason" else "unavailable"
        return {"ok": True, "reason": reason, "teams": []}

    playoff_teams = standings_bundle.get("playoff_teams")
    if not playoff_teams or playoff_teams <= 0:
        return {"ok": True, "reason": "no_playoff_format", "teams": []}

    frame = standings_bundle["frame"]
    power_by_roster = {
        _roster_id_str(row.get("roster_id")): float(row.get("power_score") or 0.0)
        for _, row in rankings_frame.iterrows()
    }
    for override_rid, override_power in (power_overrides or {}).items():
        if _roster_id_str(override_rid) in power_by_roster:
            power_by_roster[_roster_id_str(override_rid)] = float(override_power)

    roster_ids: list[str] = []
    power_scores: list[float] = []
    current_wins: list[float] = []
    current_losses: list[float] = []
    current_ties: list[float] = []
    points_for: list[float] = []
    points_against: list[float] = []
    team_names: list[str] = []
    for _, row in frame.iterrows():
        rid = _roster_id_str(row.get("roster_id"))
        if not rid or rid not in power_by_roster:
            continue
        roster_ids.append(rid)
        power_scores.append(power_by_roster[rid])
        current_wins.append(float(row.get("wins") or 0.0))
        current_losses.append(float(row.get("losses") or 0.0))
        current_ties.append(float(row.get("ties") or 0.0))
        points_for.append(float(row.get("points_for") or 0.0))
        points_against.append(float(row.get("points_against") or 0.0))
        team_names.append(str(row.get("team_name") or "Team"))

    if len(roster_ids) < 2:
        return {"ok": True, "reason": "no_rankings_data", "teams": []}

    current_week, regular_season_end, _max_history_week = league_recaps.league_history_window(league)

    # One concurrent prefetch of every week this scan reads (cached per week, so
    # the loops below are pure lookups) instead of ~17 serial Sleeper round trips.
    matchups_by_week = sleeper.get_matchups_for_weeks(
        league_id,
        [*range(1, max(current_week, 1)), *range(max(current_week, 1), regular_season_end + 1)],
    )

    completed_games: list[tuple[str, str, str]] = []
    for week in range(1, max(current_week, 1)):
        completed_games.extend(_group_completed_week_games(matchups_by_week[week]))

    remaining_games: list[tuple[str, str]] = []
    remaining_weeks: list[list[tuple[str, str]]] = []
    for week in range(max(current_week, 1), regular_season_end + 1):
        week_pairs = _group_remaining_week_pairs(matchups_by_week[week])
        remaining_games.extend(week_pairs)
        remaining_weeks.append(week_pairs)

    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    league_median = bool(_safe_int(league_settings.get("league_average_match")))
    divisions: list[int | None] | None = None
    if _safe_int(league_settings.get("divisions")) > 0:
        by_rid = {
            _roster_id_str(row.get("roster_id")): row.get("division_id")
            for _, row in frame.iterrows()
        }
        divisions = [_safe_int(by_rid.get(rid)) or None for rid in roster_ids]
        if not any(divisions):
            divisions = None

    title_format = playoff_bracket_format(
        league_settings, int(playoff_teams), playoffs_started=current_week > regular_season_end
    )

    simulation = simulate_playoff_odds(
        roster_ids=roster_ids,
        power_scores=power_scores,
        current_wins=current_wins,
        current_losses=current_losses,
        current_ties=current_ties,
        points_for=points_for,
        points_against=points_against,
        team_names=team_names,
        completed_games=completed_games,
        remaining_games=remaining_games,
        playoff_teams=int(playoff_teams),
        n_trials=n_trials,
        rng=rng,
        remaining_weeks=remaining_weeks,
        league_median=league_median,
        divisions=divisions,
        title_bracket=title_format,
    )

    teams: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        rid = _roster_id_str(row.get("roster_id"))
        sim = simulation["teams"].get(rid)
        if sim is None:
            continue
        teams.append(
            {
                "roster_id": rid,
                "team_name": str(row.get("team_name") or "Team"),
                "owner_name": row.get("owner_name"),
                "avatar_url": row.get("avatar_url"),
                "record_label": row.get("record_label"),
                "playoff_probability": round(sim["playoff_probability"], 1),
                "median_final_wins": round(sim["median_final_wins"]),
                "median_final_losses": round(sim["median_final_losses"]),
                "median_seed": sim["median_seed"],
                "remaining_games": sim["remaining_games"],
                "clinched": sim["clinched"],
                "eliminated": sim["eliminated"],
                "title_probability": (
                    round(sim["title_probability"], 1) if sim.get("title_probability") is not None else None
                ),
            }
        )
    teams.sort(key=lambda t: (-t["playoff_probability"], t["median_seed"]))

    return {
        "ok": True,
        "reason": "",
        "teams": teams,
        "playoff_teams": int(playoff_teams),
        "current_week": current_week,
        "regular_season_end": regular_season_end,
        "weeks_remaining": max(0, regular_season_end - current_week + 1),
        "trials": simulation["trials"],
        "slope_fitted": simulation["slope_fitted"],
        "games_used_for_fit": simulation["games_used_for_fit"],
        "season": standings_bundle.get("season"),
        "slope": simulation["slope"],
        "title_odds": {"available": title_format["available"], "reason": title_format["reason"]},
    }


def _build_league_playoff_odds_cached(
    league_id: str,
    lens: str,
    players_db_path: str,
    n_trials: int,
    _bucket: int,
) -> dict[str, Any]:
    # Fixed seed keyed off the cache bucket: identical inputs within one TTL
    # window always return identical output (no jitter between two requests
    # hitting the same bucket), while a new bucket reseeds for a fresh draw —
    # consistent with this being an estimate that's expected to move only
    # when the TTL rolls over or real results change, never on reload.
    rng = np.random.default_rng(seed=hash((league_id, lens, n_trials, _bucket)) & 0xFFFFFFFF)
    return build_league_playoff_odds(
        league_id, lens=lens, players_db_path=players_db_path, n_trials=n_trials, rng=rng
    )


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache):
# without a single-flight guard, N concurrent requests that all miss the
# same (league_id, lens, players_db_path, n_trials, bucket) key before the
# first one finishes would each independently pay the full
# DEFAULT_TRIALS=3000-trial simulation cost instead of sharing one. That
# directly contradicts this cache's own purpose (see
# PLAYOFF_ODDS_TTL_SECONDS's comment: "collapsing many requests from many
# users ... down to roughly one real simulation run"). A concrete trigger:
# every league member's app polling/opening at once right after a 3-hour
# TTL rollover, or the mobile client's own navigation retries.
#
# This used to be a per-process threading.Lock + functools.lru_cache pair,
# which only protected ONE uvicorn worker: under docker-compose.yml's
# multiple mobile-api workers, each worker has its own process memory, so
# that old pair would let the same simulation run redundantly once per
# worker AND a cache hit in worker A would never help a request that
# happened to land on worker B. Redis fixes both: the distributed lock
# makes only one worker, cluster-wide, actually run a given simulation,
# and the cached result lives in Redis, not in any one worker's memory.
_PLAYOFF_ODDS_LOCK_TIMEOUT_SECONDS = 15.0


def build_league_playoff_odds_cached(
    *,
    league_id: str,
    lens: str = "Dynasty",
    players_db_path: str,
    n_trials: int = DEFAULT_TRIALS,
) -> dict[str, Any]:
    """Cached front door — see ``PLAYOFF_ODDS_TTL_SECONDS``/module docstring.

    Single-flight + cache, now shared across every mobile-api worker via
    Redis: see ``modules.redis_cache.redis_single_flight_cache`` and this
    module's own comment above.
    """

    key = (league_id, lens, players_db_path, n_trials, _playoff_odds_cache_bucket())
    cache_key = redis_cache.build_cache_key("playoff_odds", *key)
    return redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=PLAYOFF_ODDS_TTL_SECONDS,
        compute=lambda: _build_league_playoff_odds_cached(*key),
        lock_timeout_seconds=_PLAYOFF_ODDS_LOCK_TIMEOUT_SECONDS,
    )
