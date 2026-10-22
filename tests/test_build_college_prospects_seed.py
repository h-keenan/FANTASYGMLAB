"""scripts/build_college_prospects_seed.py — the generator for the
College Scouting prospect seed (public.college_prospects).

Covers the position filter, draft-eligibility mapping, stable ids across
refreshes, duplicate protection, SQL escaping, the roster/board parsers,
and that the committed seed SQL is exactly what the committed manifest
renders to.
"""

from __future__ import annotations

import json
import re

import pytest

from modules import college_scouting
from scripts import build_college_prospects_seed as seed


def _row(name, school="Texas", position="WR", draft_year=2027, **extra):
    return {"name": name, "school": school, "position": position, "draft_year": draft_year, **extra}


# ---------------------------------------------------------------------------
# Position filter
# ---------------------------------------------------------------------------


def test_relevant_positions_match_the_app_read_time_filter():
    assert set(seed.RELEVANT_POSITIONS) == college_scouting.SCOUTING_RELEVANT_POSITIONS


@pytest.mark.parametrize(
    "label, expected",
    [
        ("QB", "QB"),
        ("Quarterback", "QB"),
        ("Running Back -", "RB"),
        ("WR/RB", "WR"),
        ("Wide Receiver", "WR"),
        ("Tight End", "TE"),
        ("CB", None),
        ("Safety", None),
        ("OL", None),
        ("EDGE", None),
        ("", None),
    ],
)
def test_map_position(label, expected):
    assert seed.map_position(label) == expected


def test_collect_candidates_keeps_only_fantasy_positions():
    board = (
        '<span class="pick-number">1.</span><b><a>Ok Receiver</a>, WR, Texas <br>'
        '<span class="pick-number">2.</span><b><a>Big Tackle</a>, OT, Texas <br>'
        '<span class="pick-number">3.</span><b><a>Edge Guy*</a>, DE, Texas <br>'
        '<span class="pick-number">4.</span><b>Ok Back**, RB, Miami <br>'
    )
    config = {"key": "wf", "parser": "walterfootball", "url": "https://example.test/wf"}
    candidates = seed.collect_candidates({"wf": (config, board)})
    assert sorted(c["name"] for c in candidates.values()) == ["Ok Back", "Ok Receiver"]
    back = candidates[seed.normalize_name("Ok Back")]
    assert back["boards"][0]["listed_school"] == "Miami (FL)"  # alias -> canonical


def test_render_sql_drops_non_fantasy_rows_and_validate_rejects_them():
    rows = [
        {**_row("Real Receiver"), "id": "2027-real-receiver-texas"},
        {**_row("Some Corner", position="CB"), "id": "2027-some-corner-texas"},
    ]
    sql = seed.render_sql(rows)
    assert "Real Receiver" in sql
    assert "Some Corner" not in sql
    with pytest.raises(ValueError):
        seed.validate_rows(rows)


def test_verify_rejects_roster_listed_defender():
    candidates = {
        seed.normalize_name("Two Way"): {
            "name": "Two Way",
            "boards": [{"source": "b", "url": "u", "listed_name": "Two Way", "listed_position": "WR", "listed_school": "Texas"}],
        }
    }
    page = _sidearm_page([("Two", "Way", "CB", "Jr.")])
    verified, rejected = seed.verify_candidates(candidates, {"Texas": page})
    assert verified == []
    assert rejected[0]["reason"].startswith("roster_position_not_fantasy")


# ---------------------------------------------------------------------------
# Draft eligibility (3 years out of high school)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, years, draft_year",
    [
        ("Fr.", 1, 2029),
        ("Freshman", 1, 2029),
        ("R-Fr.", 2, 2028),
        ("So.", 2, 2028),
        ("2nd", 2, 2028),
        ("R-So.", 3, 2027),
        ("Redshirt Sophomore", 3, 2027),
        ("Jr.", 3, 2027),
        ("JR", 3, 2027),
        ("3rd", 3, 2027),
        ("Junior", 3, 2027),
        ("Sr.", 4, 2027),
        ("R-Jr.", 4, 2027),
        ("4th", 4, 2027),
        ("Redshirt Senior", 5, 2027),
        ("5th", 5, 2027),
        ("5TH YR", 5, 2027),
        ("Fifth Year", 5, 2027),
        ("Gr.", 5, 2027),
        ("6th", 5, 2027),
        ("Post-Bacc", 5, 2027),
    ],
)
def test_class_label_to_first_eligible_draft(label, years, draft_year):
    assert seed.years_in_college(label) == years
    assert seed.first_eligible_draft_year(label, season=2026) == draft_year


def test_unknown_class_label_is_not_guessed():
    assert seed.years_in_college("") is None
    assert seed.years_in_college("Fy.") is None
    assert seed.first_eligible_draft_year("??", season=2026) is None


