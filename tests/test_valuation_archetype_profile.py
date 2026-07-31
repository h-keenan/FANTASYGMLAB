import json

from modules import profile
from modules.valuation_archetypes import BALANCED_DYNASTY_ID


def test_profile_migrates_and_persists_default_archetype(tmp_path, monkeypatch):
    profile_path = tmp_path / "profile.json"
    monkeypatch.setattr(profile, "PROFILE_PATH", str(profile_path))
    monkeypatch.chdir(tmp_path)

    loaded = profile.load_profile_key("fixture-user", "fixture-league")
    assert loaded["valuation_archetype_id"] == BALANCED_DYNASTY_ID

    profile.save_profile_key("fixture-user", "fixture-league", loaded)
    stored = json.loads(profile_path.read_text(encoding="utf-8"))
    assert next(iter(stored.values()))["valuation_archetype_id"] == BALANCED_DYNASTY_ID
