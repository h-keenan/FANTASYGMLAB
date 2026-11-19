from pathlib import Path

from modules import experimental_graduation as eg
from modules import partner_context as pc

ROOT = Path(__file__).resolve().parents[1]


def test_registry_entries_have_owner_criterion_review_and_a_reader():
    src = "\n".join(p.read_text() for p in (ROOT / "modules").glob("*.py") if p.name != "experimental_graduation.py")
    for key, row in eg.FLAG_REGISTRY.items():
        assert row["default"] in {"on", "off"}
        assert row["owner"] and row["criterion"] and row["review"], key
        assert key in src, f"{key} has no reader in modules/"


def test_registry_default_on_flags_read_on_when_unset(monkeypatch):
    for key, row in eg.FLAG_REGISTRY.items():
        monkeypatch.delenv(key, raising=False)
        if row["default"] == "on":
            assert eg.graduated_kill_switch_enabled(key, default=True) is True


def test_partner_surface_default_dict_is_gone_and_surfaces_default_on(monkeypatch):
    assert not hasattr(pc, "SURFACE_DEFAULT_ON")
    for key in (pc.FINDER_ENV_KEY, pc.DASHBOARD_ENV_KEY, pc.SEARCH_ENV_KEY, pc.ASK_PICK_ENV_KEY):
        monkeypatch.delenv(key, raising=False)
        assert pc.surface_enabled(key) is True