def test_verify_excludes_players_not_yet_eligible_for_requested_class():
    candidates = {
        seed.normalize_name(n): {
            "name": n,
            "boards": [{"source": "b", "url": "u", "listed_name": n, "listed_position": "WR", "listed_school": "Texas"}],
        }
        for n in ("Third Year", "Second Year")
    }
    page = _sidearm_page([("Third", "Year", "WR", "Jr."), ("Second", "Year", "WR", "So.")])
    verified, rejected = seed.verify_candidates(candidates, {"Texas": page}, draft_years=[2027])
    assert [r["name"] for r in verified] == ["Third Year"]
    assert verified[0]["draft_year"] == 2027
    assert rejected == [
        {"name": "Second Year", "listed_schools": ["Texas"], "boards": ["b"], "reason": "eligible_2028:So."}
    ]


def test_verify_rejects_candidate_missing_from_official_roster():
    candidates = {
        seed.normalize_name("Transferred Away"): {
            "name": "Transferred Away",
            "boards": [{"source": "b", "url": "u", "listed_name": "Transferred Away", "listed_position": "QB", "listed_school": "Texas"}],
        }
    }
    verified, rejected = seed.verify_candidates(candidates, {"Texas": _sidearm_page([("Someone", "Else", "QB", "Sr.")])})
    assert verified == []
    assert rejected[0]["reason"] == "not_on_official_roster"


# ---------------------------------------------------------------------------
# Stable ids / no duplicates
# ---------------------------------------------------------------------------


def test_prospect_id_is_deterministic_slug():
    assert seed.make_prospect_id("Trey'Dez Green", "LSU", 2027) == "2027-treydez-green-lsu"
    assert seed.make_prospect_id("Shaquille O'Neal", "Texas A&M", 2027) == "2027-shaquille-oneal-texas-a-and-m"
    assert seed.make_prospect_id("José Núñez Jr.", "Miami (FL)", 2028) == "2028-jose-nunez-jr-miami-fl"
    assert seed.make_prospect_id("A B", "C", 2027) == seed.make_prospect_id("A B", "C", 2027)


def test_merge_keeps_existing_id_when_player_transfers():
    existing = [{**_row("Mover Guy", school="Texas"), "id": "2027-mover-guy-texas"}]
    fresh = [_row("Mover Guy", school="Ohio State")]
    merged = seed.merge_manifest(existing, fresh)
    assert len(merged) == 1
    assert merged[0]["id"] == "2027-mover-guy-texas"
    assert merged[0]["school"] == "Ohio State"


def test_merge_never_drops_previously_seeded_players():
    existing = [{**_row("Old Guy"), "id": "2027-old-guy-texas"}]
    merged = seed.merge_manifest(existing, [_row("New Guy")])
    assert {r["id"] for r in merged} == {"2027-old-guy-texas", "2027-new-guy-texas"}


def test_merge_is_idempotent_and_dedupes_same_player():
    fresh = [_row("Same Guy"), _row("Same Guy Jr.")]  # suffix-insensitive same person
    once = seed.merge_manifest([], fresh)
    twice = seed.merge_manifest(once, fresh)
    assert len(once) == 1
    assert once == twice


def test_merge_disambiguates_id_collision_between_different_players():
    existing = [{**_row("Chris Smith", draft_year=2027), "id": "2027-chris-smith-texas"}]
    # Different draft year => different person key; force same slug id.
    fresh = [_row("Chris Smith", draft_year=2028)]
    merged = seed.merge_manifest(existing, fresh)
    ids = [r["id"] for r in merged]
    assert len(set(ids)) == 2
    collide = seed.merge_manifest(
        [{**_row("Chris Smith"), "id": "2027-chris-smith-texas"}],
        [{**_row("Chris  Smith!", draft_year=2027)}],
    )
    assert len(collide) == 1  # same normalized name + year is the same player


def test_validate_rows_rejects_duplicate_ids_and_duplicate_players():
    a = {**_row("One Guy"), "id": "2027-x"}
    with pytest.raises(ValueError, match="duplicate id"):
        seed.validate_rows([a, {**_row("Other Guy"), "id": "2027-x"}])
    with pytest.raises(ValueError, match="duplicate player"):
        seed.validate_rows([a, {**_row("One Guy Jr."), "id": "2027-y"}])
    with pytest.raises(ValueError, match="unsafe id"):
        seed.validate_rows([{**_row("Bad Id"), "id": "2027-x'; drop table"}])


# ---------------------------------------------------------------------------
# SQL escaping
# ---------------------------------------------------------------------------


def test_sql_literal_escapes_single_quotes():
    assert seed.sql_literal("O'Neal") == "'O''Neal'"
    assert seed.sql_literal("a''b") == "'a''''b'"
    assert seed.sql_literal(2027) == "2027"
    assert seed.sql_literal(None) == "null"
    with pytest.raises(ValueError):
        seed.sql_literal("bad\x00value")


def test_render_sql_escapes_names_and_is_idempotent_upsert():
    rows = [{**_row("Shaquille O'Neal", school="St. Mary's"), "id": "2027-shaquille-oneal-st-marys"}]
    sql = seed.render_sql(rows)
    assert "('2027-shaquille-oneal-st-marys', 'Shaquille O''Neal', 'WR', 'St. Mary''s', 2027)" in sql
    assert "on conflict (id) do update set" in sql
    body = "\n".join(line for line in sql.splitlines() if not line.startswith("--"))
    assert not re.search(r"\b(delete|truncate|drop)\b", body, re.I)
    # every quote inside the values block is paired
    values = body.split(" values\n", 1)[1].split("on conflict", 1)[0]
    for line in values.splitlines():
        inner = re.sub(r"'(?:[^']|'')*'", "", line)
        assert "'" not in inner, line


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def _nuxt(payload):
    return f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(payload)}</script>'


