import pytest

from modules import gsis_crosswalk, news_signal, nfl_schedule, nflverse_advanced_stats, player_identity, rankings
from modules.nfl_teams import NFL_TEAM_CODES, TEAM_CODE_ALIASES, canonical_team
from modules.platforms import espn
from modules.player_names import loose_name_key, normalize_player_name, player_name_key

GOLDEN = [
    ("Kenneth Walker III", "kenneth walker", "kennethwalker"),
    ("Brian Thomas Jr.", "brian thomas", "brianthomas"),
    ("Ja'Marr Chase", "jamarr chase", "jamarrchase"),
    ("A.J. Brown", "aj brown", "ajbrown"),
    ("Amon-Ra St. Brown", "amon ra st brown", "amonrastbrown"),
    ("José Alvarado, Sr.", "jose alvarado", "josealvarado"),
    ("  Patrick   Mahomes ", "patrick mahomes", "patrickmahomes"),
    ("V", "v", "v"),
    ("", "", ""),
    (None, "", ""),
]


@pytest.mark.parametrize("raw,spaced,joined", GOLDEN)
def test_canonical_normalizer(raw, spaced, joined):
    assert normalize_player_name(raw) == spaced
    assert player_name_key(raw) == joined


@pytest.mark.parametrize("raw,spaced,joined", GOLDEN)
def test_every_legacy_entry_point_delegates(raw, spaced, joined):
    assert rankings._normalize_name(raw) == joined
    assert player_identity.normalize_player_name(raw) == spaced
    assert gsis_crosswalk.normalize_name(raw) == spaced
    assert news_signal.normalize_player_name(raw or "") == spaced


def test_nickname_fold_is_separate_and_loose_only():
    assert player_name_key("Kenny Gainwell") != player_name_key("Kenneth Gainwell")
    assert loose_name_key("Kenny Gainwell") == loose_name_key("Kenneth Gainwell")
    # a single-token name is never rewritten
    assert loose_name_key("Kenny") == "kenny"


def test_one_alias_table_everywhere():
    assert nfl_schedule.TEAM_CODE_ALIASES is TEAM_CODE_ALIASES
    assert nflverse_advanced_stats.TEAM_ALIASES is TEAM_CODE_ALIASES
    assert espn.ESPN_TEAM_ALIASES is TEAM_CODE_ALIASES
    assert espn.SLEEPER_DEF_IDS is NFL_TEAM_CODES and len(NFL_TEAM_CODES) == 32


@pytest.mark.parametrize(
    "code,expected",
    [("LA", "LAR"), ("STL", "LAR"), ("OAK", "LV"), ("SD", "LAC"), ("JAC", "JAX"), ("WSH", "WAS"),
     ("kc", "KC"), ("DAL", "DAL"), ("", ""), (None, "")],
)
def test_canonical_team_golden(code, expected):
    assert canonical_team(code) == expected
    assert nflverse_advanced_stats.normalize_team(code) == expected
    assert espn.normalize_espn_team(code) == expected


def test_provider_specific_codes_layer_on_top():
    from modules import mfl_leagues

    assert mfl_leagues.normalize_team_abbreviation("GBP") == "GB"
    assert mfl_leagues.normalize_team_abbreviation("STL") == "LAR"
    assert mfl_leagues.normalize_team_abbreviation("FA") == ""
    assert canonical_team("GBP", extra={"GBP": "GB"}) == "GB"


def test_aliases_target_real_codes():
    assert set(TEAM_CODE_ALIASES.values()) <= NFL_TEAM_CODES
