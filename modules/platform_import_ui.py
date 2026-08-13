from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import streamlit as st

from modules.platforms.espn import ESPNAdapterUnavailable, get_espn_adapter


ESPN_MAPPING_WARN_THRESHOLD = 0.85
ESPN_MAPPING_BLOCK_THRESHOLD = 0.60
DEFAULT_LEAGUE_IMPORT_PLATFORM = "Sleeper"
ESPN_LIMITED_FEATURES = {
    "enabled": ["Import review", "Roster mapping review"],
    "degraded": [
        "Dashboard/My Team/League Overview remain gated until ESPN page wiring is validated.",
        "Trade Hub and Waivers remain Sleeper-first until ESPN free-agent and transaction paths are validated.",
        "Draft Assistant live support and traded-pick features are unavailable for ESPN early access.",
    ],
}


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def sanitized_espn_error(error: Exception | str) -> str:
    text = _safe_text(error)
    if not text:
        return "ESPN league could not be loaded."
    lowered = text.lower()
    if "swid" in lowered or "espn_s2" in lowered or "cookie" in lowered or "unauthorized" in lowered:
        return "ESPN league could not be loaded. Private leagues require valid SWID and ESPN_S2 cookies."
    return "ESPN league could not be loaded. Check the league ID, season, and access settings."


def classify_mapping_quality(
    diagnostics: dict[str, Any],
    *,
    warn_threshold: float = ESPN_MAPPING_WARN_THRESHOLD,
    block_threshold: float = ESPN_MAPPING_BLOCK_THRESHOLD,
) -> dict[str, Any]:
    total = _safe_int(diagnostics.get("total_espn_players_seen"), 0)
    matched = _safe_int(diagnostics.get("canonical_matched_count"), 0)
    rate = float(matched / total) if total else 0.0
    if total <= 0:
        status = "fail"
        message = "No ESPN roster players were found to map."
        proceed = False
    elif rate < block_threshold:
        status = "blocked"
        message = "ESPN import loaded, but too few roster players matched FantasyGM Lab player IDs."
        proceed = False
    elif rate < warn_threshold:
        status = "degraded"
        message = "ESPN import loaded with partial player mapping. Limited review mode is available."
        proceed = True
    else:
        status = "success"
        message = "ESPN import loaded with enough player mapping for limited testing."
        proceed = True
    return {
        "status": status,
        "message": message,
        "matched_rate": rate,
        "can_proceed": proceed,
    }


def build_espn_import_result(
    *,
    league_id: str,
    season: int | str,
    df_players: pd.DataFrame,
    swid: str = "",
    espn_s2: str = "",
    adapter_factory: Callable[..., Any] = get_espn_adapter,
) -> dict[str, Any]:
    league_key = _safe_text(league_id).strip()
    season_value = _safe_int(season, 0)
    if not league_key or season_value <= 0:
        return {
            "ok": False,
            "status": "fail",
            "error": "Enter an ESPN league ID and season/year.",
            "can_proceed": False,
        }

    adapter = adapter_factory(df_players=df_players)
    try:
        league = adapter.get_league(
            league_key,
            season=season_value,
            swid=_safe_text(swid).strip() or None,
            espn_s2=_safe_text(espn_s2).strip() or None,
        )
        rosters = adapter.get_rosters(
            league_key,
            season=season_value,
            swid=_safe_text(swid).strip() or None,
            espn_s2=_safe_text(espn_s2).strip() or None,
        )
    except (ESPNAdapterUnavailable, RuntimeError, ValueError) as exc:
        return {
            "ok": False,
            "status": "fail",
            "error": sanitized_espn_error(exc),
            "can_proceed": False,
        }

    diagnostics = adapter.mapping_diagnostics()
    quality = classify_mapping_quality(diagnostics)
    teams_found = len(rosters or [])
    result = {
        "ok": bool(teams_found) and quality["status"] != "fail",
        "platform": "espn",
        "league": {
            "platform": "espn",
            "league_id": _safe_text(league.get("league_id") or league_key),
            "name": _safe_text(league.get("name"), "ESPN league"),
            "season": league.get("season") or season_value,
        },
        "rosters": rosters,
        "diagnostics": {
            **diagnostics,
            "teams_found": teams_found,
            "matched_rate": quality["matched_rate"],
        },
        "status": quality["status"],
        "message": quality["message"],
        "can_proceed": bool(teams_found) and bool(quality["can_proceed"]),
        "features": ESPN_LIMITED_FEATURES,
    }
    if not teams_found:
        result.update(
            {
                "ok": False,
                "status": "fail",
                "message": "ESPN league loaded, but no teams or rosters were returned.",
                "can_proceed": False,
            }
        )
    return result


def store_espn_import_result(session_state: dict, result: dict[str, Any]) -> None:
    sanitized = dict(result or {})
    sanitized.pop("swid", None)
    sanitized.pop("espn_s2", None)
    session_state["active_platform"] = "espn"
    session_state["espn_import_result"] = sanitized
    session_state["espn_limited_mode"] = bool(sanitized.get("can_proceed"))