def _sidearm_page(players, title="2026 Football Roster - Test U"):
    arr = [["Reactive", 1], {"players": 2}, []]
    for first, last, pos, cls in players:
        base = len(arr)
        arr[2].append(base)
        arr.append({"firstName": base + 1, "lastName": base + 2, "positionShort": base + 3, "academicYearShort": base + 4, "previousSchool": -1})
        arr.extend([first, last, pos, cls])
    return f"<html><head><title>{title}</title></head><body>{_nuxt(arr)}</body></html>"


def test_parse_sidearm_nuxt_roster():
    players = seed.parse_nuxt_roster(_sidearm_page([("Jeremiah", "Smith", "WR", "Jr.")]))
    assert players[0]["name"] == "Jeremiah Smith"
    assert players[0]["position"] == "WR"
    assert players[0]["class_label"] == "Jr."


def test_sidearm_roster_for_other_season_is_ignored():
    page = _sidearm_page([("Old", "Guy", "WR", "Jr.")], title="2025 Football Roster - Test U")
    assert seed.parse_nuxt_roster(page, season=2026) == []


def test_parse_wmt_uses_season_roster_class_not_stale_master_record():
    arr = [
        {"entry": 1},
        {"player": 2, "roster": 6, "class_level": 8, "player_position": 10, "permalink": 12},
        {"first_name": 3, "last_name": 4, "full_name": 5, "class_level": 13, "previous_school": -1},
        "LJ", "Martin", "LJ Martin",
        {"name": 7}, "Football 2026",
        {"name": 9, "abbreviation": -1}, "Senior",
        {"abbreviation": 11, "name": 11}, "Running Back",
        "https://example.test/roster/season/2026/player/lj-martin",
        {"name": 14, "abbreviation": -1}, "Freshman",
    ]
    players = seed.parse_nuxt_roster(f"<title>Football 2026</title>{_nuxt(arr)}")
    assert players == [
        {
            "name": "LJ Martin",
            "position": "Running Back",
            "class_label": "Senior",
            "previous_school": "",
            "method": "nuxt",
            "profile_url": "https://example.test/roster/season/2026/player/lj-martin",
        }
    ]


def test_text_fallback_reads_table_row():
    page = (
        "<title>Roster</title><select><option selected >2026-27</option></select>"
        "<table><tr><td>6</td><td>Chris Marshall</td><td>WR</td><td>5th</td><td>6-3</td></tr></table>"
    )
    hit = seed.match_roster_player([], page, "Chris Marshall", season=2026)
    assert hit["position"] == "WR" and hit["class_label"] == "5th"
    assert seed.match_roster_player([], page, "Chris Marshall", season=2027) is None


def test_class_from_profile_page():
    page = "<dl><dt>Year</dt><dd>Senior</dd><dt>Hometown</dt><dd>Alpharetta</dd></dl>"
    assert seed.class_from_profile_page(page) == "Senior"


def test_parse_sticktothemodel_board():
    page = (
        '<tr data-rank="7" data-pos="WR" data-ht="75"><td><span class="nm-txt">'
        '<a href="/player/cam-coleman">Cam Coleman</a><small class="nm-sub">WR &middot; Texas</small>'
        "</span></td></tr>"
    )
    assert seed.parse_sticktothemodel_board(page) == [{"name": "Cam Coleman", "position": "WR", "school": "Texas"}]


# ---------------------------------------------------------------------------
# Committed artifacts
# ---------------------------------------------------------------------------


def _strip_generated(sql):
    return "\n".join(line for line in sql.splitlines() if not line.startswith("-- Generated:"))


def test_committed_seed_matches_committed_manifest():
    manifest = seed.manifest_path([2027])
    sql_path = seed.seed_path([2027])
    rows = seed.load_manifest(manifest)
    assert rows, "manifest is empty"
    committed = sql_path.read_text(encoding="utf-8")
    assert _strip_generated(committed) == _strip_generated(seed.render_sql(rows))
    assert len(committed.encode("utf-8")) < 200 * 1024


def test_committed_manifest_rows_are_real_cited_and_unique():
    rows = seed.load_manifest(seed.manifest_path([2027]))
    seed.validate_rows(rows)
    for row in rows:
        assert row["position"] in seed.RELEVANT_POSITIONS
        assert row["draft_year"] == 2027
        assert row["school"] in seed.SCHOOL_ROSTERS
        assert row["roster_url"] == seed.SCHOOL_ROSTERS[row["school"]]
        assert row["class_source_url"].startswith("https://")
        assert seed.first_eligible_draft_year(row["roster_class"], row["roster_season"]) == row["draft_year"]
        assert row["boards"], f"{row['name']} has no board citation"
        assert row["id"] == row["id"].lower()
