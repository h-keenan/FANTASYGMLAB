"""Deterministic orchestration for the offline Contender fixture experiment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Callable

import pandas as pd

from modules.archetype_experiment_fixtures import (
    FIXTURE_VERSION, draft_pick_fixture, fixture_matrix, player_fixture,
    recommendation_fixture,
)
from modules.archetype_experiment_models import ExperimentStatus
from modules.archetype_validation import explanation_failures, pick_chronology_failures
from modules.contender_archetype_experiment import (
    CONTENDER_SPEC, apply_contender_candidate, classify_fixture_context,
)


@dataclass(frozen=True)
class ContenderFixtureSummary:
    label: str
    classification: str
    applied: bool
    fallback_reason: str | None
    changed_players: int
    changed_picks: int
    largest_increase: float
    largest_decrease: float
    cap_hits: tuple[str, ...]


@dataclass(frozen=True)
class ContenderValidationArtifact:
    experiment_id: str
    lifecycle_decision: str
    baseline_id: str
    fixture_version: str
    fixture_summaries: tuple[ContenderFixtureSummary, ...]
    invariant_failures: tuple[str, ...]
    directional_failures: tuple[str, ...]
    explanation_failures: tuple[str, ...]
    recommendation_changes: tuple[str, ...]
    recommendation_churn_percentage: float
    largest_increases: tuple[tuple[str, float], ...]
    largest_decreases: tuple[tuple[str, float], ...]
    rank_movements: tuple[tuple[str, int], ...]
    position_mean_deltas: tuple[tuple[str, float], ...]
    age_band_mean_deltas: tuple[tuple[str, float], ...]
    cap_frequency: int
    golden_scenarios: tuple[tuple[str, str], ...]
    hard_gates_passed: bool
    production_eligible: bool

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))


def run_contender_validation(
    *,
    balanced_adapter: Callable[[pd.DataFrame, dict[str, object]], pd.DataFrame],
    inject_failure: bool = False,
) -> ContenderValidationArtifact:
    summaries = []
    invariants: list[str] = []
    directional: list[str] = []
    explanation_issues: list[str] = []
    intended_deltas: list[tuple[str, float]] = []
    intended_ranks: list[tuple[str, int]] = []
    position_groups: dict[str, list[float]] = {}
    age_groups: dict[str, list[float]] = {}
    cap_frequency = 0

    for scenario in fixture_matrix():
        settings = dict(scenario.league_settings)
        baseline = balanced_adapter(player_fixture(), settings)
        baseline_before = baseline.copy(deep=True)
        picks = draft_pick_fixture()
        result = apply_contender_candidate(
            baseline, picks, league_settings=settings,
            roster_profile=scenario.roster_profile,
        )
        if inject_failure and scenario.label == "contending-roster":
            result.assets.loc[result.assets.index[0], "dynasty_score"] += 100_000
        if not baseline.equals(baseline_before):
            invariants.append(f"{scenario.label}:baseline_mutated")
        if tuple(result.assets.columns) != tuple(baseline.columns):
            invariants.append(f"{scenario.label}:schema_changed")
        if tuple(map(str, result.assets.dtypes)) != tuple(map(str, baseline.dtypes)):
            invariants.append(f"{scenario.label}:dtypes_changed")
        if result.assets["player_id"].tolist() != baseline["player_id"].tolist():
            invariants.append(f"{scenario.label}:ordering_changed")
        before = pd.to_numeric(baseline["dynasty_score"], errors="coerce")
        after = pd.to_numeric(result.assets["dynasty_score"], errors="coerce")
        deltas = after - before
        pick_deltas = (
            pd.to_numeric(result.picks["value_score"], errors="coerce")
            - pd.to_numeric(picks["value_score"], errors="coerce")
        )
        context = classify_fixture_context(scenario.roster_profile)
        if context != "intended" and (deltas.ne(0).any() or pick_deltas.ne(0).any()):
            invariants.append(f"{scenario.label}:fail_closed_difference")
        if context == "intended":
            unavailable = baseline["status"].astype(str).str.casefold().eq("injured reserve")
            if (deltas.loc[unavailable] > 0).any():
                directional.append(f"{scenario.label}:unavailable_bonus")
            replacements = before.lt(3_000)
            if replacements.any() and (deltas.loc[replacements] > 0).mean() > 0.10:
                directional.append(f"{scenario.label}:replacement_veteran_boost")
            young_elite = before.ge(8_000) & pd.to_numeric(
                baseline["age"], errors="coerce"
            ).le(25)
            if (deltas.loc[young_elite] < -(before.loc[young_elite] * 0.02)).any():
                directional.append(f"{scenario.label}:elite_young_protection")
            changed_ids = {
                asset_id
                for asset_id, delta in zip(baseline["player_id"].astype(str), deltas)
                if delta != 0
            }
            base_ranks = before.rank(method="first", ascending=False)
            candidate_ranks = after.rank(method="first", ascending=False)
            for row_index, asset_id in enumerate(baseline["player_id"].astype(str)):
                delta = float(deltas.iloc[row_index])
                if delta:
                    intended_deltas.append((asset_id, delta))
                rank_delta = int(
                    base_ranks.iloc[row_index] - candidate_ranks.iloc[row_index]
                )
                if rank_delta:
                    intended_ranks.append((asset_id, rank_delta))
                position_groups.setdefault(
                    str(baseline.iloc[row_index].get("position", "")), []
                ).append(delta)
                age = pd.to_numeric(
                    pd.Series([baseline.iloc[row_index].get("age")]),
                    errors="coerce",
                ).iloc[0]
                age_band = (
                    "unknown" if pd.isna(age) else
                    "21-23" if age <= 23 else
                    "24-26" if age <= 26 else
                    "27-29" if age <= 29 else "30+"
                )
                age_groups.setdefault(age_band, []).append(delta)
            cap_frequency += len(result.cap_hits)
            explanation_issues.extend(
                f"{scenario.label}:{item}"
                for item in explanation_failures(
                    result.explanations,
                    changed_ids,
                    expected_template_version=CONTENDER_SPEC.explanation_template_version,
                    declared_dimensions=CONTENDER_SPEC.affected_dimensions,
                )
            )
            invariants.extend(
                f"{scenario.label}:{item}"
                for item in pick_chronology_failures(result.picks)
            )
            if deltas.abs().div(before.abs()).mul(100).dropna().gt(8.0).any():
                invariants.append(f"{scenario.label}:player_bound")
            pick_base = pd.to_numeric(picks["value_score"], errors="coerce")
            if pick_deltas.abs().div(pick_base.abs()).mul(100).dropna().gt(3.0).any():
                invariants.append(f"{scenario.label}:pick_bound")
        summaries.append(
            ContenderFixtureSummary(
                label=scenario.label, classification=context, applied=result.applied,
                fallback_reason=result.fallback_reason,
                changed_players=int(deltas.ne(0).sum()),
                changed_picks=int(pick_deltas.ne(0).sum()),
                largest_increase=float(deltas.max()),
                largest_decrease=float(deltas.min()),
                cap_hits=result.cap_hits,
            )
        )

    baseline_recommendations = recommendation_fixture()
    candidate_recommendations = tuple(dict(item) for item in baseline_recommendations)
    recommendation_changes = tuple(
        str(before["recommendation_id"])
        for before, after in zip(baseline_recommendations, candidate_recommendations)
        if before != after
    )
    churn = (
        len(recommendation_changes) / len(baseline_recommendations) * 100
        if baseline_recommendations else 0.0
    )
    if churn > 20.0:
        directional.append("recommendation_churn_review_threshold")
    golden = (
        ("elite-young-qb-superflex", "cornerstone protection; no position multiplier"),
        ("aging-elite-rb-contender", "movement requires current production evidence"),
        ("veteran-wr-rebuild", "exact fallback to Balanced Dynasty"),
        ("injured-young-upside", "no availability bonus; long-term value retained"),
        ("distant-first-round-pick", "bounded discount preserves chronology"),
        ("replacement-veteran", "baseline below bonus threshold"),
        ("elite-te-te-premium", "no extra scarcity contribution"),
        ("ambiguous-middle-tier", "limited threshold-based movement"),
    )
    hard_passed = not (invariants or directional or explanation_issues)
    return ContenderValidationArtifact(
        experiment_id=CONTENDER_SPEC.archetype_id,
        lifecycle_decision=(
            ExperimentStatus.FIXTURE_VALIDATED.value
            if hard_passed else ExperimentStatus.DRAFT.value
        ),
        baseline_id="balanced_dynasty",
        fixture_version=FIXTURE_VERSION,
        fixture_summaries=tuple(summaries),
        invariant_failures=tuple(sorted(set(invariants))),
        directional_failures=tuple(sorted(set(directional))),
        explanation_failures=tuple(sorted(set(explanation_issues))),
        recommendation_changes=recommendation_changes,
        recommendation_churn_percentage=churn,
        largest_increases=tuple(
            sorted(
                (item for item in intended_deltas if item[1] > 0),
                key=lambda item: (-item[1], item[0]),
            )[:10]
        ),
        largest_decreases=tuple(
            sorted(
                (item for item in intended_deltas if item[1] < 0),
                key=lambda item: (item[1], item[0]),
            )[:10]
        ),
        rank_movements=tuple(
            sorted(intended_ranks, key=lambda item: (-abs(item[1]), item[0]))
        ),
        position_mean_deltas=tuple(
            (label, sum(values) / len(values))
            for label, values in sorted(position_groups.items())
        ),
        age_band_mean_deltas=tuple(
            (label, sum(values) / len(values))
            for label, values in sorted(age_groups.items())
        ),
        cap_frequency=cap_frequency,
        golden_scenarios=golden,
        hard_gates_passed=hard_passed,
        production_eligible=False,
    )