def render_espn_diagnostics(result: dict[str, Any]) -> None:
    diagnostics = result.get("diagnostics") if isinstance(result, dict) else {}
    diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    status = _safe_text(result.get("status"), "unknown").title()
    if result.get("can_proceed"):
        st.success(_safe_text(result.get("message"), "ESPN import loaded."))
    elif result.get("ok"):
        st.warning(_safe_text(result.get("message"), "ESPN import is degraded."))
    else:
        st.error(_safe_text(result.get("error") or result.get("message"), "ESPN import failed."))

    c1, c2, c3 = st.columns(3)
    c1.metric("ESPN teams", _safe_int(diagnostics.get("teams_found"), 0))
    c2.metric("Matched players", _safe_int(diagnostics.get("canonical_matched_count"), 0))
    c3.metric("Mapping rate", f"{float(diagnostics.get('matched_rate') or 0.0):.0%}")
    c4, c5, c6 = st.columns(3)
    c4.metric("ESPN players seen", _safe_int(diagnostics.get("total_espn_players_seen"), 0))
    c5.metric("Unmatched", _safe_int(diagnostics.get("unmatched_count"), 0))
    c6.metric("Ambiguous", _safe_int(diagnostics.get("ambiguous_count"), 0))
    st.caption(
        f"ESPN import status: {status}. Cookie values are never displayed or saved by this "
        "Founder Beta import flow."
    )

    unmatched = diagnostics.get("unmatched_examples") or []
    ambiguous = diagnostics.get("ambiguous_examples") or []
    if unmatched:
        with st.expander("Sample unmatched ESPN players", expanded=False):
            for item in unmatched[:10]:
                st.write(
                    f"{_safe_text(item.get('name'), 'Unknown')} | "
                    f"{_safe_text(item.get('position'))} | {_safe_text(item.get('team'))}"
                )
    if ambiguous:
        with st.expander("Sample ambiguous ESPN players", expanded=False):
            for item in ambiguous[:10]:
                st.write(
                    f"{_safe_text(item.get('name'), 'Unknown')} | "
                    f"{_safe_text(item.get('position'))} | {_safe_text(item.get('team'))}"
                )


def render_platform_import_panel(df_players: pd.DataFrame) -> dict[str, Any]:
    actions = {"platform": "sleeper", "handled": False, "espn_result": None}
    if "league_import_platform" not in st.session_state:
        st.session_state["league_import_platform"] = DEFAULT_LEAGUE_IMPORT_PLATFORM

    st.markdown(
        "<div class='launch-section-intro launch-import-intro' id='fgl-import-league' "
        "data-fgl-import='1'>"
        "<div class='launch-section-eyebrow'>Import</div>"
        "<div class='launch-section-title'>Import your Sleeper league</div>"
        "<div class='launch-section-copy'>"
        "Enter your Sleeper username to load your leagues."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    platform = _safe_text(st.session_state.get("league_import_platform"), DEFAULT_LEAGUE_IMPORT_PLATFORM)
    if platform != "ESPN experimental":
        with st.expander("ESPN experimental", expanded=False):
            st.caption(
                "ESPN import is experimental and limited. Sleeper remains the primary "
                "supported path for FantasyGM Lab."
            )
            if st.button(
                "Use ESPN experimental import",
                key="league_import_use_espn",
                use_container_width=True,
            ):
                st.session_state["league_import_platform"] = "ESPN experimental"
                st.rerun()
        return actions

    actions["platform"] = "espn"
    actions["handled"] = True
    if st.button("Back to Sleeper import", key="league_import_back_sleeper", use_container_width=True):
        st.session_state["league_import_platform"] = DEFAULT_LEAGUE_IMPORT_PLATFORM
        st.rerun()
    st.markdown("#### ESPN experimental import")
    st.caption(
        "ESPN support is experimental. Private ESPN leagues require SWID and ESPN_S2 cookies. "
        "Cookie values are sensitive; do not paste them on shared or public devices. "
        "Cookies are session-only for this Founder Beta and are not saved."
    )
    with st.form("espn_experimental_import_form", clear_on_submit=False):
        league_id = st.text_input("ESPN League ID", key="espn_import_league_id")
        season = st.number_input("Season/year", min_value=2018, max_value=2035, value=2026, step=1, key="espn_import_season")
        swid = st.text_input("SWID (optional private league cookie)", type="password", key="espn_import_swid")
        espn_s2 = st.text_input("ESPN_S2 (optional private league cookie)", type="password", key="espn_import_espn_s2")
        submitted = st.form_submit_button("Import ESPN league", use_container_width=True, type="primary")

    if submitted:
        result = build_espn_import_result(
            league_id=league_id,
            season=season,
            df_players=df_players,
            swid=swid,
            espn_s2=espn_s2,
        )
        st.session_state["espn_import_result"] = result
        actions["espn_result"] = result

    result = st.session_state.get("espn_import_result")
    if isinstance(result, dict) and result.get("platform") == "espn":
        render_espn_diagnostics(result)
        features = result.get("features") if isinstance(result.get("features"), dict) else ESPN_LIMITED_FEATURES
        with st.expander("ESPN feature status", expanded=False):
            st.write("Enabled now:")
            for item in features.get("enabled", []):
                st.write(f"- {item}")
            st.write("Degraded or hidden:")
            for item in features.get("degraded", []):
                st.write(f"- {item}")
        if result.get("can_proceed"):
            if st.button("Proceed with limited ESPN review mode", key="espn_limited_mode_proceed", use_container_width=True):
                store_espn_import_result(st.session_state, result)
                st.rerun()
        else:
            st.caption("Fix mapping or access issues before limited ESPN mode is enabled.")

    if st.session_state.get("espn_limited_mode"):
        st.info("Limited ESPN review mode is active. Sleeper pages remain the supported full workflow.")
    return actions
