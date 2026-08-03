from pathlib import Path

from scripts.audit_experimental_features import (
    documented_routes,
    experimental_routes,
    priority_score,
)


ROOT = Path(__file__).resolve().parents[1]


def test_audit_covers_every_registered_experimental_route():
    registry = (ROOT / "modules" / "ui_architecture.py").read_text(encoding="utf-8")
    audit = (ROOT / "docs" / "experimental-feature-inventory-and-roi-audit.md").read_text(
        encoding="utf-8"
    )
    assert documented_routes(audit) == experimental_routes(registry)


def test_priority_score_rewards_benefit_and_penalizes_cost():
    high = {
        "user_value": 5, "differentiation": 5, "readiness": 5,
        "revenue": 5, "retention": 5, "data_reliability": 5,
        "mobile": 5, "time_to_ship": 5, "maintenance_cost": 1,
        "technical_risk": 1,
    }
    low = {key: (5 if key in {"maintenance_cost", "technical_risk"} else 1) for key in high}
    assert priority_score(high) == 100.0
    assert priority_score(low) == 20.0
    assert priority_score(high) > priority_score(low)


def test_audit_records_required_decision_outputs_and_boundaries():
    audit = (ROOT / "docs" / "experimental-feature-inventory-and-roi-audit.md").read_text(
        encoding="utf-8"
    )
    for heading in (
        "Ranked top ten",
        "Quick wins",
        "High-risk / high-reward",
        "Archive candidates",
        "Dependency map",
        "Three-phase roadmap",
        "One recommended next implementation",
    ):
        assert heading in audit
    assert "No production behavior was changed" in audit
