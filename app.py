import time as _bootstrap_time

_APP_MODULE_IMPORT_STARTED = _bootstrap_time.perf_counter()

import base64
import importlib
import json
import os
import re
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from html import escape
from urllib.parse import urlparse

import streamlit as st
import pandas as pd

from modules import rankings as rankings_module
from modules import player_asset_explorer_ui
from modules import account_store
from modules import account_ui
from modules import application_shell
from modules import brand_identity
from modules import canonical_player_ranking
from modules.app_styles import APP_CSS
from modules.executive_command_header_styles import (
    COMMAND_COLUMN_WEIGHTS,
    EXECUTIVE_COMMAND_HEADER_CSS,
)
from modules.ux_polish_styles import FOUNDER_BETA_UX_CSS
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules import auth_supabase
from modules import auth_restore_lifecycle
from modules import draft_assistant
from modules import draft_center_ui
from modules import dashboard_orientation
from modules import dashboard_workflow
from modules import daily_gm_briefing
from modules import daily_gm_briefing_ui
from modules import decision_change_history
from modules import decision_change_history_ui
from modules import decision_memory
from modules import gm_targets
from modules import gm_targets_ui
from modules import comparative_metrics
from modules.dashboard_workflow_styles import DASHBOARD_WORKFLOW_CSS
from modules import deferred_rendering
from modules import executive_table_ui
from modules.trades import trade_gain
from modules.sleeper import (
    get_draft,
    get_draft_picks,
    get_league,
    get_league_drafts,
    get_players,
    get_league_roster_profiles,
    get_matchups,
    get_roster_player_ids,
    get_roster_profile,
    get_rosters,
    get_transactions,
    get_user_roster_id,
)
from modules.faab import recommend_faab
from modules.feedback import (
    append_feedback_report,
    build_feedback_report,
    build_global_feedback_report,
    feedback_context_payload,
)
from modules import feedback_ui
from modules import notification_center
from modules import app_config
from modules import league_workspace_ui
from modules import league_standings
from modules import league_intelligence as league_intelligence_feed
from modules import league_intelligence_ui
from modules import league_maturity
from modules import live_draft
from modules import live_draft_ui
from modules import injury_ui
from modules import legal_pages
from modules import my_team_ui
from modules import onboarding_ui
from modules import platform_import_ui
from modules import premium
from modules import premium_page
from modules import performance
from modules import prepared_player_frame
from modules import runtime_trace
from modules import startup_coordinator
from modules import startup_critical_path
from modules import startup_cold_path
from modules import shell_chrome_schema
from modules import trade_hub_first_useful
from modules import league_switch_first_useful
from modules import interaction_latency
from modules.roster_needs import (
    TeamNeedsAssessment,
    assess_team_needs,
)
from modules import team_eval as team_eval_module
from modules import trade_ideas as trade_ideas_module
from modules.draft_prospects import draft_watch_positions, prospects_for_positions
from modules.player_images import fetch_player_headshot_bytes
from modules import player_cards
from modules.player_eligibility import filter_current_fantasy_players
from modules.player_tiers import assign_player_tiers
from modules.trust_enforcement import (
    enforce_trade_board,
    enforcement_from_player_annotations,
)
from modules import player_profile_ui
from modules import user_preferences
from modules import player_history
from modules import player_quick_view
from modules import canonical_recommendation_narrative
from modules import trade_hub_ui
from modules import trade_detail_navigation
from modules import session_integrity
from modules import founder_ops
from modules import founder_ops_ui
from modules import waivers_ui
from modules import valuation_archetype_service
from modules import valuation_archetype_ui
from modules import valuation_archetypes
from modules import weekly_report_ui
from modules import workspace_ui
from modules import ui_primitives
from modules import workspace_context
from modules.accounts import get_current_account, upsert_account
from modules.profile import load_profile_key, save_profile_key
from modules.my_news import (
    build_quick_news_summary,
    build_sleeper_roster_updates,
    curate_player_news,
    filter_news_for_players,
    relative_news_time,
)
from modules.sleeper_leagues import get_user_leagues, league_lookup_customer_message, lookup_user_leagues
from modules.platforms.sleeper import get_sleeper_adapter
from modules.ui_architecture import (
    PLATFORM_DESTINATIONS,
    current_platform_destinations,
)
from modules.navigation_state import (
    LAST_DESTINATION_KEY,
    commit_destination_navigation,
    consume_scroll_reset,
    preserved_league_switch_destination,
    queue_destination_navigation,
    request_scroll_reset,
    request_scroll_restore,
    scroll_storage_scope,
    synchronize_destination_change,
)
from modules import workflow_continuity
from modules import recommendation_lifecycle

# Streamlit already reruns this module when source changes. Re-importing every
# dependency on each user interaction invalidates otherwise stable module state
# and cache identities. Keep manual reload available only for explicit local
# development troubleshooting.
if app_config.config_bool("DYNASTYGM_DEV_RELOAD_MODULES"):
    rankings_module = importlib.reload(rankings_module)
    account_store = importlib.reload(account_store)
    account_ui = importlib.reload(account_ui)
    auth_supabase = importlib.reload(auth_supabase)
    draft_assistant = importlib.reload(draft_assistant)
    team_eval_module = importlib.reload(team_eval_module)
    trade_ideas_module = importlib.reload(trade_ideas_module)
    trade_hub_ui = importlib.reload(trade_hub_ui)
    player_cards = importlib.reload(player_cards)
    injury_ui = importlib.reload(injury_ui)
    waivers_ui = importlib.reload(waivers_ui)
    platform_import_ui = importlib.reload(platform_import_ui)
    premium = importlib.reload(premium)
    live_draft = importlib.reload(live_draft)
    live_draft_ui = importlib.reload(live_draft_ui)
    premium_page = importlib.reload(premium_page)
build_players_table = rankings_module.build_players_table
current_availability_multiplier = getattr(
    rankings_module,
    "current_availability_multiplier",
    rankings_module.risk_multiplier,
)
load_players = rankings_module.load_players
injury_level = rankings_module.injury_level
is_injury_status = rankings_module.is_injury_status
is_probably_stale_free_agent = rankings_module.is_probably_stale_free_agent
summarize_team_injuries = rankings_module.summarize_team_injuries
build_league_summary = team_eval_module.build_league_summary
get_team_vs_league = team_eval_module.get_team_vs_league
normalize_team_strategy = team_eval_module.normalize_team_strategy
refine_team_directions = team_eval_module.refine_team_directions
suggest_optimal_lineup = team_eval_module.suggest_optimal_lineup
team_strategy_label = team_eval_module.team_strategy_label
team_strategy_mode = team_eval_module.team_strategy_mode
build_player_trade_hub_ideas = trade_ideas_module.build_player_trade_hub_ideas
build_trade_ideas = trade_ideas_module.build_trade_ideas
list_draft_pick_assets = trade_ideas_module.list_draft_pick_assets

DB_PATH = "data/players.db"
STRATEGY_SELECTOR_OPTIONS = ("Auto", "Contender", "Retool", "Rebuild", "Tank")
WEEKLY_RANK_SNAPSHOT_PATH = os.path.join("data", "weekly_rank_snapshots.json")
INJURY_EMOJI = "INJ"
TRADE_SUMMARY_MARKET_REALISM_MIN = 68


def fetch_news(*args, **kwargs):
    """Load optional news infrastructure only when a news surface needs it."""

    from modules.news import fetch_news as _fetch_news

    return _fetch_news(*args, **kwargs)


def load_cached_news_pool(*args, **kwargs):
    """Disk-only news pool for PQV warm hydration (no live RSS)."""

    from modules.news import load_cached_news_pool as _load_cached_news_pool

    return _load_cached_news_pool(*args, **kwargs)


def fetch_roster_news(*args, **kwargs):
    """Load optional roster-news infrastructure outside the startup path."""

    from modules.news import fetch_roster_news as _fetch_roster_news

    return _fetch_roster_news(*args, **kwargs)


def get_news_status(*args, **kwargs):
    from modules.news import get_news_status as _get_news_status

    return _get_news_status(*args, **kwargs)


def explain_player_decision(*args, **kwargs):
    """Load optional explanation infrastructure only after user interaction."""

    from modules.chat import explain_player_decision as _explain_player_decision

    return _explain_player_decision(*args, **kwargs)


@dataclass(frozen=True)
class TradeTrustContext:
    ownership_by_player: tuple[tuple[str, int], ...]
    valid_roster_ids: frozenset[int]
    team_name_to_roster: tuple[tuple[str, int], ...]
    league_context_valid: bool

TEAM_CARD_TAP_COMPONENT = st.components.v2.component(
    "team_card_tap_grid",
    html="""
    <div id="team-card-tap-root"></div>
    """,
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const root = parentElement.querySelector("#team-card-tap-root")
      if (!root) return

      root.innerHTML = (data && data.html) || ""

      const emit = (card) => {
        const rosterId = card.dataset.rosterId || card.getAttribute("data-roster-id") || ""
        if (!rosterId) return
        setTriggerValue("clicked", {
          roster_id: rosterId,
          team_name: card.dataset.teamName || card.getAttribute("data-team-name") || "",
          ts: Date.now()
        })
      }

      root.querySelectorAll(".team-card-tappable[data-roster-id]").forEach((card) => {
        if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "0")
        if (!card.hasAttribute("role")) card.setAttribute("role", "button")

        card.onclick = () => emit(card)
        card.onkeydown = (event) => {
          if (event.key !== "Enter" && event.key !== " ") return
          event.preventDefault()
          emit(card)
        }
      })
    }
    """,
    isolate_styles=False,
)




LEAGUE_SWITCH_CARD_COMPONENT = st.components.v2.component(
    "league_switch_card_grid",
    html="<div id='league-switch-card-root'></div>",
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const root = parentElement.querySelector("#league-switch-card-root")
      if (!root) return
      const cards = (data && data.cards) || []
      root.innerHTML = ""
      const grid = document.createElement("div")
      grid.className = "league-switch-card-grid"
      cards.forEach((item) => {
        const card = document.createElement("button")
        card.type = "button"
        card.className = "league-switch-card" + (item.current ? " league-switch-card-current" : "")
        card.dataset.leagueId = item.league_id || ""
        card.setAttribute("aria-label", (item.current ? "Current league " : "Switch to ") + (item.title || "saved league"))

        const title = document.createElement("span")
        title.className = "league-switch-card-title"
        title.textContent = item.title || "Saved league"
        card.appendChild(title)

        const meta = document.createElement("span")
        meta.className = "league-switch-card-meta"
        meta.textContent = item.meta || "Saved league"
        card.appendChild(meta)

        const badges = document.createElement("span")
        badges.className = "league-switch-card-badges"
        if (item.current) {
          const current = document.createElement("span")
          current.className = "league-switch-card-badge league-switch-card-badge-current"
          current.textContent = "Current"
          badges.appendChild(current)
        }
        if (item.is_default) {
          const preferred = document.createElement("span")
          preferred.className = "league-switch-card-badge league-switch-card-badge-default"
          preferred.textContent = "Default"
          badges.appendChild(preferred)
        }
        if (badges.childElementCount) card.appendChild(badges)

        card.onclick = () => {
          if (!item.league_id || item.current) return
          const leagueTitle = item.title || "league"
          card.classList.add("league-switch-card-loading")
          card.disabled = true
          meta.textContent = "Switching to " + leagueTitle + "..."
          card.setAttribute("aria-busy", "true")
          setTriggerValue("clicked", { league_id: item.league_id, ts: Date.now() })
          window.setTimeout(() => {
            if (card.classList.contains("league-switch-card-loading")) {
              meta.textContent = "Loading league..."
            }
          }, 220)
        }
        grid.appendChild(card)
      })
      root.appendChild(grid)
    }
    """,
    isolate_styles=False,
)


NAVIGATION_SCROLL_RESET_COMPONENT = st.components.v2.component(
    "navigation_scroll_reset",
    html="<span class='navigation-scroll-reset-marker' aria-hidden='true'></span>",
    js="""
    export default function(component) {
      const data = component.data || {}
      const token = Number(data.token || 0)
      const dest = String(data.destination || "")
      const scope = String(data.scope || "none")
      const mode = String(data.mode || "reset")
      const hostWindow = window.parent || window
      const storeKey = dest ? `dg-scroll-${scope}-${dest}` : ""
      const readY = () => {
        if (!storeKey) return 0
        try {
          const value = Number(hostWindow.sessionStorage.getItem(storeKey))
          return Number.isFinite(value) && value >= 0 ? value : 0
        } catch (_error) {
          return 0
        }
      }
      const writeY = () => {
        const page = String(hostWindow.__dgScrollTrackPage || dest || "")
        if (!page) return
        const doc = hostWindow.document
        const y = Number((doc.scrollingElement && doc.scrollingElement.scrollTop)
          || doc.documentElement.scrollTop || doc.body.scrollTop || 0)
        try {
          hostWindow.sessionStorage.setItem(`dg-scroll-${scope}-${page}`, String(y))
        } catch (_error) {}
      }
      if (!hostWindow.__dgScrollTrackBound) {
        hostWindow.__dgScrollTrackBound = true
        let timer = null
        const schedule = () => {
          if (timer) hostWindow.clearTimeout(timer)
          timer = hostWindow.setTimeout(writeY, 120)
        }
        hostWindow.addEventListener("scroll", schedule, { passive: true })
        hostWindow.addEventListener("pagehide", writeY)
      }
      if (!token) {
        if (dest) hostWindow.__dgScrollTrackPage = dest
        writeY()
        return
      }
      if (Number(hostWindow.__dynastyGmScrollResetToken || 0) >= token) return
      hostWindow.__dynastyGmScrollResetToken = token

      const applyScroll = (top) => {
        const doc = hostWindow.document
        const targets = [
          doc.scrollingElement,
          doc.documentElement,
          doc.body,
          doc.querySelector('[data-testid="stAppViewContainer"]'),
          doc.querySelector('[data-testid="stMain"]')
        ].filter(Boolean)
        targets.forEach((target) => {
          if (typeof target.scrollTo === "function") {
            target.scrollTo({ top, left: 0, behavior: "auto" })
          } else {
            target.scrollTop = top
            target.scrollLeft = 0
          }
        })
        hostWindow.scrollTo({ top, left: 0, behavior: "auto" })
      }

      const run = () => applyScroll(mode === "restore" ? readY() : 0)
      hostWindow.requestAnimationFrame(() => {
        hostWindow.requestAnimationFrame(run)
      })
      hostWindow.setTimeout(run, 80)
    }
    """,
    isolate_styles=False,
)


CHART_COLORS = ["#2563eb", "#64748b", "#14b8a6", "#f59e0b", "#ef4444"]
CHART_CONFIG = {
    "displayModeBar": False,
    "modeBarButtonsToRemove": [
        "zoom2d",
        "pan2d",
        "select2d",
        "lasso2d",
        "zoomIn2d",
        "zoomOut2d",
        "autoScale2d",
        "resetScale2d",
        "hoverClosestCartesian",
        "hoverCompareCartesian",
        "toggleSpikelines",
        "toImage",
    ],
    "responsive": True,
    "staticPlot": True,
    "scrollZoom": False,
    "showTips": False,
}


def tidy_label(s):
    if not isinstance(s, str):
        return str(s)
    return s.replace("_", " ").title()


@runtime_trace.traced("roster_normalization", phase="roster_normalization")
def normalize_player_ids(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "player_id" not in df.columns:
        return df
    df = df.copy()
    df["player_id"] = df["player_id"].astype(str)
    return df


def format_score_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    score_cols = [
        "value",
        "market_score",
        "age_penalty",
        "scarcity_score",
        "role_score",
        "score",
        "rebuild_score",
        "dynasty_score",
        "value_score",
    ]
    for col in score_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).round().astype(int)
    return df


VALUATION_LENS_TO_SCORE_FIELD = {
    "Dynasty": "dynasty_score",
    "Rebuild": "rebuild_score",
    "Non-Dynasty": "value_score",
}

DRAFT_PICK_SCORE_MULTIPLIERS = {
    "Dynasty": 1.0,
    "Rebuild": 1.16,
    "Non-Dynasty": 0.45,
}
PICK_VALUATION_SETTING_KEYS = (
    "league_format",
    "qb_format",
    "te_premium",
    "league_size",
    "starter_count",
    "flex_count",
    "bench_count",
    "taxi_count",
    "ir_count",
)

DEFAULT_LEAGUE_VALUE_SETTINGS = {
    "league_format": "Dynasty",
    "scoring_format": "PPR",
    "qb_format": "1QB",
    "te_premium": False,
    "qb_count": 1,
    "rb_count": 2,
    "wr_count": 3,
    "te_count": 1,
    "starter_count": 9,
    "flex_count": 2,
    "regular_flex_count": 1,
    "wrrb_flex_count": 1,
    "superflex_count": 0,
    "k_count": 0,
    "bench_count": 0,
    "taxi_count": 0,
    "ir_count": 0,
    "other_starter_count": 0,
    "league_size": 12,
}

NEWS_REASON_LABELS = {
    "injury/status": "Injury / Status",
    "transaction/drama": "Trade / Drama",
    "role/depth chart": "Starting Role",
    "player mention": "Player mention",
    "sleeper status/role metadata changed": "Sleeper update",
}


def valuation_score_field(valuation_lens: str) -> str:
    return VALUATION_LENS_TO_SCORE_FIELD.get(valuation_lens, "dynasty_score")


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_positive_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def _safe_nonnegative_int(value, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed if parsed >= 0 else default


def detect_league_value_settings(league_id: str | None) -> dict:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings["_sources"] = {key: "default" for key in DEFAULT_LEAGUE_VALUE_SETTINGS}
    if not league_id:
        return settings

    league = get_league(league_id) or {}
    scoring = league.get("scoring_settings") if isinstance(league.get("scoring_settings"), dict) else {}
    league_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    roster_positions = [
        str(pos or "").upper()
        for pos in league.get("roster_positions", []) or []
    ]

    league_type = league_settings.get("type")
    if league_type is not None:
        settings["league_format"] = "Redraft" if _safe_positive_int(league_type, 0) == 0 else "Dynasty"
        settings["_sources"]["league_format"] = "Sleeper"

    rec_score = _safe_float(scoring.get("rec"), 1.0)
    if rec_score >= 0.95:
        settings["scoring_format"] = "PPR"
    elif rec_score >= 0.45:
        settings["scoring_format"] = "Half-PPR"
    else:
        settings["scoring_format"] = "Standard"
    if "rec" in scoring:
        settings["_sources"]["scoring_format"] = "Sleeper"

    te_bonus_keys = [
        "bonus_rec_te",
        "rec_bonus_te",
        "te_rec_bonus",
        "bonus_fd_te",
        "te_fd_bonus",
    ]
    settings["te_premium"] = any(
        _safe_float(scoring.get(key), 0.0) > 0
        for key in te_bonus_keys
    )
    if any(key in scoring for key in te_bonus_keys):
        settings["_sources"]["te_premium"] = "Sleeper"

    qb_count = roster_positions.count("QB")
    rb_count = roster_positions.count("RB")
    wr_count = roster_positions.count("WR")
    te_count = roster_positions.count("TE")
    k_count = roster_positions.count("K")
    superflex_count = sum(1 for pos in roster_positions if pos in {"SUPER_FLEX", "OP"})
    if qb_count >= 2:
        settings["qb_format"] = "2QB"
    elif superflex_count:
        settings["qb_format"] = "Superflex"
    else:
        settings["qb_format"] = "1QB"
    if roster_positions:
        settings["_sources"]["qb_format"] = "Sleeper"
        settings["qb_count"] = max(1, qb_count)
        settings["rb_count"] = rb_count if rb_count > 0 else settings["rb_count"]
        settings["wr_count"] = wr_count if wr_count > 0 else settings["wr_count"]
        settings["te_count"] = te_count if te_count > 0 else settings["te_count"]
        settings["k_count"] = k_count
        settings["superflex_count"] = superflex_count
        for key in ["qb_count", "rb_count", "wr_count", "te_count", "k_count", "superflex_count"]:
            settings["_sources"][key] = "Sleeper"

    bench_slots = {"BN", "BE", "BENCH", "IR", "TAXI"}
    bench_positions = {"BN", "BE", "BENCH"}
    starter_positions = [
        pos for pos in roster_positions if pos and pos not in bench_slots
    ]
    if starter_positions:
        settings["starter_count"] = len(starter_positions)
        settings["_sources"]["starter_count"] = "Sleeper"
    regular_flex_positions = [
        pos
        for pos in starter_positions
        if pos not in {"SUPER_FLEX", "OP"}
        and ("FLEX" in pos or pos in {"W/R/T", "RB/WR/TE", "WR/RB/TE"})
    ]
    wrrb_flex_positions = [
        pos
        for pos in starter_positions
        if pos in {"W/R", "WR/RB", "RB/WR", "WRRB_FLEX"}
    ]
    if starter_positions:
        settings["regular_flex_count"] = len(regular_flex_positions)
        settings["wrrb_flex_count"] = len(wrrb_flex_positions)
        settings["flex_count"] = len(regular_flex_positions) + len(wrrb_flex_positions)
        counted_core = (
            int(settings["qb_count"])
            + int(settings["rb_count"])
            + int(settings["wr_count"])
            + int(settings["te_count"])
            + int(settings["k_count"])
            + int(settings["flex_count"])
            + int(settings["superflex_count"])
        )
        settings["other_starter_count"] = max(0, len(starter_positions) - counted_core)
        for key in ["flex_count", "regular_flex_count", "wrrb_flex_count", "other_starter_count"]:
            settings["_sources"][key] = "Sleeper"

    bench_count = sum(1 for pos in roster_positions if pos in bench_positions)
    taxi_count = sum(1 for pos in roster_positions if pos == "TAXI")
    ir_count = _safe_nonnegative_int(league_settings.get("reserve_slots"), 0)
    if not ir_count:
        ir_count = sum(1 for pos in roster_positions if pos == "IR")
    if roster_positions or ir_count:
        settings["bench_count"] = bench_count
        settings["taxi_count"] = taxi_count
        settings["ir_count"] = ir_count
        settings["_sources"]["bench_count"] = "Sleeper"
        settings["_sources"]["taxi_count"] = "Sleeper"
        settings["_sources"]["ir_count"] = "Sleeper"

    settings["league_size"] = _safe_positive_int(
        league.get("total_rosters") or league_settings.get("num_teams"),
        settings["league_size"],
    )
    if league.get("total_rosters") or league_settings.get("num_teams"):
        settings["_sources"]["league_size"] = "Sleeper"
    return settings


def resolve_league_value_settings(auto_settings: dict) -> dict:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(auto_settings or {})
    sources = dict((auto_settings or {}).get("_sources", {}))
    settings["_sources"] = sources

    format_override = st.session_state.get("league_format_override", "Auto")
    if format_override != "Auto":
        settings["league_format"] = format_override
        sources["league_format"] = "manual"

    scoring_override = st.session_state.get("league_scoring_override", "Auto")
    if scoring_override != "Auto":
        settings["scoring_format"] = scoring_override
        sources["scoring_format"] = "manual"

    qb_override = st.session_state.get("league_qb_override", "Auto")
    if qb_override != "Auto":
        settings["qb_format"] = qb_override
        settings["qb_count"] = 2 if qb_override == "2QB" else 1
        settings["superflex_count"] = 1 if qb_override == "Superflex" else 0
        sources["qb_format"] = "manual"
        sources["qb_count"] = "manual"
        sources["superflex_count"] = "manual"

    te_override = st.session_state.get("league_te_premium_override", "Auto")
    if te_override != "Auto":
        settings["te_premium"] = te_override == "Yes"
        sources["te_premium"] = "manual"

    for key, session_key in [
        ("rb_count", "league_rb_count_override"),
        ("wr_count", "league_wr_count_override"),
        ("te_count", "league_te_count_override"),
    ]:
        override = st.session_state.get(session_key, "Auto")
        if override != "Auto":
            settings[key] = _safe_nonnegative_int(override, settings[key])
            sources[key] = "manual"

    starter_override = st.session_state.get("league_starters_override", "Auto")
    if starter_override != "Auto":
        settings["starter_count"] = _safe_positive_int(starter_override, settings["starter_count"])
        sources["starter_count"] = "manual"

    flex_override = st.session_state.get("league_flex_override", "Auto")
    if flex_override != "Auto":
        settings["flex_count"] = _safe_nonnegative_int(flex_override, settings["flex_count"])
        settings["regular_flex_count"] = settings["flex_count"]
        settings["wrrb_flex_count"] = 0
        sources["flex_count"] = "manual"
        sources["regular_flex_count"] = "manual"
        sources["wrrb_flex_count"] = "manual"

    bench_override = st.session_state.get("league_bench_override", "Auto")
    if bench_override != "Auto":
        settings["bench_count"] = _safe_nonnegative_int(bench_override, settings["bench_count"])
        sources["bench_count"] = "manual"

    taxi_override = st.session_state.get("league_taxi_override", "Auto")
    if taxi_override != "Auto":
        settings["taxi_count"] = _safe_nonnegative_int(taxi_override, settings["taxi_count"])
        sources["taxi_count"] = "manual"

    ir_override = st.session_state.get("league_ir_override", "Auto")
    if ir_override != "Auto":
        settings["ir_count"] = _safe_nonnegative_int(ir_override, settings["ir_count"])
        sources["ir_count"] = "manual"

    league_size_override = st.session_state.get("league_size_override", "Auto")
    if league_size_override != "Auto":
        settings["league_size"] = _safe_positive_int(league_size_override, settings["league_size"])
        sources["league_size"] = "manual"

    if starter_override == "Auto":
        core_count = (
            int(settings.get("qb_count") or 0)
            + int(settings.get("rb_count") or 0)
            + int(settings.get("wr_count") or 0)
            + int(settings.get("te_count") or 0)
            + int(settings.get("k_count") or 0)
            + int(settings.get("flex_count") or 0)
            + int(settings.get("superflex_count") or 0)
            + int(settings.get("other_starter_count") or 0)
        )
        if core_count > 0:
            settings["starter_count"] = core_count

    return settings


def format_league_value_settings(settings: dict) -> str:
    te_text = "TE premium" if settings.get("te_premium") else "No TE premium"
    return (
        f"{settings.get('league_format', 'Dynasty')} | "
        f"{settings.get('scoring_format', 'PPR')} | "
        f"{settings.get('qb_format', '1QB')} | "
        f"{te_text} | "
        f"{int(settings.get('starter_count') or 0)} starters "
        f"({int(settings.get('qb_count') or 0)} QB, "
        f"{int(settings.get('rb_count') or 0)} RB, "
        f"{int(settings.get('wr_count') or 0)} WR, "
        f"{int(settings.get('te_count') or 0)} TE, "
        f"{int(settings.get('flex_count') or 0)} FLEX) | "
        f"{int(settings.get('bench_count') or 0)} bench | "
        f"{int(settings.get('taxi_count') or 0)} taxi | "
        f"{int(settings.get('ir_count') or 0)} IR | "
        f"{int(settings.get('league_size') or 0)} teams"
    )


def compact_league_value_settings(settings: dict) -> str:
    parts = [
        f"{int(settings.get('league_size') or 0)} Team",
        str(settings.get("qb_format") or "1QB"),
        str(settings.get("scoring_format") or "PPR"),
    ]
    if settings.get("te_premium"):
        parts.append("TE Premium")
    parts.append(str(settings.get("league_format") or "Dynasty"))
    return ", ".join(parts)


def format_defaulted_league_settings(settings: dict) -> str:
    sources = settings.get("_sources", {}) if isinstance(settings, dict) else {}
    labels = {
        "league_format": "League format",
        "scoring_format": "Scoring",
        "qb_format": "QB format",
        "te_premium": "TE premium",
        "qb_count": "QB starters",
        "rb_count": "RB starters",
        "wr_count": "WR starters",
        "te_count": "TE starters",
        "starter_count": "Lineup size",
        "flex_count": "Flex spots",
        "bench_count": "Bench size",
        "taxi_count": "Taxi size",
        "ir_count": "IR size",
        "league_size": "League size",
    }
    defaulted = [
        label
        for key, label in labels.items()
        if sources.get(key, "default") == "default"
    ]
    if not defaulted:
        return "All displayed settings came from Sleeper unless manually adjusted."
    return "Defaulted or estimated: " + ", ".join(defaulted)


def league_value_settings_key(settings: dict) -> str:
    return "|".join(
        [
            str(settings.get("league_format", "Dynasty")),
            str(settings.get("scoring_format", "PPR")),
            str(settings.get("qb_format", "1QB")),
            str(bool(settings.get("te_premium"))),
            str(int(settings.get("qb_count") or 0)),
            str(int(settings.get("rb_count") or 0)),
            str(int(settings.get("wr_count") or 0)),
            str(int(settings.get("te_count") or 0)),
            str(int(settings.get("starter_count") or 0)),
            str(int(settings.get("flex_count") or 0)),
            str(int(settings.get("regular_flex_count") or 0)),
            str(int(settings.get("wrrb_flex_count") or 0)),
            str(int(settings.get("superflex_count") or 0)),
            str(int(settings.get("k_count") or 0)),
            str(int(settings.get("bench_count") or 0)),
            str(int(settings.get("taxi_count") or 0)),
            str(int(settings.get("ir_count") or 0)),
            str(int(settings.get("league_size") or 0)),
        ]
    )


def draft_pick_score_multiplier(valuation_lens: str, league_settings: dict | None = None) -> float:
    multiplier = DRAFT_PICK_SCORE_MULTIPLIERS.get(valuation_lens, 1.0)
    settings = league_settings or {}
    league_size = int(settings.get("league_size") or DEFAULT_LEAGUE_VALUE_SETTINGS["league_size"])
    if settings.get("league_format") == "Redraft" and valuation_lens != "Non-Dynasty":
        multiplier *= 0.45
    if valuation_lens in {"Dynasty", "Rebuild"}:
        multiplier *= 1 + max(-4, min(8, league_size - 12)) * 0.015
    return multiplier


def draft_pick_valuation_settings(league_settings: dict | None = None) -> dict:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    return {
        "league_format": str(settings.get("league_format") or "Dynasty"),
        "qb_format": str(settings.get("qb_format") or "1QB"),
        "te_premium": bool(settings.get("te_premium")),
        "league_size": int(settings.get("league_size") or DEFAULT_LEAGUE_VALUE_SETTINGS["league_size"]),
        "starter_count": int(settings.get("starter_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["starter_count"]),
        "flex_count": int(settings.get("flex_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["flex_count"]),
        "bench_count": int(settings.get("bench_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["bench_count"]),
        "taxi_count": int(settings.get("taxi_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["taxi_count"]),
        "ir_count": int(settings.get("ir_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["ir_count"]),
        "superflex_count": int(settings.get("superflex_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["superflex_count"]),
        "qb_count": int(settings.get("qb_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["qb_count"]),
        "rb_count": int(settings.get("rb_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["rb_count"]),
        "wr_count": int(settings.get("wr_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["wr_count"]),
        "te_count": int(settings.get("te_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["te_count"]),
    }


def draft_pick_valuation_settings_items(league_settings: dict | None = None) -> tuple[tuple[str, object], ...]:
    settings = draft_pick_valuation_settings(league_settings)
    return tuple((key, settings[key]) for key in PICK_VALUATION_SETTING_KEYS)


def _league_settings_multiplier(df: pd.DataFrame, league_settings: dict | None) -> pd.Series:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})

    positions = (
        df["position"].fillna("").astype(str).str.upper()
        if "position" in df.columns
        else pd.Series("", index=df.index, dtype="object")
    )
    ages = pd.to_numeric(df.get("age", pd.Series(float("nan"), index=df.index)), errors="coerce")
    multiplier = pd.Series(1.0, index=df.index, dtype="float64")

    scoring_format = str(settings.get("scoring_format") or "PPR")
    if scoring_format == "Half-PPR":
        multiplier = multiplier.mask(positions == "RB", multiplier * 1.02)
        multiplier = multiplier.mask(positions == "WR", multiplier * 0.985)
        multiplier = multiplier.mask(positions == "TE", multiplier * 0.985)
    elif scoring_format == "Standard":
        multiplier = multiplier.mask(positions == "RB", multiplier * 1.07)
        multiplier = multiplier.mask(positions == "WR", multiplier * 0.96)
        multiplier = multiplier.mask(positions == "TE", multiplier * 0.96)

    qb_format = str(settings.get("qb_format") or "1QB")
    if qb_format == "Superflex":
        multiplier = multiplier.mask(positions == "QB", multiplier * 1.35)
    elif qb_format == "2QB":
        multiplier = multiplier.mask(positions == "QB", multiplier * 1.55)

    if settings.get("te_premium"):
        multiplier = multiplier.mask(positions == "TE", multiplier * 1.18)

    rb_delta = int(settings.get("rb_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["rb_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["rb_count"]
    wr_delta = int(settings.get("wr_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["wr_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["wr_count"]
    te_delta = int(settings.get("te_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["te_count"]) - DEFAULT_LEAGUE_VALUE_SETTINGS["te_count"]
    multiplier = multiplier.mask(positions == "RB", multiplier * (1 + max(-2, min(3, rb_delta)) * 0.035))
    multiplier = multiplier.mask(positions == "WR", multiplier * (1 + max(-3, min(3, wr_delta)) * 0.030))
    multiplier = multiplier.mask(positions == "TE", multiplier * (1 + max(-1, min(2, te_delta)) * 0.050))

    starter_count = int(settings.get("starter_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["starter_count"])
    flex_count = int(settings.get("flex_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["flex_count"])
    league_size = int(settings.get("league_size") or DEFAULT_LEAGUE_VALUE_SETTINGS["league_size"])
    starter_pressure = max(-0.18, min(0.35, ((starter_count * league_size) - 108) / 108))
    lineup_boost = 1 + starter_pressure * 0.18
    multiplier = multiplier.mask(positions.isin(["QB", "RB", "WR", "TE"]), multiplier * lineup_boost)

    flex_delta = max(-2, min(4, flex_count - DEFAULT_LEAGUE_VALUE_SETTINGS["flex_count"]))
    flex_adjustment = 1 + flex_delta * 0.018
    multiplier = multiplier.mask(positions.isin(["RB", "WR", "TE"]), multiplier * flex_adjustment)

    if league_size > 12 and qb_format == "1QB":
        multiplier = multiplier.mask(positions == "QB", multiplier * (1 + min(league_size - 12, 8) * 0.012))

    reserve_depth = (
        int(settings.get("bench_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["bench_count"])
        + int(settings.get("taxi_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["taxi_count"])
        + int(settings.get("ir_count") or DEFAULT_LEAGUE_VALUE_SETTINGS["ir_count"])
    )
    if reserve_depth > 0:
        reserve_delta = max(-6, min(12, reserve_depth - 8))
        youth_boost = 1 + (reserve_delta * 0.010)
        taxi_delta = max(0, min(6, int(settings.get("taxi_count") or 0)))
        taxi_boost = 1 + (taxi_delta * 0.020)
        young_skill = positions.isin(["QB", "RB", "WR", "TE"]) & ages.le(25)
        stash_core = positions.isin(["QB", "RB", "WR", "TE"]) & ages.le(23)
        multiplier = multiplier.mask(young_skill, multiplier * youth_boost)
        if taxi_delta > 0:
            multiplier = multiplier.mask(stash_core, multiplier * taxi_boost)

    return multiplier.clip(lower=0.35, upper=2.2)


def apply_valuation_lens(
    df: pd.DataFrame,
    valuation_lens: str,
    league_settings: dict | None = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    df = df.copy()
    dynasty_scores = (
        pd.to_numeric(df["dynasty_score"], errors="coerce").fillna(0)
        if "dynasty_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    value_scores = (
        pd.to_numeric(df["value_score"], errors="coerce").fillna(0)
        if "value_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    ages = (
        pd.to_numeric(df["age"], errors="coerce")
        if "age" in df.columns
        else pd.Series(float("nan"), index=df.index, dtype="float64")
    )
    positions = (
        df["position"].fillna("").astype(str).str.upper()
        if "position" in df.columns
        else pd.Series("", index=df.index, dtype="object")
    )
    years_exp = (
        pd.to_numeric(df["years_exp"], errors="coerce")
        if "years_exp" in df.columns
        else pd.Series(float("nan"), index=df.index, dtype="float64")
    )
    market_scores = (
        pd.to_numeric(df["market_score"], errors="coerce").fillna(0)
        if "market_score" in df.columns
        else value_scores
    )
    role_scores = (
        pd.to_numeric(df["role_score"], errors="coerce").fillna(0)
        if "role_score" in df.columns
        else value_scores
    )
    opportunity_scores = (
        pd.to_numeric(df["opportunity_score"], errors="coerce").fillna(0)
        if "opportunity_score" in df.columns
        else role_scores
    )
    scarcity_scores = (
        pd.to_numeric(df["scarcity_score"], errors="coerce").fillna(0)
        if "scarcity_score" in df.columns
        else pd.Series(0, index=df.index, dtype="float64")
    )
    risk_multiplier = (
        pd.to_numeric(df["risk_multiplier"], errors="coerce").fillna(1.0)
        if "risk_multiplier" in df.columns
        else pd.Series(1.0, index=df.index, dtype="float64")
    )
    current_risk_multiplier = df.apply(
        lambda row: current_availability_multiplier(
            row.get("status"),
            row.get("team"),
            row.get("search_rank"),
            row.get("injury_status"),
        ),
        axis=1,
    )

    current_scores = (
        market_scores * 0.64
        + role_scores * 0.11
        + opportunity_scores * 0.10
        + scarcity_scores * 0.10
        + value_scores * 0.05
    ) * pd.to_numeric(current_risk_multiplier, errors="coerce").fillna(risk_multiplier)
    df["value_score"] = current_scores.clip(lower=0).round().astype(int)
    value_scores = pd.to_numeric(df["value_score"], errors="coerce").fillna(0)

    if (league_settings or {}).get("league_format") == "Redraft":
        df["dynasty_score"] = (
            (dynasty_scores * 0.40) + (value_scores * 0.60)
        ).clip(lower=0).round().astype(int)
        dynasty_scores = pd.to_numeric(df["dynasty_score"], errors="coerce").fillna(0)

    rebuild_base = (dynasty_scores * 0.82) + (value_scores * 0.18)
    rebuild_multiplier = pd.Series(1.0, index=df.index, dtype="float64")
    rebuild_multiplier = rebuild_multiplier.mask(ages.le(22), 1.18)
    rebuild_multiplier = rebuild_multiplier.mask(ages.gt(22) & ages.le(24), 1.10)
    rebuild_multiplier = rebuild_multiplier.mask(ages.gt(24) & ages.le(26), 1.04)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "RB") & ages.ge(28), 0.72)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "WR") & ages.ge(30), 0.82)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "TE") & ages.ge(31), 0.86)
    rebuild_multiplier = rebuild_multiplier.mask((positions == "QB") & ages.ge(34), 0.90)

    rookie_bonus = pd.Series(0.0, index=df.index, dtype="float64")
    rookie_bonus = rookie_bonus.mask(years_exp.le(1) & dynasty_scores.ge(1800), 180.0)

    df["rebuild_score"] = (
        (rebuild_base * rebuild_multiplier) + rookie_bonus
    ).clip(lower=0).round().astype(int)

    settings_multiplier = _league_settings_multiplier(df, league_settings)
    for column in ["dynasty_score", "value_score", "rebuild_score"]:
        if column in df.columns:
            df[column] = (
                pd.to_numeric(df[column], errors="coerce").fillna(0)
                * settings_multiplier
            ).clip(lower=0).round().astype(int)
    df = assign_player_tiers(
        df,
        primary_score_field=valuation_score_field(valuation_lens),
    )
    return format_score_columns(df)


def score_asset_value(asset) -> int:
    try:
        return int(asset.get("score", asset.get("value_score", 0)) or 0)
    except Exception:
        return 0


def tidy_news_reason(reason: str) -> str:
    key = _safe_text(reason).strip().lower()
    if not key:
        return ""
    if key in NEWS_REASON_LABELS:
        return NEWS_REASON_LABELS[key]
    parts = [part.strip() for part in key.split(",") if part.strip()]
    if parts:
        return " + ".join(NEWS_REASON_LABELS.get(part, tidy_label(part)) for part in parts)
    return tidy_label(key)


def render_news_card(item: dict, idx: int):
    title = escape(_safe_text(item.get("title"), "Player update"))
    link = _safe_text(item.get("link")).strip()
    source_name = _safe_text(item.get("source")).strip()
    age_label = relative_news_time(item)
    matched_player = _safe_text(item.get("matched_player")).strip()
    reason = _safe_text(item.get("relevance_reason")).strip().lower()
    summary = escape(build_quick_news_summary(item))

    badge_parts = []
    pretty_reason = tidy_news_reason(reason)
    if pretty_reason:
        badge_class = "news-badge news-badge-priority"
        if reason == "player mention":
            badge_class = "news-badge"
        elif "trade" in reason or "drama" in reason:
            badge_class = "news-badge news-badge-warning"
        badge_parts.append(f"<span class='{badge_class}'>{escape(pretty_reason)}</span>")
    if age_label:
        badge_parts.append(f"<span class='news-badge'>{escape(age_label)}</span>")
    if source_name:
        badge_parts.append(f"<span class='news-badge'>{escape(source_name)}</span>")
    if matched_player:
        badge_parts.append(f"<span class='news-badge'>{escape(matched_player)}</span>")

    title_html = (
        f"<a class='news-card-title' href='{escape(link, quote=True)}' target='_blank' rel='noopener noreferrer'>{title}</a>"
        if link
        else f"<div class='news-card-title'>{title}</div>"
    )
    badges_html = "".join(badge_parts)

    html = f"""
    <div class="news-card" id="news-card-{idx}">
        <div class="news-card-top">
            <div>{title_html}</div>
            <div class="news-badges">{badges_html}</div>
        </div>
        <div class="news-summary">{summary}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def player_display_name(row) -> str:
    name = _clean_player_name_for_display(
        _safe_text(row.get("name"), _safe_text(row.get("label"), "Player"))
    )
    return player_profile_ui.player_display_name(
        {"name": name},
        is_injury_status=lambda _: is_injury_status(row),
        injury_marker=INJURY_EMOJI,
    )


def _clean_player_name_for_display(name: str) -> str:
    text = _safe_text(name).strip()
    if not text:
        return "Player"

    while True:
        original = text
        stripped = text.lstrip()

        for marker in ("[INJ]", "INJ", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¹", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â©ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¹", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¤ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¸ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¹ÃƒÆ’Ã¢â‚¬Â¦ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ"):
            if stripped.startswith(marker):
                remainder = stripped[len(marker):].lstrip(" :-|")
                if remainder:
                    text = remainder
                    break
        else:
            token, sep, rest = stripped.partition(" ")
            if (
                token
                and len(token) <= 8
                and any(ch in token for ch in ("ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¸", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢", "ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢"))
                and not any(ch.isascii() and ch.isalnum() for ch in token)
                and rest
            ):
                text = rest.lstrip(" :-|")

        if text == original:
            break

    return text or "Player"


def add_injury_markers(df: pd.DataFrame, source_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if df.empty or "name" not in df.columns:
        return df
    df = df.copy()
    df["name"] = df["name"].apply(_clean_player_name_for_display)
    return df


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_headshot_bytes(player_id: str):
    img = fetch_player_headshot_bytes(str(player_id))
    return img.getvalue() if img else None


@st.cache_data(ttl=24 * 60 * 60, show_spinner=False)
def cached_headshot_data_url(player_id: str) -> str:
    img_bytes = cached_headshot_bytes(str(player_id))
    if not img_bytes:
        return ""
    encoded = base64.b64encode(img_bytes).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def avatar_html(image_url: str, fallback_text: str, css_class: str = "player-avatar") -> str:
    return player_profile_ui.avatar_html(image_url, fallback_text, css_class)


@runtime_trace.traced("player_data_loading", phase="loading_data")
def ensure_players(*, allow_network_refresh: bool = False):
    """Load the public player frame for startup/routes.

    Prefer the persisted SQLite baseline so a stale ``sleeper_players.json`` TTL
    cannot force a multi-second Sleeper/FantasyCalc rebuild onto the global
    loading screen. Network refresh is deferred unless explicitly allowed or the
    DB is missing.
    """

    with performance.time_block("public_player_data_load", category="data"):
        if not os.path.exists("data"):
            os.makedirs("data")
        return startup_cold_path.ensure_players_for_startup(
            db_path=DB_PATH,
            load_players_fn=load_players,
            build_players_table_fn=build_players_table,
            session_state=st.session_state,
            allow_network_refresh=allow_network_refresh,
        )


@st.cache_data(ttl=15 * 60, show_spinner=False)
def cached_sleeper_player_directory() -> dict[str, dict]:
    players = performance.timed_call("sleeper_player_directory", get_players, refresh=False, category="sleeper")
    return players if isinstance(players, dict) else {}


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def _format_score(value) -> str:
    try:
        return f"{int(round(float(value))):,}"
    except Exception:
        return "0"


NO_TEAM_MARKERS = {
    "",
    "FA",
    "FREE AGENT",
    "FREEAGENT",
    "FREE_AGENT",
    "NO TEAM",
    "NONE",
    "N/A",
    "NA",
    "NULL",
    "UNKNOWN",
    "UNASSIGNED",
}
NO_TEAM_STATUS_MARKERS = {
    "free agent",
    "inactive",
    "retired",
    "unsigned",
}
FALLBACK_ROSTER_POSITIONS = {"QB", "RB", "WR", "TE", "K"}


def _normalized_team_marker(value) -> str:
    text = _safe_text(value).strip().upper()
    if not text:
        return ""
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text).strip()


def _coerce_bool_flag(value) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_text(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return bool(value)


def _player_no_team_diagnostics(player) -> dict:
    item = player.to_dict() if hasattr(player, "to_dict") else dict(player or {})
    team = _normalized_team_marker(item.get("team"))
    nfl_team = _normalized_team_marker(item.get("nfl_team"))
    recent_team = _normalized_team_marker(item.get("recent_team"))
    team_abbr = _normalized_team_marker(item.get("team_abbr"))
    team_tokens = [token for token in [team, nfl_team, recent_team, team_abbr] if token]
    has_real_team = any(token not in NO_TEAM_MARKERS for token in team_tokens)
    has_fa_team = any(token in NO_TEAM_MARKERS - {""} for token in team_tokens)
    status = re.sub(r"\s+", " ", _safe_text(item.get("status")).strip().lower().replace("_", " "))
    active_flag = _coerce_bool_flag(item.get("active"))
    depth_chart_position = _safe_text(item.get("depth_chart_position")).strip()
    blank_team = not team and not nfl_team and not recent_team and not team_abbr
    suspicious_team_metadata = not has_real_team and not blank_team and not has_fa_team
    no_nfl_team_flag = not has_real_team and (
        blank_team
        or has_fa_team
        or status in NO_TEAM_STATUS_MARKERS
        or not active_flag
    )
    reasons: list[str] = []
    if blank_team:
        reasons.append("blank team")
    if has_fa_team:
        reasons.append("FA team marker")
    if status in NO_TEAM_STATUS_MARKERS:
        reasons.append(f"status {status}")
    if not active_flag:
        reasons.append("active flag false")
    if suspicious_team_metadata:
        reasons.append("suspicious team metadata")
    if not depth_chart_position:
        reasons.append("no depth chart slot")
    seen: set[str] = set()
    deduped_reasons = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        deduped_reasons.append(reason)
    return {
        "blank_team_flag": blank_team,
        "fa_team_flag": has_fa_team,
        "active_flag": active_flag,
        "has_real_team": has_real_team,
        "suspicious_team_metadata_flag": suspicious_team_metadata,
        "no_nfl_team_flag": no_nfl_team_flag,
        "depth_chart_position": depth_chart_position,
        "reasons": deduped_reasons,
        "reason_text": ", ".join(deduped_reasons),
    }


def _fallback_player_tier_from_value(value_score: float) -> str:
    if value_score >= 7000:
        return "Star"
    if value_score >= 3500:
        return "Contributor"
    if value_score >= 1200:
        return "Depth"
    return "Developmental"


def _build_missing_rostered_player_row(player_id: str, raw_player: dict | None) -> dict | None:
    raw = dict(raw_player or {})
    position = _safe_text(raw.get("position")).upper()
    if position == "PK":
        position = "K"
    if position not in FALLBACK_ROSTER_POSITIONS:
        return None
    search_rank = _safe_positive_int(raw.get("search_rank"), 0)
    age = _safe_float(raw.get("age"), 0.0)
    years_exp = _safe_positive_int(raw.get("years_exp"), 0)
    base_value = rankings_module.rank_to_value(search_rank)
    decay = 0.18
    if position == "QB" and years_exp <= 2 and age and age <= 25 and search_rank and search_rank <= 220:
        decay = 0.55
    elif years_exp <= 1 and age and age <= 23 and search_rank and search_rank <= 120:
        decay = 0.55
    elif position in {"RB", "WR", "TE"} and years_exp <= 2 and age and age <= 24 and search_rank and search_rank <= 160:
        decay = 0.36
    elif search_rank and search_rank <= 80:
        decay = 0.42
    elif search_rank and search_rank <= 140:
        decay = 0.32
    fallback_value = int(round(base_value * decay)) if base_value > 0 else 0
    fallback_tier = _fallback_player_tier_from_value(fallback_value)
    diagnostics = _player_no_team_diagnostics(raw)
    raw_team = (
        _safe_text(raw.get("team"))
        or _safe_text(raw.get("nfl_team"))
        or _safe_text(raw.get("recent_team"))
        or _safe_text(raw.get("team_abbr"))
    )
    status_text = _safe_text(raw.get("status"), "Inactive")
    return {
        "player_id": _safe_text(player_id).strip(),
        "name": _safe_text(raw.get("full_name") or raw.get("name"), "Player"),
        "position": position,
        "team": raw_team,
        "team_abbr": _safe_text(raw.get("team_abbr")),
        "nfl_team": _safe_text(raw.get("nfl_team")),
        "recent_team": _safe_text(raw.get("recent_team")),
        "age": _safe_float(raw.get("age"), None),
        "value": fallback_value,
        "search_rank": search_rank or None,
        "active": _coerce_bool_flag(raw.get("active")),
        "status": status_text,
        "years_exp": years_exp,
        "news_updated": raw.get("news_updated"),
        "depth_chart_position": _safe_text(raw.get("depth_chart_position")),
        "depth_chart_order": raw.get("depth_chart_order"),
        "hashtag": _safe_text(raw.get("hashtag")),
        "injury_status": _safe_text(raw.get("injury_status") or raw.get("injury_notes")),
        "injury_level": "healthy",
        "injury_risk_score": 0,
        "injury_multiplier": 1.0,
        "age_penalty": 0,
        "score": fallback_value,
        "news_factor": 0,
        "fantasycalc_value": fallback_value,
        "market_score": fallback_value,
        "age_multiplier": 1.0,
        "age_curve_score": 0,
        "scarcity_score": 0,
        "role_score": fallback_value,
        "depth_chart_slot": 0,
        "projected_starter": False,
        "opportunity_label": "No NFL Team",
        "opportunity_score": 0,
        "opportunity_confidence": 0,
        "opportunity_source_flags": ["no_nfl_team"],
        "opportunity_explanation": "No current NFL team on Sleeper. Treat this as stash-only dynasty value until a real landing spot appears.",
        "snap_share": None,
        "rush_share": None,
        "target_share": None,
        "route_participation": None,
        "opportunity_share": None,
        "workload_trend": "No Team",
        "risk_multiplier": 1.0,
        "valuation_blend": fallback_value,
        "dynasty_score": fallback_value,
        "value_score": fallback_value,
        "role": "Bench",
        "player_tier": fallback_tier,
        "no_nfl_team_flag": diagnostics["no_nfl_team_flag"],
        "no_team_reason_text": diagnostics["reason_text"],
        "source_missing_roster_player_flag": True,
    }


def _format_rank(value) -> str:
    try:
        rank = int(round(float(value)))
    except Exception:
        return "N/A"
    return f"#{rank}" if rank > 0 else "N/A"


def _normalize_pick_query_text(text: str) -> str:
    normalized = _safe_text(text).strip().lower()
    replacements = {
        "first": "1",
        "1st": "1",
        "second": "2",
        "2nd": "2",
        "third": "3",
        "3rd": "3",
        "fourth": "4",
        "4th": "4",
        "round": "r",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return " ".join(normalized.split())


def _parse_pick_query(query: str) -> dict:
    raw = _safe_text(query).strip().lower()
    normalized = _normalize_pick_query_text(raw)
    tokens = normalized.split()
    year = None
    round_num = None
    team_tokens: list[str] = []

    for token in tokens:
        if token.isdigit():
            numeric = _safe_positive_int(token, 0)
            if len(token) == 4 and 2020 <= numeric <= 2035 and year is None:
                year = numeric
            elif 1 <= numeric <= 8 and round_num is None:
                round_num = numeric
            else:
                team_tokens.append(token)
        elif token.startswith("r") and token[1:].isdigit():
            parsed_round = _safe_positive_int(token[1:], 0)
            if 1 <= parsed_round <= 8 and round_num is None:
                round_num = parsed_round
            else:
                team_tokens.append(token)
        elif token != "pick":
            team_tokens.append(token)

    pick_words = {"1st", "2nd", "3rd", "4th", "first", "second", "third", "fourth", "pick", "round", "r1", "r2", "r3", "r4"}
    is_pick_query = bool(
        year is not None
        or round_num is not None
        or any(word in raw for word in pick_words)
    )
    return {
        "raw": raw,
        "normalized": normalized,
        "tokens": tokens,
        "year": year,
        "round": round_num,
        "team_tokens": team_tokens,
        "is_pick_query": is_pick_query,
    }


def _query_requires_pick_focus(query: str) -> bool:
    parsed = _parse_pick_query(query)
    return bool(
        parsed.get("is_pick_query")
        and (parsed.get("year") is not None or parsed.get("round") is not None)
    )


def _pick_matches_query(pick: dict, query: str) -> bool:
    if not query:
        return True
    round_num = _safe_positive_int(pick.get("round"), 0)
    season = _safe_positive_int(pick.get("season"), 0)
    combined = " ".join(
        part
        for part in [
            _safe_text(pick.get("label")),
            _safe_text(pick.get("owner_team_name")),
            _safe_text(pick.get("original_team_name")),
            str(season) if season else "",
            f"r{round_num}" if round_num else "",
            str(round_num) if round_num else "",
        ]
        if part
    )
    normalized_query = _normalize_pick_query_text(query)
    normalized_haystack = _normalize_pick_query_text(combined)
    return all(token in normalized_haystack for token in normalized_query.split())


def _pick_match_score(pick: dict, query: str) -> int:
    parsed = _parse_pick_query(query)
    if not parsed["normalized"]:
        return 0
    if not _pick_matches_query(pick, query):
        return -1

    round_num = _safe_positive_int(pick.get("round"), 0)
    season = _safe_positive_int(pick.get("season"), 0)
    owner_team = _normalize_pick_query_text(_safe_text(pick.get("owner_team_name")))
    original_team = _normalize_pick_query_text(_safe_text(pick.get("original_team_name")))
    label = _normalize_pick_query_text(_safe_text(pick.get("label")))
    combined = " ".join(part for part in [label, owner_team, original_team] if part)

    score = 0
    if parsed["is_pick_query"]:
        score += 30
    if parsed["year"] and season == parsed["year"]:
        score += 50
    if parsed["round"] and round_num == parsed["round"]:
        score += 55
    if parsed["year"] and parsed["round"] and season == parsed["year"] and round_num == parsed["round"]:
        score += 40
    if label == parsed["normalized"]:
        score += 70
    elif parsed["normalized"] in label:
        score += 28

    if parsed["team_tokens"]:
        owner_match = all(token in owner_team for token in parsed["team_tokens"])
        original_match = all(token in original_team for token in parsed["team_tokens"])
        partial_hits = sum(token in combined for token in parsed["team_tokens"])
        if owner_match:
            score += 32
        elif original_match:
            score += 24
        score += partial_hits * 6

    token_hits = sum(token in combined for token in parsed["tokens"])
    score += token_hits * 5
    score += max(0, int(round(_safe_float(pick.get("score"), 0) / 1000)))
    return score


def _format_age(value) -> str:
    try:
        age = float(value)
    except Exception:
        return ""
    if age <= 0:
        return ""
    return str(int(age)) if age.is_integer() else f"{age:.1f}"


def valid_strategy_override(value: str) -> str:
    choice = _safe_text(value, "Auto")
    return choice if choice in STRATEGY_SELECTOR_OPTIONS else "Auto"


def resolve_team_strategy(metrics: dict | None, profile: dict | None) -> tuple[str, str, str]:
    auto_strategy = normalize_team_strategy((metrics or {}).get("strategy") or (metrics or {}).get("mode"))
    override = valid_strategy_override((profile or {}).get("strategy_override", "Auto"))
    active_strategy = auto_strategy if override == "Auto" else normalize_team_strategy(override, default=auto_strategy)
    return auto_strategy, active_strategy, override


def apply_strategy_to_metrics(metrics: dict | None, strategy: str) -> dict | None:
    if not metrics:
        return metrics
    strategy_key = normalize_team_strategy(strategy)
    updated = dict(metrics)
    updated["strategy"] = strategy_key
    updated["strategy_label"] = team_strategy_label(strategy_key)
    updated["mode"] = team_strategy_mode(strategy_key)
    return updated


def strategy_adjusted_pick_score_multiplier(base_multiplier: float, strategy: str) -> float:
    strategy_key = normalize_team_strategy(strategy)
    strategy_multipliers = {
        "contender": 0.88,
        "fringe_contender": 0.95,
        "retool": 1.02,
        "rebuild": 1.16,
        "tank": 1.25,
    }
    return float(base_multiplier) * strategy_multipliers.get(strategy_key, 1.0)


def apply_strategy_age_curve(
    df: pd.DataFrame,
    strategy: str,
    score_field: str,
) -> pd.DataFrame:
    if df.empty:
        return df

    strategy_key = normalize_team_strategy(strategy)
    df = df.copy()
    ages = pd.to_numeric(df.get("age", pd.Series(float("nan"), index=df.index)), errors="coerce")
    positions = (
        df.get("position", pd.Series("", index=df.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    multiplier = pd.Series(1.0, index=df.index, dtype="float64")

    if strategy_key == "contender":
        multiplier = multiplier.mask(ages.ge(25) & ages.le(30), 1.04)
        multiplier = multiplier.mask(ages.le(22), 0.98)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(29), 0.94)
    elif strategy_key == "fringe_contender":
        multiplier = multiplier.mask(ages.ge(24) & ages.le(29), 1.025)
        multiplier = multiplier.mask(ages.le(24), 1.01)
        multiplier = multiplier.mask((positions.isin(["RB", "WR", "TE"])) & ages.ge(31), 0.96)
    elif strategy_key == "retool":
        multiplier = multiplier.mask(ages.le(25), 1.04)
        multiplier = multiplier.mask(ages.ge(26) & ages.le(29), 1.01)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(28), 0.91)
        multiplier = multiplier.mask((positions.isin(["WR", "TE"])) & ages.ge(31), 0.94)
    elif strategy_key == "rebuild":
        multiplier = multiplier.mask(ages.le(23), 1.10)
        multiplier = multiplier.mask(ages.gt(23) & ages.le(25), 1.06)
        multiplier = multiplier.mask(ages.gt(25) & ages.le(26), 1.02)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(28), 0.82)
        multiplier = multiplier.mask((positions == "WR") & ages.ge(30), 0.86)
        multiplier = multiplier.mask((positions == "TE") & ages.ge(31), 0.88)
        multiplier = multiplier.mask((positions == "QB") & ages.ge(34), 0.92)
    elif strategy_key == "tank":
        multiplier = multiplier.mask(ages.le(23), 1.15)
        multiplier = multiplier.mask(ages.gt(23) & ages.le(25), 1.09)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(27), 0.75)
        multiplier = multiplier.mask((positions == "WR") & ages.ge(30), 0.80)
        multiplier = multiplier.mask((positions == "TE") & ages.ge(31), 0.84)
        multiplier = multiplier.mask((positions == "QB") & ages.ge(34), 0.88)

    score_columns = [
        col
        for col in ["dynasty_score", "value_score", "rebuild_score", score_field]
        if col in df.columns
    ]
    for column in list(dict.fromkeys(score_columns)):
        df[column] = (
            pd.to_numeric(df[column], errors="coerce").fillna(0) * multiplier
        ).clip(lower=0).round().astype(int)

    df = assign_player_tiers(
        df,
        primary_score_field=score_field,
    )
    return format_score_columns(df)


def strategy_trade_result_note(strategy: str) -> str:
    strategy_key = normalize_team_strategy(strategy)
    if strategy_key == "contender":
        return "Contender lens: prioritizes current points, elite starters, and useful consolidation while discounting future picks slightly."
    if strategy_key == "fringe_contender":
        return "Fringe contender lens: favors lineup upgrades, but keeps enough future flexibility to avoid getting trapped in the middle."
    if strategy_key == "rebuild":
        return "Rebuild lens: prioritizes youth and draft capital, and discounts aging veterans unless the value gap is strong."
    if strategy_key == "tank":
        return "Tank/Rebuild lens: heavily prioritizes picks, young players, and future value over short-term production."
    return "Retool lens: balances current production with future value, so picks and young starters keep meaningful weight."


def trade_value_verdict(score: int) -> str:
    if score >= 0:
        return "Favorable"
    if score >= -500:
        return "Fair"
    if score >= -1500:
        return "Slight Overpay"
    return "Major Overpay"


def _lineup_depth_thresholds(league_settings: dict | None = None) -> dict[str, int]:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    qb_count = max(1, int(settings.get("qb_count") or 1))
    superflex_count = max(0, int(settings.get("superflex_count") or 0))
    flex_count = max(0, int(settings.get("flex_count") or 0))
    return {
        "QB": qb_count + (1 if superflex_count > 0 else 0),
        "RB": max(2, int(settings.get("rb_count") or 2) + (1 if flex_count > 0 else 0)),
        "WR": max(3, int(settings.get("wr_count") or 3) + (1 if flex_count > 0 else 0)),
        "TE": max(1, int(settings.get("te_count") or 1)),
    }


def _team_position_counts(df_team: pd.DataFrame) -> dict[str, int]:
    if df_team is None or df_team.empty or "position" not in df_team.columns:
        return {pos: 0 for pos in ["QB", "RB", "WR", "TE"]}
    counts = (
        df_team["position"]
        .fillna("")
        .astype(str)
        .str.upper()
        .value_counts()
        .to_dict()
    )
    return {pos: int(counts.get(pos, 0)) for pos in ["QB", "RB", "WR", "TE"]}


def _starter_lineup_snapshot(
    team_df: pd.DataFrame,
    score_field: str,
    lineup_settings: dict | None = None,
) -> dict | None:
    if team_df is None or team_df.empty:
        return {
            "lineup_df": pd.DataFrame(),
            "starter_score": 0.0,
            "starter_count": 0,
            "position_scores": {pos: 0.0 for pos in ["QB", "RB", "WR", "TE", "K"]},
        }

    if score_field in team_df.columns:
        resolved_score_field = score_field
    elif "value_score" in team_df.columns:
        resolved_score_field = "value_score"
    elif "dynasty_score" in team_df.columns:
        resolved_score_field = "dynasty_score"
    else:
        return None

    lineup_df = suggest_optimal_lineup(team_df.copy(), lineup_settings)
    if lineup_df.empty or "suggested_starter" not in lineup_df.columns:
        return None

    starters = lineup_df[lineup_df["suggested_starter"].fillna(False)].copy()
    starter_scores = pd.to_numeric(starters[resolved_score_field], errors="coerce").fillna(0)
    position_scores: dict[str, float] = {}
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        pos_scores = starter_scores[starters["position"].astype(str).str.upper() == pos]
        position_scores[pos] = float(pos_scores.sum()) if not pos_scores.empty else 0.0

    return {
        "lineup_df": lineup_df,
        "starter_score": float(starter_scores.sum()),
        "starter_count": int(len(starters)),
        "position_scores": position_scores,
        "score_field": resolved_score_field,
    }


def _simulate_post_trade_roster(
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    send_assets: list[dict],
    receive_assets: list[dict],
) -> pd.DataFrame:
    if my_team_df is None:
        return pd.DataFrame()

    current = normalize_player_ids(my_team_df.copy())
    if "player_id" not in current.columns:
        return current
    current["player_id"] = current["player_id"].astype(str)

    send_ids = {
        str(asset.get("player_id") or "")
        for asset in send_assets or []
        if asset.get("asset_type") == "player" and asset.get("player_id")
    }
    receive_ids = {
        str(asset.get("player_id") or "")
        for asset in receive_assets or []
        if asset.get("asset_type") == "player" and asset.get("player_id")
    }

    post_df = current[~current["player_id"].isin(send_ids)].copy()
    if not receive_ids:
        return post_df.reset_index(drop=True)

    player_pool = normalize_player_ids(all_players_df.copy()) if all_players_df is not None else pd.DataFrame()
    if not player_pool.empty and "player_id" in player_pool.columns:
        player_pool["player_id"] = player_pool["player_id"].astype(str)
        receive_df = player_pool[player_pool["player_id"].isin(receive_ids)].copy()
    else:
        receive_df = pd.DataFrame()

    if receive_df.empty:
        fallback_rows = []
        template_columns = list(post_df.columns)
        for asset in receive_assets or []:
            if asset.get("asset_type") != "player":
                continue
            row = {column: None for column in template_columns}
            row.update(
                {
                    "player_id": str(asset.get("player_id") or ""),
                    "name": _safe_text(asset.get("name") or asset.get("label"), "Player"),
                    "position": _safe_text(asset.get("position")).upper(),
                    "team": _safe_text(asset.get("team")),
                    "status": _safe_text(asset.get("status")),
                    "injury_status": _safe_text(asset.get("injury_status")),
                    "age": asset.get("age"),
                    "value_score": _safe_float(asset.get("value_score"), 0),
                    "dynasty_score": _safe_float(asset.get("score"), 0),
                    "rebuild_score": _safe_float(asset.get("score"), 0),
                    "score": _safe_float(asset.get("score"), 0),
                }
            )
            fallback_rows.append(row)
        receive_df = pd.DataFrame(fallback_rows)

    if receive_df.empty:
        return post_df.reset_index(drop=True)

    post_df = pd.concat([post_df, receive_df], ignore_index=True, sort=False)
    post_df["player_id"] = post_df["player_id"].astype(str)
    post_df = post_df.drop_duplicates(subset=["player_id"], keep="last")
    return post_df.reset_index(drop=True)


def evaluate_trade_analyzer_fit(
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    send_assets: list[dict],
    receive_assets: list[dict],
    metrics: dict | None,
    strategy: str,
    lineup_settings: dict | None,
    score_field: str,
) -> dict | None:
    if my_team_df is None or my_team_df.empty:
        return None
    if not send_assets and not receive_assets:
        return None

    score_column = (
        "value_score"
        if "value_score" in my_team_df.columns
        else score_field
        if score_field in my_team_df.columns
        else "dynasty_score"
    )
    if score_column not in my_team_df.columns:
        return None

    current_snapshot = _starter_lineup_snapshot(my_team_df, score_column, lineup_settings)
    post_team_df = _simulate_post_trade_roster(my_team_df, all_players_df, send_assets, receive_assets)
    post_snapshot = _starter_lineup_snapshot(post_team_df, score_column, lineup_settings)
    if not current_snapshot or not post_snapshot:
        return None

    value_delta = int(sum(score_asset_value(asset) for asset in receive_assets) - sum(score_asset_value(asset) for asset in send_assets))
    lineup_delta = int(round(float(post_snapshot["starter_score"]) - float(current_snapshot["starter_score"])))

    strategy_key = normalize_team_strategy(strategy)
    current_needs = get_needed_positions(
        my_team_df,
        metrics,
        lineup_settings,
        include_fallback=False,
    )
    need_set = {str(pos).upper() for pos in current_needs}
    strength_set = {str(pos).upper() for pos in (metrics or {}).get("strengths", []) or []}

    send_positions = {
        str(asset.get("position") or "").upper()
        for asset in send_assets or []
        if asset.get("asset_type") == "player"
    }
    receive_positions = {
        str(asset.get("position") or "").upper()
        for asset in receive_assets or []
        if asset.get("asset_type") == "player"
    }
    filled_needs = sorted(pos for pos in receive_positions & need_set if pos)
    exposed_needs = sorted(pos for pos in (send_positions & need_set) - receive_positions if pos)
    surplus_moves = sorted(pos for pos in send_positions & strength_set if pos)

    current_counts = _team_position_counts(my_team_df)
    post_counts = _team_position_counts(post_team_df)
    depth_thresholds = _lineup_depth_thresholds(lineup_settings)
    depth_losses = [
        pos
        for pos in ["QB", "RB", "WR", "TE"]
        if post_counts.get(pos, 0) < current_counts.get(pos, 0)
        and post_counts.get(pos, 0) < depth_thresholds.get(pos, 0)
    ]

    position_deltas = {}
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        before = float(current_snapshot["position_scores"].get(pos, 0.0))
        after = float(post_snapshot["position_scores"].get(pos, 0.0))
        position_deltas[pos] = int(round(after - before))
    improved_positions = [
        pos
        for pos, delta in sorted(position_deltas.items(), key=lambda item: item[1], reverse=True)
        if delta >= 120
    ]
    weakened_positions = [
        pos
        for pos, delta in sorted(position_deltas.items(), key=lambda item: item[1])
        if delta <= -120
    ]

    current_avg_age = pd.to_numeric(my_team_df.get("age", pd.Series(dtype="float64")), errors="coerce").dropna()
    post_avg_age = pd.to_numeric(post_team_df.get("age", pd.Series(dtype="float64")), errors="coerce").dropna()
    current_age = float(current_avg_age.mean()) if not current_avg_age.empty else None
    new_age = float(post_avg_age.mean()) if not post_avg_age.empty else None
    age_delta = (new_age - current_age) if current_age is not None and new_age is not None else None

    current_lineup_df = current_snapshot.get("lineup_df", pd.DataFrame())
    post_lineup_df = post_snapshot.get("lineup_df", pd.DataFrame())
    current_starters = (
        current_lineup_df[current_lineup_df["suggested_starter"].fillna(False)].copy()
        if not current_lineup_df.empty and "suggested_starter" in current_lineup_df.columns
        else pd.DataFrame()
    )
    post_starters = (
        post_lineup_df[post_lineup_df["suggested_starter"].fillna(False)].copy()
        if not post_lineup_df.empty and "suggested_starter" in post_lineup_df.columns
        else pd.DataFrame()
    )
    current_health_ctx = roster_injury_context(my_team_df, current_lineup_df)
    post_health_ctx = roster_injury_context(post_team_df, post_lineup_df)
    current_injured_starters = int(current_health_ctx.get("injured_starters") or 0)
    post_injured_starters = int(post_health_ctx.get("injured_starters") or 0)
    current_injury_burden = float(current_health_ctx.get("injury_burden") or 0.0)
    post_injury_burden = float(post_health_ctx.get("injury_burden") or 0.0)
    current_health_flag = _safe_text(current_health_ctx.get("health_flag"), "Stable")
    post_health_flag = _safe_text(post_health_ctx.get("health_flag"), "Stable")
    current_injury_positions = (
        {
            str(pos).upper()
            for pos in (current_health_ctx.get("injured_positions") or [])
            if str(pos).upper()
        }
    )
    send_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in send_assets or []
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    receive_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in receive_assets or []
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    receive_injury_levels = [
        injury_level(asset.get("status"), asset.get("injury_status"))
        for asset in receive_assets or []
        if asset.get("asset_type") == "player"
    ]
    incoming_major_injuries = sum(1 for level in receive_injury_levels if level == "major")
    incoming_moderate_injuries = sum(1 for level in receive_injury_levels if level == "moderate")
    injury_reinforcements = sorted(pos for pos in receive_healthy_positions & current_injury_positions if pos)
    injury_exposure = sorted(pos for pos in send_healthy_positions & current_injury_positions if pos)

    send_pick_value = int(sum(score_asset_value(asset) for asset in send_assets if asset.get("asset_type") == "pick"))
    receive_pick_value = int(sum(score_asset_value(asset) for asset in receive_assets if asset.get("asset_type") == "pick"))
    send_pick_count = sum(1 for asset in send_assets if asset.get("asset_type") == "pick")
    receive_pick_count = sum(1 for asset in receive_assets if asset.get("asset_type") == "pick")

    value_component = 2 if value_delta >= 700 else 1 if value_delta >= 150 else 0 if value_delta > -250 else -1 if value_delta > -1000 else -2
    lineup_component = 2 if lineup_delta >= 500 else 1 if lineup_delta >= 120 else 0 if lineup_delta > -120 else -1 if lineup_delta > -500 else -2
    need_component = min(2, len(filled_needs)) - min(2, len(exposed_needs) + len(depth_losses))
    if surplus_moves:
        need_component = min(2, need_component + 1)

    age_component = 0
    if age_delta is not None:
        if strategy_key in {"rebuild", "tank"}:
            if age_delta <= -0.4:
                age_component = 2
            elif age_delta < 0:
                age_component = 1
            elif age_delta >= 0.5:
                age_component = -2
            elif age_delta > 0:
                age_component = -1
        elif strategy_key in {"contender", "fringe_contender"}:
            if lineup_delta >= 120 and age_delta <= 0.6:
                age_component = 1
            elif age_delta >= 0.8 and lineup_delta <= 0:
                age_component = -1
        else:
            if age_delta <= -0.35:
                age_component = 1
            elif age_delta >= 0.75 and lineup_delta <= 0:
                age_component = -1

    draft_component = 0
    if send_pick_count or receive_pick_count:
        pick_delta = receive_pick_value - send_pick_value
        if strategy_key in {"rebuild", "tank"}:
            if pick_delta > 0:
                draft_component = 2
            elif pick_delta < 0:
                draft_component = -2
        elif strategy_key in {"contender", "fringe_contender"}:
            if send_pick_value > 0 and lineup_delta >= 120:
                draft_component = 1
            elif receive_pick_value > send_pick_value and lineup_delta <= 0:
                draft_component = -1
        else:
            if pick_delta > 0:
                draft_component = 1
            elif pick_delta < 0 and lineup_delta <= 0:
                draft_component = -1

    strategy_component = 0
    if strategy_key in {"contender", "fringe_contender"}:
        if lineup_delta >= 120:
            strategy_component += 2
        if filled_needs:
            strategy_component += 1
        if depth_losses or exposed_needs:
            strategy_component -= 2
        if receive_pick_count > send_pick_count and lineup_delta <= 0:
            strategy_component -= 1
    elif strategy_key in {"rebuild", "tank"}:
        if receive_pick_value > send_pick_value:
            strategy_component += 2
        if age_delta is not None and age_delta < 0:
            strategy_component += 1
        if send_pick_value > receive_pick_value:
            strategy_component -= 2
        if lineup_delta <= -500 and receive_pick_value <= send_pick_value:
            strategy_component -= 1
    else:
        if filled_needs:
            strategy_component += 1
        if lineup_delta >= 120:
            strategy_component += 1
        if age_delta is not None and age_delta < 0:
            strategy_component += 1
        if depth_losses:
            strategy_component -= 1

    injury_component = 0
    if post_injured_starters < current_injured_starters:
        injury_component += min(2, current_injured_starters - post_injured_starters)
    elif post_injured_starters > current_injured_starters:
        injury_component -= min(2, post_injured_starters - current_injured_starters)
    if injury_reinforcements:
        injury_component += 1
    if injury_exposure:
        injury_component -= 1
    if strategy_key in {"contender", "fringe_contender"}:
        injury_component -= (incoming_major_injuries * 2) + incoming_moderate_injuries
    elif strategy_key == "retool":
        injury_component -= incoming_major_injuries
    else:
        injury_component -= max(0, incoming_major_injuries - 1)
    injury_burden_delta = post_injury_burden - current_injury_burden

    fit_total = (
        value_component
        + lineup_component
        + need_component
        + age_component
        + draft_component
        + strategy_component
        + injury_component
    )
    if fit_total >= 5:
        roster_fit_verdict = "Strong Fit"
    elif fit_total >= 2:
        roster_fit_verdict = "Helpful Fit"
    elif fit_total >= 0:
        roster_fit_verdict = "Mixed Fit"
    elif fit_total >= -2:
        roster_fit_verdict = "Risky Fit"
    else:
        roster_fit_verdict = "Poor Fit"

    if not send_positions and not receive_positions:
        lineup_summary = "No direct starter-lineup change because only draft capital moves."
    else:
        if lineup_delta >= 120:
            lineup_summary = f"Starter lineup improves by +{_format_score(lineup_delta)}."
        elif lineup_delta <= -120:
            lineup_summary = f"Starter lineup drops by {_format_score(abs(lineup_delta))}."
        else:
            lineup_summary = "Starter lineup stays close to neutral."
        if improved_positions:
            lineup_summary += f" Biggest lift: {' / '.join(improved_positions[:2])}."
        if weakened_positions:
            lineup_summary += f" Weakest hit: {' / '.join(weakened_positions[:2])}."
        if depth_losses:
            lineup_summary += f" Depth gets thinner at {' / '.join(depth_losses[:2])}."
        if current_injured_starters > post_injured_starters:
            lineup_summary += f" Injury pressure eases from {current_injured_starters} to {post_injured_starters} injured starters."
        elif post_injured_starters > current_injured_starters:
            lineup_summary += f" Injury pressure rises to {post_injured_starters} injured starters."
        elif injury_reinforcements:
            lineup_summary += f" Adds healthy cover at {' / '.join(injury_reinforcements[:2])}."

    strategy_parts = []
    if strategy_key in {"contender", "fringe_contender"}:
        strategy_parts.append("Contender-friendly" if strategy_component >= 1 else "Mixed contender fit" if strategy_component >= 0 else "Poor contender fit")
        if filled_needs:
            strategy_parts.append(f"fills {' / '.join(filled_needs[:2])} need")
        if send_pick_value > 0 and lineup_delta >= 120:
            strategy_parts.append("uses future capital to improve now")
        elif receive_pick_value > send_pick_value:
            strategy_parts.append("keeps more future flexibility")
        if injury_reinforcements:
            strategy_parts.append(f"adds healthy cover at {' / '.join(injury_reinforcements[:2])}")
        elif incoming_major_injuries:
            strategy_parts.append("takes on injured production")
    elif strategy_key in {"rebuild", "tank"}:
        strategy_parts.append("Rebuild-friendly" if strategy_component >= 1 else "Mixed rebuild fit" if strategy_component >= 0 else "Poor rebuild fit")
        if receive_pick_value > send_pick_value:
            strategy_parts.append("adds future draft capital")
        if age_delta is not None and age_delta < 0:
            strategy_parts.append("gets the roster younger")
        elif age_delta is not None and age_delta > 0.4:
            strategy_parts.append("pushes the roster older")
        if incoming_major_injuries and receive_pick_value > send_pick_value:
            strategy_parts.append("can absorb a longer injury timeline")
    else:
        strategy_parts.append("Retool-friendly" if strategy_component >= 1 else "Mixed retool fit" if strategy_component >= 0 else "Poor retool fit")
        if filled_needs:
            strategy_parts.append(f"addresses {' / '.join(filled_needs[:2])}")
        if age_delta is not None and age_delta < 0:
            strategy_parts.append("keeps the future outlook healthier")
        if injury_reinforcements:
            strategy_parts.append("stabilizes injury depth")
    strategy_fit_label = strategy_parts[0] if strategy_parts else team_strategy_label(strategy)
    strategy_summary = ". ".join(
        part[:1].upper() + part[1:] if idx == 0 and part else part
        for idx, part in enumerate(strategy_parts)
        if part
    )
    if strategy_summary and not strategy_summary.endswith("."):
        strategy_summary += "."
    if not strategy_summary:
        strategy_summary = strategy_trade_result_note(strategy)

    positives = []
    negatives = []
    if value_delta > 0:
        positives.append("wins on raw value")
    if lineup_delta > 0:
        positives.append("improves the starting lineup")
    if filled_needs:
        positives.append(f"helps at {' / '.join(filled_needs[:2])}")
    if receive_pick_value > send_pick_value:
        positives.append("adds future capital")
    if age_delta is not None and age_delta < 0:
        positives.append("gets a bit younger")
    if injury_reinforcements or post_injured_starters < current_injured_starters:
        positives.append("improves injury cover")

    if value_delta < 0:
        negatives.append("pays a raw-value premium")
    if lineup_delta < 0:
        negatives.append("costs starter strength")
    if exposed_needs:
        negatives.append(f"moves from a weak {' / '.join(exposed_needs[:2])} room")
    if depth_losses:
        negatives.append(f"thins {' / '.join(depth_losses[:2])} depth")
    if send_pick_value > receive_pick_value:
        negatives.append("spends future draft capital")
    if age_delta is not None and age_delta > 0.6:
        negatives.append("ages the roster up")
    if incoming_major_injuries or incoming_moderate_injuries:
        negatives.append("brings back injured production")
    if injury_exposure:
        negatives.append(f"removes healthy cover at {' / '.join(injury_exposure[:2])}")

    if positives and negatives:
        explanation = f"Helps because it {', '.join(positives[:2])}, but it also {', '.join(negatives[:2])}."
    elif positives:
        explanation = f"Helps because it {', '.join(positives[:3])}."
    elif negatives:
        explanation = f"Hurts because it {', '.join(negatives[:3])}."
    else:
        explanation = "This is mostly a value-level reshuffle without a strong roster-fit swing."

    injury_summary_parts = []
    if injury_reinforcements:
        injury_summary_parts.append(f"adds healthy cover at {' / '.join(injury_reinforcements[:2])}")
    if injury_exposure:
        injury_summary_parts.append(f"removes healthy cover at {' / '.join(injury_exposure[:2])}")
    if incoming_major_injuries:
        injury_summary_parts.append(
            f"acquires {incoming_major_injuries} major injury risk{'s' if incoming_major_injuries != 1 else ''}"
        )
    elif incoming_moderate_injuries:
        injury_summary_parts.append(
            f"acquires {incoming_moderate_injuries} shorter-term injury risk{'s' if incoming_moderate_injuries != 1 else ''}"
        )
    if post_injury_burden <= current_injury_burden - 1.0:
        injury_summary = (
            f"Injury risk improves from {current_health_flag} to {post_health_flag}. "
            + (", ".join(injury_summary_parts) if injury_summary_parts else "The roster comes out healthier overall.")
            + "."
        )
    elif post_injury_burden >= current_injury_burden + 1.0:
        injury_summary = (
            f"Injury risk rises from {current_health_flag} to {post_health_flag}. "
            + (", ".join(injury_summary_parts) if injury_summary_parts else "The return adds more health volatility than it removes.")
            + "."
        )
    elif injury_summary_parts:
        injury_summary = (
            "Health context: "
            + ", ".join(injury_summary_parts)
            + "."
        )
    else:
        injury_summary = "Health context stays close to neutral."

    return {
        "available": True,
        "value_delta": value_delta,
        "value_verdict": trade_value_verdict(value_delta),
        "roster_fit_verdict": roster_fit_verdict,
        "lineup_delta": lineup_delta,
        "lineup_summary": lineup_summary,
        "strategy_fit_label": strategy_fit_label,
        "strategy_summary": strategy_summary,
        "injury_summary": injury_summary,
        "explanation": explanation,
        "component_scores": {
            "value": value_component,
            "lineup": lineup_component,
            "needs": need_component,
            "age": age_component,
            "draft": draft_component,
            "strategy": strategy_component,
            "injury": injury_component,
        },
        "injury_burden_delta": injury_burden_delta,
    }


_asset_initials = trade_hub_ui.asset_initials
_trade_asset_injury_context = partial(
    trade_hub_ui.trade_asset_injury_context,
    injury_level=injury_level,
)
_trade_idea_injury_display_context = partial(
    trade_hub_ui.trade_idea_injury_display_context,
    asset_injury_context=_trade_asset_injury_context,
)


_trade_asset_html = partial(
    trade_hub_ui.trade_asset_html,
    injury_marker=INJURY_EMOJI,
    is_injury_status=is_injury_status,
    format_score=_format_score,
    resolve_player_status=lambda row, **kwargs: _resolve_player_status(row, **kwargs),
    asset_injury_context=lambda asset: _trade_asset_injury_context(asset),
    cached_headshot_data_url=cached_headshot_data_url,
    avatar_html=avatar_html,
    format_age=_format_age,
    canonical_player_status=lambda label: _canonical_player_status(label),
    tier_chip_html=lambda label: tier_chip_html(label),
    player_support_chip_html=lambda text, tone="neutral": player_support_chip_html(text, tone),
    player_status_pill_html=lambda label: player_status_pill_html(label),
)


def _trade_assets_html(assets: list[dict]) -> str:
    return trade_hub_ui.trade_assets_html(
        assets,
        asset_html_builder=_trade_asset_html,
    )



def render_recommendation_feedback(
    *,
    page: str,
    surface: str,
    recommendation_type: str,
    key_prefix: str,
    recommendation_title: str = "",
    recommendation_summary: str = "",
    player_ids=None,
    player_names=None,
    score_fields: dict | None = None,
    confidence_fields: dict | None = None,
    reason_fields: dict | None = None,
    team_id: str = "",
    roster_id: str = "",
) -> None:
    active_context = st.session_state.get("active_league_context", {})
    if not isinstance(active_context, dict):
        active_context = {}
    username = _safe_text(st.session_state.get("username") or active_context.get("username")).strip()
    league_id = _safe_text(
        st.session_state.get("selected_league_id") or active_context.get("selected_league_id")
    ).strip()
    league_name = _safe_text(
        st.session_state.get("selected_league_name") or active_context.get("selected_league_name")
    ).strip()
    resolved_roster_id = _safe_text(
        roster_id
        or active_context.get("my_roster_id")
        or st.session_state.get("selected_team_roster_id")
    ).strip()
    feedback_ui.render_feedback_form(
        page=page,
        surface=surface,
        recommendation_type=recommendation_type,
        key_prefix=_safe_text(key_prefix, "recommendation_feedback"),
        username=username,
        league_id=league_id,
        league_name=league_name,
        team_id=_safe_text(team_id),
        roster_id=resolved_roster_id,
        player_ids=player_ids,
        player_names=player_names,
        recommendation_title=recommendation_title,
        recommendation_summary=recommendation_summary,
        score_fields=score_fields,
        confidence_fields=confidence_fields,
        reason_fields=reason_fields,
        build_feedback_report=build_feedback_report,
        append_feedback_report=append_feedback_report,
    )


def render_global_feedback_entry(
    *,
    current_page: str,
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
    key_prefix: str = "global_feedback",
    placement: str = "floating",
) -> None:
    if (
        placement == "floating"
        and st.session_state.get("_executive_command_header_mounted")
    ):
        # Feedback lives in the executive command header to avoid duplicate controls.
        return
    active_context = st.session_state.get("active_league_context", {})
    if not isinstance(active_context, dict):
        active_context = {}
    platform = _safe_text(st.session_state.get("selected_platform") or active_context.get("platform"), "Sleeper")
    user_id = auth_supabase.current_user_id(st.session_state)
    email = _safe_text(st.session_state.get(auth_supabase.AUTH_EMAIL_KEY))
    access_token = auth_supabase.current_access_token(st.session_state)
    config = _supabase_config()
    viewport_width = None
    try:
        viewport_width = int(st.session_state.get("_viewport_width") or 0) or None
    except (TypeError, ValueError):
        viewport_width = None
    context = feedback_context_payload(
        current_page=current_page,
        platform=platform,
        league_id=_safe_text(selected_league_id or active_context.get("selected_league_id")),
        league_name=_safe_text(selected_league_name or active_context.get("selected_league_name")),
        team_id=_safe_text(st.session_state.get("selected_team_roster_id")),
        roster_id=_safe_text(my_roster_id or active_context.get("my_roster_id")),
        user_id=user_id,
        entitlement=current_user_entitlement(),
        viewport_width=viewport_width,
        auth_state="signed_in" if user_id else "guest",
    )

    def _persist_feedback(report: dict) -> tuple[bool, str]:
        # Attach user_id for RLS-owned inserts without putting email in context.
        if user_id:
            report = {**report, "user_id": user_id}
            context_payload = report.get("context") if isinstance(report.get("context"), dict) else {}
            report["context"] = {**context_payload, "user_id": user_id}
        saved, error = append_feedback_report(
            report,
            config=config,
            access_token=access_token,
            prefer_supabase=bool(config and auth_supabase.is_configured(config)),
        )
        if saved:
            try:
                from modules import launch_analytics

                launch_analytics.track_event(
                    "feedback_submitted",
                    props=launch_analytics.build_context_props(
                        st.session_state,
                        route=_safe_text(current_page),
                        source_surface="feedback",
                        extra={"item_kind": _safe_text(report.get("category"))[:80]},
                    ),
                    state=st.session_state,
                )
            except Exception:
                pass
        return saved, error

    feedback_ui.render_global_feedback_button(
        context=context,
        build_global_feedback_report=build_global_feedback_report,
        append_feedback_report=_persist_feedback,
        default_email=email,
        key_prefix=key_prefix,
        placement=placement,
    )


free_agent_priority_badge = waivers_ui.free_agent_priority_badge
select_top_waiver_opportunity = waivers_ui.select_top_waiver_opportunity


def free_agent_reason_text(
    row,
    position_rank: int,
    score_label: str,
    needed_positions: list[str] | None = None,
) -> str:
    return waivers_ui.free_agent_reason_text(
        row,
        position_rank,
        score_label,
        needed_positions=needed_positions,
        recommendation_reason_text=_recommendation_reason_text,
    )


def render_free_agent_summary_cards(
    free_agents: pd.DataFrame,
    score_field: str,
):
    return waivers_ui.render_free_agent_summary_cards(
        free_agents,
        score_field,
        player_display_name=player_display_name,
        cached_headshot_data_url=cached_headshot_data_url,
        asset_initials=_asset_initials,
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
    )


def render_free_agent_cards(
    free_agents: pd.DataFrame,
    score_field: str,
    max_items: int = 12,
    needed_positions: list[str] | None = None,
    key_prefix: str = "waiver",
):
    return waivers_ui.render_free_agent_cards(
        free_agents,
        score_field,
        max_items=max_items,
        needed_positions=needed_positions,
        key_prefix=key_prefix,
        recommendation_reason_text=_recommendation_reason_text,
        player_display_name=player_display_name,
        cached_headshot_data_url=cached_headshot_data_url,
        asset_initials=_asset_initials,
        player_status_style=_player_status_style,
        canonical_player_status=_canonical_player_status,
        tier_chip_html=tier_chip_html,
        player_support_chip_html=player_support_chip_html,
        player_status_pill_html=player_status_pill_html,
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        render_recommendation_feedback=render_recommendation_feedback,
    )

def _trade_target_reason(idea: dict) -> str:
    return trade_hub_ui.trade_target_reason(
        idea,
        recommendation_reason_text=_recommendation_reason_text,
    )


def _trade_partner_reason(idea: dict) -> str:
    return trade_hub_ui.trade_partner_reason(
        idea,
        recommendation_reason_text=_recommendation_reason_text,
    )


def _trade_confidence_reason(idea: dict) -> str:
    return trade_hub_ui.trade_confidence_reason(
        idea,
        recommendation_reason_text=_recommendation_reason_text,
        injury_display_context=_trade_idea_injury_display_context,
    )


def _trade_display_confidence_label(idea: dict) -> str:
    return trade_hub_ui.trade_display_confidence_label(
        idea,
        injury_display_context=_trade_idea_injury_display_context,
    )


def _normalize_trade_html(html: str) -> str:
    return trade_hub_ui.normalize_trade_html(html)


def _render_trade_html(html: str) -> None:
    trade_hub_ui.render_trade_html(html)


def render_trade_idea_card(
    idea: dict,
    idea_idx: int,
    *,
    key_prefix: str = "trade_idea",
    render_player_dossier=None,
):
    def _render_detail_actions(idea: dict, detail_key: str) -> None:
        render_trade_idea_player_actions(
            idea,
            key_prefix=detail_key,
            return_page="trade_hub",
            source_label="Trade Hub",
        )

    trade_hub_ui.render_trade_idea_card(
        idea,
        idea_idx,
        format_score=_format_score,
        tidy_label=tidy_label,
        trade_target_reason=_trade_target_reason,
        trade_partner_reason=_trade_partner_reason,
        trade_confidence_reason=_trade_confidence_reason,
        trade_value_verdict=trade_value_verdict,
        trade_display_confidence_label=_trade_display_confidence_label,
        injury_display_context=_trade_idea_injury_display_context,
        glyph_chip_html=glyph_chip_html,
        assets_html=_trade_assets_html,
        key_prefix=key_prefix,
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        render_player_dossier=render_player_dossier,
        render_detail_actions=_render_detail_actions,
    )


def render_trade_idea_player_actions(
    idea: dict,
    *,
    key_prefix: str,
    return_page: str,
    source_label: str,
) -> None:
    trade_hub_ui.render_trade_idea_player_actions(
        idea,
        key_prefix=key_prefix,
        return_page=return_page,
        source_label=source_label,
        render_player_detail_button_grid=render_player_detail_button_grid,
        render_recommendation_feedback=render_recommendation_feedback,
        trade_target_reason=_trade_target_reason,
        trade_partner_reason=_trade_partner_reason,
        trade_confidence_reason=_trade_confidence_reason,
    )


def split_trade_surface_ideas(ideas: list[dict] | None) -> tuple[list[dict], list[dict]]:
    primary: list[dict] = []
    secondary: list[dict] = []
    for idea in ideas or []:
        if _safe_text(idea.get("trade_surface_tier"), "primary").strip().lower() == "secondary":
            secondary.append(idea)
        else:
            primary.append(idea)
    return primary, secondary


def select_trade_hub_headline_idea(ideas: list[dict] | None) -> dict | None:
    """Return the executive lead: first idea in presentation surface order.

    Categories never select the lead. Callers should pass already-ordered ideas
    when possible; this helper re-applies the presentation sort defensively so a
    mid-board Medium/High package cannot steal the Headline badge from #1.
    """

    ordered = trade_hub_ui.order_trade_hub_visible_ideas(list(ideas or []))
    return ordered[0] if ordered else None


def enrich_trade_ideas_with_manager_tendencies(
    ideas: list[dict],
    summary_df: pd.DataFrame,
    maturity_context: dict | None = None,
) -> list[dict]:
    if not ideas or summary_df is None or summary_df.empty:
        return ideas

    if maturity_context is None:
        maturity_context = league_maturity.build_league_evidence(
            league_frame=summary_df,
        )
    history_available = league_maturity.insight_is_available(
        "trade_tendencies",
        maturity_context,
    )
    team_rows = summary_df.copy()
    by_team_name = {
        _safe_text(row.get("team_name")).strip().casefold(): row.to_dict()
        for _, row in team_rows.iterrows()
        if _safe_text(row.get("team_name"))
    }
    enriched = []
    for idea in ideas:
        updated = dict(idea)
        partner_name = _safe_text(idea.get("partner_team_name")).strip().casefold()
        partner_row = by_team_name.get(partner_name, {})
        partner_evidence = league_maturity.trade_partner_evidence(
            updated,
            historical_evidence_available=history_available,
        )
        updated["partner_evidence_reason"] = partner_evidence["reason"]
        updated["partner_evidence_basis"] = partner_evidence["basis"]
        if history_available:
            updated["partner_tendencies_summary"] = _safe_text(partner_row.get("manager_tendencies_summary"))
            updated["partner_trade_implication"] = _safe_text(partner_row.get("manager_trade_implication"))
            updated["partner_trading_style"] = _safe_text(partner_row.get("trading_style"))
            updated["partner_asset_behavior"] = _safe_text(partner_row.get("asset_behavior"))
            updated["partner_activity_level"] = _safe_text(partner_row.get("activity_level"))
        else:
            updated["partner_tendencies_summary"] = ""
            updated["partner_trade_implication"] = ""
            updated["partner_trading_style"] = ""
            updated["partner_asset_behavior"] = ""
            updated["partner_activity_level"] = ""
        enriched.append(updated)
    return enriched


def player_trade_hub_option_label(row, score_field: str) -> str:
    tier = _safe_text(row.get("player_tier"), "Developmental")
    opportunity = _safe_text(row.get("opportunity_label"))
    if opportunity in STRONG_OPPORTUNITY_LABELS and _trade_asset_injury_context(row)["risk"]:
        opportunity = f"{opportunity} (Health Risk)"
    score = _format_score(row.get(score_field, row.get("value_score", 0)))
    return (
        f"{player_display_name(row)} | {_safe_text(row.get('position'))} | "
        f"{tier}{(' | ' + opportunity) if opportunity else ''} | {league_score_label(score_field)} {score}"
    )


def player_trade_hub_selected_summary(row, score_field: str) -> str:
    if row is None or getattr(row, "empty", False):
        return ""
    parts = [
        _safe_text(row.get("player_tier"), "Developmental"),
        _safe_text(row.get("position")),
        _safe_text(row.get("team"), "FA"),
    ]
    opportunity = _safe_text(row.get("opportunity_label"))
    health_context = _trade_asset_injury_context(row)
    if opportunity in STRONG_OPPORTUNITY_LABELS and health_context["risk"]:
        opportunity = f"{opportunity} (Health Risk)"
    if opportunity:
        parts.append(opportunity)
    age = _safe_float(row.get("age"), 0.0)
    if age > 0:
        parts.append(f"Age {age:.1f}")
    parts.append(f"{league_score_label(score_field)} {_format_score(row.get(score_field, row.get('value_score', 0)))}")
    injury = _safe_text(row.get("injury_level"), "healthy")
    if health_context["risk"]:
        parts.append(health_context["label"])
    elif injury and injury != "healthy":
        parts.append(f"Injury {injury}")
    return " | ".join(part for part in parts if part)


def _asset_bundle_summary(assets: list[dict], max_assets: int = 2) -> str:
    return trade_hub_ui.asset_bundle_summary(assets, max_assets=max_assets)


def render_trade_return_explorer(
    *,
    all_players_df: pd.DataFrame,
    owned_player_df: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    untouchables: tuple[str, ...] | list[str],
    role_map: dict[str, str],
    score_field: str,
    pick_score_multiplier: float,
    team_strategy: str,
    league_settings: dict,
    key_prefix: str,
    team_archetype: str = "",
    team_lens_label: str = "",
    max_ideas: int = 5,
    preselected_player_id: str = "",
    show_header: bool = True,
    compact: bool = False,
    card_key_prefix: str = "player_hub_profile",
    trust_context: TradeTrustContext | None = None,
    render_player_dossier=None,
):
    if owned_player_df is None or owned_player_df.empty:
        st.info("No eligible roster players are available for return exploration.")
        return

    if show_header:
        render_section_header(
            "Trade Return Explorer",
            kicker="What Could I Get?",
            note="Uses your league's rosters, manager tendencies, and team needs to show realistic return paths.",
            compact=compact,
        )

    trade_pool = owned_player_df.copy()
    if "player_id" in trade_pool.columns:
        trade_pool["player_id"] = trade_pool["player_id"].astype(str)
    trade_pool = trade_pool.sort_values(score_field, ascending=False)
    option_map = {
        player_trade_hub_option_label(row, score_field): str(row["player_id"])
        for _, row in trade_pool.iterrows()
    }
    if not option_map:
        st.info("No eligible roster players are available for return exploration.")
        return

    option_labels = list(option_map.keys())
    default_index = 0
    preselected = str(preselected_player_id or "").strip()
    if preselected:
        for idx, label in enumerate(option_labels):
            if option_map.get(label) == preselected:
                default_index = idx
                break
    selectbox_key = f"{key_prefix}_return_explorer_player"
    if preselected and option_labels:
        st.session_state[selectbox_key] = option_labels[default_index]

    selected_label = st.selectbox(
        "Select one of your players",
        option_labels,
        index=default_index,
        key=selectbox_key,
    )
    selected_player_id = option_map[selected_label]
    selected_row = trade_pool[trade_pool["player_id"] == selected_player_id].iloc[0]

    with st.spinner("Searching realistic return packages..."):
        search_result = cached_player_trade_hub_ideas(
            df_players=all_players_df,
            league_id=league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            untouchables=tuple(sorted(str(name) for name in untouchables)),
            role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            team_strategy=team_strategy,
            team_archetype=team_archetype,
            mode="my_player",
            selected_player_id=selected_player_id,
            league_settings_items=draft_pick_valuation_settings_items(league_settings),
            max_ideas=max(max_ideas, 5),
        )
    search_result = {
        **search_result,
        "ideas": enforce_cached_trade_ideas(
            search_result.get("ideas") or [],
            df_players=all_players_df,
            league_id=league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            untouchables=tuple(sorted(str(name) for name in untouchables)),
            trust_context=trust_context,
        ),
    }
    ideas = enrich_trade_ideas_with_manager_tendencies(search_result.get("ideas") or [], df_summary)

    render_summary_tiles(
        [
            {
                "label": "Selected Player",
                "value": player_display_name(selected_row),
                "note": player_trade_hub_selected_summary(selected_row, score_field),
                "tone": "opportunity",
            },
            {
                "label": "Team Focus",
                "value": team_lens_label or team_strategy_label(team_strategy),
                "note": "Return packages are filtered through your current roster strategy and partner fit.",
                "tone": "strategy",
            },
        ]
    )

    if search_result.get("fallback_used"):
        st.caption("Expanded search used because this player has fewer direct trade matches.")

    if not ideas:
        st.info("No realistic return packages cleared the current fit and value filters for this player.")
        if search_result.get("diagnostic_summary"):
            st.caption("Fewer matching partners for this search — the board was widened. " + _safe_text(search_result.get("diagnostic_summary")))
        return

    unique_paths = []
    for idea in ideas:
        path = _safe_text(idea.get("hub_path") or idea.get("tag"))
        if path and path not in unique_paths:
            unique_paths.append(path)
    # Presentation order: best executive move first (scores/Trust unchanged).
    visible_ideas = trade_hub_ui.order_trade_hub_visible_ideas(ideas[:max_ideas])
    primary_ideas, secondary_ideas = split_trade_surface_ideas(visible_ideas)
    headline_idea = select_trade_hub_headline_idea(visible_ideas)
    if headline_idea is not None:
        render_summary_tiles(
            [
                {
                    "label": "Likely Return",
                    "value": _asset_bundle_summary(headline_idea.get("receive_assets") or []),
                    "note": _safe_text(headline_idea.get("hub_solution_reason"), _trade_target_reason(headline_idea)),
                    "tone": "power",
                },
                {
                    "label": "Best Partner",
                    "value": _safe_text(headline_idea.get("partner_team_name"), "League partner"),
                    "note": _safe_text(headline_idea.get("hub_partner_reason"), _trade_partner_reason(headline_idea)),
                    "tone": "franchise",
                },
                                {
                                    "label": "Confidence",
                                    "value": _trade_display_confidence_label(headline_idea),
                                    "note": _trade_confidence_reason(headline_idea),
                                    "tone": "strategy",
                                },
            ]
        )
    elif secondary_ideas:
        render_summary_tiles(
            [
                {
                    "label": "Headline Status",
                    "value": "No clean lead path yet",
                    "note": "Secondary return paths are available below, but none are strong enough to headline right now.",
                    "tone": "risk",
                },
                {
                    "label": "Path Mix",
                    "value": ", ".join(unique_paths[:3]) if unique_paths else "Focused board",
                    "note": "These paths stay available for exploration, but FantasyGM Lab is not promoting one as the lead recommendation.",
                    "tone": "opportunity",
                },
            ]
        )

    for idea_idx, idea in enumerate(primary_ideas):
        render_player_trade_hub_card(
            idea,
            idea_idx,
            key_prefix=card_key_prefix,
            render_player_dossier=render_player_dossier,
        )
    if secondary_ideas:
        with st.expander("Secondary / thin-market return paths", expanded=False):
            st.caption("These return paths are weaker backups — still possible, but less likely to close than the lead board.")
            base_idx = len(primary_ideas)
            for offset, idea in enumerate(secondary_ideas):
                render_player_trade_hub_card(
                    idea,
                    base_idx + offset,
                    key_prefix=card_key_prefix,
                    render_player_dossier=render_player_dossier,
                )


render_player_trade_hub_card = partial(
    trade_hub_ui.render_player_trade_hub_card,
    recommendation_reason_text=lambda value, limit: _recommendation_reason_text(value, limit),
    render_trade_idea_card=lambda idea, idea_idx, **kwargs: render_trade_idea_card(
        idea,
        idea_idx,
        **kwargs,
    ),
    render_trade_idea_player_actions=lambda idea, **kwargs: render_trade_idea_player_actions(idea, **kwargs),
)


def render_trade_result_panel(
    send_assets: list[dict],
    receive_assets: list[dict],
    score_label: str,
    strategy: str = "retool",
    fit_evaluation: dict | None = None,
):
    send_score = sum(score_asset_value(asset) for asset in send_assets)
    receive_score = sum(score_asset_value(asset) for asset in receive_assets)
    max_score = max(send_score, receive_score, 1)
    send_pct = max(3, min(100, int(round((send_score / max_score) * 100)))) if send_score else 0
    receive_pct = max(3, min(100, int(round((receive_score / max_score) * 100)))) if receive_score else 0
    delta = receive_score - send_score

    if delta > 0:
        delta_class = "trade-delta-positive"
        delta_text = f"+{_format_score(delta)} {escape(score_label.lower())}"
    elif delta < 0:
        delta_class = "trade-delta-negative"
        delta_text = f"-{_format_score(abs(delta))} {escape(score_label.lower())}"
    else:
        delta_class = "trade-delta-neutral"
        delta_text = f"Even {escape(score_label.lower())}"

    strategy_note_text = strategy_trade_result_note(strategy)
    strategy_note = escape(strategy_note_text)
    strategy_label_text = team_strategy_label(strategy)
    strategy_label = escape(strategy_label_text)
    fit = fit_evaluation or {}
    fit_available = bool(fit.get("available"))
    value_verdict_text = _safe_text(fit.get("value_verdict"), trade_value_verdict(delta))
    roster_fit_verdict_text = _safe_text(fit.get("roster_fit_verdict"), "Value-only")
    strategy_fit_label_text = _safe_text(fit.get("strategy_fit_label"), strategy_label_text)
    value_verdict = escape(value_verdict_text)
    roster_fit_verdict = escape(roster_fit_verdict_text)
    strategy_fit_label = escape(strategy_fit_label_text)
    lineup_summary = escape(_safe_text(fit.get("lineup_summary"), ""))
    strategy_summary = escape(_safe_text(fit.get("strategy_summary"), ""))
    injury_summary = escape(_safe_text(fit.get("injury_summary"), ""))
    explanation = escape(_safe_text(fit.get("explanation"), strategy_trade_result_note(strategy)))
    lineup_delta = int(fit.get("lineup_delta") or 0) if fit_available else 0
    component_scores = fit.get("component_scores") if isinstance(fit.get("component_scores"), dict) else {}
    component_tags = []
    for label, value in [
        ("Value", component_scores.get("value")),
        ("Lineup", component_scores.get("lineup")),
        ("Needs", component_scores.get("needs")),
        ("Age", component_scores.get("age")),
        ("Draft", component_scores.get("draft")),
        ("Strategy", component_scores.get("strategy")),
        ("Injury", component_scores.get("injury")),
    ]:
        if value is None:
            continue
        try:
            numeric = int(value)
        except Exception:
            continue
        sign = "+" if numeric > 0 else ""
        component_tags.append(f"<span class='trade-reason-tag'>{label} {sign}{numeric}</span>")
    component_row = (
        "<div class='trade-reason-tags'>" + "".join(component_tags) + "</div>"
        if component_tags
        else ""
    )
    summary_meta = "".join(
        [
            glyph_chip_html(strategy_label_text, "success"),
            glyph_chip_html(value_verdict_text, "primary"),
            glyph_chip_html(roster_fit_verdict_text, "warning" if fit_available else "premium"),
        ]
    )
    fit_grid = ""
    if fit_available:
        lineup_note = lineup_summary or "Lineup impact was neutral."
        strategy_note_text = strategy_summary or strategy_trade_result_note(strategy)
        injury_note_text = injury_summary or "Health context stays close to neutral."
        fit_grid = f"""
        <div class="trade-fit-grid">
            <div class="trade-fit-card">
                <div class="trade-fit-label">Value Verdict</div>
                <div class="trade-fit-value">{value_verdict}</div>
                <div class="trade-fit-note">Raw package delta: {delta_text}</div>
            </div>
            <div class="trade-fit-card">
                <div class="trade-fit-label">Roster Fit Verdict</div>
                <div class="trade-fit-value">{roster_fit_verdict}</div>
                <div class="trade-fit-note">Balances lineup impact, need coverage, depth loss, age, pick fit, and current injury pressure.</div>
            </div>
            <div class="trade-fit-card">
                <div class="trade-fit-label">Lineup Impact</div>
                <div class="trade-fit-value">{'+' if lineup_delta > 0 else ''}{_format_score(lineup_delta)} starters</div>
                <div class="trade-fit-note">{lineup_note}</div>
            </div>
            <div class="trade-fit-card">
                <div class="trade-fit-label">Strategy Fit</div>
                <div class="trade-fit-value">{strategy_fit_label}</div>
                <div class="trade-fit-note">{escape(_safe_text(strategy_note_text))}</div>
            </div>
        </div>
        <div class="trade-rationale"><strong>Injury:</strong> {escape(_safe_text(injury_note_text))}</div>
        """

    html = textwrap.dedent(f"""
    <div class="trade-idea-card trade-result-card dg-card-primary">
        <div class="trade-card-top">
            <div>
                <div class="trade-card-kicker">Trade Result</div>
                <div class="trade-card-title">Selected package comparison</div>
                <div class="trade-card-meta-row">{summary_meta}</div>
                <div class="trade-card-subtitle">Current lens: {escape(score_label)}</div>
                {component_row}
            </div>
            <div class="trade-delta-pill {delta_class}">{delta_text}</div>
        </div>
        <div class="trade-matchup">
            <div class="trade-side">
                <div class="trade-side-header"><span>You send</span><span class="trade-side-value">{_format_score(send_score)}</span></div>
                {_trade_assets_html(send_assets)}
            </div>
            <div class="trade-vs">FOR</div>
            <div class="trade-side">
                <div class="trade-side-header"><span>You get</span><span class="trade-side-value">{_format_score(receive_score)}</span></div>
                {_trade_assets_html(receive_assets)}
            </div>
        </div>
        <div class="trade-value-meter">
            <div class="trade-meter-row">
                <div class="trade-meter-label">Send</div>
                <div class="trade-meter-track"><div class="trade-meter-fill trade-meter-send" style="width:{send_pct}%"></div></div>
                <div class="trade-meter-number">{_format_score(send_score)}</div>
            </div>
            <div class="trade-meter-row">
                <div class="trade-meter-label">Get</div>
                <div class="trade-meter-track"><div class="trade-meter-fill trade-meter-receive" style="width:{receive_pct}%"></div></div>
                <div class="trade-meter-number">{_format_score(receive_score)}</div>
            </div>
        </div>
        {fit_grid}
        <div class="trade-rationale">{explanation if fit_available else strategy_note}</div>
    </div>
    """).strip()
    trade_hub_ui.render_trade_html_with_player_taps(
        html,
        send_assets + receive_assets,
        key_prefix="trade_analyzer_result",
        source_label="Trade Analyzer",
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
    )


def _team_initials(name: str) -> str:
    parts = [part for part in _safe_text(name).replace("_", " ").split() if part]
    return "".join(part[0] for part in parts[:2]).upper() or "GM"


PAGE_GLYPHS = {
    "dashboard": "GM",
    "my_team": "TM",
    "players": "PL",
    "rankings": "RK",
    "trade_hub": "TH",
    "trade_analyzer": "TA",
    "waivers": "WV",
    "teams": "LG",
    "draft_summary": "DR",
    "startup_draft_center": "SD",
    "news": "NW",
    "premium": "PR",
    "founder_ops": "OPS",
    "about_disclaimer": "AB",
    "terms": "TO",
    "privacy": "PR",
    "no_affiliation": "NA",
}

TIER_CLASS_MAP = {
    "elite": "dg-tier-elite",
    "star": "dg-tier-star",
    "core starter": "dg-tier-core-starter",
    "starter": "dg-tier-starter",
    "contributor": "dg-tier-contributor",
    "depth": "dg-tier-depth",
    "developmental": "dg-tier-developmental",
}


def page_glyph(page_key: str) -> str:
    return PAGE_GLYPHS.get(_safe_text(page_key).strip().lower(), "GM")


def tier_design_class(tier_label: str) -> str:
    return TIER_CLASS_MAP.get(_safe_text(tier_label).strip().lower(), "dg-tier-developmental")


def tier_chip_html(tier_label: str) -> str:
    tier_text = _safe_text(tier_label, "Developmental")
    return f"<span class='dg-tier-chip {tier_design_class(tier_text)}'>{escape(tier_text)}</span>"


def glyph_chip_html(text: str, tone: str = "primary") -> str:
    tone_key = _safe_text(tone, "primary").strip().lower()
    tone_key = tone_key if tone_key in {"primary", "success", "warning", "premium"} else "primary"
    return f"<span class='dg-glyph-chip dg-glyph-chip-{tone_key}'>{escape(_safe_text(text))}</span>"


PLAYER_STATUS_ALIASES = player_cards.PLAYER_STATUS_ALIASES
PLAYER_STATUS_STYLES = player_cards.PLAYER_STATUS_STYLES
STRONG_OPPORTUNITY_LABELS = player_cards.STRONG_OPPORTUNITY_LABELS
PLAYER_CARD_PRESTIGE_STATUSES = player_cards.PLAYER_CARD_PRESTIGE_STATUSES
PLAYER_CARD_PRIMARY_TIERS = player_cards.PLAYER_CARD_PRIMARY_TIERS
PLAYER_CARD_ROLE_FALLBACKS = player_cards.PLAYER_CARD_ROLE_FALLBACKS
PLAYER_CARD_CONTEXT_TAGS = player_cards.PLAYER_CARD_CONTEXT_TAGS
_canonical_player_status = player_cards.canonical_player_status
_player_status_style = player_cards.player_status_style
player_status_pill_html = player_cards.player_status_pill_html
player_support_chip_html = player_cards.player_support_chip_html
injury_adjusted_value_html = player_cards.injury_adjusted_value_html


def render_page_shell(
    *,
    page_key: str,
    title: str,
    subtitle: str,
    meta_items: list[tuple[str, str]] | None = None,
):
    page_class = re.sub(r"[^a-z0-9-]+", "-", _safe_text(page_key).strip().lower()).strip("-") or "general"
    chips = []
    page_definition = next(
        (page for page in PLATFORM_DESTINATIONS if page.key == page_key),
        None,
    )
    resolved_meta = list(meta_items or [])
    if (
        page_definition is not None
        and page_definition.category == "EXPERIMENTAL"
        and not any(
            brand_identity.EXPERIMENTAL_LABEL in _safe_text(label)
            for label, _tone in resolved_meta
        )
    ):
        resolved_meta.insert(0, (brand_identity.EXPERIMENTAL_LABEL, "warning"))
    for label, tone in resolved_meta:
        if _safe_text(label):
            chips.append(glyph_chip_html(label, tone))
    # The application workspace is the single canonical page hero. Page
    # renderers may contribute compact context chips, never a second title.
    if chips:
        st.markdown(
            f"<section class='dg-page-context dg-page-shell--{escape(page_class)}' "
            f"aria-label='{escape(_safe_text(title))} context'>"
            f"<div class='dg-page-meta'>{''.join(chips)}</div></section>",
            unsafe_allow_html=True,
        )


def style_tier_table(df: pd.DataFrame) -> "pd.io.formats.style.Styler | pd.DataFrame":
    if df is None or getattr(df, "empty", False):
        return df

    tier_columns = [col for col in df.columns if str(col).strip().lower() == "tier"]
    if not tier_columns:
        return df

    def tier_style(value):
        tier_text = _safe_text(value).strip().lower()
        styles = {
            "elite": "background-color: rgba(250, 204, 21, 0.18); color: #fef08a; font-weight: 800;",
            "star": "background-color: rgba(168, 85, 247, 0.16); color: #e9d5ff; font-weight: 800;",
            "core starter": "background-color: rgba(56, 189, 248, 0.16); color: #bae6fd; font-weight: 800;",
            "starter": "background-color: rgba(20, 184, 166, 0.14); color: #99f6e4; font-weight: 800;",
            "contributor": "background-color: rgba(245, 158, 11, 0.14); color: #fde68a; font-weight: 800;",
            "depth": "background-color: rgba(148, 163, 184, 0.14); color: #cbd5e1; font-weight: 760;",
            "developmental": "background-color: rgba(71, 85, 105, 0.22); color: #cbd5e1; font-weight: 760;",
        }
        return styles.get(tier_text, "font-weight: 760;")

    styler = df.style
    if hasattr(styler, "map"):
        return styler.map(tier_style, subset=tier_columns)
    return styler.applymap(tier_style, subset=tier_columns)


def _resolve_player_detail_return_page(return_page: str = "") -> str:
    candidate = _safe_text(
        return_page
        or st.session_state.get("player_detail_return_page")
        or st.session_state.get("platform_nav_page")
        or st.session_state.get("current_page")
        or "my_team"
    ).strip()
    if not candidate or candidate == "player_detail":
        return "my_team"
    return candidate


def open_player_detail(player_id: str, *, return_page: str, source_label: str = "") -> None:
    player_id = _safe_text(player_id).strip()
    if not player_id:
        return
    resolve_active_league_context()
    st.session_state["player_detail_player_id"] = player_id
    st.session_state["player_detail_return_page"] = _resolve_player_detail_return_page(return_page)
    st.session_state["player_detail_source_label"] = _safe_text(source_label)
    st.session_state["_player_detail_table_epoch"] = _safe_positive_int(
        st.session_state.get("_player_detail_table_epoch"),
        0,
    ) + 1
    _queue_platform_route("player_detail")
    st.rerun()


PLAYER_QUICK_VIEW_STATE_KEYS = (
    "player_quick_view_player_id",
    "player_quick_view_source_label",
    "player_quick_view_source_note",
    "player_quick_view_status_label",
)


def _clear_player_quick_view() -> None:
    for key in PLAYER_QUICK_VIEW_STATE_KEYS:
        st.session_state.pop(key, None)
    canonical_recommendation_narrative.clear_narrative(st.session_state)


def _clear_league_switch_workflow_state(*, previous_league_id: str = "") -> None:
    workflow_continuity.clear_return_context(st.session_state)
    _ = previous_league_id


def open_player_quick_view(
    player_id: str,
    *,
    source_label: str = "",
    source_note: str = "",
    status_label: str = "",
    recommendation_narrative=None,
) -> None:
    player_id = _safe_text(player_id).strip()
    if not player_id:
        return
    context = resolve_active_league_context()
    st.session_state["player_quick_view_player_id"] = player_id
    st.session_state["player_quick_view_source_label"] = _safe_text(source_label)
    st.session_state["player_quick_view_source_note"] = _safe_text(source_note)
    st.session_state["player_quick_view_status_label"] = _safe_text(status_label)
    # Bind provenance only when a matching recommendation is supplied.
    # Opening without one must not reuse a prior-league or prior-route narrative.
    if recommendation_narrative is not None:
        model = (
            recommendation_narrative
            if isinstance(
                recommendation_narrative,
                canonical_recommendation_narrative.CanonicalRecommendationNarrative,
            )
            else canonical_recommendation_narrative.CanonicalRecommendationNarrative.from_dict(
                recommendation_narrative
            )
        )
        if model is not None:
            payload = model.to_dict()
            if not _safe_text(payload.get("league_id")):
                payload["league_id"] = _safe_text(context.get("selected_league_id"))
            if not _safe_text(payload.get("roster_id")):
                payload["roster_id"] = _safe_text(context.get("my_roster_id"))
            canonical_recommendation_narrative.bind_narrative(
                st.session_state,
                payload,
            )
        else:
            canonical_recommendation_narrative.clear_narrative(st.session_state)
    else:
        canonical_recommendation_narrative.clear_narrative(st.session_state)
    interaction_latency.mark_interaction_milestone("pqv_open_received")
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "pqv_opened",
            props=launch_analytics.build_context_props(
                st.session_state,
                source_surface=_safe_text(source_label)[:80] or "player_quick_view",
            ),
            once_key=player_id,
            state=st.session_state,
        )
    except Exception:
        pass


def _player_on_active_roster(player_id: str, selected_league_id: str, my_roster_id) -> bool:
    player_key = _safe_text(player_id).strip()
    if not player_key or not selected_league_id or my_roster_id is None:
        return False
    roster_ids = {
        str(pid)
        for pid in get_roster_player_ids(selected_league_id, my_roster_id) or []
        if pid is not None
    }
    return player_key in roster_ids


def _toggle_player_untouchable(
    *,
    player_row: pd.Series,
    username: str,
    selected_league_id: str,
) -> bool:
    player_name = _safe_text(player_row.get("name")).strip()
    if not username or not selected_league_id or not player_name:
        return False

    profile = load_profile_key(username, selected_league_id)
    current = [
        _safe_text(name).strip()
        for name in profile.get("untouchables", [])
        if _safe_text(name).strip()
    ]
    if player_name in current:
        updated = [name for name in current if name != player_name]
        is_untouchable = False
    else:
        updated = current + [player_name]
        is_untouchable = True

    profile["untouchables"] = updated
    save_profile_key(username, selected_league_id, profile)

    untouchables_key = f"untouchables_ms_{selected_league_id}"
    if untouchables_key in st.session_state:
        st.session_state[untouchables_key] = updated

    return is_untouchable


def _open_trade_hub_for_player_focus(
    *,
    player_row: pd.Series,
    selected_league_id: str,
    my_roster_id,
    username: str = "",
) -> None:
    player_id = _safe_text(player_row.get("player_id")).strip()
    selected_league_key = _safe_text(selected_league_id).strip()
    if not selected_league_key or not player_id:
        return

    context = resolve_active_league_context()
    active_username = _safe_text(username).strip() or _safe_text(context.get("username")).strip()
    if active_username:
        st.session_state["username"] = active_username
        st.session_state["_sync_sidebar_username_input"] = True
        st.session_state["_sync_home_launch_username_input"] = True
    on_roster = _player_on_active_roster(player_id, selected_league_key, my_roster_id)
    current_name = _safe_text(context.get("selected_league_name")).strip()
    if str(context.get("selected_league_id") or "") != selected_league_key:
        set_selected_league(selected_league_key, current_name or _safe_text(st.session_state.get("selected_league_name")))
    elif not current_name:
        set_selected_league(selected_league_key, _safe_text(st.session_state.get("selected_league_name")))
    st.session_state[f"trade_hub_mode_{selected_league_key or 'none'}"] = "Player-Centric"
    st.session_state[f"player_trade_hub_mode_{selected_league_key}"] = (
        "My Player Mode" if on_roster else "Target Player Mode"
    )
    st.session_state[f"trade_hub_focus_player_id_{selected_league_key}"] = player_id
    st.session_state[f"trade_hub_focus_mode_{selected_league_key}"] = (
        "my_player" if on_roster else "target_player"
    )
    _capture_workflow_handoff(
        "trade_hub",
        origin_page=_safe_text(st.session_state.get("platform_nav_page"), "dashboard"),
        origin_label="Player Quick View",
        note=f"Continue trade evaluation for {_safe_text(player_row.get('name'), 'this player')}.",
        league_id=selected_league_key,
        handoff_source="player_quick_view",
    )
    _clear_player_quick_view()
    _queue_platform_route("trade_hub")
    st.rerun()


def render_player_detail_picker(
    player_df: pd.DataFrame,
    *,
    key_prefix: str,
    return_page: str,
    source_label: str,
    label: str = "Open player detail",
    score_field_for_label: str = "value_score",
    open_mode: str = "detail",
) -> None:
    if player_df is None or player_df.empty:
        return
    options = {
        player_trade_hub_option_label(
            row,
            score_field_for_label if score_field_for_label in row.index else "value_score" if "value_score" in row.index else "score",
        ): str(row.get("player_id"))
        for _, row in player_df.iterrows()
        if _safe_text(row.get("player_id"))
    }
    if not options:
        return
    picker_cols = st.columns([4, 1])
    with picker_cols[0]:
        selected_label = st.selectbox(
            label,
            list(options.keys()),
            key=f"{key_prefix}_detail_picker",
        )
    with picker_cols[1]:
        quick_view_mode = _safe_text(open_mode).strip().lower() == "quick_view"
        action_label = "Quick View" if quick_view_mode else "Open Profile"
        if st.button(action_label, key=f"{key_prefix}_detail_open", use_container_width=True):
            if quick_view_mode:
                open_player_quick_view(
                    options[selected_label],
                    source_label=source_label,
                )
            else:
                open_player_detail(
                    options[selected_label],
                    return_page=return_page,
                    source_label=source_label,
                )


def render_player_detail_button_grid(
    players: list[dict] | list[pd.Series] | pd.DataFrame,
    *,
    key_prefix: str,
    return_page: str,
    source_label: str,
    title: str = "",
    max_buttons: int = 6,
    open_mode: str = "detail",
) -> None:
    if isinstance(players, pd.DataFrame):
        rows = [row for _, row in players.iterrows()]
    else:
        rows = list(players or [])
    items = []
    seen_ids: set[str] = set()
    for row in rows:
        player_id = _safe_text(row.get("player_id") if isinstance(row, dict) else row.get("player_id")).strip()
        if not player_id or player_id in seen_ids:
            continue
        seen_ids.add(player_id)
        name = player_display_name(row)
        items.append((player_id, name))
        if len(items) >= max_buttons:
            break
    if not items:
        return
    if title:
        st.caption(title)
    for row_start in range(0, len(items), 2):
        chunk = items[row_start:row_start + 2]
        columns = st.columns(len(chunk), gap="small")
        for (player_id, name), column in zip(chunk, columns):
            with column:
                if st.button(
                    f"{'Open' if _safe_text(open_mode).strip().lower() == 'quick_view' else page_glyph('player_detail')} {name}",
                    key=f"{key_prefix}_{player_id}",
                    use_container_width=True,
                ):
                    if _safe_text(open_mode).strip().lower() == "quick_view":
                        open_player_quick_view(
                            player_id,
                            source_label=source_label,
                        )
                    else:
                        open_player_detail(
                            player_id,
                            return_page=return_page,
                            source_label=source_label,
                        )


_truncate_text = player_cards.truncate_text
_recommendation_reason_text = player_cards.recommendation_reason_text
_resolve_player_status = partial(
    player_cards.resolve_player_status,
    is_injury_status=is_injury_status,
)
_resolve_player_card_primary_status = partial(
    player_cards.resolve_player_card_primary_status,
    is_injury_status=is_injury_status,
)
_player_scan_tags = partial(
    player_cards.player_scan_tags,
    is_injury_status=is_injury_status,
)


def _player_scan_card_html(
    row,
    *,
    score_field: str,
    score_label: str,
    status_label: str = "",
    note_text: str = "",
    extra_tags: list[str] | None = None,
    show_slot: bool = False,
    avatar_class: str = "scan-card-avatar",
    compact: bool = False,
    interactive: bool = False,
    show_inline_reason: bool = False,
) -> str:
    return player_cards.player_scan_card_html(
        row,
        score_field=score_field,
        score_label=score_label,
        player_display_name=player_display_name,
        format_age=_format_age,
        format_score=_format_score,
        cached_headshot_data_url=cached_headshot_data_url,
        avatar_html=avatar_html,
        asset_initials=_asset_initials,
        is_injury_status=is_injury_status,
        status_label=status_label,
        note_text=note_text,
        extra_tags=extra_tags,
        show_slot=show_slot,
        avatar_class=avatar_class,
        compact=compact,
        interactive=interactive,
        show_inline_reason=show_inline_reason,
    )


def _compact_player_row_html(
    row,
    *,
    score_field: str,
    score_label: str,
    status_label: str = "",
    note_text: str = "",
    extra_tags: list[str] | None = None,
    show_slot: bool = False,
    avatar_class: str = "compact-player-avatar",
    interactive: bool = False,
    design_system: bool = True,
) -> str:
    return player_cards.compact_player_row_html(
        row,
        score_field=score_field,
        score_label=score_label,
        player_display_name=player_display_name,
        format_age=_format_age,
        format_score=_format_score,
        cached_headshot_data_url=cached_headshot_data_url,
        avatar_html=avatar_html,
        asset_initials=_asset_initials,
        is_injury_status=is_injury_status,
        status_label=status_label,
        note_text=note_text,
        extra_tags=extra_tags,
        show_slot=show_slot,
        avatar_class=avatar_class,
        interactive=interactive,
        design_system=design_system,
    )


_render_player_scan_tap_grid = player_cards.render_player_tap_grid
_render_tappable_player_html = player_cards.render_tappable_player_html
_render_player_interaction_grid = player_cards.render_player_interaction_grid


def _capture_workflow_handoff(
    destination: str,
    *,
    origin_page: str = "",
    origin_label: str = "",
    note: str = "",
    league_id: str = "",
    handoff_source: str = "",
) -> None:
    """Record return context when moving between executive workflow surfaces."""

    origin = _safe_text(origin_page) or _safe_text(
        st.session_state.get("platform_nav_page"),
        "dashboard",
    )
    if origin == _safe_text(destination):
        return
    narrative = canonical_recommendation_narrative.load_narrative(st.session_state)
    workflow_continuity.push_return_context(
        st.session_state,
        origin,
        origin_label=_safe_text(origin_label),
        note=_safe_text(note),
        league_id=_safe_text(league_id) or _safe_text(st.session_state.get("selected_league_id")),
        recommendation_id=_safe_text(getattr(narrative, "recommendation_id", "")),
        handoff_source=_safe_text(handoff_source),
    )


def _workflow_return_to_origin() -> None:
    """Return to the prior workflow step without losing league or narrative context."""

    context = workflow_continuity.current_return_context(
        st.session_state,
        league_id=_safe_text(st.session_state.get("selected_league_id")),
    )
    if context is None:
        return
    destination = _safe_text(context.origin_page, "dashboard")
    # Notification Center is a command-bar popover, not a route body.
    if destination == "notification_center":
        destination = "dashboard"
        st.session_state["_notification_return_ack"] = True
    workflow_continuity.clear_return_context(st.session_state)
    st.session_state["platform_nav_page"] = destination
    request_scroll_restore(
        st.session_state,
        destination,
        reason="workflow_back",
    )
    performance.mark_interaction("destination_navigation_render", lightweight=False)


def render_workflow_continuity_bar(
    current_page: str,
    *,
    selected_league_id: str = "",
    extra_note: str = "",
) -> None:
    """Show breadcrumb + Back when the user arrived via a workflow handoff."""

    context = workflow_continuity.current_return_context(
        st.session_state,
        league_id=selected_league_id,
    )
    if context is None:
        return
    note = _safe_text(extra_note) or _safe_text(context.note)
    if note and note != context.note:
        banner_context = workflow_continuity.WorkflowReturnContext(
            **{
                **context.to_dict(),
                "note": note,
            }
        )
    else:
        banner_context = context
    st.markdown(
        workflow_continuity.continuity_banner_html(
            banner_context,
            current_page=current_page,
        ),
        unsafe_allow_html=True,
    )
    hint = workflow_continuity.next_action_hint(current_page, has_return=True)
    if hint:
        st.caption(hint)
    st.button(
        f"← Back to {context.origin_label}",
        key=f"workflow_return_{current_page}_{context.origin_page}",
        type="tertiary",
        use_container_width=False,
        on_click=_workflow_return_to_origin,
    )


def _open_home_command_route(
    route_key: str,
    *,
    player_id: str = "",
    focus_mode: str = "",
    source_label: str = "",
    source_note: str = "",
    recommendation_narrative=None,
    handoff_source: str = "dashboard_quick_action",
    origin_page: str = "dashboard",
    origin_label: str = "",
) -> None:
    route_key = _safe_text(route_key).strip()
    if not route_key:
        return
    league_id = _safe_text(st.session_state.get("selected_league_id")).strip()
    if recommendation_narrative is not None:
        canonical_recommendation_narrative.bind_narrative(
            st.session_state,
            recommendation_narrative,
        )
    elif route_key == "trade_hub":
        # Route-only handoff without a recommendation must not keep stale copy.
        canonical_recommendation_narrative.clear_narrative(st.session_state)
    if route_key == "trade_hub" and league_id:
        focus_player_id = _safe_text(player_id).strip()
        focus_mode = _safe_text(focus_mode, "target_player").strip() or "target_player"
        if focus_player_id:
            st.session_state[f"trade_hub_focus_player_id_{league_id}"] = focus_player_id
            st.session_state[f"trade_hub_focus_mode_{league_id}"] = focus_mode
        st.session_state[f"trade_hub_home_source_label_{league_id}"] = _safe_text(source_label)
        st.session_state[f"trade_hub_home_source_note_{league_id}"] = _safe_text(source_note)
    _capture_workflow_handoff(
        route_key,
        origin_page=_safe_text(origin_page, "dashboard"),
        origin_label=_safe_text(origin_label) or _safe_text(source_label, "Dashboard"),
        note=_safe_text(source_note),
        league_id=league_id,
        handoff_source=_safe_text(handoff_source, "dashboard_quick_action"),
    )
    _queue_platform_route(route_key, source=_safe_text(handoff_source, "dashboard_quick_action"))


def _open_daily_gm_briefing_item(item) -> None:
    """Open an existing workflow from a composed Today's Game Plan row."""

    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "game_plan_item_opened",
            props=launch_analytics.build_context_props(
                st.session_state,
                source_surface="daily_gm_briefing",
                extra={
                    "destination": _safe_text(getattr(item, "destination", "")),
                    "item_kind": _safe_text(getattr(item, "kind", "")),
                },
            ),
            state=st.session_state,
        )
    except Exception:
        pass
    destination = _safe_text(getattr(item, "destination", "")).strip() or "dashboard"
    narrative = getattr(item, "recommendation_narrative", None)
    _open_home_command_route(
        destination,
        player_id=_safe_text(getattr(item, "route_player_id", "")),
        focus_mode=_safe_text(getattr(item, "route_focus_mode", "")),
        source_label="Today's Game Plan",
        source_note=_safe_text(getattr(item, "reason", "")),
        recommendation_narrative=narrative,
        handoff_source="daily_gm_briefing",
        origin_page="dashboard",
        origin_label="Today's Game Plan",
    )


def _open_decision_change_event(event) -> None:
    """Open current destination truth for a historical decision-change event.

    Never resurrects stale recommendation meaning as if it were current.
    """

    destination = _safe_text(getattr(event, "destination", "")).strip()
    if not destination:
        return
    try:
        from modules import launch_analytics

        if decision_memory.experiment_enabled():
            launch_analytics.track_event(
                "decision_memory_event_opened",
                props=launch_analytics.build_context_props(
                    st.session_state,
                    source_surface="decision_memory",
                    extra={"destination": destination},
                ),
                state=st.session_state,
            )
    except Exception:
        pass
    _open_home_command_route(
        destination,
        player_id=_safe_text(getattr(event, "player_id", "")),
        focus_mode="",
        source_label="What Changed",
        source_note=_safe_text(getattr(event, "summary_detail", "")),
        recommendation_narrative=None,
        handoff_source="what_changed",
        origin_page="dashboard",
        origin_label="What Changed",
    )


def _render_team_card_tap_grid(*, html: str, key_prefix: str) -> dict:
    result = TEAM_CARD_TAP_COMPONENT(
        key=f"{key_prefix}_team_tap_grid",
        data={"html": html},
        width="stretch",
        height="content",
        on_clicked_change=lambda: None,
    )
    clicked = getattr(result, "clicked", None)
    return clicked if isinstance(clicked, dict) else {}


def _open_league_team_from_tap(clicked: dict) -> bool:
    roster_id = _safe_text(clicked.get("roster_id")).strip()
    if not roster_id:
        return False
    st.session_state["selected_team_roster_id"] = roster_id
    st.session_state["selected_team_name"] = _safe_text(clicked.get("team_name")).strip()
    st.session_state["_pending_selected_team_roster_id"] = roster_id
    _queue_platform_route("teams")
    return True


def _team_tap_markup(row) -> tuple[str, str]:
    roster_id = _safe_text(row.get("roster_id")).strip()
    if not roster_id:
        return "", ""
    team_name = _safe_text(row.get("team_name"), "Team")
    return (
        " team-card-tappable",
        f" data-roster-id='{escape(roster_id, quote=True)}'"
        + f" data-team-name='{escape(team_name, quote=True)}'"
        + " role='button' tabindex='0'"
        + f" aria-label='Open {escape(team_name, quote=True)} team page'",
    )


def render_player_scan_cards(
    player_df: pd.DataFrame,
    *,
    score_field: str,
    title: str,
    note: str,
    max_items: int = 8,
    show_slot: bool = False,
    status_label: str = "",
    status_fn=None,
    extra_tags_fn=None,
    note_fn=None,
    recommendation_narrative_fn=None,
    compact: bool = False,
    enable_quick_view: bool = False,
    quick_view_source_label: str = "",
    quick_view_key_prefix: str = "",
    show_inline_reason: bool = False,
    enable_feedback: bool = False,
    feedback_recommendation_type: str = "player_decision",
    show_header: bool = True,
    design_system: bool = True,
) -> None:
    player_cards.render_player_scan_cards(
        player_df,
        score_field=score_field,
        title=title,
        note=note,
        league_score_label=league_score_label,
        player_display_name=player_display_name,
        card_html_builder=_player_scan_card_html,
        compact_row_builder=_compact_player_row_html,
        render_tappable_player_html_callback=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        render_recommendation_feedback=render_recommendation_feedback,
        max_items=max_items,
        show_slot=show_slot,
        status_label=status_label,
        status_fn=status_fn,
        extra_tags_fn=extra_tags_fn,
        note_fn=note_fn,
        recommendation_narrative_fn=recommendation_narrative_fn,
        compact=compact,
        enable_quick_view=enable_quick_view,
        quick_view_source_label=quick_view_source_label,
        quick_view_key_prefix=quick_view_key_prefix,
        show_inline_reason=show_inline_reason,
        enable_feedback=enable_feedback,
        feedback_recommendation_type=feedback_recommendation_type,
        show_header=show_header,
        design_system=design_system,
    )


def render_draft_team_cards(
    summary: pd.DataFrame,
    *,
    title: str,
    note: str,
    max_items: int = 6,
    mode: str = "top_capital",
) -> None:
    def on_team_tap(clicked: dict) -> None:
        if _open_league_team_from_tap(clicked):
            st.rerun()

    player_cards.render_draft_team_cards(
        summary,
        title=title,
        note=note,
        format_score=_format_score,
        format_rank=_format_rank,
        team_tap_markup=_team_tap_markup,
        render_team_card_tap_grid=_render_team_card_tap_grid,
        on_team_tap=on_team_tap,
        render_recommendation_feedback=render_recommendation_feedback,
        max_items=max_items,
        mode=mode,
    )


def _candidate_note_map(items: list[str] | None) -> dict[str, str]:
    note_map: dict[str, str] = {}
    for item in items or []:
        text = _safe_text(item).strip()
        if not text:
            continue
        left, _, right = text.partition(" - ")
        name = left
        if " (" in left:
            name = left.split(" (", 1)[0].strip()
        note_map[name] = right.strip() or text
    return note_map


def _structured_candidate_note(candidate: dict | None) -> str:
    item = candidate if isinstance(candidate, dict) else {}
    name = _safe_text(item.get("player_name") or item.get("name"), "Player")
    position = _safe_text(item.get("position")).upper()
    chips = []
    tier = _safe_text(item.get("tier"))
    opportunity = _safe_text(item.get("opportunity_label"))
    role = _safe_text(item.get("role"))
    if tier:
        chips.append(tier)
    if opportunity:
        chips.append(opportunity)
    if role and role != "Flex":
        chips.append(role)
    meta = " | ".join(chips)
    reason = _safe_text(item.get("reason") or item.get("note"))
    base = name + (f" ({position})" if position else "")
    if meta and reason:
        return f"{base} - {meta}. {reason}"
    if meta:
        return f"{base} - {meta}"
    if reason:
        return f"{base} - {reason}"
    return base


def _structured_candidate_note_map(candidates: list[dict] | None) -> dict[str, str]:
    note_map: dict[str, str] = {}
    for item in candidates or []:
        player_id = _safe_text(item.get("player_id")).strip()
        if not player_id:
            continue
        note_map[player_id] = _safe_text(item.get("reason") or item.get("note") or _structured_candidate_note(item))
    return note_map


def _rows_for_candidate_player_ids(
    player_df: pd.DataFrame,
    player_ids: list[str] | tuple[str, ...] | set[str],
) -> pd.DataFrame:
    if player_df is None or player_df.empty or not player_ids:
        return pd.DataFrame(columns=getattr(player_df, "columns", []))
    ordered_ids = []
    seen: set[str] = set()
    for player_id in player_ids:
        pid = _safe_text(player_id).strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        ordered_ids.append(pid)
    if not ordered_ids:
        return pd.DataFrame(columns=player_df.columns)
    order_map = {player_id: idx for idx, player_id in enumerate(ordered_ids)}
    scan_df = player_df.copy()
    scan_df["_candidate_order"] = scan_df["player_id"].astype(str).map(order_map)
    matched = scan_df[scan_df["_candidate_order"].notna()].copy()
    if matched.empty:
        return matched.drop(columns=["_candidate_order"], errors="ignore")
    matched["_candidate_order"] = pd.to_numeric(matched["_candidate_order"], errors="coerce").fillna(9999)
    matched = matched.sort_values(["_candidate_order"], ascending=[True])
    return matched.drop(columns=["_candidate_order"], errors="ignore")


def _merge_structured_candidates(
    primary: list[dict] | None,
    secondary: list[dict] | None,
    *,
    max_items: int = 3,
) -> list[dict]:
    merged: list[dict] = []
    seen: set[str] = set()
    for group in (primary or [], secondary or []):
        for item in group if isinstance(group, list) else []:
            if not isinstance(item, dict):
                continue
            player_id = _safe_text(item.get("player_id")).strip()
            if not player_id or player_id in seen:
                continue
            seen.add(player_id)
            merged.append(item)
            if len(merged) >= max_items:
                return merged
    return merged


def _build_structured_decision_candidate(
    row,
    *,
    bucket: str,
    reason: str,
    priority: int,
    source: str = "roster_limit",
) -> dict:
    item = row.to_dict() if hasattr(row, "to_dict") else dict(row or {})
    position = _safe_text(item.get("position_key") or item.get("position")).upper()
    return {
        "player_id": _safe_text(item.get("player_id")).strip(),
        "player_name": player_display_name(item),
        "name": _safe_text(item.get("name")),
        "position": position,
        "team": _safe_text(item.get("team"), "FA"),
        "age": item.get("age"),
        "role": _safe_text(item.get("role_label") or item.get("role")),
        "tier": _safe_text(item.get("tier_label") or item.get("player_tier")),
        "player_tier": _safe_text(item.get("tier_label") or item.get("player_tier")),
        "opportunity_label": _safe_text(item.get("opportunity_label_text") or item.get("opportunity_label")),
        "reason": _safe_text(reason),
        "note": _safe_text(reason),
        "bucket": _safe_text(bucket),
        "priority": int(priority),
        "source": _safe_text(source, "roster_limit"),
        "starter_flag": bool(item.get("starter_flag")),
        "need_flag": bool(item.get("need_flag")),
        "surplus_flag": bool(item.get("surplus_flag")),
        "untouchable_flag": bool(item.get("untouchable_flag")),
        "score": float(pd.to_numeric(pd.Series([item.get("score_num", item.get("value_score", 0))]), errors="coerce").fillna(0).iloc[0]),
        "market_score": _safe_float(item.get("market_score_num", item.get("market_score", item.get("value", 0))), 0.0),
        "opportunity_score": _safe_float(item.get("opportunity_score_num", item.get("opportunity_score", 0)), 0.0),
        "roster_utility_score": _safe_float(item.get("roster_utility_score"), 0.0),
    }


def _rows_for_candidate_names(player_df: pd.DataFrame, names: list[str] | tuple[str, ...] | set[str]) -> pd.DataFrame:
    if player_df is None or player_df.empty or not names:
        return pd.DataFrame(columns=getattr(player_df, "columns", []))
    wanted = {_safe_text(name).strip() for name in names if _safe_text(name).strip()}
    if not wanted:
        return pd.DataFrame(columns=player_df.columns)
    scan_df = player_df.copy()
    scan_df["_display_name"] = scan_df.apply(player_display_name, axis=1)
    matched = scan_df[scan_df["_display_name"].isin(wanted) | scan_df["name"].astype(str).isin(wanted)].copy()
    return matched.drop(columns=["_display_name"], errors="ignore")


def _player_injury_chip(row) -> str:
    injury = _safe_text(row.get("injury_level"), "healthy").strip().lower()
    if not injury or injury == "healthy":
        return glyph_chip_html("Healthy", "success")
    if injury == "major":
        return glyph_chip_html("Injury Watch", "warning")
    return glyph_chip_html(tidy_label(injury), "warning")


def _player_detail_trade_outlook(
    *,
    player_row: pd.Series,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    my_roster_id,
    score_field: str,
    league_settings: dict,
    team_strategy: str,
    pick_score_multiplier: float,
) -> dict:
    default = {
        "headline": "No trade outlook available yet.",
        "subhead": "Load a league and roster to reuse live trade paths.",
        "items": ["Trade Hub uses your league's rosters and current values once a league is imported."],
        "tone": "reference",
    }
    if not selected_league_id or my_roster_id is None or player_row is None or getattr(player_row, "empty", False):
        return default

    df_summary = cached_team_direction_summary(
        df_players,
        selected_league_id,
        score_field=score_field,
        lineup_settings=league_settings,
    )
    profile = load_profile_key(username, selected_league_id) if username else {}
    role_map = {str(k): str(v) for k, v in st.session_state.get("role_map", {}).items()}
    untouchables = tuple(sorted(str(name) for name in profile.get("untouchables", [])))
    strategy_pick_multiplier = strategy_adjusted_pick_score_multiplier(pick_score_multiplier, team_strategy)
    roster_ids = {
        str(pid)
        for pid in get_roster_player_ids(selected_league_id, my_roster_id) or []
        if pid is not None
    }
    selected_player_id = _safe_text(player_row.get("player_id"))
    on_roster = selected_player_id in roster_ids
    mode = "my_player" if on_roster else "target_player"

    search_result = cached_player_trade_hub_ideas(
        df_players=apply_strategy_age_curve(df_players, team_strategy, score_field),
        league_id=selected_league_id,
        df_summary=df_summary,
        my_roster_id=my_roster_id,
        untouchables=untouchables,
        role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
        score_field=score_field,
        pick_score_multiplier=strategy_pick_multiplier,
        team_strategy=team_strategy,
        mode=mode,
        selected_player_id=selected_player_id,
        league_settings_items=draft_pick_valuation_settings_items(league_settings),
        max_ideas=2,
    )
    search_result = {
        **search_result,
        "ideas": enforce_cached_trade_ideas(
            search_result.get("ideas") or [],
            df_players=df_players,
            league_id=selected_league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            untouchables=untouchables,
        ),
    }
    ideas = enrich_trade_ideas_with_manager_tendencies(search_result.get("ideas") or [], df_summary)
    if not ideas:
        return default
    best = ideas[0]
    if on_roster:
        return {
            "headline": _asset_bundle_summary(best.get("receive_assets") or []),
            "subhead": _safe_text(best.get("partner_team_name"), "Trade partner"),
            "items": [
                _safe_text(best.get("hub_solution_reason"), _safe_text(best.get("rationale"))),
                _safe_text(best.get("hub_candidate_reason"), _safe_text(best.get("partner_trade_implication"))),
            ],
            "tone": "opportunity",
        }
    return {
        "headline": _safe_text(best.get("hub_path"), _safe_text(best.get("tag"), "Acquisition path")),
        "subhead": _safe_text(best.get("partner_team_name"), "Trade partner"),
        "items": [
            _safe_text(best.get("hub_target_fit_reason"), _safe_text(best.get("rationale"))),
            _safe_text(best.get("hub_partner_reason"), _safe_text(best.get("partner_trade_implication"))),
        ],
        "tone": "power",
    }


def _player_detail_row(df_players: pd.DataFrame, player_id: str) -> pd.Series | None:
    player_key = _safe_text(player_id).strip()
    if not player_key or df_players is None or df_players.empty:
        raw_row = _build_missing_rostered_player_row(
            player_key,
            cached_sleeper_player_directory().get(player_key),
        )
        return pd.Series(raw_row) if raw_row else None
    player_matches = df_players[df_players["player_id"].astype(str) == player_key].copy()
    if player_matches.empty:
        raw_row = _build_missing_rostered_player_row(
            player_key,
            cached_sleeper_player_directory().get(player_key),
        )
        return pd.Series(raw_row) if raw_row else None
    return player_matches.iloc[0]


def _player_summary_sentence(text: str, limit: int = 180) -> str:
    sentence = re.sub(r"\s+", " ", _safe_text(text)).strip(" .|-")
    if not sentence:
        return ""
    sentence = _truncate_text(sentence, limit).strip()
    if sentence and sentence[-1] not in ".!?":
        sentence += "."
    return sentence


def _player_profile_stat_groups(row: pd.Series) -> list[tuple[str, list[dict]]]:
    return player_profile_ui.player_profile_stat_groups(row)


def _player_quick_view_dense_section_html(
    title: str,
    items: list[dict],
    *,
    css_class: str = "player-quick-view-stat-section",
) -> str:
    if css_class == "player-quick-view-stat-section":
        normalized_items = tuple(
            player_quick_view.StatItem(
                label=_safe_text(item.get("label"), "Metric"),
                value=_safe_text(item.get("value"), ""),
                note=_safe_text(item.get("note"), ""),
                tone=_safe_text(item.get("tone"), "reference"),
            )
            for item in items
        )
        return player_quick_view.dense_section_html(title, normalized_items)
    rows_html = []
    for item in items:
        label = _safe_text(item.get("label"), "Metric")
        value = _safe_text(item.get("value"), "")
        note = _safe_text(item.get("note"), "")
        tone = _safe_text(item.get("tone"), "reference")
        rows_html.append(
            "<div class='player-quick-view-stat-row'>"
            + f"<div class='player-quick-view-stat-label'>{escape(label)}</div>"
            + "<div class='player-quick-view-stat-copy'>"
            + f"<div class='player-quick-view-stat-value dg-stat-tone-{escape(tone)}'>{escape(value)}</div>"
            + (f"<div class='player-quick-view-stat-note'>{escape(note)}</div>" if note else "")
            + "</div></div>"
        )
    return (
        f"<div class='{escape(css_class)}'>"
        + f"<div class='player-quick-view-stat-heading'>{escape(title)}</div>"
        + "<div class='player-quick-view-stat-grid'>"
        + "".join(rows_html)
        + "</div></div>"
    )


def render_player_profile_stat_sections(row: pd.Series, *, compact: bool = False) -> list[str]:
    stat_groups = _player_profile_stat_groups(row)
    for group_label, items in stat_groups:
        st.markdown(
            _player_quick_view_dense_section_html(group_label, items),
            unsafe_allow_html=True,
        )
    return [group_label for group_label, _ in stat_groups]


def _resolve_pqv_news_pool(*, allow_network: bool = True) -> list:
    """Resolve the league news pool for PQV without duplicate provider calls.

    Warm order: session → disk cache. Live RSS only when ``allow_network`` and
    both warm sources are empty.
    """

    news_pool = st.session_state.get("news", [])
    if news_pool:
        return list(news_pool)
    try:
        disk_pool = load_cached_news_pool() or []
    except Exception:
        disk_pool = []
    if disk_pool:
        st.session_state["news"] = disk_pool
        return list(disk_pool)
    if not allow_network:
        return []
    try:
        news_pool = fetch_news() or []
    except Exception:
        news_pool = []
    if news_pool:
        st.session_state["news"] = news_pool
    return list(news_pool)


def _pqv_news_presentation_key(player_id: str) -> str:
    return f"pqv_news_presentation__{_safe_text(player_id) or 'unknown'}"


def _get_pqv_news_presentation(player_id: str) -> dict | None:
    from modules.news import NEWS_CACHE_TTL_SECONDS

    bundle = st.session_state.get(_pqv_news_presentation_key(player_id))
    if not isinstance(bundle, dict):
        return None
    saved_at = float(bundle.get("saved_at") or 0)
    if saved_at <= 0:
        return None
    import time as _time

    if _time.time() - saved_at > float(NEWS_CACHE_TTL_SECONDS):
        return None
    return bundle


def _set_pqv_news_presentation(
    player_id: str,
    *,
    items: list[player_quick_view.NewsItem],
    status: str,
) -> dict:
    import time as _time

    bundle = {
        "items": list(items),
        "status": _safe_text(status, "ok"),
        "saved_at": _time.time(),
    }
    st.session_state[_pqv_news_presentation_key(player_id)] = bundle
    return bundle


def _player_quick_view_news_items(
    row,
    *,
    max_items: int = 4,
    allow_network: bool = True,
) -> list[player_quick_view.NewsItem]:
    news_pool = _resolve_pqv_news_pool(allow_network=allow_network)
    player_news = (
        filter_news_for_players(news_pool, [player_display_name(row)], {_safe_text(row.get("team"))})
        if news_pool
        else []
    )
    player_news = curate_player_news(player_news, max_items=max_items) if player_news else []

    items: list[player_quick_view.NewsItem] = []
    for item in player_news:
        headline = _safe_text(item.get("title")).strip()
        if not headline:
            continue
        source = player_quick_view.normalize_news_source(item.get("source"))
        freshness = _safe_text(relative_news_time(item, compact=True)).strip()
        snippet = _safe_text(build_quick_news_summary(item)).strip()
        if snippet and snippet.casefold() == headline.casefold():
            snippet = ""
        items.append(
            player_quick_view.NewsItem(
                headline=_truncate_text(headline, 140),
                source=source,
                freshness=freshness,
                snippet=_truncate_text(snippet, 180) if snippet else "",
                url=player_quick_view.safe_news_url(item.get("link")),
                summary=_truncate_text(headline, 140),
            )
        )
    return items


def _paint_pqv_news_bundle(bundle: dict, *, include_shell: bool = False) -> None:
    status = _safe_text(bundle.get("status"), "ok")
    items = bundle.get("items") or []
    player_quick_view.render_news(
        list(items),
        include_shell=include_shell,
        status=status,
        default_limit=3,
    )


def _render_pqv_recent_news_auto(row, *, player_id: str) -> None:
    """Auto-hydrate Recent News after first-useful without a Load button.

    Streamlit cannot paint mid-script. Network RSS therefore runs inside a
    short-lived ``st.fragment(run_every=…)`` after the first fragment tick so
    identity/recommendation/rank/value can finish the parent render first.
    Warm session/disk pools render immediately with zero provider calls.
    """

    st.markdown(
        player_quick_view.dossier_section_heading_html(
            "Recent News",
            "Automatically loaded player headlines.",
        ),
        unsafe_allow_html=True,
    )

    cached = _get_pqv_news_presentation(player_id)
    if cached is not None:
        _paint_pqv_news_bundle(cached, include_shell=False)
        interaction_latency.mark_interaction_milestone("pqv_news_complete")
        return

    # Warm path: session or disk only — never block first-useful on live RSS.
    warm_pool = _resolve_pqv_news_pool(allow_network=False)
    if warm_pool:
        try:
            items = _player_quick_view_news_items(row, max_items=4, allow_network=False)
            bundle = _set_pqv_news_presentation(
                player_id,
                items=items,
                status="ok" if items else "empty",
            )
        except Exception:
            bundle = _set_pqv_news_presentation(player_id, items=[], status="error")
        _paint_pqv_news_bundle(bundle, include_shell=False)
        interaction_latency.mark_interaction_milestone("pqv_news_complete")
        return

    done_key = f"pqv_news_network_done_{_safe_text(player_id) or 'unknown'}"
    armed_key = f"pqv_news_fragment_armed_{_safe_text(player_id) or 'unknown'}"

    if st.session_state.get(done_key):
        bundle = _get_pqv_news_presentation(player_id) or {
            "items": [],
            "status": "error",
        }
        _paint_pqv_news_bundle(bundle, include_shell=False)
        return

    if not hasattr(st, "fragment"):
        interaction_latency.mark_interaction_milestone("pqv_news_start")
        try:
            items = _player_quick_view_news_items(row, max_items=4, allow_network=True)
            bundle = _set_pqv_news_presentation(
                player_id,
                items=items,
                status="ok" if items else "empty",
            )
        except Exception:
            bundle = _set_pqv_news_presentation(player_id, items=[], status="error")
        st.session_state[done_key] = True
        _paint_pqv_news_bundle(bundle, include_shell=False)
        interaction_latency.mark_interaction_milestone("pqv_news_complete")
        return

    @st.fragment(run_every="0.6s")
    def _pqv_news_hydrate_fragment() -> None:
        if st.session_state.get(done_key):
            bundle = _get_pqv_news_presentation(player_id) or {
                "items": [],
                "status": "error",
            }
            _paint_pqv_news_bundle(bundle, include_shell=False)
            return
        if not st.session_state.get(armed_key):
            # First fragment tick shares the parent render — skip network so
            # first-useful content can reach the browser before RSS work.
            st.session_state[armed_key] = True
            interaction_latency.mark_interaction_milestone("pqv_news_start")
            player_quick_view.render_news([], include_shell=False, status="loading")
            return
        interaction_latency.mark_interaction_milestone("pqv_news_start")
        try:
            items = _player_quick_view_news_items(row, max_items=4, allow_network=True)
            _set_pqv_news_presentation(
                player_id,
                items=items,
                status="ok" if items else "empty",
            )
        except Exception:
            _set_pqv_news_presentation(player_id, items=[], status="error")
        st.session_state[done_key] = True
        interaction_latency.mark_interaction_milestone("pqv_news_complete")
        # Remount without run_every so the fragment timer does not keep polling.
        st.rerun()

    _pqv_news_hydrate_fragment()


@runtime_trace.traced("player_fit_construction", phase="player_fit_construction")
def build_player_roster_needs_context(
    df_players: pd.DataFrame,
    *,
    selected_league_id: str,
    my_roster_id,
    score_field: str,
    league_settings: dict | None,
) -> dict:
    """Build the shared player-fit roster context once for a rendered profile."""

    if not selected_league_id or my_roster_id is None:
        return {
            "roster_player_ids": set(),
            "roster_df": pd.DataFrame(),
            "metrics": {},
            "assessment": None,
        }
    roster_player_ids = {
        str(player_id)
        for player_id in get_roster_player_ids(
            selected_league_id,
            my_roster_id,
        )
        or []
        if player_id is not None
    }
    roster_df = df_players[
        df_players["player_id"].astype(str).isin(roster_player_ids)
    ].copy()
    if roster_df.empty:
        return {
            "roster_player_ids": roster_player_ids,
            "roster_df": roster_df,
            "metrics": {},
            "assessment": None,
        }
    summary = cached_team_direction_summary(
        df_players,
        selected_league_id,
        score_field=score_field,
        lineup_settings=league_settings,
    )
    metrics = get_team_vs_league(summary, my_roster_id)
    lineup_df = suggest_optimal_lineup(roster_df, league_settings)
    assessment = build_team_needs_assessment(
        roster_df,
        metrics,
        league_settings,
        lineup_df=lineup_df,
    )
    return {
        "roster_player_ids": roster_player_ids,
        "roster_df": roster_df,
        "metrics": metrics,
        "assessment": assessment,
    }


def render_player_quick_view_content(
    *,
    player_row: pd.Series,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    pick_score_multiplier: float,
    source_label: str = "",
    source_note: str = "",
    status_label: str = "",
    recommendation_narrative=None,
) -> None:
    row = player_row
    player_id = _safe_text(row.get("player_id")).strip()
    raw_name = _safe_text(row.get("name"), _safe_text(row.get("label"), "Player")).strip()
    clean_name = _clean_player_name_for_display(raw_name)
    image_url = cached_headshot_data_url(player_id) if player_id else ""
    avatar = avatar_html(
        image_url,
        _asset_initials(raw_name or "Player"),
        css_class="player-detail-avatar player-quick-view-avatar",
    )

    player_roster_context, _fit_hit = interaction_latency.get_or_build_fit_context(
        st.session_state,
        signature=interaction_latency.build_fit_context_signature(
            league_id=selected_league_id,
            roster_id=my_roster_id,
            score_field=score_field,
            league_settings_key=league_value_settings_key(league_settings or {}),
            frame_signature=f"{len(df_players)}|{score_field}",
        ),
        builder=lambda: build_player_roster_needs_context(
            df_players,
            selected_league_id=selected_league_id,
            my_roster_id=my_roster_id,
            score_field=score_field,
            league_settings=league_settings,
        ),
    )
    on_roster = player_id in player_roster_context["roster_player_ids"]
    role_map = {str(k): str(v) for k, v in st.session_state.get("role_map", {}).items()}
    role_label = role_map.get(player_id, "")
    profile = load_profile_key(username, selected_league_id) if username and selected_league_id else {}
    untouchables = {
        _safe_text(name).strip()
        for name in profile.get("untouchables", [])
        if _safe_text(name).strip()
    }
    is_untouchable = raw_name in untouchables

    source_label_key = _safe_text(source_label).strip().casefold()
    if is_untouchable:
        roster_classification = "Untouchable"
        roster_tone = "premium"
    elif on_roster and role_label == "Core":
        roster_classification = "Core"
        roster_tone = "premium"
    elif on_roster and role_label == "Flex":
        roster_classification = "Flex"
        roster_tone = "primary"
    elif on_roster and role_label == "Bench":
        roster_classification = "Bench"
        roster_tone = "warning"
    elif on_roster:
        roster_classification = "On Roster"
        roster_tone = "primary"
    elif "waiver" in source_label_key:
        roster_classification = "Waiver Target"
        roster_tone = "success"
    else:
        roster_classification = "League Target"
        roster_tone = "primary"

    primary_status = _canonical_player_status(status_label)
    if not primary_status:
        if is_untouchable:
            primary_status = "Untouchable"
        elif on_roster and role_label == "Core":
            primary_status = "Core Asset"
        elif on_roster and role_label in {"Flex", "Bench"}:
            primary_status = "Hold"
        else:
            primary_status = _resolve_player_status(
                row,
                extra_tags=[role_label],
            )["label"]

    tier_label = _safe_text(row.get("player_tier"), "Developmental")
    opportunity_label = _safe_text(row.get("opportunity_label"), "Opportunity unclear")
    position = _safe_text(row.get("position"), "Player")
    team = _safe_text(row.get("team"), "FA")
    age_text = _format_age(row.get("age")) or "N/A"
    value_label = league_score_label(score_field)
    value_score = _format_score(row.get(score_field, row.get("value_score", 0)))
    dynasty_score = _format_score(row.get("dynasty_score", row.get(score_field, 0)))
    detail_ranks = canonical_player_ranking.format_detail_ranks(
        overall_rank=row.get("canonical_overall_rank", row.get("overall_rank")),
        position_rank=row.get("canonical_position_rank", row.get("position_rank")),
        position=position,
        scoring_format=(
            row.get("rank_scoring_format")
            or (league_settings or {}).get("scoring_format")
        ),
        unavailable_reason=row.get("rank_unavailable_reason"),
    )
    overall_rank = _safe_positive_int(
        row.get("canonical_overall_rank", row.get("overall_rank")),
        0,
    ) or _safe_positive_int(row.get("rank"), 0)
    overall_rank_label = detail_ranks["overall_display"]
    position_rank = _safe_positive_int(
        row.get("canonical_position_rank", row.get("position_rank")),
        0,
    )
    position_rank_label = detail_ranks["position_display"]
    rank_format_label = _safe_text(detail_ranks.get("format"))
    market_score = _format_score(row.get("market_score", row.get("value", 0)))
    opportunity_score = _format_score(row.get("opportunity_score", 0))
    scarcity_score = _format_score(row.get("scarcity_score", 0))
    role_score = _format_score(row.get("role_score", 0))
    age_score_raw = row.get("age_score") if "age_score" in row.index else None
    age_score_value = pd.to_numeric(pd.Series([age_score_raw]), errors="coerce").iloc[0]
    age_metric_is_native = pd.notna(age_score_value)
    age_metric_label = "Age Score" if age_metric_is_native else "Age Lens"
    age_metric_value = _format_score(age_score_raw if age_metric_is_native else row.get("age_penalty", 0))
    age_metric_note = "Age-curve contribution." if age_metric_is_native else "Age-curve adjustment vs market."
    opportunity_confidence = _safe_positive_int(row.get("opportunity_confidence"), 0)
    projected_starter = bool(row.get("projected_starter"))
    workload_trend = _safe_text(row.get("workload_trend"), "Unknown")
    opportunity_source_flags = {
        part.strip().lower()
        for part in str(row.get("opportunity_source_flags") or "").split("|")
        if part.strip()
    }
    injury_level_text = tidy_label(_safe_text(row.get("injury_level"), "healthy"))
    injury_note = _safe_text(row.get("injury_status") or row.get("status"), "No active injury tag")
    injury_chip_class = "healthy" if _safe_text(row.get("injury_level"), "healthy") == "healthy" else ""

    summary_candidates: list[str] = []
    if source_note:
        summary_candidates.append(source_note)
    base_summary = (
        _safe_text(row.get("opportunity_explanation"))
        or _safe_text(row.get("manager_trade_implication"))
        or _safe_text(row.get("injury_replacement_note"))
    )
    if base_summary:
        summary_candidates.append(base_summary)

    if _safe_text(row.get("injury_level"), "healthy") != "healthy":
        summary_candidates.append(f"Health watch: {injury_note}.")

    summary_sentences: list[str] = []
    seen_sentences: set[str] = set()
    for candidate in summary_candidates:
        sentence = _player_summary_sentence(candidate)
        if not sentence:
            continue
        sentence_key = sentence.casefold()
        if sentence_key in seen_sentences:
            continue
        seen_sentences.add(sentence_key)
        summary_sentences.append(sentence)
        if len(summary_sentences) >= 3:
            break
    if not summary_sentences:
        summary_sentences = ["No concise player summary is available yet."]

    fit_items = ["Select a league and roster to evaluate direct team fit."]
    fit_tone = "reference"
    strategy_label = team_strategy_label(active_team_strategy)
    if player_roster_context["assessment"] is not None:
        team_metrics = player_roster_context["metrics"]
        team_needs_assessment = player_roster_context["assessment"]
        strengths = [
            str(pos).upper()
            for pos in (team_metrics or {}).get("strengths", []) or []
        ]
        player_pos = position.upper()
        fit_items = []
        if on_roster:
            fit_items.append(
                "Already on your roster under the current league context."
            )
            if role_label:
                fit_items.append(f"Current roster role: {role_label}.")
            if player_pos in strengths:
                fit_items.append(
                    f"{player_pos} is currently a roster strength, so this player can be used as consolidation leverage."
                )
            else:
                fit_items.append(
                    player_fit_context(
                        player_pos,
                        team_needs_assessment,
                        on_roster=True,
                    )["message"]
                )
            fit_tone = "strength"
        else:
            fit_context = player_fit_context(
                player_pos,
                team_needs_assessment,
            )
            fit_items.append(fit_context["message"])
            fit_tone = fit_context["tone"]
            if player_pos in strengths:
                fit_items.append(
                    f"{player_pos} is already a roster strength, so the fit is more luxury than need."
                )
            fit_items.append(f"Active team strategy: {strategy_label}.")
    context_items = [
        item for item in fit_items
        if _safe_text(item)
        and item not in {"Already on your roster under the current league context."}
    ]
    if not context_items:
        context_items = fit_items[:1] if fit_items else ["No roster-context read is available yet."]

    opportunity_note_parts = [opportunity_label]
    if projected_starter:
        opportunity_note_parts.append("Projected starter")
    elif workload_trend and workload_trend.lower() != "unknown":
        opportunity_note_parts.append(workload_trend)
    generic_opportunity_confidence = (
        opportunity_confidence >= 84
        and projected_starter
        and workload_trend.lower() == "stable"
        and opportunity_source_flags.issubset({"sleeper_depth", "depth_chart_order", "usage_unavailable"})
    )
    show_opportunity_confidence = opportunity_confidence > 0 and not generic_opportunity_confidence
    if show_opportunity_confidence:
        opportunity_note_parts.append(f"{opportunity_confidence}/100 role confidence")
    opportunity_metric_note = _truncate_text(" | ".join(opportunity_note_parts[:3]), 76)

    tag_specs = [
        (tier_label, tier_chip_html(tier_label)),
        (opportunity_label, glyph_chip_html(opportunity_label, "success")),
    ]
    if roster_classification.casefold() not in {primary_status.casefold(), role_label.casefold()}:
        tag_specs.append((roster_classification, glyph_chip_html(roster_classification, roster_tone)))
    if role_label and role_label.casefold() not in {primary_status.casefold(), roster_classification.casefold()}:
        tag_specs.append((role_label, glyph_chip_html(role_label, "premium" if role_label == "Core" else "primary")))

    quick_view_tag_html: list[str] = []
    seen_tag_keys: set[str] = set()
    for tag_key, tag_html in tag_specs:
        normalized_tag_key = _safe_text(tag_key).strip().casefold()
        if not normalized_tag_key or normalized_tag_key in seen_tag_keys:
            continue
        seen_tag_keys.add(normalized_tag_key)
        quick_view_tag_html.append(tag_html)
        if len(quick_view_tag_html) >= 3:
            break

    context_tile_tone = (
        "power"
        if on_roster
        else "opportunity"
        if fit_tone == "opportunity"
        else "strategy"
    )
    show_action_tile = not (on_roster and primary_status in {"Core Asset", "Untouchable"})
    if on_roster:
        if primary_status == "Trade Candidate":
            action_value = "Shop"
        elif primary_status == "Drop Candidate":
            action_value = "Drop"
        elif primary_status == "Move Now":
            action_value = "Use Exempt Slot"
        else:
            action_value = "Hold"
    else:
        action_value = "Waiver Add" if "waiver" in source_label_key else "Trade Target" if fit_tone == "opportunity" else "Monitor"

    action_note = ""
    seen_action_notes: set[str] = set()
    for candidate in [_safe_text(source_note), *context_items, *summary_sentences]:
        cleaned_candidate = _safe_text(candidate).strip()
        if not cleaned_candidate:
            continue
        candidate_key = cleaned_candidate.casefold()
        if candidate_key in seen_action_notes or candidate_key == _safe_text(action_value).strip().casefold():
            continue
        seen_action_notes.add(candidate_key)
        action_note = cleaned_candidate
        break
    if not action_note:
        action_note = (
            "Foundation piece under the current roster lens."
            if on_roster and primary_status in {"Core Asset", "Untouchable"}
            else "Still worth the roster spot under your current strategy focus."
            if on_roster and action_value == "Hold"
            else "Market value still beats a pure cut decision."
            if action_value == "Shop"
            else "Clearest drop candidate under current roster pressure."
            if action_value == "Drop"
            else "Fits a current roster need or opportunity opening."
            if action_value in {"Waiver Add", "Trade Target"}
            else "No forced action yet under the current roster lens."
        )

    action_tile_tone = (
        "risk"
        if action_value in {"Drop", "Shop"}
        else "opportunity"
        if action_value in {"Waiver Add", "Trade Target", "Use Exempt Slot"}
        else "strategy"
    )

    summary_text = " ".join(summary_sentences[:2])

    metric_cards = [
        (
            "Market Score",
            market_score,
            f"Scarcity {scarcity_score} | Role {role_score}",
        ),
        (
            "Opportunity Score",
            opportunity_score,
            opportunity_metric_note,
        ),
        (
            age_metric_label,
            age_metric_value,
            age_metric_note,
        ),
    ]
    if show_opportunity_confidence:
        confidence_note = "Role-based opportunity confidence from the current depth-chart signal."
        if "team_competition" in opportunity_source_flags:
            confidence_note = "Role confidence is being shaped by credible competition inside the current team room."
        elif "injury_overlay" in opportunity_source_flags:
            confidence_note = "Role confidence is being adjusted for the current injury overlay."
        elif "market_inference" in opportunity_source_flags or "depth_unknown" in opportunity_source_flags:
            confidence_note = "Role confidence is partially inferred because the direct depth signal is incomplete."
        metric_cards.append(
            (
                "Opportunity Confidence",
                f"{opportunity_confidence}/100",
                confidence_note,
            )
        )
    detail_rows = [
        ("Current Lens", f"{value_label} {value_score}", f"Dynasty {dynasty_score} | Market {market_score}"),
        ("Identity", f"{position} | {team} | Age {age_text}", tier_label),
        ("Roster Role", roster_classification, opportunity_metric_note),
        ("Health", injury_level_text, _truncate_text(injury_note, 92) or "No active injury tag"),
        ("Team Context", " / ".join(context_items[:2]), f"Active strategy: {strategy_label}"),
    ]
    detail_rows.extend(metric_cards)
    advanced_detail_rows_html = (
        "<div class='player-quick-view-detail-list'>"
        + "".join(
            "<div class='player-quick-view-detail-row'>"
            + f"<div class='player-quick-view-detail-label'>{escape(label)}</div>"
            + "<div class='player-quick-view-detail-copy'>"
            + f"<div class='player-quick-view-detail-value'>{escape(value)}</div>"
            + f"<div class='player-quick-view-detail-note'>{escape(note)}</div>"
            + "</div>"
            + "</div>"
            for label, value, note in detail_rows
        )
        + "</div>"
    )
    quick_view_stats = player_quick_view.build_stats_view(row)
    fantasy_ppg = ""
    if quick_view_stats.seasons:
        fantasy_ppg = next(
            (
                item.value
                for item in quick_view_stats.seasons[0].fantasy
                if "PPG" in item.label.upper()
            ),
            "",
        )
    dossier_snapshot = player_quick_view.DossierSnapshot(
        dynasty_value=dynasty_score,
        rank=overall_rank_label,
        position_rank=position_rank_label,
        fantasy_ppg=fantasy_ppg,
        health=injury_level_text,
        tier=tier_label,
        recommendation=action_value if show_action_tile else primary_status,
        trend=workload_trend,
        recommendation_note=_truncate_text(
            action_note if show_action_tile else summary_text,
            160,
        ),
        recommendation_tone=action_tile_tone,
        scoring_format=rank_format_label,
    )
    current_season = _safe_positive_int(row.get("stats_season"), 0) or None
    history_state_key = f"player_dossier_history_{player_id}"
    history_expanded_key = f"player_dossier_history_expanded_{player_id}"
    current_resume = player_history.build_career_resume(
        [row.to_dict()],
        position=position,
        current_season=current_season,
        source_note="Verified current regular-season aggregate.",
    )
    career_years_exp = None
    try:
        player_metadata_early = (
            cached_sleeper_player_directory().get(player_id, {}) if player_id else {}
        )
        raw_exp = player_metadata_early.get("years_exp")
        if raw_exp is not None and str(raw_exp).strip() != "":
            career_years_exp = int(float(raw_exp))
    except Exception:
        career_years_exp = None
    stored_resume = st.session_state.get(history_state_key)
    history_expanded = bool(st.session_state.get(history_expanded_key, False))
    career_resume = (
        stored_resume
        if history_expanded and isinstance(stored_resume, player_history.CareerResume)
        else current_resume
    )

    quick_view_html = (
        "<div class='player-quick-view-shell dg-quick-view-panel'>"
        + "<div class='player-quick-view-header-band player-quick-view-hero'>"
        + avatar
        + "<div class='player-quick-view-copy'>"
        + (f"<div class='player-quick-view-source'>{escape(source_label)}</div>" if source_label else "")
        + f"<h3 class='player-quick-view-name'>{escape(clean_name)}</h3>"
        + f"<div class='player-quick-view-meta'>{escape(position)} | {escape(team)} | Age {escape(age_text)}</div>"
        + "<div class='player-quick-view-primary-row'>"
        + player_status_pill_html(primary_status)
        + f"<div class='player-quick-view-injury-pill {injury_chip_class}'>{escape(injury_level_text)} | {escape(_truncate_text(injury_note, 48) or 'No active injury tag')}</div>"
        + "</div>"
        + "<div class='player-quick-view-tag-group'>"
        + "".join(quick_view_tag_html)
        + "</div>"
        + "</div></div></div>"
    )
    st.markdown(quick_view_html, unsafe_allow_html=True)
    bound_narrative = None
    if recommendation_narrative is not None:
        bound_narrative = (
            recommendation_narrative
            if isinstance(
                recommendation_narrative,
                canonical_recommendation_narrative.CanonicalRecommendationNarrative,
            )
            else canonical_recommendation_narrative.CanonicalRecommendationNarrative.from_dict(
                recommendation_narrative
            )
        )
        if bound_narrative is not None:
            canonical_recommendation_narrative.bind_narrative(
                st.session_state,
                bound_narrative,
            )
    if bound_narrative is None:
        bound_narrative = (
            canonical_recommendation_narrative.resolve_narrative_for_player(
                st.session_state,
                player_id=player_id,
                league_id=_safe_text(selected_league_id),
                roster_id=_safe_text(my_roster_id),
                valuation_lens=_safe_text(score_field),
            )
        )
    if bound_narrative is None:
        # No matching recommendation provenance: neutral player analysis only.
        # Do not synthesize Shop/Hold/Monitor as an active recommendation.
        bound_narrative = (
            canonical_recommendation_narrative.build_neutral_player_narrative(
                row,
                league_id=_safe_text(selected_league_id),
                roster_id=_safe_text(my_roster_id),
                valuation_lens=_safe_text(score_field),
                source_surface=_safe_text(source_label, "player_quick_view"),
                analysis_note=_safe_text(source_note) or summary_text,
                roster_context=_safe_text(context_items[0]) if context_items else "",
            )
        )
    pqv_story = bound_narrative.pqv_presentation(limit=160)
    st.markdown(
        player_quick_view.recommendation_context_html(
            pqv_story["summary"],
            pqv_story["context"],
            action=pqv_story["action"],
            active_recommendation=bound_narrative.is_active_recommendation,
            recommendation_id=bound_narrative.recommendation_id,
        ),
        unsafe_allow_html=True,
    )
    # Keep local recommendation labels aligned with the canonical story when active.
    if bound_narrative.is_active_recommendation and bound_narrative.action:
        recommendation_action = bound_narrative.action
        action_value = bound_narrative.action
        action_note = bound_narrative.reason
        show_action_tile = True
        concise_rationale = bound_narrative.shorten("reason", 160)
    else:
        recommendation_action = primary_status
        show_action_tile = False
        concise_rationale = _truncate_text(summary_text, 160)

    compact_rank = canonical_player_ranking.format_compact_rank(
        row.get("canonical_overall_rank", row.get("overall_rank")),
        row.get("canonical_position_rank", row.get("position_rank")),
        position,
        unavailable_reason=row.get("rank_unavailable_reason"),
    )
    rank_strip = player_quick_view.rank_strip_html(
        overall_display=compact_rank,
        position_display="",
        scoring_format=rank_format_label,
        dynasty_value=value_score,
    )
    if rank_strip:
        st.markdown(rank_strip, unsafe_allow_html=True)
    st.markdown(
        player_quick_view.snapshot_html(dossier_snapshot, include_recommendation=False),
        unsafe_allow_html=True,
    )
    # First useful PQV: identity + ranks + value + recommendation + health + PPG.
    interaction_latency.mark_interaction_milestone("pqv_first_useful")

    season_summary_html = player_quick_view.current_season_summary_html(quick_view_stats)
    snapshot_col, news_col = st.columns(2)
    with snapshot_col:
        if season_summary_html:
            st.markdown(season_summary_html, unsafe_allow_html=True)
        else:
            st.caption("Current season production is not available for this player.")
    with news_col:
        _render_pqv_recent_news_auto(row, player_id=player_id)

    if not (
        history_expanded and isinstance(stored_resume, player_history.CareerResume)
    ):
        # Local disk cache only — after first-useful; fail soft.
        try:
            position_lookup = {
                _safe_text(candidate.get("player_id")): _safe_text(candidate.get("position"))
                for _, candidate in df_players[["player_id", "position"]].iterrows()
                if _safe_text(candidate.get("player_id"))
            }
            career_resume = player_history.load_cached_career_resume(
                player_id=player_id,
                current_row=row.to_dict(),
                position_lookup=position_lookup,
            )
            st.session_state[history_state_key] = career_resume
        except Exception:
            career_resume = current_resume

    st.markdown(
        player_quick_view.career_resume_html(
            career_resume,
            expanded=False,
            position=position,
            years_exp=career_years_exp,
        ),
        unsafe_allow_html=True,
    )

    quick_view_context_items = [
        {
            "label": "Roster Context",
            "value": roster_classification if on_roster else "League Target",
            "note": _truncate_text(context_items[0], 120),
            "tone": context_tile_tone,
        }
    ]
    if show_action_tile:
        quick_view_context_items.append(
            {
                "label": "Recommendation",
                "value": action_value,
                "note": _truncate_text(action_note, 120),
                "tone": action_tile_tone,
            }
        )

    more_key = f"pqv_more_details_open_{player_id or 'unknown'}"
    more_open = bool(st.session_state.get(more_key, False))

    def _toggle_pqv_more_details() -> None:
        st.session_state[more_key] = not bool(st.session_state.get(more_key, False))

    st.button(
        "Hide details" if more_open else "More details",
        key=f"pqv_more_details_toggle_{player_id or 'unknown'}",
        use_container_width=True,
        on_click=_toggle_pqv_more_details,
    )
    if more_open:
        st.caption(
            f"Active format: {_safe_text(rank_format_label) or 'unknown'}. "
            f"{canonical_player_ranking.RANK_METHODOLOGY}"
        )
        if overall_rank_label == "Rank unavailable":
            st.caption(
                _safe_text(
                    detail_ranks.get("unavailable_reason"),
                    "Rank unavailable for this player.",
                )
            )
        else:
            st.caption(
                "To compare PPR vs Half-PPR vs Standard, use League scoring overrides. "
                "Ranks refresh for the selected format without changing recommendation logic."
            )
        player_quick_view.render_current_season(quick_view_stats)

        position_lookup = {
            _safe_text(candidate.get("player_id")): _safe_text(candidate.get("position"))
            for _, candidate in df_players[["player_id", "position"]].iterrows()
            if _safe_text(candidate.get("player_id"))
        }
        try:
            full_resume = player_history.load_cached_career_resume(
                player_id=player_id,
                current_row=row.to_dict(),
                position_lookup=position_lookup,
            )
        except Exception:
            full_resume = career_resume
        st.session_state[history_state_key] = full_resume
        st.session_state[history_expanded_key] = True
        st.markdown(
            player_quick_view.career_resume_html(
                full_resume,
                expanded=True,
                position=position,
                years_exp=career_years_exp,
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            player_quick_view.career_timeline_html(
                full_resume,
                expanded=True,
                include_achievements=False,
            ),
            unsafe_allow_html=True,
        )

        player_metadata = (
            cached_sleeper_player_directory().get(player_id, {}) if player_id else {}
        )
        executive_snapshot = player_quick_view.build_executive_snapshot(
            row.to_dict(),
            player_metadata,
        )
        executive_html = player_quick_view.executive_snapshot_html(executive_snapshot)
        if executive_html:
            st.markdown(executive_html, unsafe_allow_html=True)
        st.markdown(
            _player_quick_view_dense_section_html(
                "Roster Read",
                quick_view_context_items,
                css_class="player-quick-view-context-section",
            ),
            unsafe_allow_html=True,
        )
        st.markdown(advanced_detail_rows_html, unsafe_allow_html=True)
        player_quick_view.render_college_production(quick_view_stats)
        player_quick_view.render_developer_diagnostics(row)
        interaction_latency.mark_interaction_milestone("pqv_secondary_ready")

    st.markdown("<div class='player-quick-view-actions-label'>Actions</div>", unsafe_allow_html=True)
    trade_hub_disabled = not selected_league_id or my_roster_id is None
    if st.button(
        "Open in Trade Hub",
        key=f"player_quick_view_trade_hub_{player_id}",
        use_container_width=True,
        type="primary",
        disabled=trade_hub_disabled,
    ):
        # Clear dialog-owned state before routing so the destination rerun
        # cannot reopen the quick-view dialog over Trade Hub.
        _clear_player_quick_view()
        _open_trade_hub_for_player_focus(
            player_row=row,
            selected_league_id=selected_league_id,
            my_roster_id=my_roster_id,
            username=username,
        )

    secondary_left, secondary_right = st.columns(2)
    with secondary_left:
        if on_roster:
            untouchable_disabled = not (username and selected_league_id)
            untouchable_label = "Remove Untouchable" if is_untouchable else "Mark as Untouchable"
            if st.button(
                untouchable_label,
                key=f"player_quick_view_untouchable_{player_id}",
                use_container_width=True,
                disabled=untouchable_disabled,
                on_click=_toggle_player_untouchable,
                kwargs={
                    "player_row": row,
                    "username": username,
                    "selected_league_id": selected_league_id,
                },
            ):
                pass
    with secondary_right:
        gm_targets_ui.render_pqv_target_control(
            session=st.session_state,
            league_id=_safe_text(selected_league_id),
            player_id=player_id,
            source_surface="player_quick_view",
        )

    try:
        from modules import share_recommendation_cards as share_cards
        from modules import share_recommendation_ui

        if share_cards.experiment_enabled():
            def _rank_int(label: object) -> int | None:
                text = _safe_text(label)
                if not text or "unavailable" in text.casefold():
                    return None
                digits = "".join(ch for ch in text if ch.isdigit())
                try:
                    return int(digits) if digits else None
                except ValueError:
                    return None

            share_card = share_cards.build_player_share_card(
                display_name=_safe_text(clean_name, "Player"),
                player_id=_safe_text(player_id),
                position=_safe_text(position),
                team=_safe_text(team),
                overall_rank=_rank_int(overall_rank_label),
                position_rank=_rank_int(position_rank_label),
                scoring_format=_safe_text(rank_format_label),
                narrative=bound_narrative,
                source_surface="player_quick_view",
                value_label=_safe_text(value_label),
            )
            with st.expander("Share", expanded=False):
                share_recommendation_ui.render_share_controls(
                    share_card,
                    key=f"pqv_share_{_safe_text(player_id)}",
                    state=st.session_state,
                )
    except Exception:
        pass

    with st.expander("Feedback", expanded=False):
        render_recommendation_feedback(
            page="player_quick_view",
            surface="Player Quick View Recommendation",
            recommendation_type="player_action",
            key_prefix=f"player_quick_view_feedback_{player_id}",
            recommendation_title=action_value if show_action_tile else primary_status,
            recommendation_summary=action_note if show_action_tile else summary_text,
            player_ids=[player_id],
            player_names=[clean_name],
            score_fields={
                "dynasty_score": row.get("dynasty_score", row.get("value_score")),
                "market_score": row.get("market_score"),
                "opportunity_score": row.get("opportunity_score"),
                "age_curve_score": row.get("age_curve_score"),
            },
            confidence_fields={
                "opportunity_confidence": row.get("opportunity_confidence"),
            },
            reason_fields={
                "primary_status": primary_status,
                "roster_context": roster_classification if on_roster else "League Target",
                "source_label": source_label,
                "source_note": source_note,
                "summary": summary_text,
            },
            roster_id=_safe_text(my_roster_id),
        )


def render_player_detail_content(
    *,
    player_row: pd.Series,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    pick_score_multiplier: float,
    source_label: str = "",
    source_note: str = "",
    include_news: bool = True,
) -> None:
    row = player_row
    player_id = _safe_text(row.get("player_id")).strip()
    image_url = cached_headshot_data_url(player_id) if player_id else ""
    avatar = avatar_html(image_url, _asset_initials(_safe_text(row.get("name"), "Player")), css_class="player-detail-avatar")
    tier_label = _safe_text(row.get("player_tier"), "Developmental")
    opportunity_label = _safe_text(row.get("opportunity_label"), "Opportunity unclear")
    strategy_label = team_strategy_label(active_team_strategy)
    age_text = _format_age(row.get("age")) or "N/A"
    header_html = (
        "<div class='player-detail-shell'>"
        + "<div class='player-detail-hero'>"
        + avatar
        + "<div>"
        + f"<div class='player-detail-name'>{escape(player_display_name(row))}</div>"
        + f"<div class='player-detail-meta'>{escape(_safe_text(row.get('position')))} | {escape(_safe_text(row.get('team'), 'FA'))} | Age {escape(age_text)}</div>"
        + "<div class='player-detail-chip-row'>"
        + tier_chip_html(tier_label)
        + glyph_chip_html(opportunity_label, "success")
        + _player_injury_chip(row)
        + glyph_chip_html(strategy_label, "premium")
        + "</div>"
        + "<div class='player-detail-score-row'>"
        + "<div class='player-detail-score-pill'>"
        + "<div class='player-detail-score-label'>Dynasty Value</div>"
        + injury_adjusted_value_html(
            "",
            _format_score(row.get('dynasty_score', row.get(score_field, 0))),
            row,
            css_class="player-detail-score-value",
        )
        + "<div class='player-detail-score-note'>Current dynasty lens</div>"
        + "</div>"
        + "<div class='player-detail-score-pill'>"
        + "<div class='player-detail-score-label'>Current Lens</div>"
        + injury_adjusted_value_html(
            "",
            _format_score(row.get(score_field, row.get('value_score', 0))),
            row,
            css_class="player-detail-score-value",
        )
        + f"<div class='player-detail-score-note'>{escape(league_score_label(score_field))}</div>"
        + "</div>"
        + "<div class='player-detail-score-pill'>"
        + "<div class='player-detail-score-label'>Market</div>"
        + f"<div class='player-detail-score-value'>{escape(_format_score(row.get('market_score', row.get('value', 0))))}</div>"
        + "<div class='player-detail-score-note'>Market score</div>"
        + "</div>"
        + "<div class='player-detail-score-pill'>"
        + "<div class='player-detail-score-label'>Opportunity</div>"
        + f"<div class='player-detail-score-value'>{escape(_format_score(row.get('opportunity_score', 0)))}</div>"
        + "<div class='player-detail-score-note'>Current role signal</div>"
        + "</div>"
        + "</div></div></div></div>"
    )
    st.markdown(header_html, unsafe_allow_html=True)

    source_items = []
    if source_label:
        source_items.append(f"Opened from {source_label}.")
    if source_note:
        source_items.append(source_note)
    summary_text = _safe_text(row.get("opportunity_explanation")) or _safe_text(row.get("manager_trade_implication")) or _safe_text(row.get("injury_replacement_note"))
    if summary_text:
        source_items.append(summary_text)
    if source_items:
        render_analysis_cards(
            [
                {
                    "label": "Quick View",
                    "title": "Why this player is in front of you",
                    "items": source_items[:3],
                    "tone": "strategy",
                }
            ]
        )

    render_section_header("Overview", kicker="Profile Snapshot", note="Core role, value, and roster context without leaving the player view.")
    render_summary_tiles(
        [
            {
                "label": "Position",
                "value": _safe_text(row.get("position"), "N/A"),
                "note": _safe_text(row.get("team"), "Free agent / no team"),
                "tone": "power",
            },
            {
                "label": "Tier",
                "value": tier_label,
                "note": "Visual treatment only. Tier calculations are unchanged.",
                "tone": "franchise",
            },
            {
                "label": "Age",
                "value": age_text,
                "note": f"Age penalty {_format_score(row.get('age_penalty', 0))}",
                "tone": "strategy",
            },
            {
                "label": "Injury Status",
                "value": tidy_label(_safe_text(row.get('injury_level'), 'healthy')),
                "note": _safe_text(row.get("injury_status") or row.get("status"), "No active injury tag"),
                "tone": "risk" if _safe_text(row.get("injury_level"), "healthy") != "healthy" else "strength",
            },
        ]
    )

    render_section_header("Opportunity", kicker="Role and Workload", note="Current opportunity is an input to the same canonical valuation pipeline.")
    source_flags = row.get("opportunity_source_flags") or []
    if not isinstance(source_flags, list):
        source_flags = [str(source_flags)] if _safe_text(source_flags) else []
    render_summary_tiles(
        [
            {
                "label": "Opportunity Label",
                "value": opportunity_label,
                "note": _safe_text(row.get("opportunity_explanation"), "No opportunity explanation available yet."),
                "tone": "opportunity",
            },
            {
                "label": "Projected Starter",
                "value": "Yes" if bool(row.get("projected_starter")) else "No / Unclear",
                "note": f"Confidence {_safe_positive_int(row.get('opportunity_confidence'), 0)} / 100",
                "tone": "power",
            },
            {
                "label": "Workload Trend",
                "value": _safe_text(row.get("workload_trend"), "Unknown"),
                "note": "Phase 1 uses depth, injuries, and role context. Snap and route metrics remain nullable.",
                "tone": "strategy",
            },
            {
                "label": "Source Flags",
                "value": str(len(source_flags)),
                "note": ", ".join(source_flags[:4]) if source_flags else "Depth-chart inference only.",
                "tone": "franchise",
            },
        ]
    )

    render_player_profile_stat_sections(row, compact=False)

    render_section_header("Market Value", kicker="Value Stack", note="All scores below are existing outputs from the current player pipeline.")
    render_summary_tiles(
        [
            {
                "label": league_score_label(score_field),
                "value": _format_score(row.get(score_field, row.get("value_score", 0))),
                "note": "Current active valuation lens.",
                "tone": "power",
            },
            {
                "label": "Dynasty Score",
                "value": _format_score(row.get("dynasty_score", 0)),
                "note": "Long-horizon baseline.",
                "tone": "franchise",
            },
            {
                "label": "Market Score",
                "value": _format_score(row.get("market_score", row.get("value", 0))),
                "note": "External market signal.",
                "tone": "strategy",
            },
            {
                "label": "Scarcity",
                "value": _format_score(row.get("scarcity_score", 0)),
                "note": f"Role score {_format_score(row.get('role_score', 0))}",
                "tone": "opportunity",
            },
        ]
    )

    on_roster = False
    role_label = ""
    fit_items = ["Select a league and roster to evaluate direct team fit."]
    fit_tone = "reference"
    player_roster_context = build_player_roster_needs_context(
        df_players,
        selected_league_id=selected_league_id,
        my_roster_id=my_roster_id,
        score_field=score_field,
        league_settings=league_settings,
    )
    if player_roster_context["assessment"] is not None:
        on_roster = player_id in player_roster_context["roster_player_ids"]
        role_map = {str(k): str(v) for k, v in st.session_state.get("role_map", {}).items()}
        role_label = role_map.get(player_id, "")
        team_metrics = player_roster_context["metrics"]
        team_needs_assessment = player_roster_context["assessment"]
        strengths = [str(pos).upper() for pos in (team_metrics or {}).get("strengths", []) or []]
        player_pos = _safe_text(row.get("position")).upper()
        fit_items = []
        if on_roster:
            fit_items.append("Already on your roster under the current league context.")
            if role_label:
                fit_items.append(f"Current roster role: {role_label}.")
            if player_pos in strengths:
                fit_items.append(f"{player_pos} is currently a roster strength, so this player can be used as consolidation leverage.")
            else:
                fit_items.append(
                    player_fit_context(
                        player_pos,
                        team_needs_assessment,
                        on_roster=True,
                    )["message"]
                )
            fit_tone = "strength"
        else:
            fit_context = player_fit_context(
                player_pos,
                team_needs_assessment,
            )
            fit_items.append(fit_context["message"])
            fit_tone = fit_context["tone"]
            if player_pos in strengths:
                fit_items.append(f"{player_pos} is already a roster strength, so the fit is more luxury than need.")
            fit_items.append(f"Active team strategy: {team_strategy_label(active_team_strategy)}.")

    render_section_header("Team Fit", kicker="Your Franchise", note="Fit is evaluated against the currently selected league, roster, and strategy lens.")
    render_summary_tiles(
        [
            {
                "label": "Roster Status",
                "value": "On Your Team" if on_roster else "External Target",
                "note": source_label or "Selected from the current workspace.",
                "tone": "power" if on_roster else "opportunity",
            },
            {
                "label": "Strategy Lens",
                "value": strategy_label,
                "note": "Same strategy lens used across the trade and roster surfaces.",
                "tone": "strategy",
            },
            {
                "label": "Role",
                "value": role_label or "Unassigned",
                "note": "Uses your existing Core / Flex / Bench role map when available.",
                "tone": "strategy",
            },
            {
                "label": "Fit Summary",
                "value": fit_items[0] if fit_items else "No fit read yet.",
                "note": "Short logic-based fit read.",
                "tone": fit_tone,
            },
        ]
    )
    render_analysis_cards(
        [
            {
                "label": "Team Fit",
                "title": "Why this player fits the current roster",
                "items": fit_items,
                "tone": fit_tone if fit_tone in {"strength", "weakness", "risk"} else "strength" if on_roster else "opportunity",
            }
        ]
    )

    trade_outlook = _player_detail_trade_outlook(
        player_row=row,
        df_players=df_players,
        username=username,
        selected_league_id=selected_league_id,
        my_roster_id=my_roster_id,
        score_field=score_field,
        league_settings=league_settings,
        team_strategy=active_team_strategy,
        pick_score_multiplier=pick_score_multiplier,
    )
    render_section_header("Trade Outlook", kicker="League Market", note="Uses your league's rosters and values to find realistic trade outlooks.")
    render_summary_tiles(
        [
            {
                "label": "Primary Read",
                "value": _safe_text(trade_outlook.get("headline"), "No trade outlook available yet."),
                "note": _safe_text(trade_outlook.get("subhead"), ""),
                "tone": _safe_text(trade_outlook.get("tone"), "opportunity"),
            }
        ]
    )
    render_analysis_cards(
        [
            {
                "label": "Trade Outlook",
                "title": "What the current market says",
                "items": list(trade_outlook.get("items") or ["No trade read available yet."]),
                "tone": _safe_text(trade_outlook.get("tone"), "opportunity"),
            }
        ]
    )

    if include_news:
        render_section_header("News", kicker="Latest Context", note="Recent player-specific headlines and Sleeper-style update context when available.")
        news_pool = st.session_state.get("news", [])
        if not news_pool:
            try:
                news_pool = fetch_news() or []
            except Exception:
                news_pool = []
            if news_pool:
                st.session_state["news"] = news_pool
        player_news = filter_news_for_players(news_pool, [player_display_name(row)], {_safe_text(row.get("team"))}) if news_pool else []
        player_news = curate_player_news(player_news, max_items=3) if player_news else []
        if not player_news:
            st.caption("No recent matched headlines are cached for this player yet.")
        else:
            for news_idx, item in enumerate(player_news):
                render_news_card(item, news_idx)


def render_player_detail_page(
    *,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    selected_league_name: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    pick_score_multiplier: float,
) -> None:
    player_id = _safe_text(st.session_state.get("player_detail_player_id")).strip()
    return_page = _resolve_player_detail_return_page(
        _safe_text(st.session_state.get("player_detail_return_page"))
    )
    source_label = _safe_text(st.session_state.get("player_detail_source_label"))

    render_page_shell(
        page_key="player_detail",
        title="Player Detail",
        subtitle="Player profile with opportunity, market value, team fit, trade outlook, and news context.",
        meta_items=[
            (selected_league_name or "League", "success"),
            (team_strategy_label(active_team_strategy), "premium"),
        ],
    )

    back_cols = st.columns([1, 4])
    with back_cols[0]:
        if st.button("Back", key="player_detail_back_btn", use_container_width=True):
            _queue_platform_route(return_page or "my_team")
            st.rerun()
    with back_cols[1]:
        if source_label:
            st.caption(f"Opened from {source_label}.")

    if not player_id or df_players.empty:
        st.info("Open a player from League Overview, My Team, Trade Hub, Trade Analyzer, Waivers, or Draft Center to load the profile here.")
        return

    row = _player_detail_row(df_players, player_id)
    if row is None:
        st.warning("That player is not available in the current player table.")
        return
    render_player_detail_content(
        player_row=row,
        df_players=df_players,
        username=username,
        selected_league_id=selected_league_id,
        my_roster_id=my_roster_id,
        league_settings=league_settings,
        score_field=score_field,
        active_team_strategy=active_team_strategy,
        pick_score_multiplier=pick_score_multiplier,
        source_label=source_label,
        include_news=True,
    )


def render_trade_player_dossier_content(
    player_id: str,
    *,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    pick_score_multiplier: float,
    source_label: str = "Trade Hub",
    source_note: str = "",
    recommendation_narrative=None,
) -> None:
    """Render the canonical dossier inside an existing trade dialog."""

    row = _player_detail_row(df_players, player_id)
    if row is None:
        st.error("Player details are unavailable for this asset.")
        return
    if recommendation_narrative is not None:
        canonical_recommendation_narrative.bind_narrative(
            st.session_state,
            recommendation_narrative,
        )
    render_player_quick_view_content(
        player_row=row,
        df_players=df_players,
        username=username,
        selected_league_id=selected_league_id,
        my_roster_id=my_roster_id,
        league_settings=league_settings,
        score_field=score_field,
        active_team_strategy=active_team_strategy,
        pick_score_multiplier=pick_score_multiplier,
        source_label=source_label,
        source_note=source_note,
        recommendation_narrative=recommendation_narrative,
    )


def render_player_quick_view_modal(
    *,
    df_players: pd.DataFrame,
    username: str,
    selected_league_id: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    pick_score_multiplier: float,
) -> None:
    player_id = _safe_text(st.session_state.get("player_quick_view_player_id")).strip()
    if not player_id:
        return
    row = _player_detail_row(df_players, player_id)
    if row is None:
        _clear_player_quick_view()
        return

    source_label = _safe_text(st.session_state.get("player_quick_view_source_label"))
    source_note = _safe_text(st.session_state.get("player_quick_view_source_note"))
    status_label = _safe_text(st.session_state.get("player_quick_view_status_label"))
    dialog_title = "Player Quick View"

    @st.dialog(dialog_title, width="large", dismissible=True, on_dismiss=_clear_player_quick_view)
    def _player_quick_view_dialog() -> None:
        render_player_quick_view_content(
            player_row=row,
            df_players=df_players,
            username=username,
            selected_league_id=selected_league_id,
            my_roster_id=my_roster_id,
            league_settings=league_settings,
            score_field=score_field,
            active_team_strategy=active_team_strategy,
            pick_score_multiplier=pick_score_multiplier,
            source_label=source_label,
            source_note=source_note,
            status_label=status_label,
        )

    _player_quick_view_dialog()

render_section_header = workspace_ui.render_section_header
render_concept_band = workspace_ui.render_concept_band
render_summary_tiles = workspace_ui.render_summary_tiles
render_analysis_cards = workspace_ui.render_analysis_cards
_decision_bucket_status_label = workspace_ui._decision_bucket_status_label
render_roster_utility_debug = workspace_ui.render_roster_utility_debug
render_no_team_player_debug = workspace_ui.render_no_team_player_debug
render_visible_decision_source_debug = workspace_ui.render_visible_decision_source_debug
_recommendation_player_row = workspace_ui._recommendation_player_row
render_home_status_strip = workspace_ui.render_home_status_strip


def render_team_identity_card(team_profile: dict, selected_league_name: str, metrics: dict | None):
    return workspace_ui.render_team_identity_card(
        team_profile,
        selected_league_name,
        metrics,
        format_score=_format_score,
        glyph_chip_html=glyph_chip_html,
        team_initials=_team_initials,
        team_strategy_label=team_strategy_label,
    )


def render_structured_decision_cards(cards: list[dict], *, container_class: str = ""):
    return workspace_ui.render_structured_decision_cards(
        cards,
        container_class=container_class,
        player_scan_card_html=_player_scan_card_html,
        compact_player_row_html=_compact_player_row_html,
        recommendation_reason_text=_recommendation_reason_text,
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        key_prefix=f"structured_decisions_{container_class or 'default'}",
    )


def render_home_command_hero(
    *,
    team_profile: dict,
    selected_league_name: str,
    record_label: str = "",
    direction_label: str,
    health_status: str,
    archetype_label: str = "",
    power_rank,
    franchise_rank,
):
    return workspace_ui.render_home_command_hero(
        team_profile=team_profile,
        selected_league_name=selected_league_name,
        record_label=record_label,
        direction_label=direction_label,
        health_status=health_status,
        archetype_label=archetype_label,
        power_rank=power_rank,
        franchise_rank=franchise_rank,
        owner_handle=owner_handle,
        team_logo_html=team_logo_html,
        format_rank=_format_rank,
    )


def render_home_command_tiles(items: list[dict], *, key_prefix: str = "home_command_tiles"):
    return workspace_ui.render_home_command_tiles(
        items,
        player_scan_card_html=_player_scan_card_html,
        compact_player_row_html=_compact_player_row_html,
        render_interactive_html=_render_player_interaction_grid,
        render_tappable_player_html=_render_tappable_player_html,
        open_player_quick_view=open_player_quick_view,
        open_route_action=_open_home_command_route,
        key_prefix=key_prefix,
    )


def render_home_quick_actions(actions: list[tuple[str, str]]):
    return workspace_ui.render_home_quick_actions(
        actions,
        commit_platform_destination=_commit_platform_destination,
    )


def refresh_current_user_entitlement() -> str:
    user_id = auth_supabase.current_user_id(st.session_state)
    profile = st.session_state.get("account_profile") if user_id else None
    memo_user = _safe_text(
        st.session_state.get(auth_restore_lifecycle.ENTITLEMENT_MEMO_USER_KEY)
    )
    memo_value = _safe_text(
        st.session_state.get(auth_restore_lifecycle.ENTITLEMENT_MEMO_KEY)
    ).casefold()
    if (
        user_id
        and memo_user == user_id
        and memo_value in {premium.FREE, premium.PREMIUM}
        and _safe_text(st.session_state.get("_effective_entitlement")).casefold()
        == memo_value
    ):
        return memo_value
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "entitlement_fetch_start",
        once=True,
    )
    auth_restore_lifecycle.record_entitlement_refresh(st.session_state)
    entitlement = premium.effective_entitlement(
        account_profile=profile,
        session_state=st.session_state,
        secrets=getattr(st, "secrets", None),
    )
    st.session_state["_effective_entitlement"] = entitlement
    if user_id:
        st.session_state[auth_restore_lifecycle.ENTITLEMENT_MEMO_KEY] = entitlement
        st.session_state[auth_restore_lifecycle.ENTITLEMENT_MEMO_USER_KEY] = user_id
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "entitlement_fetch_complete",
        once=True,
    )
    return entitlement


def current_user_entitlement() -> str:
    entitlement = _safe_text(st.session_state.get("_effective_entitlement")).casefold()
    if entitlement not in {premium.FREE, premium.PREMIUM}:
        entitlement = refresh_current_user_entitlement()
    return entitlement


def current_user_is_premium() -> bool:
    return current_user_entitlement() == premium.PREMIUM


def render_deferred_section_gate(
    section_id: str,
    *,
    button_label: str,
    note: str,
) -> bool:
    """Render a lightweight boundary before secondary Streamlit work."""

    if deferred_rendering.is_deferred_section_ready(st.session_state, section_id):
        return True
    st.caption(note)
    st.button(
        button_label,
        key=f"load_{deferred_rendering.deferred_state_key(section_id)}",
        use_container_width=True,
        on_click=deferred_rendering.mark_deferred_section_ready,
        args=(st.session_state, section_id),
    )
    return False


def increment_session_counter(key: str, amount: int, minimum: int = 0) -> None:
    """Commit pagination state before Streamlit's normal widget rerun."""

    current = max(int(st.session_state.get(key, minimum)), int(minimum))
    st.session_state[key] = current + int(amount)


def render_premium_lock(title: str, body: str = "", *, feature: str = "") -> None:
    # Presentation boundary: a stale caller must never show an upgrade prompt
    # after the canonical entitlement has resolved Premium.
    if current_user_is_premium():
        return
    premium.render_premium_lock(title, body, feature=feature)
    key_base = re.sub(
        r"[^a-z0-9_]+",
        "_",
        f"{_safe_text(feature)}_{_safe_text(title)}".casefold(),
    ).strip("_") or "premium"

    def _premium_lock_cta() -> None:
        try:
            from modules import launch_analytics

            launch_analytics.track_event(
                "premium_cta_clicked",
                props=launch_analytics.build_context_props(
                    st.session_state,
                    route="premium",
                    source_surface="premium_lock",
                    extra={"item_kind": _safe_text(feature)[:80]},
                ),
                state=st.session_state,
            )
        except Exception:
            pass
        _commit_platform_destination("premium", source="premium_lock")

    st.button(
        "Unlock with Premium",
        key=f"premium_lock_route_{key_base}",
        use_container_width=True,
        on_click=_premium_lock_cta,
    )


def build_home_league_pulse_items(df_intel: pd.DataFrame) -> list[dict]:
    if df_intel.empty:
        return []

    contender_mask = df_intel["mode"].astype(str).str.lower().eq("contender") if "mode" in df_intel.columns else None
    rebuild_mask = df_intel["mode"].astype(str).str.lower().eq("rebuild") if "mode" in df_intel.columns else None

    strongest_contender = _select_intelligence_row(
        df_intel,
        ["starter_current_score", "power_rank", "team_name"],
        [False, True, True],
        mask=contender_mask,
    )
    biggest_rebuilder = _select_intelligence_row(
        df_intel,
        ["rebuild_index", "draft_capital", "team_name"],
        [False, False, True],
        mask=rebuild_mask,
    )
    draft_capital_leader = _select_intelligence_row(
        df_intel,
        ["draft_capital", "first_rounders", "team_name"],
        [False, False, True],
    )
    most_active_manager = _select_intelligence_row(
        df_intel,
        ["trade_count", "trade_asset_total", "team_name"],
        [False, False, True],
    )

    active_trade_count = int(most_active_manager.get("trade_count") or 0) if most_active_manager is not None else 0
    return [
        {
            "label": "Biggest Contender",
            "value": _safe_text(strongest_contender.get("team_name"), "No clear leader") if strongest_contender is not None else "No clear leader",
            "note": (
                f"Power {_format_rank(strongest_contender.get('power_rank'))} | Starter {_format_rank(strongest_contender.get('starter_rank'))}"
                if strongest_contender is not None
                else "No contender read available yet."
            ),
            "tone": "power",
        },
        {
            "label": "Biggest Rebuilder",
            "value": _safe_text(biggest_rebuilder.get("team_name"), "No clear leader") if biggest_rebuilder is not None else "No clear leader",
            "note": (
                f"Draft {_format_rank(biggest_rebuilder.get('draft_capital_rank'))} | {_safe_text(biggest_rebuilder.get('strategy_display'), 'Rebuild')}"
                if biggest_rebuilder is not None
                else "No rebuild read available yet."
            ),
            "tone": "strategy",
        },
        {
            "label": "Draft Capital Leader",
            "value": _safe_text(draft_capital_leader.get("team_name"), "No clear leader") if draft_capital_leader is not None else "No clear leader",
            "note": (
                f"{_format_score(draft_capital_leader.get('draft_capital'))} | {int(draft_capital_leader.get('first_rounders') or 0)} firsts"
                if draft_capital_leader is not None
                else "No draft-capital read available yet."
            ),
            "tone": "opportunity",
        },
        {
            "label": "Most Active Manager",
            "value": (
                owner_handle(most_active_manager.get("owner_username"), most_active_manager.get("owner_name", "Manager"))
                if most_active_manager is not None and active_trade_count > 0
                else "Quiet market"
            ),
            "note": (
                f"{_safe_text(most_active_manager.get('team_name'))} | {active_trade_count} completed trades"
                if most_active_manager is not None and active_trade_count > 0
                else "No completed trade activity tracked yet."
            ),
            "tone": "franchise",
        },
    ]


def roster_record_label(league_id: str, roster_id) -> str:
    if not league_id or roster_id is None:
        return ""
    for roster in get_rosters(league_id) or []:
        if str(roster.get("roster_id")) != str(roster_id):
            continue
        settings = roster.get("settings") if isinstance(roster.get("settings"), dict) else {}
        wins = _safe_positive_int(settings.get("wins"), 0)
        losses = _safe_positive_int(settings.get("losses"), 0)
        ties = _safe_positive_int(settings.get("ties"), 0)
        if wins or losses or ties:
            return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        break
    return ""


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_user_league_launch_cards(
    username: str,
    leagues_signature: tuple[tuple[str, str, str], ...],
) -> list[dict]:
    cards: list[dict] = []
    for league_id, league_name, league_season in leagues_signature:
        if not league_id:
            continue
        rosters = get_rosters(league_id) or []
        roster_id = get_user_roster_id(league_id, username) if username else None
        profile = get_roster_profile(league_id, roster_id) if roster_id is not None else {}
        roster_row = next(
            (row for row in rosters if str(row.get("roster_id")) == str(roster_id)),
            {},
        )
        roster_settings = roster_row.get("settings") if isinstance(roster_row.get("settings"), dict) else {}
        wins = _safe_positive_int(roster_settings.get("wins"), 0)
        losses = _safe_positive_int(roster_settings.get("losses"), 0)
        ties = _safe_positive_int(roster_settings.get("ties"), 0)
        record_label = ""
        if wins or losses or ties:
            record_label = f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        rostered_player_count = sum(
            len(row.get("players") or [])
            for row in rosters
            if isinstance(row, dict)
        )
        settings_snapshot = detect_league_value_settings(league_id)
        format_label = "Redraft" if settings_snapshot.get("league_format") == "Redraft" else "Dynasty"
        cards.append(
            {
                "league_id": league_id,
                "league_name": _safe_text(league_name, "Unnamed league"),
                "season": _safe_text(league_season),
                "team_name": _safe_text(profile.get("team_name"), "Team"),
                "avatar_url": _safe_text(profile.get("avatar_url")),
                "record_label": record_label,
                "format_label": format_label,
                "draft_state_label": "Drafted" if rostered_player_count else "Not drafted",
                "league_size": len(rosters),
                "platform_label": "Sleeper",
            }
        )
    return cards


def render_home_launch_screen(
    *,
    username: str,
    selected_league_id: str,
    df_players: pd.DataFrame | None = None,
):
    if st.session_state.pop("_sync_home_launch_username_input", False):
        st.session_state["home_launch_username_input"] = username or st.session_state.get("username", "")
    elif "home_launch_username_input" not in st.session_state:
        st.session_state["home_launch_username_input"] = username or st.session_state.get("username", "")

    leagues = st.session_state.get("leagues_for_user", [])
    from modules import marketing_landing

    marketing_landing.render_marketing_landing()
    account_actions = account_ui.render_mobile_auth_entry(
        config=_supabase_config(),
        username=username,
        selected_league_id=selected_league_id,
    )
    if account_actions.get("resume_league"):
        _resume_saved_supabase_league(account_actions["resume_league"])
        st.rerun()
    platform_actions = platform_import_ui.render_platform_import_panel(
        df_players if df_players is not None else pd.DataFrame()
    )
    if platform_actions.get("handled"):
        return True

    with st.form("home_launch_form", clear_on_submit=False):
        launch_username_input = st.text_input(
            "Sleeper Username",
            key="home_launch_username_input",
            placeholder="Enter your Sleeper username",
        )
        submitted = st.form_submit_button(
            "Load My Leagues",
            use_container_width=True,
            type="primary",
        )
    if submitted:
        with st.spinner("Loading leagues from Sleeper..."):
            load_leagues_for_username(launch_username_input)
        st.rerun()

    if st.session_state.get("league_lookup_attempted"):
        lookup_status = _safe_text(st.session_state.get("league_lookup_status")).strip()
        lookup_message = league_lookup_customer_message(lookup_status) if lookup_status != "ok" else ""
        if lookup_message:
            st.warning(lookup_message)

    if not leagues:
        return True

    leagues_signature = tuple(
        (
            str(league.get("league_id") or ""),
            _safe_text(league.get("name"), "Unnamed league"),
            _safe_text(league.get("season")),
        )
        for league in leagues
    )
    league_cards = cached_user_league_launch_cards(
        username or _safe_text(st.session_state.get("home_launch_username_input")),
        leagues_signature,
    )
    last_league_id = _safe_text(st.session_state.get("last_league_option_id")).strip()
    last_league_card = next(
        (
            card
            for card in league_cards
            if str(card.get("league_id")) == last_league_id
        ),
        None,
    )
    if last_league_card is not None and not selected_league_id:
        if st.button(
            f"Continue last league: {_safe_text(last_league_card.get('league_name'))}",
            key=f"launch_continue_league_{last_league_id}",
            use_container_width=True,
            type="primary",
        ):
            set_selected_league(
                last_league_id,
                _safe_text(last_league_card.get("league_name")),
                route_to_dashboard=True,
            )
            st.rerun()
    st.markdown("<div class='launch-league-label'>Choose a League</div>", unsafe_allow_html=True)
    for card in league_cards:
        st.markdown(
            onboarding_ui.league_card_html(
                card,
                team_logo_html=team_logo_html,
                selected=bool(
                    selected_league_id
                    and str(card.get("league_id")) == str(selected_league_id)
                ),
                last_used=str(card.get("league_id")) == last_league_id,
            ),
            unsafe_allow_html=True,
        )
        if st.button(
            f"Open { _safe_text(card.get('league_name')) }",
            key=f"launch_open_league_{card.get('league_id')}",
            use_container_width=True,
            type="secondary",
        ):
            set_selected_league(
                str(card.get("league_id") or ""),
                _safe_text(card.get("league_name")),
                route_to_dashboard=True,
            )
            st.rerun()

    return True


def render_onboarding_handoff(
    *,
    username: str,
    selected_league_id: str,
    note: str,
):
    if _safe_text(note):
        st.info(_safe_text(note))
    render_home_launch_screen(
        username=username,
        selected_league_id=selected_league_id,
        df_players=None,
    )


def render_workspace_handoff(
    *,
    key_prefix: str,
    route_key: str,
    button_label: str,
    note: str,
    tone: str = "info",
):
    note_text = _safe_text(note)
    tone_key = _safe_text(tone, "info").strip().lower()
    if note_text:
        if tone_key == "caption":
            st.caption(note_text)
        elif tone_key == "warning":
            st.warning(note_text)
        else:
            st.info(note_text)

    def _handoff_with_return() -> None:
        _capture_workflow_handoff(
            route_key,
            origin_label=_safe_text(
                st.session_state.get("platform_nav_page"),
                "dashboard",
            ).replace("_", " ").title(),
            note=note_text,
            league_id=_safe_text(st.session_state.get("selected_league_id")),
            handoff_source="workspace_handoff",
        )
        _commit_platform_destination(route_key, source="workspace_handoff")

    st.button(
        button_label,
        key=f"{key_prefix}_{route_key}_handoff",
        use_container_width=True,
        on_click=_handoff_with_return,
    )


def render_trade_workflow_handoff(*, key_prefix: str, note: str):
    st.caption(_safe_text(note))
    action_cols = st.columns(2, gap="small")
    with action_cols[0]:
        st.button(
            "Open Trade Hub",
            key=f"{key_prefix}_open_trade_hub",
            use_container_width=True,
            on_click=_commit_platform_destination,
            args=("trade_hub",),
            kwargs={"source": "trade_workflow_handoff"},
        )
    with action_cols[1]:
        st.button(
            "Open Trade Analyzer",
            key=f"{key_prefix}_open_trade_analyzer",
            use_container_width=True,
            on_click=_commit_platform_destination,
            args=("trade_analyzer",),
            kwargs={"source": "trade_workflow_handoff"},
        )


render_archetype_summary = league_workspace_ui.render_archetype_summary
render_manager_tendencies_summary = (
    league_workspace_ui.render_manager_tendencies_summary
)

@runtime_trace.traced("waiver_generation", phase="waiver_generation")
def build_home_dashboard_free_agent_preview(
    df_players: pd.DataFrame,
    league_id: str,
    my_roster_id,
    score_field: str,
    league_settings: dict,
) -> tuple[pd.DataFrame, set[str], int]:
    if df_players is None or df_players.empty or not league_id:
        return pd.DataFrame(), set(), 0

    platform_adapter = get_sleeper_adapter()
    rosters = platform_adapter.get_rosters(league_id)
    rostered_ids = {
        str(pid)
        for roster in rosters or []
        for pid in roster.get("players", []) or []
        if pid is not None
    }
    free_agents = df_players[
        ~df_players["player_id"].astype(str).isin(rostered_ids)
    ].copy()
    free_agents = filter_current_fantasy_players(
        free_agents,
        surface="dashboard_free_agents",
    )
    if free_agents.empty:
        return free_agents, set(), 0

    free_agents["stale_free_agent"] = free_agents.apply(
        is_probably_stale_free_agent,
        axis=1,
    )
    free_agents.loc[
        free_agents["stale_free_agent"],
        ["dynasty_score", "value_score"],
    ] = 0
    free_agents = free_agents.sort_values(
        ["stale_free_agent", score_field],
        ascending=[True, False],
    )
    free_agents["position_rank"] = (
        free_agents.groupby("position")[score_field]
        .rank(method="first", ascending=False)
        .fillna(0)
        .astype(int)
    )

    injury_positions: set[str] = set()
    injured_starters = 0
    if my_roster_id is not None:
        player_ids = {
            str(pid)
            for pid in platform_adapter.get_roster_player_ids(league_id, my_roster_id) or []
            if pid is not None
        }
        injury_team_df = df_players[
            df_players["player_id"].astype(str).isin(player_ids)
        ].copy()
        injury_lineup_df = suggest_optimal_lineup(injury_team_df, league_settings)
        injury_context = roster_injury_context(injury_team_df, injury_lineup_df)
        injury_positions = {
            str(pos).upper()
            for pos in (injury_context.get("injury_need_positions") or set())
            if str(pos).upper() in {"QB", "RB", "WR", "TE", "K"}
        }
        injured_starters = int(injury_context.get("injured_starters") or 0)

    score_fit = pd.to_numeric(free_agents.get(score_field, 0), errors="coerce").fillna(0) > 0
    stale_fit = ~free_agents.get(
        "stale_free_agent",
        pd.Series(False, index=free_agents.index, dtype="bool"),
    ).fillna(False)
    injury_fit = (
        free_agents.get("position", pd.Series("", index=free_agents.index))
        .fillna("")
        .astype(str)
        .str.upper()
        .isin(injury_positions)
    ) & ~free_agents.apply(is_injury_status, axis=1) & score_fit & stale_fit
    free_agents["injury_replacement_fit"] = injury_fit
    free_agents["injury_replacement_note"] = free_agents.apply(
        lambda row: (
            f"Healthy cover for your injury-hit {str(row.get('position') or '').upper()} room."
            if bool(row.get("injury_replacement_fit"))
            else ""
        ),
        axis=1,
    )
    free_agents = free_agents.sort_values(
        ["injury_replacement_fit", "stale_free_agent", score_field],
        ascending=[False, True, False],
    )
    return free_agents, injury_positions, injured_starters


def dashboard_premium_content_state(
    effective_entitlement: str,
) -> dict[str, bool]:
    """Resolve Dashboard content visibility from the canonical entitlement."""

    is_premium = effective_entitlement == premium.PREMIUM
    return {
        "is_premium": is_premium,
        "show_upgrade_prompts": not is_premium,
    }


def render_home_dashboard(
    df_players: pd.DataFrame,
    *,
    username: str,
    authenticated: bool,
    selected_league_id: str,
    selected_league_name: str,
    my_roster_id,
    league_settings: dict,
    score_field: str,
    active_team_strategy: str,
    active_team_strategy_label: str,
    pick_score_multiplier: int,
    startup_mode: bool,
    startup_context: dict | None,
    league_context: dict | None = None,
    effective_entitlement: str = premium.FREE,
    valuation_archetype=None,
):
    dashboard_started = time.perf_counter()
    if startup_mode and selected_league_id:
        startup_context = startup_context or {}
        st.markdown(
            f"<div class='home-command-kicker'>{escape(brand_identity.PRODUCT_NAME)} Command</div>"
            "<div class='home-command-hero'>"
            f"<div class='home-hero-logo'>{brand_identity.mark_img_html(size_px=40, css_class='home-hero-logo-img')}</div>"
            "<div>"
            f"<div class='home-command-team'>{escape(_safe_text(selected_league_name, 'Startup League'))}</div>"
            "<div class='home-command-meta'>Startup draft workflow active.</div>"
            "<div class='home-command-badges'>"
            "<span class='home-command-badge home-command-badge-strategy'>Startup Mode</span>"
            "<span class='home-command-badge home-command-badge-archetype'>Pre-Roster</span>"
            "</div>"
            "<div class='home-hero-stats'>"
            "<div class='home-hero-stat'><div class='home-hero-stat-label'>Draft</div>"
            f"<div class='home-hero-stat-value'>{escape(tidy_label(_safe_text(startup_context.get('draft_status'), 'unknown')))}</div></div>"
            "<div class='home-hero-stat'><div class='home-hero-stat-label'>Picks</div>"
            f"<div class='home-hero-stat-value'>{escape(str(_safe_positive_int(startup_context.get('picks_made'), 0)))}</div></div>"
            "<div class='home-hero-stat'><div class='home-hero-stat-label'>Workflow</div>"
            "<div class='home-hero-stat-value'>Startup Draft Center</div></div>"
            "<div class='home-hero-stat'><div class='home-hero-stat-label'>Unlock</div>"
            "<div class='home-hero-stat-value'>Post Draft</div></div>"
            "</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div class='home-action-center-label'>Next Moves</div>", unsafe_allow_html=True)
        render_home_command_tiles(
            [
                {
                    "label": "Top Action",
                    "value": "Run Startup Draft Center",
                    "note": "Use the draft workflow first. That is the only surface that matters before rosters are built.",
                    "tone": "trade",
                    "wide": True,
                },
                {
                    "label": "Trade Surface",
                    "value": "Locked",
                    "note": "Trade tools stay gated until the startup draft completes.",
                    "tone": "risk",
                },
                {
                    "label": "News Surface",
                    "value": "Available",
                    "note": "Use Players and News while the draft board is still forming.",
                    "tone": "waiver",
                },
            ]
        )
        render_home_quick_actions(
            [
                ("Startup Draft Center", "startup_draft_center"),
                ("Players", "players"),
                ("News", "news"),
            ]
        )
        return

    if (
        st.session_state.get("active_platform") == "espn"
        and st.session_state.get("espn_limited_mode")
        and not selected_league_id
    ):
        render_section_header(
            "ESPN limited review mode",
            kicker="ESPN Import",
            note="ESPN import is currently mapping-review first. Sleeper remains the full Dashboard path while ESPN page support is validated.",
        )
        st.markdown(
            "<div class='app-degraded-state'>Dashboard recommendations are gated for ESPN until roster mapping and page support are fully validated. Use the import review to check match quality, or switch back to Sleeper for the full command center.</div>",
            unsafe_allow_html=True,
        )
        render_home_quick_actions(
            [
                ("Players", "players"),
                ("News", "news"),
            ]
        )
        return

    if not username or not selected_league_id:
        render_home_launch_screen(
            username=username,
            selected_league_id=selected_league_id,
            df_players=df_players,
        )
        return
    if my_roster_id is None:
        st.warning(f"Could not find a roster for username '{username}' in the selected league.")
        render_home_launch_screen(
            username=username,
            selected_league_id=selected_league_id,
            df_players=df_players,
        )
        return

    # Orientation preferences are consumed only by the authenticated Dashboard.
    # Loading them here removes a Supabase request from every other startup path
    # while preserving the durable, no-flash dismissal contract.
    if authenticated:
        with performance.time_block("user_preference_loading", category="supabase"):
            user_preferences.refresh_authenticated_preferences(
                config=_supabase_config(),
                session_state=st.session_state,
            )

    player_ids = [
        str(pid)
        for pid in ((league_context or {}).get("roster_player_map") or {}).get(
            str(my_roster_id), ()
        )
        if pid is not None
    ]
    if not player_ids:
        player_ids = [
            str(pid)
            for pid in get_roster_player_ids(selected_league_id, my_roster_id) or []
        ]
    if not player_ids:
        st.warning("No players found on this roster (Sleeper returned none).")
        return

    my_team_df = df_players[df_players["player_id"].isin(player_ids)].copy()
    if my_team_df.empty:
        st.warning("No players found on this roster after valuation filtering.")
        return

    profile = load_profile_key(username, selected_league_id)
    roles_state = {str(k): v for k, v in profile.get("roles", {}).items()}
    role_weights = {"Core": 1.1, "Flex": 1.0, "Bench": 0.9}
    league_context = league_context or cached_league_context(
        df_players,
        selected_league_id,
        score_field,
        league_settings,
        startup_context=startup_context,
    )
    df_summary = league_context.get("team_direction_summary", pd.DataFrame())
    maturity_context = league_context.get("league_maturity", {})
    team_metrics = get_team_vs_league(df_summary, my_roster_id)
    team_metrics = apply_strategy_to_metrics(team_metrics, active_team_strategy)

    player_names = my_team_df["name"].tolist()
    untouchables = [
        name for name in profile.get("untouchables", []) if name in player_names
    ]

    adjusted_scores = []
    roles_final = []
    for _, row in my_team_df.iterrows():
        base = row[score_field]
        role_value = roles_state.get(str(row["player_id"]), "Flex")
        weight = role_weights.get(role_value, 1.0)
        adjusted_scores.append(round(base * weight))
        roles_final.append(role_value)
    my_team_df["role"] = roles_final
    my_team_df["value_score"] = adjusted_scores

    lineup_df = suggest_optimal_lineup(my_team_df, league_settings)
    starters = lineup_df[lineup_df["suggested_starter"]].copy()
    bench = lineup_df[~lineup_df["suggested_starter"]].copy()
    team_needs_assessment = build_team_needs_assessment(
        my_team_df,
        team_metrics,
        league_settings,
        lineup_df=lineup_df,
    )
    needed_positions = get_needed_positions(
        my_team_df,
        team_metrics,
        league_settings,
        include_fallback=False,
        assessment=team_needs_assessment,
    )
    advice_items = build_my_team_advice(
        my_team_df,
        lineup_df,
        team_metrics,
        league_settings,
        needed_positions=needed_positions,
        assessment=team_needs_assessment,
    )

    df_display = league_context.get("league_detail_ranks", pd.DataFrame())
    df_intel = league_context.get("league_intelligence_frame", pd.DataFrame())
    team_row = df_display[df_display["roster_id"].astype(str) == str(my_roster_id)]
    team_row = team_row.iloc[0] if not team_row.empty else pd.Series(dtype="object")
    intel_row = df_intel[df_intel["roster_id"].astype(str) == str(my_roster_id)]
    intel_row = intel_row.iloc[0] if not intel_row.empty else pd.Series(dtype="object")

    advisor_trade_df = apply_strategy_age_curve(df_players, active_team_strategy, score_field)
    role_map = {str(pid): role for pid, role in roles_state.items()}
    dashboard_trade_candidates = cached_dashboard_trade_headline(
        df_players=advisor_trade_df,
        league_id=selected_league_id,
        df_summary=df_summary,
        my_roster_id=my_roster_id,
        untouchables=tuple(sorted(str(name) for name in untouchables)),
        role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
        score_field=score_field,
        pick_score_multiplier=strategy_adjusted_pick_score_multiplier(
            pick_score_multiplier,
            active_team_strategy,
        ),
        team_strategy=active_team_strategy,
        league_settings_items=draft_pick_valuation_settings_items(league_settings),
        maturity_context=maturity_context,
    )
    dashboard_trade_candidates = enforce_cached_trade_ideas(
        dashboard_trade_candidates,
        df_players=advisor_trade_df,
        league_id=selected_league_id,
        df_summary=df_summary,
        my_roster_id=my_roster_id,
        untouchables=tuple(sorted(str(name) for name in untouchables)),
        trust_context=league_context.get("trade_trust_context"),
    )
    enriched_dashboard_trade_candidates = enrich_trade_ideas_with_manager_tendencies(
        dashboard_trade_candidates,
        df_summary,
        maturity_context,
    )
    headline_idea = (
        enriched_dashboard_trade_candidates[0]
        if enriched_dashboard_trade_candidates
        else None
    )
    ideas = [headline_idea] if headline_idea else []

    injury_context = roster_injury_context(my_team_df, lineup_df)
    injury_display_context = injury_ui.resolve_team_injury_context(injury_context)
    injured_starters = _safe_nonnegative_int(
        injury_display_context.get("active_injured_starters"),
        _safe_nonnegative_int(injury_display_context.get("injured_starters"), 0),
    )
    health_flag = injury_ui.team_injury_display_label(
        injury_display_context,
        include_uncertainty=True,
    ) or "Stable"
    injury_advice_context = injury_ui.team_injury_advice(injury_display_context)
    key_injuries_summary = _safe_text(
        intel_row.get("key_injuries_summary")
        or ", ".join(injury_context.get("key_injuries") or [])
    )
    injury_need_positions = [
        str(pos).upper()
        for pos in (injury_context.get("injury_need_positions") or set())
        if str(pos).upper()
    ]
    acute_injury_pressure = injury_ui.is_acute_injury_pressure(
        injury_display_context
    )
    trade_summary = franchise_trade_summary(
        ideas,
        injury_positions=injury_need_positions,
        acute_injury_pressure=acute_injury_pressure,
    )
    trade_target_row = _recommendation_player_row(
        df_players,
        player_name=trade_summary.get("buy_low"),
    )
    free_agent_preview, _, _ = build_home_dashboard_free_agent_preview(
        df_players,
        selected_league_id,
        my_roster_id,
        score_field,
        league_settings,
    )
    home_roster_limit = roster_limit_status(
        league_id=selected_league_id,
        roster_id=my_roster_id,
        roster_df=my_team_df,
        lineup_df=lineup_df,
        league_settings=league_settings,
        score_field=score_field,
        active_team_strategy=active_team_strategy,
        needed_positions=needed_positions,
        surplus_positions=team_metrics.get("strengths", []),
        untouchables=untouchables,
    )
    top_waiver = select_top_waiver_opportunity(
        free_agent_preview,
        my_team_df,
        league_settings,
        score_field,
        needed_positions=needed_positions,
    )

    need_display = team_need_display(team_needs_assessment)
    biggest_need_note = (
        f"{need_display['note']} Open My Team for the full roster decision board."
    )
    injury_alert = injury_ui.my_team_injury_alert(injury_display_context)
    injury_alert_value = injury_alert["value"]
    injury_alert_note = injury_alert["note"]
    record_label = roster_record_label(selected_league_id, my_roster_id)

    performance.record_timing(
        "dashboard_computation",
        (time.perf_counter() - dashboard_started) * 1000,
        category="analysis",
    )
    dashboard_render_started = time.perf_counter()
    trade_note = _safe_text(
        trade_summary["rationale"],
        "Open Trade Hub for the cleanest path from this roster state.",
    )
    trade_card_note = (
        f"{_safe_text(trade_summary.get('partner'), 'Trade partner')}: {trade_note}"
        if trade_target_row is not None
        else trade_note
    )
    waiver_note = (
        _safe_text(top_waiver.get("injury_replacement_note"))
        or _safe_text(top_waiver.get("opportunity_label"))
        or "Open Waivers for the best live add."
    )
    dashboard_trade_narrative = None
    if headline_idea is not None:
        dashboard_trade_narrative = (
            canonical_recommendation_narrative.build_trade_narrative(
                headline_idea,
                league_id=_safe_text(selected_league_id),
                roster_id=_safe_text(my_roster_id),
                valuation_lens=_safe_text(score_field),
                source_surface="dashboard",
                target_reason=_trade_target_reason(headline_idea),
                partner_reason=_trade_partner_reason(headline_idea),
                confidence_reason=_trade_confidence_reason(headline_idea),
                confidence_label=_trade_display_confidence_label(headline_idea),
                value_verdict=trade_value_verdict(
                    int(headline_idea.get("trade_gain") or 0)
                ),
                value_delta=(
                    f"+{_format_score(headline_idea.get('trade_gain'))}"
                    if int(headline_idea.get("trade_gain") or 0) > 0
                    else (
                        f"-{_format_score(abs(int(headline_idea.get('trade_gain') or 0)))}"
                        if int(headline_idea.get("trade_gain") or 0) < 0
                        else "Even"
                    )
                ),
                health_context=_trade_idea_injury_display_context(headline_idea),
            )
        )
        trade_card_note = dashboard_trade_narrative.shorten("reason", 150)
    dashboard_waiver_narrative = None
    if not top_waiver.empty:
        waiver_action, _ = waivers_ui.waiver_recommendation_label(
            top_waiver,
            _safe_positive_int(top_waiver.get("position_rank"), 99) or 99,
        )
        dashboard_waiver_narrative = (
            canonical_recommendation_narrative.build_waiver_narrative(
                top_waiver,
                action=waiver_action,
                reason=waiver_note,
                league_id=_safe_text(selected_league_id),
                roster_id=_safe_text(my_roster_id),
                valuation_lens=_safe_text(score_field),
                source_surface="dashboard",
            )
        )

    roster_limit_value = (
        f"{int(home_roster_limit.get('over_by') or 0)} Over"
        if home_roster_limit.get("over_limit")
        else "Within Limit"
    )
    roster_limit_note = (
        f"{int(home_roster_limit.get('current_roster_size') or 0)} active vs {int(home_roster_limit.get('max_roster_size') or 0)} limit"
        if home_roster_limit.get("max_roster_size")
        else "Sleeper roster limit unavailable."
    )

    # Maturity changes presentation priority only.  Every value below comes
    # from the existing team, trade, waiver, lineup, and injury builders.
    roster_pressure_item = {
        "label": "Roster Pressure",
        "value": roster_limit_value,
        "note": roster_limit_note,
        "tone": "risk" if home_roster_limit.get("over_limit") else "draft",
        "route_key": "my_team",
    }
    trade_item = {
        "label": "Top Trade Opportunity",
        "value": _safe_text(
            (dashboard_trade_narrative.target_label if dashboard_trade_narrative else ""),
            _safe_text(trade_summary["partner"], "Open Trade Hub"),
        ),
        "note": trade_card_note,
        "tone": "trade",
        "player_row": trade_target_row,
        "recommendation_label": (
            dashboard_trade_narrative.action
            if dashboard_trade_narrative is not None
            else "Trade Target"
        ),
        "score_field": score_field,
        "route_key": "trade_hub",
        "route_player_id": _safe_text(trade_target_row.get("player_id")) if trade_target_row is not None and hasattr(trade_target_row, "get") else "",
        "route_focus_mode": "target_player",
        "recommendation_narrative": (
            dashboard_trade_narrative.to_dict()
            if dashboard_trade_narrative is not None
            else None
        ),
        "recommendation_id": (
            dashboard_trade_narrative.recommendation_id
            if dashboard_trade_narrative is not None
            else ""
        ),
    }
    waiver_item = {
        "label": "Top Waiver Opportunity",
        "value": _safe_text(top_waiver.get("name"), "Open Waivers"),
        "note": (
            dashboard_waiver_narrative.shorten("reason", 150)
            if dashboard_waiver_narrative is not None
            else waiver_note
        ),
        "tone": "waiver",
        "player_row": top_waiver if not top_waiver.empty else None,
        "recommendation_label": (
            dashboard_waiver_narrative.action
            if dashboard_waiver_narrative is not None
            else "Priority Add"
        ),
        "score_field": score_field,
        "route_key": "waivers",
        "route_player_id": _safe_text(top_waiver.get("player_id")) if not top_waiver.empty else "",
        "recommendation_narrative": (
            dashboard_waiver_narrative.to_dict()
            if dashboard_waiver_narrative is not None
            else None
        ),
        "recommendation_id": (
            dashboard_waiver_narrative.recommendation_id
            if dashboard_waiver_narrative is not None
            else ""
        ),
    }
    need_item = {
        "label": need_display["label"],
        "value": need_display["value"],
        "note": biggest_need_note,
        "tone": need_display["tone"],
        "route_key": "my_team",
    }
    injury_item = {
        "label": "Injury Alert",
        "value": injury_alert_value,
        "note": injury_alert_note,
        "tone": "risk",
        "route_key": "my_team",
    }
    dashboard_phase = _safe_text(
        maturity_context.get("dashboard_phase"),
        "in_season",
    )
    if dashboard_phase == "startup":
        strongest_room = (
            str((team_metrics or {}).get("strengths", ["Balanced"])[0]).upper()
            if (team_metrics or {}).get("strengths")
            else "Balanced"
        )
        action_center_items = [
            {
                "label": "Roster Quality",
                "value": f"Power {_format_rank(team_row.get('power_rank'))}",
                "note": f"Franchise {_format_rank(team_row.get('franchise_rank'))} after the completed startup.",
                "tone": "power",
            },
            need_item,
            trade_item,
            {
                "label": "Lineup Construction",
                "value": f"{len(starters)} projected starters",
                "note": f"Starter rank {_format_rank(team_row.get('starter_rank'))} | Bench rank {_format_rank(team_row.get('bench_rank'))}.",
                "tone": "franchise",
            },
            {
                "label": "Startup Observation",
                "value": active_team_strategy_label,
                "note": f"Current roster-only read; strongest room: {strongest_room}.",
                "tone": "draft",
            },
        ]
    elif dashboard_phase == "playoff_push":
        action_center_items = [
            injury_item,
            trade_item,
            waiver_item,
            roster_pressure_item,
            need_item,
        ]
    elif dashboard_phase == "early_season":
        action_center_items = [
            roster_pressure_item,
            need_item,
            trade_item,
            waiver_item,
            injury_item,
        ]
    else:
        action_center_items = [
            roster_pressure_item,
            trade_item,
            waiver_item,
            need_item,
            injury_item,
        ]
    premium_content = dashboard_premium_content_state(effective_entitlement)
    is_premium = premium_content["is_premium"]
    visible_action_items = action_center_items if is_premium else action_center_items[:4]
    immediate_labels = frozenset(
        label
        for label, active in (
            ("Roster Pressure", bool(home_roster_limit.get("over_limit"))),
            ("Injury Alert", injured_starters > 0),
        )
        if active
    )
    dashboard_briefing = dashboard_workflow.organize_dashboard_items(
        visible_action_items,
        immediate_labels=immediate_labels,
    )
    roster_version = recommendation_lifecycle.roster_state_version_from_player_ids(
        my_team_df["player_id"].tolist() if not my_team_df.empty else ()
    )
    st.session_state[recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY] = roster_version
    lifecycle_fingerprint = recommendation_lifecycle.build_context_fingerprint(
        session=st.session_state,
        league_id=_safe_text(selected_league_id),
        roster_id=_safe_text(my_roster_id),
        season=_safe_text(
            st.session_state.get("stats_season") or (league_settings or {}).get("season")
        ),
        week=_safe_text((league_settings or {}).get("week")),
        scoring_format=_safe_text((league_settings or {}).get("scoring_format"), "PPR"),
        valuation_lens=_safe_text(score_field),
        roster_state_version=roster_version,
        provider_data_version=league_value_settings_key(league_settings or {}),
    )
    # Lightweight inbox inventory from already-built tiles — no new football work.
    notification_center.publish_activity_inventory(
        st.session_state,
        visible_action_items,
        league_id=_safe_text(selected_league_id),
        roster_id=_safe_text(my_roster_id),
        entitlement=_safe_text(effective_entitlement, "free"),
        live_draft_active=bool(st.session_state.get("_cached_live_draft_active")),
        context_fingerprint=lifecycle_fingerprint.digest,
        scoring_format=_safe_text((league_settings or {}).get("scoring_format"), "PPR"),
        valuation_lens=_safe_text(score_field),
        supabase_config=_supabase_config(),
    )
    average_age = team_metrics.get("avg_age")
    average_age_label = (
        f"{float(average_age):.1f}"
        if average_age is not None and pd.notna(average_age)
        else "Unavailable"
    )
    snapshot_comparisons = comparative_metrics.dashboard_comparison_payloads(
        df_intel,
        my_roster_id,
    )
    snapshot_items = [
        {
            "label": "Record",
            "value": record_label or "Unavailable",
            "note": "Current league record",
            "tone": "current",
            "tappable": False,
        },
        {
            "label": "Health",
            "value": health_flag,
            "note": "Active roster availability",
            "tone": "risk" if injured_starters else "opportunity",
            "comparison": snapshot_comparisons.get("Health"),
        },
        {
            "label": "Average Age",
            "value": average_age_label,
            "note": "Active roster profile",
            "tone": "current",
            "comparison": snapshot_comparisons.get("Average Age"),
        },
        {
            "label": "Starter Strength",
            "value": _format_rank(team_row.get("starter_rank")),
            "note": "Projected lineup rank",
            "tone": "power",
            "comparison": snapshot_comparisons.get("Starter Strength"),
        },
        {
            "label": "Bench Strength",
            "value": _format_rank(team_row.get("bench_rank")),
            "note": "Depth rank",
            "tone": "franchise",
            "comparison": snapshot_comparisons.get("Bench Strength"),
        },
    ]

    def _render_dashboard_league_pulse() -> None:
        pulse_section_id = f"dashboard_league_pulse_{selected_league_id}"
        if render_deferred_section_gate(
            pulse_section_id,
            button_label="Load League Pulse",
            note="Load league-wide context only when you need the broader read.",
        ):
            with performance.time_block(
                "dashboard_deferred_league_pulse",
                category="analysis",
            ):
                league_pulse_items = build_home_league_pulse_items(df_intel)
            render_summary_tiles(
                league_pulse_items,
                compact=True,
                detail_dialog_renderer=workspace_ui.render_canonical_summary_tile_detail_dialog,
            )

    def _render_full_recommendations_lock() -> None:
        render_premium_lock(
            "More next moves",
            "See the rest of today's roster, trade, waiver, and health signals so you do not miss the next best move.",
            feature="Premium Dashboard",
        )

    def _render_league_pulse_lock() -> None:
        render_premium_lock(
            "Full League Pulse",
            "See contender, rebuilder, and trading posture across the league before you pick a partner.",
            feature="Premium League Pulse",
        )

    def _render_dashboard_orientation() -> None:
        dashboard_orientation.render_orientation_if_applicable(
            authenticated=authenticated,
            page_ready=True,
            route="dashboard",
            platform=st.session_state.get("active_platform", "sleeper"),
            league_identity=selected_league_id,
            active_roster_available=my_roster_id is not None,
            startup_mode=startup_mode,
            on_open_my_team=lambda: _commit_platform_destination(
                "my_team",
                source="dashboard_orientation",
            ),
            persistently_dismissed=user_preferences.onboarding_is_dismissed(
                st.session_state.get("account_user_settings")
            ),
            on_dont_show_again=_persist_onboarding_dismissal,
        )

    todays_game_plan = daily_gm_briefing.compose_daily_gm_briefing(
        dashboard_briefing,
        league_id=_safe_text(selected_league_id),
        roster_id=_safe_text(my_roster_id),
        valuation_lens=_safe_text(score_field),
        scoring_format=_safe_text(
            (league_settings or {}).get("scoring_format"),
            "PPR",
        ),
        entitlement=effective_entitlement,
        context_fingerprint=lifecycle_fingerprint.digest,
    )
    st.session_state[recommendation_lifecycle.LIFECYCLE_BRIEFING_SIGNATURE_KEY] = (
        recommendation_lifecycle.briefing_content_signature(
            [item.to_dict() for item in todays_game_plan.items],
            quiet=todays_game_plan.quiet,
        )
    )

    def _render_todays_game_plan() -> None:
        # Pure composition of already-built dashboard_briefing — no new football work.
        try:
            from modules import launch_analytics

            launch_analytics.track_event(
                "first_game_plan_seen",
                props=launch_analytics.build_context_props(
                    st.session_state,
                    route="dashboard",
                    source_surface="daily_gm_briefing",
                ),
                once_key=f"game_plan:{_safe_text(selected_league_id) or 'none'}",
                state=st.session_state,
            )
        except Exception:
            pass
        daily_gm_briefing_ui.render_todays_game_plan(
            todays_game_plan,
            open_item=_open_daily_gm_briefing_item,
            key_prefix=f"daily_gm_{_safe_text(selected_league_id) or 'none'}",
        )
        st.markdown(
            '<div data-fgl-dashboard-useful="1" hidden aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )

    def _render_what_changed() -> None:
        league_key = _safe_text(selected_league_id)
        if decision_memory.can_access_history(st.session_state):
            events = decision_memory.dashboard_recent_events(
                st.session_state,
                league_id=league_key,
            )
            try:
                from modules import launch_analytics

                launch_analytics.track_event(
                    "decision_memory_viewed",
                    props=launch_analytics.build_context_props(
                        st.session_state,
                        route="dashboard",
                        source_surface="what_changed",
                        league_id=league_key,
                    ),
                    once_key=f"dm_view:{league_key or 'none'}",
                    state=st.session_state,
                )
            except Exception:
                pass
        else:
            events = decision_change_history.dashboard_events(
                st.session_state,
                league_id=league_key,
            )
        decision_change_history_ui.render_what_changed_section(
            events,
            open_event=_open_decision_change_event,
            key_prefix=f"what_changed_{league_key or 'none'}",
            league_id=league_key,
        )

    try:
        if valuation_archetype is not None:
            valuation_archetype_ui.render_workspace_archetype_affordance(
                valuation_archetype,
                key="workspace_valuation_archetype",
            )
        dashboard_workflow.render_dashboard_workflow(
            dashboard_briefing,
            snapshot_items=snapshot_items,
            render_tiles=render_home_command_tiles,
            render_snapshot=lambda items: render_summary_tiles(items, compact=True),
            render_quick_actions=render_home_quick_actions,
            render_league_pulse=_render_dashboard_league_pulse,
            render_orientation=_render_dashboard_orientation,
            render_todays_game_plan=_render_todays_game_plan,
            render_what_changed=_render_what_changed,
            render_full_recommendations_lock=(
                _render_full_recommendations_lock
                if premium_content["show_upgrade_prompts"]
                else None
            ),
            render_league_pulse_lock=(
                _render_league_pulse_lock
                if premium_content["show_upgrade_prompts"]
                else None
            ),
        )
        st.markdown(
            '<div data-fgl-dashboard-complete="1" hidden aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
    except Exception:
        st.session_state["_startup_route_render_failed"] = True
        st.error(
            "Dashboard rendering failed. Refresh the page or switch leagues to recover."
        )
        st.button(
            "Refresh page",
            key="dashboard_startup_recovery_refresh",
            use_container_width=True,
        )
        performance.record_timing(
            "dashboard_rendering",
            (time.perf_counter() - dashboard_render_started) * 1000,
            category="render",
        )
        return

    if not st.session_state.get(startup_coordinator.STARTUP_COMPLETE_KEY):
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "dashboard_rendered",
            started_at=startup_coordinator.startup_session_origin(st.session_state),
        )
    performance.record_timing(
        "dashboard_rendering",
        (time.perf_counter() - dashboard_render_started) * 1000,
        category="render",
    )


STARTUP_DRAFT_STRATEGIES = (
    "Win Now",
    "Balanced",
    "Productive Struggle",
    "Youth / Rebuild",
    "Zero RB",
    "Hero RB",
    "Elite QB Priority",
)


def startup_strategy_team_mode(strategy_label: str) -> str:
    strategy_label = _safe_text(strategy_label)
    if strategy_label == "Win Now":
        return "contender"
    if strategy_label == "Youth / Rebuild":
        return "rebuild"
    if strategy_label == "Productive Struggle":
        return "retool"
    if strategy_label == "Elite QB Priority":
        return "fringe_contender"
    return "retool"


def startup_strategy_position_weights(
    strategy_label: str,
    current_round: int,
    league_settings: dict,
) -> dict[str, float]:
    weights = {"QB": 1.0, "RB": 1.0, "WR": 1.0, "TE": 1.0, "K": 0.2}
    qb_format = _safe_text(league_settings.get("qb_format"), "1QB")
    te_premium = bool(league_settings.get("te_premium"))
    current_round = max(1, _safe_positive_int(current_round, 1))

    if strategy_label == "Win Now":
        weights["RB"] *= 1.06
        weights["WR"] *= 1.03
    elif strategy_label == "Youth / Rebuild":
        weights["QB"] *= 1.04
        weights["WR"] *= 1.04
        weights["RB"] *= 0.94
    elif strategy_label == "Productive Struggle":
        weights["WR"] *= 1.05
        weights["TE"] *= 1.03
    elif strategy_label == "Zero RB":
        if current_round <= 5:
            weights["RB"] *= 0.82
            weights["WR"] *= 1.10
            weights["TE"] *= 1.05
        else:
            weights["RB"] *= 1.06
    elif strategy_label == "Hero RB":
        if current_round <= 2:
            weights["RB"] *= 1.12
        else:
            weights["RB"] *= 0.92
            weights["WR"] *= 1.04
    elif strategy_label == "Elite QB Priority":
        if qb_format in {"Superflex", "2QB"}:
            weights["QB"] *= 1.18 if current_round <= 3 else 1.08
        else:
            weights["QB"] *= 1.08 if current_round <= 4 else 0.98

    if qb_format in {"Superflex", "2QB"}:
        weights["QB"] *= 1.08
    if te_premium:
        weights["TE"] *= 1.06
    return weights


def build_startup_draft_board(
    df_players: pd.DataFrame,
    score_field: str,
    strategy_label: str,
    current_round: int,
    league_settings: dict,
    excluded_player_ids: set[str],
) -> pd.DataFrame:
    if df_players.empty:
        return df_players

    strategy_mode = startup_strategy_team_mode(strategy_label)
    eligible_players = filter_current_fantasy_players(
        df_players,
        surface="startup_draft_center",
    )
    if eligible_players.empty:
        return eligible_players
    board = apply_strategy_age_curve(
        eligible_players,
        strategy_mode,
        score_field,
    ).copy()
    if excluded_player_ids:
        board = board[~board["player_id"].astype(str).isin(excluded_player_ids)].copy()
    board = board[board["position"].isin(["QB", "RB", "WR", "TE", "K"])].copy()
    weights = startup_strategy_position_weights(strategy_label, current_round, league_settings)
    board["startup_position_weight"] = board["position"].map(lambda pos: float(weights.get(str(pos).upper(), 1.0)))
    board["startup_score"] = (
        pd.to_numeric(board.get(score_field, board.get("value_score", 0)), errors="coerce").fillna(0)
        * pd.to_numeric(board["startup_position_weight"], errors="coerce").fillna(1.0)
    ).round().astype(int)
    return board.sort_values(["startup_score", score_field, "market_score"], ascending=[False, False, False]).reset_index(drop=True)


def startup_tier_break_warning(board: pd.DataFrame) -> str:
    if board is None or board.empty:
        return "No tier-break read available yet."
    top = board.head(12).copy()
    if top.empty:
        return "No tier-break read available yet."
    lead = top.iloc[0]
    lead_tier = _safe_text(lead.get("player_tier"), "Developmental")
    same_tier = top[top["player_tier"].fillna("").astype(str) == lead_tier]
    if len(same_tier) <= 2:
        return f"Only {len(same_tier)} {lead_tier} options remain near the top of the board."
    if len(same_tier) >= 5:
        return f"{len(same_tier)} {lead_tier} options are still clustered together, so a small trade down is safer."
    return f"The top tier is still alive, but the board starts flattening after the next few names."


def startup_trade_move_note(board: pd.DataFrame) -> str:
    if board is None or board.empty:
        return "Hold your current slot until the board firms up."
    top = board.head(10).copy()
    if top.empty:
        return "Hold your current slot until the board firms up."
    lead_tier = _safe_text(top.iloc[0].get("player_tier"))
    same_tier_count = int((top["player_tier"].fillna("").astype(str) == lead_tier).sum())
    if same_tier_count <= 2:
        return "Trade up only if you are targeting a specific top-tier player; the tier cliff is close."
    if same_tier_count >= 5:
        return "Trade down is viable because multiple same-tier options should still be there after a short slide."
    return "Stay flexible. The board is not forcing a strong move up or down yet."


def _prefer_healthy_headline_candidate(
    board: pd.DataFrame,
    *,
    score_column: str,
    search_limit: int = 8,
    tolerance_ratio: float = 0.04,
    tolerance_points: int = 220,
) -> pd.Series:
    if board is None or board.empty:
        return pd.Series(dtype="object")

    candidate_pool = board.reset_index(drop=True).head(max(1, search_limit)).copy()
    lead = candidate_pool.iloc[0]
    if not is_injury_status(lead):
        return lead

    healthy_pool = candidate_pool[~candidate_pool.apply(is_injury_status, axis=1)].copy()
    if healthy_pool.empty:
        return lead

    lead_score = _safe_float(lead.get(score_column), 0.0)
    tolerance = max(float(tolerance_points), lead_score * float(tolerance_ratio))
    healthy_scores = pd.to_numeric(
        healthy_pool.get(score_column, pd.Series(0, index=healthy_pool.index)),
        errors="coerce",
    ).fillna(0.0)
    close_pool = healthy_pool[healthy_scores >= max(0.0, lead_score - tolerance)].copy()
    lead_tier = _safe_text(lead.get("player_tier"))
    if lead_tier and not close_pool.empty and "player_tier" in close_pool.columns:
        same_tier_pool = close_pool[
            close_pool["player_tier"].fillna("").astype(str) == lead_tier
        ]
        if not same_tier_pool.empty:
            return same_tier_pool.iloc[0]
    if not close_pool.empty:
        return close_pool.iloc[0]
    return lead


def render_startup_draft_center(
    df_players: pd.DataFrame,
    startup_context: dict,
    league_settings: dict,
    score_field: str,
    league_type: str,
):
    render_section_header(
        "Startup Draft Center",
        kicker="Pre-Roster Mode",
        note=_safe_text(startup_context.get("reason"), "This league is still in startup mode, so the app is using a draft-first dashboard instead of the normal roster workflow."),
    )

    league_summary_items = [
        {
            "label": "Format",
            "value": _safe_text(league_settings.get("league_format"), "Dynasty"),
            "note": compact_league_value_settings(league_settings),
            "tone": "power",
        },
        {
            "label": "League Size",
            "value": str(_safe_positive_int(startup_context.get("league_size"), _safe_positive_int(league_settings.get("league_size"), 12))),
            "note": f"{_safe_positive_int(league_settings.get('starter_count'), 9)} starters | {_safe_positive_int(league_settings.get('bench_count'), 0)} bench | {_safe_positive_int(league_settings.get('taxi_count'), 0)} taxi",
            "tone": "franchise",
        },
        {
            "label": "Draft Status",
            "value": tidy_label(_safe_text(startup_context.get("draft_status"), "unknown")),
            "note": f"{_safe_positive_int(startup_context.get('picks_made'), 0)} of {_safe_positive_int(startup_context.get('total_picks'), 0)} picks logged",
            "tone": "strategy",
        },
        {
            "label": "Current-Year Pick Status",
            "value": "Active",
            "note": _safe_text(startup_context.get("current_year_pick_status")),
            "tone": "opportunity",
        },
    ]
    render_summary_tiles(league_summary_items)

    default_slot = _safe_positive_int(startup_context.get("my_draft_slot"), 0) or 1
    league_size = max(1, _safe_positive_int(startup_context.get("league_size"), 12))
    input_cols = st.columns(4)
    with input_cols[0]:
        draft_slot = st.number_input("Draft slot", min_value=1, max_value=league_size, value=min(default_slot, league_size), step=1, key=f"startup_draft_slot_{startup_context.get('league_id')}")
    with input_cols[1]:
        current_round = st.number_input(
            "Current round",
            min_value=1,
            max_value=max(1, _safe_positive_int(startup_context.get("draft_rounds"), 30) or 30),
            value=max(1, min(_safe_positive_int(startup_context.get("picks_made"), 0) // max(league_size, 1) + 1, max(1, _safe_positive_int(startup_context.get("draft_rounds"), 30) or 30))),
            step=1,
            key=f"startup_current_round_{startup_context.get('league_id')}",
        )
    with input_cols[2]:
        current_pick = st.number_input(
            "Current pick",
            min_value=1,
            max_value=league_size,
            value=min(max(1, draft_slot), league_size),
            step=1,
            key=f"startup_current_pick_{startup_context.get('league_id')}",
        )
    with input_cols[3]:
        startup_strategy = st.selectbox(
            "Draft strategy",
            STARTUP_DRAFT_STRATEGIES,
            index=STARTUP_DRAFT_STRATEGIES.index("Balanced"),
            key=f"startup_strategy_{startup_context.get('league_id')}",
        )

    drafted_player_ids = set(str(pid) for pid in (startup_context.get("drafted_player_ids") or []) if pid)
    eligible_manual_pool = filter_current_fantasy_players(
        df_players,
        surface="startup_manual_exclusions",
    )
    manual_labels = {
        f"{player_display_name(row)} | {_safe_text(row.get('position'))} | {_safe_text(row.get('team'))}": str(row.get("player_id"))
        for _, row in eligible_manual_pool.sort_values(score_field, ascending=False).head(400).iterrows()
    }
    manual_exclusions = st.multiselect(
        "Manual drafted-player exclusions",
        options=list(manual_labels.keys()),
        default=[],
        help="Use this only if Sleeper draft-pick data is missing or behind. Excluded players are removed from the startup board.",
        key=f"startup_manual_exclusions_{startup_context.get('league_id')}",
    )
    manual_excluded_ids = {manual_labels[label] for label in manual_exclusions if label in manual_labels}
    excluded_ids = drafted_player_ids | manual_excluded_ids

    board = build_startup_draft_board(
        df_players,
        score_field,
        startup_strategy,
        int(current_round),
        league_settings,
        excluded_ids,
    )

    if board.empty:
        st.info("No available players remain on the startup board under the current filters.")
        return

    strategy_mode = startup_strategy_team_mode(startup_strategy)
    raw_board = apply_strategy_age_curve(
        filter_current_fantasy_players(
            df_players,
            surface="startup_best_available",
        ),
        strategy_mode,
        score_field,
    ).copy()
    raw_board = raw_board[~raw_board["player_id"].astype(str).isin(excluded_ids)].copy()
    raw_board = raw_board.sort_values(score_field, ascending=False).reset_index(drop=True)
    best_available = _prefer_healthy_headline_candidate(board, score_column="startup_score")
    best_raw = _prefer_healthy_headline_candidate(raw_board, score_column=score_field) if not raw_board.empty else best_available
    position_candidates = []
    for pos in ["QB", "RB", "WR", "TE"]:
        group = board[board["position"] == pos].copy()
        if not group.empty:
            row = _prefer_healthy_headline_candidate(
                group,
                score_column="startup_score",
                search_limit=5,
                tolerance_ratio=0.05,
                tolerance_points=180,
            )
            position_candidates.append((float(row.get("scarcity_score") or 0) + float(row.get("startup_score") or 0) * 0.08, row))
    best_positional = max(position_candidates, key=lambda item: item[0])[1] if position_candidates else best_available
    tier_warning = startup_tier_break_warning(board)
    trade_move = startup_trade_move_note(board)

    render_section_header(
        "Recommendations",
        kicker="Draft Guidance",
        note="These recommendations reuse the main valuation and strategy pipeline, with only a small strategy preset overlay for startup builds.",
    )
    render_summary_tiles(
        [
            {
                "label": "Best Player Available",
                "value": player_display_name(best_raw),
                "note": f"{_safe_text(best_raw.get('player_tier'), 'Developmental')} | {_safe_text(best_raw.get('position'))} | {_safe_text(best_raw.get('opportunity_label'), 'Opportunity unclear')}",
                "tone": "power",
            },
            {
                "label": "Best Fit By Strategy",
                "value": player_display_name(best_available),
                "note": f"{startup_strategy} | {_safe_text(best_available.get('player_tier'), 'Developmental')} | {_safe_text(best_available.get('opportunity_label'), 'Opportunity unclear')}",
                "tone": "strategy",
            },
            {
                "label": "Best Positional Value",
                "value": f"{player_display_name(best_positional)} ({_safe_text(best_positional.get('position'))})",
                "note": f"Scarcity {_format_score(best_positional.get('scarcity_score'))} | Opportunity {_safe_text(best_positional.get('opportunity_label'), 'Unknown')}",
                "tone": "opportunity",
            },
            {
                "label": "Tier Break Warning",
                "value": _safe_text(best_available.get("player_tier"), "Developmental"),
                "note": tier_warning,
                "tone": "franchise",
            },
        ]
    )
    render_player_detail_button_grid(
        [best_raw, best_available, best_positional],
        key_prefix=f"startup_detail_{startup_context.get('league_id')}",
        return_page="startup_draft_center",
        source_label="Startup Draft Center",
        title="Recommended player profiles",
        max_buttons=3,
        open_mode="quick_view",
    )
    st.caption(trade_move)

    render_section_header(
        "Draft Board",
        kicker="Available Players",
        note=f"Draft slot {int(draft_slot)} | Round {int(current_round)} | Pick {int(current_pick)} | Strategy {startup_strategy}",
    )
    card_score_field = "startup_score" if "startup_score" in board.columns else score_field
    card_board = draft_center_ui._available_card_board(
        board.head(120).reset_index(drop=True),
        card_score_field,
    )
    if not card_board.empty:
        card_board.loc[0, "recommendation_label"] = "Best Available"
        card_board.loc[0, "recommendation_reason"] = _safe_text(
            card_board.loc[0].get("opportunity_explanation")
            or card_board.loc[0].get("opportunity_label"),
            "Highest player on the existing Startup Draft Center board.",
        )
        label_targets = (
            (best_available, "Best Fit"),
            (best_positional, "Position Need"),
        )
        for target, label in label_targets:
            target_id = _safe_text(target.get("player_id"))
            if not target_id:
                continue
            matches = card_board.index[card_board["player_id"].astype(str) == target_id].tolist()
            if not matches:
                continue
            row_index = matches[0]
            if not _safe_text(card_board.loc[row_index].get("recommendation_label")):
                card_board.loc[row_index, "recommendation_label"] = label
            card_board.loc[row_index, "recommendation_reason"] = _safe_text(
                card_board.loc[row_index].get("opportunity_explanation")
                or card_board.loc[row_index].get("opportunity_label"),
                "Existing Startup Draft Center recommendation.",
            )
        st.markdown(live_draft_ui.ranking_card_styles_html(), unsafe_allow_html=True)
        board_html = "<div class='live-rank-list'>" + "".join(
            live_draft_ui._ranking_row_html(row)
            for row in card_board.to_dict("records")
        ) + "</div>"
        clicked_player_id = _render_tappable_player_html(
            html=board_html,
            key_prefix=f"startup_ranked_board_{startup_context.get('league_id')}",
        )
        if clicked_player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="Startup Draft Center",
                source_note="Startup Draft Center available-player board.",
            )
    else:
        st.info("No available players match the current startup draft board.")


    render_analysis_cards(
        [
            {
                "label": "Best Player Available",
                "title": player_display_name(best_raw),
                "items": [
                    _safe_text(best_raw.get("opportunity_explanation"), "No opportunity explanation available."),
                    f"{league_score_label(score_field)} {_format_score(best_raw.get(score_field))}",
                ],
                "tone": "strength",
            },
            {
                "label": "Best Fit By Strategy",
                "title": player_display_name(best_available),
                "items": [
                    _safe_text(best_available.get("opportunity_explanation"), "No opportunity explanation available."),
                    f"Tier {_safe_text(best_available.get('player_tier'), 'Developmental')} | Injury {_safe_text(best_available.get('injury_level'), 'healthy')}",
                ],
                "tone": "opportunity",
            },
        ]
    )

    with st.expander("Drafted players and exclusions", expanded=False):
        st.caption(
            f"Draft picks logged: {_safe_positive_int(startup_context.get('picks_made'), 0)} / {_safe_positive_int(startup_context.get('total_picks'), 0)}"
        )
        drafted_rows = []
        player_lookup = df_players.set_index(df_players["player_id"].astype(str))
        for player_id in list(drafted_player_ids)[:250]:
            if player_id in player_lookup.index:
                row = player_lookup.loc[player_id]
                drafted_rows.append(
                    {
                        "Player": player_display_name(row),
                        "Pos": _safe_text(row.get("position")),
                        "Team": _safe_text(row.get("team")),
                        "Tier": _safe_text(row.get("player_tier")),
                    }
                )
        if drafted_rows:
            executive_table_ui.render_executive_table_disclosure(
                pd.DataFrame(drafted_rows),
                title="Recently drafted players",
                primary_column="Player",
                secondary_columns=("Pos", "Team"),
                meta_column="Tier",
                max_summary_rows=10,
                expander_label="Full drafted-player table",
                key_suffix="draft_exclusion_feed",
            )
        else:
            st.caption("No drafted-player feed was available from Sleeper yet. Use manual exclusions if needed.")


def owner_handle(username: str, fallback: str = "") -> str:
    username = _safe_text(username).strip()
    if username:
        return f"@{username}"
    return _safe_text(fallback).strip()


def render_league_team_page_header(team_profile: dict, selected_league_name: str):
    return league_workspace_ui.render_league_team_page_header(
        team_profile,
        selected_league_name,
        team_logo_html=team_logo_html,
    )


def get_needed_positions(
    my_team_df: pd.DataFrame,
    metrics: dict | None,
    league_settings: dict | None = None,
    *,
    include_fallback: bool = True,
    assessment: TeamNeedsAssessment | None = None,
    lineup_df: pd.DataFrame | None = None,
) -> list[str]:
    """Return the legacy position list derived from a canonical assessment."""

    resolved_assessment = assessment or build_team_needs_assessment(
        my_team_df,
        metrics,
        league_settings,
        lineup_df=lineup_df,
    )
    ordered_positions = list(resolved_assessment.true_needs)
    if include_fallback:
        ordered_positions.extend(resolved_assessment.upgrade_opportunities)
        ordered_positions.extend(resolved_assessment.future_risks)
    return list(dict.fromkeys(ordered_positions))[:4]


def build_team_needs_assessment(
    roster_df: pd.DataFrame,
    metrics: dict | None,
    league_settings: dict | None = None,
    *,
    lineup_df: pd.DataFrame | None = None,
) -> TeamNeedsAssessment:
    """Build one immutable assessment from an already-loaded roster context."""

    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    resolved_lineup = (
        lineup_df
        if lineup_df is not None
        else suggest_optimal_lineup(roster_df, settings)
    )
    return assess_team_needs(
        roster_df,
        resolved_lineup,
        settings,
        relative_weaknesses=list((metrics or {}).get("weaknesses", []) or []),
    )


def team_need_display(assessment: TeamNeedsAssessment) -> dict[str, str]:
    """Select an accurate need-category headline without collapsing semantics."""

    position_items = {
        item.position: item for item in assessment.positions
    }
    current_needs = [
        position
        for position in assessment.true_needs
        if (
            position_items.get(position) is not None
            and position_items[position].classification == "short_term_need"
            and not position_items[position].temporary_injury_pressure
        )
    ]
    if current_needs:
        return {
            "category": "true_need",
            "label": "Biggest Team Need",
            "value": current_needs[0],
            "note": "Starter and depth coverage identify this as the clearest current roster deficiency.",
            "tone": "need",
        }
    if assessment.temporary_injury_pressures:
        return {
            "category": "injury_pressure",
            "label": "Injury Pressure",
            "value": assessment.temporary_injury_pressures[0],
            "note": "Current availability is creating temporary pressure in this room.",
            "tone": "risk",
        }
    if assessment.future_risks:
        return {
            "category": "future_risk",
            "label": "Future Roster Risk",
            "value": assessment.future_risks[0],
            "note": "Current coverage is playable, but future stability is limited.",
            "tone": "draft",
        }
    if assessment.upgrade_opportunities:
        return {
            "category": "upgrade",
            "label": "Upgrade Opportunity",
            "value": assessment.upgrade_opportunities[0],
            "note": "This covered room trails the league baseline but is not a true roster need.",
            "tone": "need",
        }
    return {
        "category": "balanced",
        "label": "Balanced Roster",
        "value": "No urgent need",
        "note": "No current roster deficiency is standing out under the canonical coverage policy.",
        "tone": "draft",
    }


def player_fit_context(
    position: str,
    assessment: TeamNeedsAssessment,
    *,
    on_roster: bool = False,
) -> dict[str, str]:
    """Return shared quick-view/detail language for one positional fit."""

    normalized = _safe_text(position).upper()
    item = assessment.for_position(normalized)
    if item is None:
        return {
            "category": "neutral",
            "message": "Does not address a current roster priority.",
            "tone": "strategy",
        }
    if item.temporary_injury_pressure:
        return {
            "category": "injury_pressure",
            "message": (
                f"Provides cover for temporary injury pressure in the {normalized} room."
                if on_roster
                else f"Helps temporary injury pressure in the {normalized} room."
            ),
            "tone": "risk",
        }
    if item.true_need and item.classification == "short_term_need":
        return {
            "category": "true_need",
            "message": (
                f"Supports a current {normalized} roster need, so moving this player creates more pressure."
                if on_roster
                else f"Fills a {normalized} roster need."
            ),
            "tone": "opportunity",
        }
    if item.upgrade_opportunity:
        return {
            "category": "upgrade",
            "message": (
                f"Contributes to a covered {normalized} room that remains an upgrade opportunity."
                if on_roster
                else f"Upgrades a covered {normalized} room."
            ),
            "tone": "opportunity",
        }
    if item.future_risk:
        return {
            "category": "future_stability",
            "message": (
                f"Provides future stability in the {normalized} room."
                if on_roster
                else f"Supports future stability in the {normalized} room."
            ),
            "tone": "strategy",
        }
    return {
        "category": "depth",
        "message": (
            f"Provides useful {normalized} depth without covering an urgent need."
            if on_roster
            else f"Adds useful {normalized} depth without filling an urgent need."
        ),
        "tone": "strategy",
    }


def roster_injury_context(
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None = None,
) -> dict:
    return summarize_team_injuries(roster_df, lineup_df)


SEVERE_RESERVE_STATUSES = {
    "out",
    "injured reserve",
    "ir",
    "pup",
    "nfi",
    "physically unable to perform",
    "non-football injury",
}

LOW_VALUE_TIERS = {"Contributor", "Depth", "Developmental"}
LOW_OPPORTUNITY_LABELS = {"Buried Depth", "Handcuff"}
UPSIDE_OPPORTUNITY_LABELS = {"Backup With Upside", "Starter At Risk", "Committee Back"}


def roster_limit_status(
    *,
    league_id: str,
    roster_id,
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame,
    league_settings: dict | None,
    score_field: str,
    active_team_strategy: str,
    needed_positions: list[str] | None,
    surplus_positions: list[str] | None,
    untouchables: list[str] | None = None,
) -> dict:
    default = {
        "available": False,
        "max_roster_size": 0,
        "current_roster_size": 0,
        "active_roster_size": 0,
        "total_rostered_players": 0,
        "starter_slots": 0,
        "bench_slots": 0,
        "taxi_slots": 0,
        "ir_slots": 0,
        "taxi_count": 0,
        "reserve_count": 0,
        "exempt_player_count": 0,
        "open_taxi_slots": 0,
        "open_ir_slots": 0,
        "over_limit": False,
        "over_by": 0,
        "strongest_surplus_positions": [],
        "thinnest_positions": [],
        "replaceable_lineup_needs": [],
        "thinnest_position_notes": {},
        "drop_candidates": [],
        "trade_candidates": [],
        "move_candidates": [],
        "keep_candidates": [],
        "drop_candidates_structured": [],
        "trade_candidates_structured": [],
        "move_candidates_structured": [],
        "keep_candidates_structured": [],
        "lowest_utility_candidates": [],
        "rostered_no_team_players": [],
        "candidate_player_rows": [],
    }
    if not league_id or roster_id is None or roster_df is None or roster_df.empty:
        return default

    resolved_settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    resolved_settings.update(league_settings or {})
    league = get_league(league_id) or {}
    league_meta_settings = league.get("settings") if isinstance(league.get("settings"), dict) else {}
    roster_positions = [str(pos or "").upper() for pos in league.get("roster_positions", []) or []]
    bench_positions = {"BN", "BE", "BENCH"}

    starter_slots = len([pos for pos in roster_positions if pos and pos not in {"IR", "TAXI", *bench_positions}])
    bench_slots = sum(1 for pos in roster_positions if pos in bench_positions)
    taxi_slots = max(
        sum(1 for pos in roster_positions if pos == "TAXI"),
        _safe_nonnegative_int(league_meta_settings.get("taxi_slots"), 0),
    )
    ir_slots = max(
        sum(1 for pos in roster_positions if pos == "IR"),
        _safe_nonnegative_int(league_meta_settings.get("reserve_slots"), 0),
    )
    max_roster_size = starter_slots + bench_slots
    if max_roster_size <= 0:
        starter_slots = _safe_positive_int(resolved_settings.get("starter_count"), 9)
        bench_slots = _safe_nonnegative_int(resolved_settings.get("bench_count"), 0)
        taxi_slots = _safe_nonnegative_int(resolved_settings.get("taxi_count"), 0)
        ir_slots = _safe_nonnegative_int(resolved_settings.get("ir_count"), 0)
        max_roster_size = starter_slots + bench_slots

    roster_payload = next(
        (roster for roster in get_rosters(league_id) or [] if str(roster.get("roster_id")) == str(roster_id)),
        {},
    )
    roster_player_ids = {str(pid) for pid in roster_payload.get("players", []) or [] if pid is not None}
    reserve_ids = {str(pid) for pid in roster_payload.get("reserve", []) or [] if pid is not None}
    taxi_ids = {str(pid) for pid in roster_payload.get("taxi", []) or [] if pid is not None}
    total_rostered_players = len(roster_player_ids) or len(roster_df)
    taxi_count = len(roster_player_ids & taxi_ids)
    reserve_count = len(roster_player_ids & reserve_ids)
    exempt_taxi_count = min(taxi_count, taxi_slots)
    exempt_reserve_count = min(reserve_count, ir_slots)
    exempt_player_count = exempt_taxi_count + exempt_reserve_count
    active_roster_size = max(0, total_rostered_players - exempt_player_count)
    current_roster_size = active_roster_size
    open_taxi_slots = max(0, taxi_slots - taxi_count)
    open_ir_slots = max(0, ir_slots - reserve_count)
    over_by = max(0, active_roster_size - max_roster_size)

    result = dict(default)
    result.update(
        {
            "available": max_roster_size > 0,
            "max_roster_size": max_roster_size,
            "current_roster_size": current_roster_size,
            "active_roster_size": active_roster_size,
            "total_rostered_players": total_rostered_players,
            "starter_slots": starter_slots,
            "bench_slots": bench_slots,
            "taxi_slots": taxi_slots,
            "ir_slots": ir_slots,
            "taxi_count": taxi_count,
            "reserve_count": reserve_count,
            "exempt_player_count": exempt_player_count,
            "open_taxi_slots": open_taxi_slots,
            "open_ir_slots": open_ir_slots,
            "over_limit": over_by > 0,
            "over_by": over_by,
        }
    )

    team_df = roster_df.copy()
    team_df["player_id"] = team_df["player_id"].astype(str)
    loaded_player_ids = set(team_df["player_id"].astype(str))
    missing_roster_player_ids = sorted(
        pid for pid in roster_player_ids
        if pid and pid not in loaded_player_ids
    )
    if missing_roster_player_ids:
        raw_player_directory = cached_sleeper_player_directory()
        missing_rows = [
            _build_missing_rostered_player_row(pid, raw_player_directory.get(pid))
            for pid in missing_roster_player_ids
        ]
        missing_rows = [row for row in missing_rows if isinstance(row, dict)]
        if missing_rows:
            missing_df = pd.DataFrame(missing_rows)
            all_cols = list(dict.fromkeys(list(team_df.columns) + list(missing_df.columns)))
            team_df = team_df.reindex(columns=all_cols)
            missing_df = missing_df.reindex(columns=all_cols)
            team_df = pd.concat([team_df, missing_df], ignore_index=True, sort=False)
    starter_ids = {
        str(pid)
        for pid in lineup_df.loc[lineup_df.get("suggested_starter", False).fillna(False), "player_id"].astype(str).tolist()
    } if lineup_df is not None and not lineup_df.empty and "suggested_starter" in lineup_df.columns else set()
    needed_set = {str(pos).upper() for pos in (needed_positions or [])}
    surplus_set = {str(pos).upper() for pos in (surplus_positions or [])}
    untouchable_set = {str(name) for name in (untouchables or [])}

    rank_column = "value_score" if "value_score" in team_df.columns else score_field
    team_df["score_num"] = pd.to_numeric(team_df.get(rank_column, 0), errors="coerce").fillna(0)
    team_df["market_score_num"] = pd.to_numeric(
        team_df.get("market_score", team_df.get("value", 0)),
        errors="coerce",
    ).fillna(0)
    team_df["opportunity_score_num"] = pd.to_numeric(
        team_df.get("opportunity_score", 0),
        errors="coerce",
    ).fillna(0)
    team_df["age_num"] = pd.to_numeric(team_df.get("age", 0), errors="coerce").fillna(0)
    team_df["years_exp_num"] = pd.to_numeric(team_df.get("years_exp", 99), errors="coerce").fillna(99)
    team_df["raw_search_rank_num"] = pd.to_numeric(team_df.get("search_rank", 999999), errors="coerce").fillna(999999)
    team_df["position_key"] = team_df.get("position", "").fillna("").astype(str).str.upper()
    team_df["role_label"] = team_df.get("role", pd.Series("Flex", index=team_df.index)).fillna("Flex").astype(str)
    team_df["tier_label"] = team_df.get("player_tier", "").fillna("").astype(str)
    team_df["opportunity_label_text"] = team_df.get("opportunity_label", "").fillna("").astype(str)
    team_df["starter_flag"] = team_df["player_id"].isin(starter_ids)
    team_df["untouchable_flag"] = team_df["name"].astype(str).isin(untouchable_set)
    team_df["need_flag"] = team_df["position_key"].isin(needed_set)
    team_df["surplus_flag"] = team_df["position_key"].isin(surplus_set)
    team_df["already_taxi_flag"] = team_df["player_id"].isin(taxi_ids)
    team_df["already_reserve_flag"] = team_df["player_id"].isin(reserve_ids)
    team_df["injury_flag"] = team_df.apply(is_injury_status, axis=1)
    team_df["core_role_flag"] = team_df["role_label"].str.strip().str.lower().eq("core")
    team_df["bench_role_flag"] = team_df["role_label"].str.strip().str.lower().eq("bench")
    team_df["severe_reserve_flag"] = (
        team_df.get("status", pd.Series("", index=team_df.index)).fillna("").astype(str).str.strip().str.lower().isin(SEVERE_RESERVE_STATUSES)
        | team_df.get("injury_status", pd.Series("", index=team_df.index)).fillna("").astype(str).str.strip().str.lower().isin(SEVERE_RESERVE_STATUSES)
    )
    low_score_cutoff = float(team_df["score_num"].median()) if not team_df["score_num"].empty else 0.0
    tradeable_score_cutoff = float(team_df["score_num"].quantile(0.40)) if not team_df["score_num"].empty else 0.0
    protected_score_cutoff = float(team_df["score_num"].quantile(0.60)) if not team_df["score_num"].empty else 0.0
    low_market_cutoff = float(team_df["market_score_num"].quantile(0.35)) if not team_df["market_score_num"].empty else 0.0
    low_opportunity_score_cutoff = (
        float(team_df["opportunity_score_num"].quantile(0.35))
        if not team_df["opportunity_score_num"].empty
        else 0.0
    )
    team_df["high_tier_flag"] = team_df["tier_label"].isin({"Elite", "Star", "Core Starter"})
    team_df["strong_opportunity_flag"] = team_df["opportunity_label_text"].isin(
        {"Elite Opportunity", "Strong Opportunity", "Starter At Risk"}
    )
    team_df["taxi_eligible_flag"] = (
        team_df["years_exp_num"].le(1)
        & ~team_df["starter_flag"]
        & ~team_df["already_taxi_flag"]
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental"})
    )
    team_df["young_upside_flag"] = team_df["age_num"].le(24) | team_df["years_exp_num"].le(1)
    team_df["low_value_flag"] = (
        team_df["score_num"].le(max(1.0, low_score_cutoff))
        | team_df["tier_label"].isin(LOW_VALUE_TIERS)
    )
    team_df["low_market_flag"] = team_df["market_score_num"].le(max(1.0, low_market_cutoff))
    team_df["low_opportunity_score_flag"] = team_df["opportunity_score_num"].le(
        max(1.0, low_opportunity_score_cutoff)
    )
    team_df["utility_opportunity_score_num"] = team_df["opportunity_score_num"].copy()
    team_df.loc[
        team_df["opportunity_label_text"].isin(LOW_OPPORTUNITY_LABELS),
        "utility_opportunity_score_num",
    ] = 0
    team_df.loc[
        team_df["opportunity_label_text"].eq("Handcuff"),
        "utility_opportunity_score_num",
    ] = team_df.loc[
        team_df["opportunity_label_text"].eq("Handcuff"),
        "utility_opportunity_score_num",
    ] * 0.35
    no_team_diagnostics = team_df.apply(_player_no_team_diagnostics, axis=1)
    team_df["blank_team_flag"] = no_team_diagnostics.apply(lambda item: bool(item.get("blank_team_flag")))
    team_df["fa_team_flag"] = no_team_diagnostics.apply(lambda item: bool(item.get("fa_team_flag")))
    team_df["active_metadata_flag"] = no_team_diagnostics.apply(lambda item: bool(item.get("active_flag")))
    team_df["suspicious_team_metadata_flag"] = no_team_diagnostics.apply(
        lambda item: bool(item.get("suspicious_team_metadata_flag"))
    )
    team_df["no_nfl_team_flag"] = no_team_diagnostics.apply(lambda item: bool(item.get("no_nfl_team_flag")))
    team_df["no_team_reason_text"] = no_team_diagnostics.apply(lambda item: _safe_text(item.get("reason_text")))
    team_df.loc[team_df["no_nfl_team_flag"], "utility_opportunity_score_num"] = 0
    team_df["position_rank_num"] = (
        team_df.groupby("position_key")["score_num"]
        .rank(method="first", ascending=False)
        .fillna(999)
    )
    team_df["blocked_count"] = (team_df["position_rank_num"] - 1).clip(lower=0)
    team_df["stale_player_flag"] = team_df.apply(is_probably_stale_free_agent, axis=1)

    starter_pos_counts = (
        lineup_df.loc[lineup_df.get("suggested_starter", False).fillna(False), "position"]
        .fillna("")
        .astype(str)
        .str.upper()
        .value_counts()
        .to_dict()
        if lineup_df is not None and not lineup_df.empty and "position" in lineup_df.columns
        else {}
    )
    roster_pos_counts = team_df["position_key"].value_counts().to_dict()
    required_kickers = _safe_nonnegative_int(
        resolved_settings.get("k_count"),
        roster_positions.count("K"),
    )
    active_kicker_count = int(
        (
            team_df["position_key"].eq("K")
            & ~team_df["injury_flag"]
            & ~team_df["stale_player_flag"]
        ).sum()
    )
    replaceable_lineup_needs = (
        ["K"]
        if required_kickers > 0 and active_kicker_count < required_kickers
        else []
    )
    reserve_pos_counts = {
        pos: max(0, _safe_positive_int(roster_pos_counts.get(pos), 0) - _safe_positive_int(starter_pos_counts.get(pos), 0))
        for pos in roster_pos_counts.keys()
    }
    bench_buffer_by_pos = {
        "QB": 1,
        "RB": 2,
        "WR": 2,
        "TE": 1,
        "K": 0,
        "DEF": 0,
        "DST": 0,
    }
    depth_target_by_pos = {
        pos: _safe_positive_int(starter_pos_counts.get(pos), 0) + bench_buffer_by_pos.get(pos, 1)
        for pos in roster_pos_counts.keys()
    }
    depth_excess_by_pos = {
        pos: max(0, _safe_positive_int(roster_pos_counts.get(pos), 0) - _safe_positive_int(depth_target_by_pos.get(pos), 0))
        for pos in roster_pos_counts.keys()
    }
    team_df["reserve_count_at_pos"] = team_df["position_key"].map(lambda pos: reserve_pos_counts.get(pos, 0)).fillna(0)
    team_df["depth_excess"] = team_df["position_key"].map(lambda pos: depth_excess_by_pos.get(pos, 0)).fillna(0)
    team_df["replaceable_position_surplus_flag"] = (
        team_df["position_key"].eq("K")
        & team_df["position_rank_num"].gt(max(1, required_kickers))
    )
    team_df["thin_room_flag"] = team_df["position_key"].map(
        lambda pos: _safe_positive_int(roster_pos_counts.get(pos), 0)
        <= (_safe_positive_int(starter_pos_counts.get(pos), 0) + (1 if pos in {"QB", "TE"} else 0))
    ).fillna(False)
    team_df["important_handcuff_flag"] = (
        team_df["opportunity_label_text"].eq("Handcuff")
        & team_df["position_key"].isin({"RB", "QB"})
        & (
            team_df["need_flag"]
            | team_df["position_key"].map(lambda pos: _safe_positive_int(starter_pos_counts.get(pos), 0) > 0).fillna(False)
            | pd.Series(normalize_team_strategy(active_team_strategy) in {"contender", "fringe_contender"}, index=team_df.index)
        )
    )
    team_df["rookie_stash_flag"] = (
        team_df["position_key"].isin({"QB", "RB", "WR", "TE"})
        & team_df["years_exp_num"].le(1)
        & team_df["age_num"].le(24)
        & ~team_df["starter_flag"]
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental", "Starter"})
    )
    team_df["developmental_qb_flag"] = (
        team_df["position_key"].eq("QB")
        & team_df["years_exp_num"].le(2)
        & team_df["age_num"].le(25)
        & ~team_df["starter_flag"]
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental", "Starter"})
    )
    team_df["young_skill_stash_flag"] = (
        team_df["position_key"].isin({"RB", "WR", "TE"})
        & team_df["years_exp_num"].le(2)
        & team_df["age_num"].le(24)
        & ~team_df["starter_flag"]
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental", "Starter"})
    )
    team_df["recent_stash_flag"] = (
        team_df["rookie_stash_flag"]
        | team_df["developmental_qb_flag"]
        | team_df["young_skill_stash_flag"]
    )
    team_df["developmental_keep_flag"] = (
        (
            (
                team_df["young_upside_flag"]
                & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental", "Starter"})
                & (
                    team_df["opportunity_label_text"].isin(UPSIDE_OPPORTUNITY_LABELS)
                    | team_df["score_num"].ge(max(1.0, protected_score_cutoff))
                )
                & ~team_df["opportunity_label_text"].eq("Buried Depth")
            )
            | team_df["recent_stash_flag"]
        )
        & ~team_df["important_handcuff_flag"]
    )
    team_df["no_team_exception_flag"] = (
        team_df["no_nfl_team_flag"]
        & (
            team_df["score_num"].ge(max(3500.0, protected_score_cutoff))
            | team_df["market_score_num"].ge(max(2200.0, low_market_cutoff * 3.0))
            | (
                team_df["rookie_stash_flag"]
                & team_df["raw_search_rank_num"].le(120)
            )
            | (
                team_df["developmental_qb_flag"]
                & team_df["raw_search_rank_num"].le(220)
                & team_df["market_score_num"].ge(900.0)
            )
        )
    )
    team_df["unsigned_no_team_flag"] = team_df["no_nfl_team_flag"] & ~team_df["no_team_exception_flag"]
    team_df["protected_low_value_flag"] = (
        team_df["untouchable_flag"]
        | team_df["core_role_flag"]
        | team_df["starter_flag"]
        | team_df["high_tier_flag"]
        | team_df["need_flag"]
        | team_df["strong_opportunity_flag"]
        | team_df["important_handcuff_flag"]
        | team_df["developmental_keep_flag"]
        | team_df["rookie_stash_flag"]
        | team_df["developmental_qb_flag"]
        | team_df["no_team_exception_flag"]
        | (team_df["young_upside_flag"] & team_df["score_num"].ge(max(1.0, protected_score_cutoff)))
    )
    team_df["little_trade_value_flag"] = (
        team_df["score_num"].le(max(1.0, tradeable_score_cutoff))
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental"})
        & ~team_df["strong_opportunity_flag"]
    )
    team_df["veteran_depth_flag"] = (
        team_df["age_num"].ge(26)
        & team_df["years_exp_num"].ge(3)
        & team_df["tier_label"].isin({"Contributor", "Depth", "Developmental"})
        & ~team_df["starter_flag"]
        & ~team_df["need_flag"]
        & ~team_df["important_handcuff_flag"]
    )
    team_df["veteran_clogger_flag"] = (
        team_df["veteran_depth_flag"]
        & ~team_df["strong_opportunity_flag"]
        & (
            team_df["opportunity_label_text"].isin(LOW_OPPORTUNITY_LABELS)
            | team_df["low_market_flag"]
            | team_df["little_trade_value_flag"]
        )
    )
    team_df["free_agent_level_veteran_flag"] = (
        team_df["veteran_clogger_flag"]
        & (
            team_df["stale_player_flag"]
            | (
                team_df["opportunity_label_text"].isin(LOW_OPPORTUNITY_LABELS)
                & team_df["market_score_num"].le(max(125.0, low_market_cutoff * 1.6))
            )
        )
    )
    team_df["replacement_level_flag"] = (
        team_df["low_value_flag"]
        & team_df["little_trade_value_flag"]
        & ~team_df["starter_flag"]
        & ~team_df["recent_stash_flag"]
        & (
            team_df["stale_player_flag"]
            | team_df["free_agent_level_veteran_flag"]
            | team_df["low_market_flag"]
            | team_df["bench_role_flag"]
        )
    )
    team_df["drop_protection_flag"] = (
        team_df["untouchable_flag"]
        | team_df["core_role_flag"]
        | team_df["starter_flag"]
        | team_df["high_tier_flag"]
        | team_df["important_handcuff_flag"]
        | team_df["rookie_stash_flag"]
        | team_df["developmental_qb_flag"]
        | team_df["no_team_exception_flag"]
        | (
            team_df["strong_opportunity_flag"]
            & team_df["score_num"].ge(max(1.0, low_score_cutoff))
        )
    )
    team_df["roster_utility_score"] = (
        team_df["score_num"] * 0.56
        + team_df["market_score_num"] * 0.26
        + team_df["utility_opportunity_score_num"] * 0.18
    )
    team_df.loc[team_df["starter_flag"], "roster_utility_score"] += 18
    team_df.loc[team_df["high_tier_flag"], "roster_utility_score"] += 14
    team_df.loc[team_df["core_role_flag"], "roster_utility_score"] += 12
    team_df.loc[team_df["need_flag"], "roster_utility_score"] += 10
    team_df.loc[team_df["strong_opportunity_flag"], "roster_utility_score"] += 10
    team_df.loc[team_df["important_handcuff_flag"], "roster_utility_score"] += 10
    team_df.loc[team_df["developmental_keep_flag"], "roster_utility_score"] += 8
    team_df.loc[team_df["young_upside_flag"] & ~team_df["low_value_flag"], "roster_utility_score"] += 6
    team_df.loc[team_df["young_skill_stash_flag"], "roster_utility_score"] += 90
    team_df.loc[team_df["rookie_stash_flag"], "roster_utility_score"] += 120
    team_df.loc[team_df["developmental_qb_flag"], "roster_utility_score"] += 140
    team_df.loc[team_df["bench_role_flag"], "roster_utility_score"] -= 8
    team_df.loc[team_df["low_value_flag"], "roster_utility_score"] -= 12
    team_df.loc[team_df["little_trade_value_flag"], "roster_utility_score"] -= 10
    team_df.loc[team_df["opportunity_label_text"].isin(LOW_OPPORTUNITY_LABELS), "roster_utility_score"] -= 10
    team_df.loc[team_df["depth_excess"].ge(1), "roster_utility_score"] -= 8
    team_df.loc[
        team_df["replaceable_position_surplus_flag"],
        "roster_utility_score",
    ] -= 18
    team_df.loc[team_df["blocked_count"].ge(1), "roster_utility_score"] -= (
        team_df.loc[team_df["blocked_count"].ge(1), "blocked_count"].clip(upper=4) * 4
    )
    team_df.loc[team_df["position_key"].isin({"QB", "TE"}) & team_df["reserve_count_at_pos"].ge(2), "roster_utility_score"] -= 6
    team_df.loc[team_df["age_num"].ge(27) & team_df["years_exp_num"].ge(4), "roster_utility_score"] -= 6
    team_df.loc[team_df["stale_player_flag"], "roster_utility_score"] -= 20
    team_df.loc[team_df["replacement_level_flag"], "roster_utility_score"] -= 18
    team_df.loc[team_df["unsigned_no_team_flag"], "roster_utility_score"] -= 260
    team_df.loc[team_df["veteran_clogger_flag"], "roster_utility_score"] -= 120
    team_df.loc[team_df["free_agent_level_veteran_flag"], "roster_utility_score"] -= 180
    strongest_surplus_positions = sorted(
        {
            pos
            for pos in roster_pos_counts.keys()
            if pos and (pos in surplus_set or depth_excess_by_pos.get(pos, 0) > 0)
        },
        key=lambda pos: (
            depth_excess_by_pos.get(pos, 0),
            reserve_pos_counts.get(pos, 0),
            roster_pos_counts.get(pos, 0),
        ),
        reverse=True,
    )
    thinnest_positions = sorted(
        {
            pos
            for pos in roster_pos_counts.keys()
            if pos in {"QB", "RB", "WR", "TE"}
            and (
                pos in needed_set
                or (
                    pos in {"RB", "WR"}
                    and
                    team_df["position_key"].eq(pos).any()
                    and _safe_positive_int(roster_pos_counts.get(pos), 0)
                    <= (_safe_positive_int(starter_pos_counts.get(pos), 0) + 1)
                )
            )
        },
        key=lambda pos: (
            _safe_positive_int(roster_pos_counts.get(pos), 0) - _safe_positive_int(starter_pos_counts.get(pos), 0),
            _safe_positive_int(roster_pos_counts.get(pos), 0),
        ),
    )
    result["strongest_surplus_positions"] = strongest_surplus_positions[:3]
    result["thinnest_positions"] = thinnest_positions[:3]
    result["replaceable_lineup_needs"] = replaceable_lineup_needs
    result["thinnest_position_notes"] = {
        pos: (
            f"{_safe_positive_int(roster_pos_counts.get(pos), 0)} rostered for "
            f"{_safe_positive_int(starter_pos_counts.get(pos), 0)} projected starter"
            + (
                "s"
                if _safe_positive_int(starter_pos_counts.get(pos), 0) != 1
                else ""
            )
        )
        for pos in thinnest_positions[:3]
    }

    def _player_note(row, reason: str) -> str:
        chips = []
        tier = _safe_text(row.get("tier_label"))
        opp = _safe_text(row.get("opportunity_label_text"))
        role = _safe_text(row.get("role_label"))
        if tier:
            chips.append(tier)
        if opp:
            chips.append(opp)
        if role and role != "Flex":
            chips.append(role)
        meta = " | ".join(chips)
        return f"{player_display_name(row)} ({_safe_text(row.get('position_key'))})" + (f" - {meta}. {reason}" if meta else f" - {reason}")

    move_candidates: list[str] = []
    move_candidates_structured: list[dict] = []
    severe_move_df = team_df[
        team_df["severe_reserve_flag"]
        & ~team_df["already_reserve_flag"]
        & ~team_df["untouchable_flag"]
    ].sort_values(["starter_flag", "score_num"], ascending=[True, False])
    move_priority = 1
    for _, row in severe_move_df.head(open_ir_slots).iterrows():
        reason = "IR slot is available and this injury designation can clear an active roster spot without burning value."
        move_candidates.append(_player_note(row, reason))
        move_candidates_structured.append(
            _build_structured_decision_candidate(
                row,
                bucket="move",
                reason=reason,
                priority=move_priority,
                source="ir_move",
            )
        )
        move_priority += 1

    remaining_taxi_slots = max(0, open_taxi_slots)
    if remaining_taxi_slots > 0:
        taxi_move_df = team_df[
            team_df["taxi_eligible_flag"]
            & ~team_df["untouchable_flag"]
        ].sort_values(["surplus_flag", "score_num", "age_num"], ascending=[False, True, True])
        for _, row in taxi_move_df.head(remaining_taxi_slots).iterrows():
            reason = "Taxi stash candidate: young, non-starter, and not a current priority lineup piece."
            move_candidates.append(_player_note(row, reason))
            move_candidates_structured.append(
                _build_structured_decision_candidate(
                    row,
                    bucket="move",
                    reason=reason,
                    priority=move_priority,
                    source="taxi_move",
                )
            )
            move_priority += 1

    keep_candidates: list[str] = []
    keep_candidates_structured: list[dict] = []
    keep_df = team_df[
        team_df["low_value_flag"]
        & team_df["protected_low_value_flag"]
    ].copy()
    keep_df["keep_score"] = 0.0
    keep_df.loc[keep_df["need_flag"], "keep_score"] += 24
    keep_df.loc[keep_df["core_role_flag"], "keep_score"] += 22
    keep_df.loc[keep_df["important_handcuff_flag"], "keep_score"] += 20
    keep_df.loc[keep_df["strong_opportunity_flag"], "keep_score"] += 18
    keep_df.loc[keep_df["developmental_keep_flag"], "keep_score"] += 16
    keep_df.loc[keep_df["young_upside_flag"], "keep_score"] += 12
    keep_df.loc[keep_df["severe_reserve_flag"], "keep_score"] += 10
    keep_df = keep_df.sort_values(["keep_score", "score_num"], ascending=[False, False])
    seen_keep_ids: set[str] = set()
    for _, row in keep_df.iterrows():
        pid = str(row.get("player_id"))
        if pid in seen_keep_ids:
            continue
        seen_keep_ids.add(pid)
        if row["need_flag"]:
            reason = f"Keep despite roster pressure because {_safe_text(row.get('position_key'))} is already one of your thinnest rooms."
        elif row["core_role_flag"]:
            reason = "Keep because you manually marked this player as a core piece in your roster plan."
        elif row["important_handcuff_flag"]:
            reason = "Important handcuff with real contingency value for the current roster shape."
        elif row["strong_opportunity_flag"]:
            reason = "Opportunity profile is too strong to treat as an easy cut, even under roster pressure."
        elif row["severe_reserve_flag"]:
            reason = "Keep because the player can be parked on IR instead of being cut."
        else:
            reason = "Young developmental stash with enough upside to protect instead of forcing a bad cut."
        keep_candidates.append(_player_note(row, reason))
        keep_candidates_structured.append(
            _build_structured_decision_candidate(
                row,
                bucket="keep",
                reason=reason,
                priority=len(keep_candidates_structured) + 1,
                source="roster_hold",
            )
        )
        if len(keep_candidates) >= 3:
            break

    strategy_key = normalize_team_strategy(active_team_strategy)
    trade_df = team_df[
        ~team_df["untouchable_flag"]
        & ~team_df["severe_reserve_flag"]
        & ~team_df["core_role_flag"]
        & ~team_df["protected_low_value_flag"]
        & ~team_df["no_nfl_team_flag"]
    ].copy()
    trade_df["trade_score"] = 0.0
    trade_df.loc[trade_df["surplus_flag"], "trade_score"] += 18
    trade_df.loc[trade_df["depth_excess"].ge(1), "trade_score"] += 16
    trade_df.loc[trade_df["blocked_count"].ge(1), "trade_score"] += 12
    trade_df.loc[trade_df["bench_role_flag"], "trade_score"] += 10
    trade_df.loc[trade_df["score_num"].gt(max(1.0, tradeable_score_cutoff)), "trade_score"] += 10
    trade_df.loc[trade_df["position_key"].isin({"QB", "TE"}) & trade_df["reserve_count_at_pos"].ge(2), "trade_score"] += 10
    if strategy_key in {"rebuild", "tank", "retool"}:
        trade_df.loc[trade_df["age_num"].ge(28), "trade_score"] += 14
    elif strategy_key in {"contender", "fringe_contender"}:
        trade_df.loc[~trade_df["starter_flag"] & (trade_df["surplus_flag"] | trade_df["depth_excess"].ge(1)), "trade_score"] += 10
        trade_df.loc[trade_df["starter_flag"], "trade_score"] -= 18
    trade_df.loc[trade_df["need_flag"], "trade_score"] -= 18
    trade_df.loc[trade_df["starter_flag"], "trade_score"] -= 16
    trade_df.loc[trade_df["young_upside_flag"], "trade_score"] -= 12
    trade_df.loc[trade_df["important_handcuff_flag"], "trade_score"] -= 14
    trade_df.loc[trade_df["strong_opportunity_flag"] & trade_df["age_num"].lt(26), "trade_score"] -= 10
    trade_df = trade_df.sort_values(["trade_score", "score_num"], ascending=[False, False])
    trade_candidates: list[str] = []
    trade_candidates_structured: list[dict] = []
    seen_trade_ids: set[str] = set()
    for _, row in trade_df.iterrows():
        if float(row.get("trade_score") or 0) <= 0:
            continue
        pid = str(row.get("player_id"))
        if pid in seen_trade_ids:
            continue
        seen_trade_ids.add(pid)
        if row["position_key"] in {"QB", "TE"} and _safe_positive_int(row.get("reserve_count_at_pos"), 0) >= 2:
            reason = f"Redundant {_safe_text(row.get('position_key'))} depth. Better to shop this piece than cut it for nothing."
        elif row["surplus_flag"] or _safe_positive_int(row.get("depth_excess"), 0) >= 1:
            reason = f"Better trade-away than drop because {_safe_text(row.get('position_key'))} is one of your surplus rooms and this player still holds some market value."
        elif strategy_key in {"rebuild", "tank", "retool"} and row["age_num"] >= 28:
            reason = "Older asset under the current strategy lens. Move the value out before the market softens."
        elif _safe_positive_int(row.get("blocked_count"), 0) >= 1:
            reason = "Blocked by stronger roster assets, but still valuable enough to market instead of cut."
        else:
            reason = "Bench asset with enough roster value to use in a 2-for-1 or pick-upgrade package."
        trade_candidates.append(_player_note(row, reason))
        trade_candidates_structured.append(
            _build_structured_decision_candidate(
                row,
                bucket="trade",
                reason=reason,
                priority=len(trade_candidates_structured) + 1,
                source="roster_trade",
            )
        )
        if len(trade_candidates) >= 3:
            break

    drop_df = team_df[
        ~team_df["untouchable_flag"]
        & ~team_df["severe_reserve_flag"]
        & ~team_df["drop_protection_flag"]
    ].copy()
    drop_df["drop_score"] = 0.0
    drop_df.loc[drop_df["unsigned_no_team_flag"], "drop_score"] += 72
    drop_df.loc[drop_df["free_agent_level_veteran_flag"], "drop_score"] += 42
    drop_df.loc[drop_df["veteran_clogger_flag"] & ~drop_df["free_agent_level_veteran_flag"], "drop_score"] += 24
    drop_df.loc[drop_df["replacement_level_flag"], "drop_score"] += 32
    drop_df.loc[drop_df["stale_player_flag"], "drop_score"] += 24
    drop_df.loc[drop_df["low_value_flag"], "drop_score"] += 18
    drop_df.loc[drop_df["tier_label"].isin({"Depth", "Developmental"}), "drop_score"] += 12
    drop_df.loc[drop_df["opportunity_label_text"].isin(LOW_OPPORTUNITY_LABELS), "drop_score"] += 16
    drop_df.loc[drop_df["bench_role_flag"], "drop_score"] += 10
    drop_df.loc[drop_df["depth_excess"].ge(1), "drop_score"] += 10
    drop_df.loc[
        drop_df["replaceable_position_surplus_flag"],
        "drop_score",
    ] += 22
    drop_df.loc[drop_df["blocked_count"].ge(1), "drop_score"] += (
        drop_df.loc[drop_df["blocked_count"].ge(1), "blocked_count"].clip(upper=3) * 5
    )
    drop_df.loc[drop_df["position_key"].isin({"QB", "TE"}) & drop_df["reserve_count_at_pos"].ge(2), "drop_score"] += 8
    drop_df.loc[drop_df["age_num"].ge(26) & drop_df["years_exp_num"].ge(4), "drop_score"] += 8
    drop_df.loc[drop_df["little_trade_value_flag"], "drop_score"] += 16
    drop_df.loc[drop_df["low_market_flag"], "drop_score"] += 8
    drop_df.loc[drop_df["young_upside_flag"], "drop_score"] -= 10
    drop_df.loc[drop_df["young_skill_stash_flag"], "drop_score"] -= 18
    drop_df.loc[drop_df["rookie_stash_flag"], "drop_score"] -= 26
    drop_df.loc[drop_df["developmental_qb_flag"], "drop_score"] -= 30
    drop_df.loc[drop_df["strong_opportunity_flag"], "drop_score"] -= 16
    drop_df.loc[drop_df["important_handcuff_flag"], "drop_score"] -= 18
    drop_df.loc[drop_df["need_flag"], "drop_score"] -= 10
    drop_df.loc[drop_df["developmental_keep_flag"], "drop_score"] -= 8
    drop_df = drop_df.sort_values(
        [
            "unsigned_no_team_flag",
            "free_agent_level_veteran_flag",
            "veteran_clogger_flag",
            "replacement_level_flag",
            "stale_player_flag",
            "roster_utility_score",
            "drop_score",
            "score_num",
        ],
        ascending=[False, False, False, False, False, True, False, True],
    )
    drop_candidates: list[str] = []
    drop_candidates_structured: list[dict] = []
    seen_drop_ids: set[str] = set()
    trade_candidate_names = {item.split(" - ", 1)[0] for item in trade_candidates}
    for _, row in drop_df.iterrows():
        pid = str(row.get("player_id"))
        if pid in seen_drop_ids:
            continue
        seen_drop_ids.add(pid)
        if float(row.get("drop_score") or 0) <= 0:
            continue
        if player_display_name(row) in trade_candidate_names and float(row.get("score_num") or 0) > max(1.0, tradeable_score_cutoff):
            continue
        if row["unsigned_no_team_flag"]:
            reason = "No current NFL team on Sleeper. This roster spot should clear first unless the player still carries meaningful stash value."
        elif row["replaceable_position_surplus_flag"]:
            reason = "Replaceable kicker surplus. Clear this roster spot before protecting low-upside specialty depth."
        elif row["free_agent_level_veteran_flag"]:
            reason = "Older buried veteran with almost no market, no clear role, and replacement-level dynasty utility."
        elif row["veteran_clogger_flag"]:
            reason = "Low-value veteran depth with weak marketability and no clean lineup path."
        elif row["replacement_level_flag"] or row["stale_player_flag"]:
            reason = "Free-agent-level roster spot: near-zero market value, poor lineup utility, and no clean growth path."
        elif row["position_key"] in {"QB", "TE"} and _safe_positive_int(row.get("reserve_count_at_pos"), 0) >= 2:
            reason = f"Redundant {_safe_text(row.get('position_key'))} depth with limited lineup utility."
        elif row["opportunity_label_text"] in LOW_OPPORTUNITY_LABELS and row["little_trade_value_flag"]:
            reason = "Low opportunity, little trade market, and not enough weekly utility to justify the roster spot."
        elif row["age_num"] >= 27 and _safe_positive_int(row.get("blocked_count"), 0) >= 1:
            reason = "Older veteran blocked by stronger roster assets at the same position."
        elif _safe_positive_int(row.get("depth_excess"), 0) >= 1:
            reason = f"Buried depth in a {_safe_text(row.get('position_key'))} room where this roster already has enough bodies."
        else:
            reason = "Clearest bench cut once current needs, lineup value, and marketability are weighed."
        drop_candidates.append(_player_note(row, reason))
        drop_candidates_structured.append(
            _build_structured_decision_candidate(
                row,
                bucket="drop",
                reason=reason,
                priority=len(drop_candidates_structured) + 1,
                source="unsigned_no_team" if bool(row.get("unsigned_no_team_flag")) else "roster_drop",
            )
        )
        if len(drop_candidates) >= 3:
            break

    result["move_candidates"] = move_candidates[: max(1, min(3, over_by + 1))]
    result["trade_candidates"] = trade_candidates[:3]
    result["drop_candidates"] = drop_candidates[:3]
    result["keep_candidates"] = keep_candidates[:3]
    result["move_candidates_structured"] = move_candidates_structured[:3]
    result["trade_candidates_structured"] = trade_candidates_structured[:3]
    result["drop_candidates_structured"] = drop_candidates_structured[:3]
    result["keep_candidates_structured"] = keep_candidates_structured[:3]
    decision_reason_map: dict[str, tuple[str, str]] = {}
    for bucket_name, candidates in (
        ("Move", move_candidates_structured),
        ("Trade", trade_candidates_structured),
        ("Drop", drop_candidates_structured),
        ("Hold", keep_candidates_structured),
    ):
        for candidate in candidates:
            player_id = _safe_text(candidate.get("player_id")).strip()
            if not player_id or player_id in decision_reason_map:
                continue
            decision_reason_map[player_id] = (bucket_name, _safe_text(candidate.get("reason")))

    rostered_no_team_rows = team_df[
        team_df["no_nfl_team_flag"] | team_df["suspicious_team_metadata_flag"]
    ].copy()
    result["rostered_no_team_players"] = [
        {
            "player_id": _safe_text(row.get("player_id")).strip(),
            "player_name": player_display_name(row),
            "position": _safe_text(row.get("position_key") or row.get("position")).upper(),
            "team": _safe_text(row.get("team"), "FA"),
            "status": _safe_text(row.get("status")),
            "active_flag": bool(row.get("active_metadata_flag")),
            "search_rank": _safe_positive_int(row.get("raw_search_rank_num"), 0),
            "roster_utility_score": _safe_float(row.get("roster_utility_score"), 0.0),
            "unsigned_no_team_flag": bool(row.get("unsigned_no_team_flag")),
            "no_team_exception_flag": bool(row.get("no_team_exception_flag")),
            "reason_text": _safe_text(row.get("no_team_reason_text")),
        }
        for _, row in rostered_no_team_rows.sort_values(
            ["unsigned_no_team_flag", "roster_utility_score", "raw_search_rank_num"],
            ascending=[False, True, True],
        ).iterrows()
    ]

    lowest_utility_rows = team_df.sort_values(
        ["roster_utility_score", "score_num", "market_score_num"],
        ascending=[True, True, True],
    ).head(15)
    result["lowest_utility_candidates"] = [
        {
            "player_id": _safe_text(row.get("player_id")).strip(),
            "player_name": player_display_name(row),
            "position": _safe_text(row.get("position_key") or row.get("position")).upper(),
            "team": _safe_text(row.get("team"), "FA"),
            "action_label": decision_reason_map.get(_safe_text(row.get("player_id")).strip(), ("Monitor", ""))[0],
            "reason": decision_reason_map.get(_safe_text(row.get("player_id")).strip(), ("", ""))[1]
            or (
                "Free-agent-level roster spot."
                if bool(row.get("replacement_level_flag"))
                else "Lowest roster impact after current role, opportunity, and marketability are weighed."
            ),
            "roster_utility_score": _safe_float(row.get("roster_utility_score"), 0.0),
        }
        for _, row in lowest_utility_rows.iterrows()
    ]
    result["candidate_player_rows"] = team_df.to_dict("records")
    return result


def render_roster_limit_alert(limit_context: dict, *, compact: bool = False):
    return my_team_ui.render_roster_limit_alert(
        limit_context,
        compact=compact,
        render_summary_tiles=render_summary_tiles,
        render_visible_decision_source_debug=render_visible_decision_source_debug,
        render_no_team_player_debug=render_no_team_player_debug,
        render_recommendation_feedback=render_recommendation_feedback,
        render_structured_decision_cards=render_structured_decision_cards,
        render_roster_utility_debug=render_roster_utility_debug,
    )


def build_my_team_advice(
    my_team_df: pd.DataFrame,
    lineup_df: pd.DataFrame,
    metrics: dict | None,
    league_settings: dict | None = None,
    *,
    needed_positions: list[str] | None = None,
    assessment: TeamNeedsAssessment | None = None,
) -> list[dict]:
    advice = []
    resolved_assessment = assessment or build_team_needs_assessment(
        my_team_df,
        metrics,
        league_settings,
        lineup_df=lineup_df,
    )
    needs = (
        list(needed_positions)
        if needed_positions is not None
        else list(resolved_assessment.true_needs)
    )
    current_needs = [
        position
        for position in needs
        if (
            resolved_assessment.for_position(position) is not None
            and resolved_assessment.for_position(position).classification
            == "short_term_need"
            and not resolved_assessment.for_position(
                position
            ).temporary_injury_pressure
        )
    ]
    mode = _safe_text((metrics or {}).get("mode"), "competitive")
    strategy = normalize_team_strategy((metrics or {}).get("strategy") or mode)
    strengths = (metrics or {}).get("strengths", []) or []

    if strategy == "contender":
        strategy_priority = {
            "label": "Priority",
            "title": "Consolidate for weekly points",
            "body": "You profile as a contender. Package bench value or picks into one stronger starter before selling core pieces.",
            "primary": True,
        }
    elif strategy == "fringe_contender":
        strategy_priority = {
            "label": "Priority",
            "title": "Push with discipline",
            "body": "You profile as a fringe contender. Upgrade one clear starter spot, but avoid emptying the pick cabinet for a short-term bump.",
            "primary": True,
        }
    elif strategy == "retool":
        strategy_priority = {
            "label": "Priority",
            "title": "Balance now and next",
            "body": "You profile as a retool. Buy young starters at need positions and sell replaceable veterans when the return improves your future outlook.",
            "primary": True,
        }
    elif strategy == "tank":
        strategy_priority = {
            "label": "Priority",
            "title": "Maximize future value",
            "body": "You profile as a tank/rebuild. Prioritize picks and young players, and avoid spending future assets for short-term depth.",
            "primary": True,
        }
    elif strategy == "rebuild":
        strategy_priority = {
            "label": "Priority",
            "title": "Protect future value",
            "body": "You profile as a rebuild. Shop older non-core starters for young players and 2027 picks instead of chasing short-term depth.",
            "primary": True,
        }
    else:
        strategy_priority = {
            "label": "Priority",
            "title": "Stay flexible",
            "body": "You are in the competitive middle. Upgrade clear weak spots, but avoid spending premium picks unless the player becomes a long-term starter.",
            "primary": True,
        }

    if current_needs:
        advice.append(
            {
                "label": "Need",
                "title": "Attack " + " / ".join(current_needs[:3]),
                "body": "Canonical starter and depth coverage identify these as genuine roster needs.",
            }
        )
    if resolved_assessment.upgrade_opportunities:
        advice.append(
            {
                "label": "Upgrade",
                "title": "Upgrade "
                + " / ".join(resolved_assessment.upgrade_opportunities[:3]),
                "body": "These rooms remain covered but trail the league comparison baseline.",
            }
        )
    future_only = [
        position
        for position in resolved_assessment.future_risks
        if (
            resolved_assessment.for_position(position) is not None
            and resolved_assessment.for_position(position).classification
            == "future_risk"
        )
    ]
    if future_only:
        advice.append(
            {
                "label": "Future Risk",
                "title": "Build future stability at " + " / ".join(future_only[:3]),
                "body": "Current coverage is playable, but this room lacks a stable young core or developmental path.",
            }
        )

    starters = lineup_df[lineup_df["suggested_starter"]].copy() if not lineup_df.empty else pd.DataFrame()
    bench = lineup_df[~lineup_df["suggested_starter"]].copy() if not lineup_df.empty else pd.DataFrame()
    team_value = float(pd.to_numeric(my_team_df["value_score"], errors="coerce").fillna(0).sum())
    bench_value = float(pd.to_numeric(bench.get("value_score", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
    bench_ratio = bench_value / team_value if team_value else 0
    injury_context = roster_injury_context(my_team_df, lineup_df)
    injured_starters = int(
        injury_context.get(
            "active_injured_starters",
            injury_context.get("injured_starters", 0),
        )
        or 0
    )
    injured_roster = int(injury_context.get("injured_roster") or 0)
    injury_advice_context = injury_ui.team_injury_advice(injury_context)
    injured_positions = list(
        injury_context.get(
            "active_injury_positions",
            injury_context.get("injured_positions", []),
        )
        or []
    )
    health_flag = injury_ui.team_injury_display_label(
        injury_context,
        include_uncertainty=True,
    ) or "Stable"
    acute_injury_pressure = injury_ui.is_acute_injury_pressure(injury_context)
    unique_injury_positions = list(dict.fromkeys(pos for pos in injured_positions if pos))
    highlighted = " / ".join(unique_injury_positions[:2]) if unique_injury_positions else "starting spots"

    if acute_injury_pressure:
        if strategy in {"contender", "fringe_contender"}:
            injury_priority = {
                "label": "Priority",
                "title": "Stabilize injured starters",
                "body": f"{health_flag} is now the main roster story. Add healthy cover at {highlighted} before chasing generic consolidation or luxury upgrades.",
                "primary": True,
            }
        elif strategy in {"rebuild", "tank"}:
            injury_priority = {
                "label": "Priority",
                "title": "Protect value through the injury spike",
                "body": f"{health_flag} is distorting the short-term roster view. Do not force win-now fixes; protect healthy depth at {highlighted} and avoid selling injured assets at a discount.",
                "primary": True,
            }
        else:
            injury_priority = {
                "label": "Priority",
                "title": "Rebuild healthy cover first",
                "body": f"{health_flag} is the immediate swing factor. Healthy cover at {highlighted} should outrank the normal strategy playbook until the lineup is steadier.",
                "primary": True,
            }
        strategy_follow_up = dict(strategy_priority)
        strategy_follow_up["label"] = "Strategy"
        strategy_follow_up["primary"] = False
        advice = [injury_priority, strategy_follow_up] + advice
    else:
        advice.insert(0, strategy_priority)

    meaningful_injury_pressure = _has_meaningful_team_injury_impact(injury_context)
    if not acute_injury_pressure and meaningful_injury_pressure and injured_starters >= 1:
        advice.append(
            {
                "label": "Health",
                "title": "Monitor starter availability",
                "body": f"{health_flag} affects {highlighted}. Keep healthy cover available, but do not overreact unless the status worsens.",
            }
        )
    elif (
        not acute_injury_pressure
        and injury_advice_context.get("focus") == "future"
    ):
        advice.append(
            {
                "label": "Health",
                "title": injury_advice_context.get("title"),
                "body": injury_advice_context.get("body"),
            }
        )
    elif (
        not acute_injury_pressure
        and meaningful_injury_pressure
        and injured_roster >= 3
        and strategy in {"contender", "fringe_contender"}
    ):
        advice.append(
            {
                "label": "Health",
                "title": "Insulate the weekly lineup",
                "body": "Your injury burden is starting to matter for a win-now roster. Avoid thin two-for-one deals unless the incoming piece clearly upgrades the lineup.",
            }
        )

    if bench_ratio < 0.18 and len(my_team_df) >= 8:
        advice.append(
            {
                "label": "Depth",
                "title": "Bench is thin",
                "body": "Keep some upside swings instead of turning every reserve into throw-in value. Injuries will hit this roster harder than average.",
            }
        )
    elif bench_ratio > 0.32 and starters is not None and not starters.empty:
        advice.append(
            {
                "label": "Depth",
                "title": "Depth can be traded up",
                "body": "You have enough bench value to build two-for-one offers for a cleaner weekly starter.",
            }
        )

    avg_age = (metrics or {}).get("avg_age")
    league_age = (metrics or {}).get("league_age_mean")
    if avg_age is not None and league_age is not None:
        if avg_age - league_age >= 1.0:
            advice.append(
                {
                    "label": "Age",
                    "title": "Get younger before value drops",
                    "body": "Your average age is meaningfully older than league average. Prioritize younger return pieces or picks in equal-value deals.",
                }
            )
        elif league_age - avg_age >= 1.0 and strategy not in {"rebuild", "tank"}:
            advice.append(
                {
                    "label": "Window",
                    "title": "Young enough to buy",
                    "body": "Your age curve gives you room to add a veteran starter if the price is mainly depth rather than elite picks.",
                }
            )

    if strengths and len(advice) < 4:
        advice.append(
            {
                "label": "Leverage",
                "title": "Shop from " + " / ".join(str(pos).upper() for pos in strengths[:2]),
                "body": "Use surplus positions as your outgoing package instead of weakening the rooms you need to fix.",
            }
        )

    return advice[:4]


render_advice_cards = my_team_ui.render_advice_cards


def render_prospect_watchlist(needed_positions: list[str]):
    return my_team_ui.render_prospect_watchlist(
        needed_positions,
        prospects_for_positions=prospects_for_positions,
    )


def _has_meaningful_team_injury_impact(team_context) -> bool:
    return injury_ui.has_meaningful_team_injury_impact(team_context)


def _team_injury_display_label(team_context) -> str:
    return injury_ui.team_injury_display_label(team_context)


def _injury_position_set(values) -> set[str]:
    return {
        str(pos).upper()
        for pos in (values or [])
        if str(pos).strip()
    }


def _headline_trade_health_view(idea: dict, injury_positions: set[str]) -> dict:
    send_assets = list(idea.get("send_assets") or [])
    receive_assets = list(idea.get("receive_assets") or [])
    incoming_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in receive_assets
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    outgoing_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in send_assets
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    incoming_levels = [
        injury_level(asset.get("status"), asset.get("injury_status"))
        for asset in receive_assets
        if asset.get("asset_type") == "player"
    ]
    return {
        "relief_positions": incoming_healthy_positions & injury_positions,
        "cover_loss_positions": outgoing_healthy_positions & injury_positions,
        "incoming_major": sum(1 for level in incoming_levels if level == "major"),
        "incoming_moderate": sum(1 for level in incoming_levels if level == "moderate"),
    }


def _headline_trade_idea(
    ideas: list[dict],
    *,
    injury_positions=None,
    acute_injury_pressure: bool = False,
) -> dict | None:
    eligible = []
    for idea in ideas or []:
        if bool(idea.get("market_realism_hard_fail")):
            continue
        confidence_label = _safe_text(idea.get("trade_confidence_label")).strip()
        if bool(idea.get("trade_headline_ready")):
            eligible.append(idea)
            continue
        if (
            int(idea.get("market_realism_score") or 0) >= TRADE_SUMMARY_MARKET_REALISM_MIN
            and confidence_label in {"High", "Medium"}
        ):
            eligible.append(idea)
    if not eligible:
        return None

    if not acute_injury_pressure:
        return eligible[0]

    injury_positions_set = _injury_position_set(injury_positions)
    health_candidates: list[tuple[tuple[int, int, int, int], dict]] = []
    for idea in eligible:
        view = _headline_trade_health_view(idea, injury_positions_set)
        if view["incoming_major"] > 0 or view["incoming_moderate"] > 0:
            continue
        if view["cover_loss_positions"]:
            continue
        if injury_positions_set and not view["relief_positions"]:
            continue
        sort_key = (
            len(view["relief_positions"]),
            int(idea.get("market_realism_score") or 0),
            int(idea.get("priority") or 0),
            int(idea.get("fit_score") or 0),
        )
        health_candidates.append((sort_key, idea))

    if not health_candidates and not injury_positions_set:
        for idea in eligible:
            view = _headline_trade_health_view(idea, set())
            if view["incoming_major"] > 0 or view["incoming_moderate"] > 0:
                continue
            sort_key = (
                0,
                int(idea.get("market_realism_score") or 0),
                int(idea.get("priority") or 0),
                int(idea.get("fit_score") or 0),
            )
            health_candidates.append((sort_key, idea))

    if not health_candidates:
        return None

    health_candidates.sort(key=lambda item: item[0], reverse=True)
    return health_candidates[0][1]


def franchise_trade_summary(
    ideas: list[dict],
    *,
    injury_positions=None,
    acute_injury_pressure: bool = False,
) -> dict:
    headline_idea = _headline_trade_idea(
        ideas,
        injury_positions=injury_positions,
        acute_injury_pressure=acute_injury_pressure,
    )
    if headline_idea is None:
        if acute_injury_pressure:
            return {
                "partner": "No clear partner yet",
                "buy_low": "Healthy cover first",
                "rationale": "Current injury pressure is acute, so FantasyGM Lab is not elevating a headline trade unless it clearly brings healthy cover or avoids worsening the stressed positions.",
                "outgoing_player": "",
                "outgoing_player_id": "",
                "outgoing_player_ids": [],
                "confidence_label": "Low",
                "market_realism_label": "Thin",
            }
        return {
            "partner": "No clear partner yet",
            "buy_low": "No clear buy-low target yet",
            "rationale": "No trade idea looked fair enough for both sides on the main board.",
            "outgoing_player": "",
            "outgoing_player_id": "",
            "outgoing_player_ids": [],
            "confidence_label": "Low",
            "market_realism_label": "Thin",
        }
    best_idea = headline_idea
    if acute_injury_pressure:
        buy_low_idea = best_idea
    else:
        buy_low_idea = next(
            (
                idea
                for idea in ideas or []
                if int(idea.get("market_realism_score") or 0) >= TRADE_SUMMARY_MARKET_REALISM_MIN
                if "Value Arbitrage" in set(idea.get("reasoning_tags") or [])
            ),
            best_idea,
        )
    outgoing_player_assets = [
        asset
        for asset in list(best_idea.get("send_assets") or [])
        if asset.get("asset_type") == "player"
    ]
    outgoing_player_ids = [
        _safe_text(asset.get("player_id")).strip()
        for asset in outgoing_player_assets
        if _safe_text(asset.get("player_id")).strip()
    ]
    outgoing_player = _safe_text(
        best_idea.get("my_player"),
        _safe_text(outgoing_player_assets[0].get("label")) if outgoing_player_assets else "",
    )
    return {
        "partner": _safe_text(best_idea.get("partner_team_name"), "Trade partner"),
        "buy_low": _safe_text(buy_low_idea.get("their_player"), _safe_text(best_idea.get("their_player"), "Target")),
        "rationale": _safe_text(best_idea.get("rationale"), "Best current path is the highest-fit trade idea under your active strategy."),
        "outgoing_player": outgoing_player,
        "outgoing_player_id": outgoing_player_ids[0] if outgoing_player_ids else "",
        "outgoing_player_ids": outgoing_player_ids,
        "confidence_label": _safe_text(best_idea.get("trade_confidence_label"), "Low"),
        "market_realism_label": _safe_text(best_idea.get("market_realism_label"), "Thin"),
    }


def prioritize_trade_candidates_with_headline(
    trade_candidates: list[dict] | None,
    *,
    headline_idea: dict | None,
    my_team_df: pd.DataFrame,
    untouchables: list[str] | None = None,
) -> list[dict]:
    existing = list(trade_candidates or [])
    if headline_idea is None or my_team_df is None or my_team_df.empty:
        return existing

    partner_name = _safe_text(headline_idea.get("partner_team_name"), "this partner")
    target_name = _safe_text(headline_idea.get("their_player"), "the headline target")
    headline_reason = f"Direct outgoing piece in the current headline trade path for {target_name} with {partner_name}."
    send_assets = [
        asset
        for asset in list(headline_idea.get("send_assets") or [])
        if asset.get("asset_type") == "player"
    ]
    headline_ids = [
        _safe_text(asset.get("player_id")).strip()
        for asset in send_assets
        if _safe_text(asset.get("player_id")).strip()
    ]
    if not headline_ids:
        return existing

    prioritized: list[dict] = []
    seen: set[str] = set()
    headline_id_set = set(headline_ids)
    for item in existing:
        player_id = _safe_text(item.get("player_id")).strip()
        if not player_id or player_id in seen:
            continue
        updated = dict(item)
        if player_id in headline_id_set:
            updated["reason"] = headline_reason
            updated["note"] = headline_reason
            updated["source"] = "headline_trade"
            prioritized.append(updated)
            seen.add(player_id)
    if len(prioritized) < 3:
        untouchable_set = {str(name) for name in (untouchables or [])}
        headline_rows = _rows_for_candidate_player_ids(my_team_df, headline_ids)
        for _, row in headline_rows.iterrows():
            player_id = _safe_text(row.get("player_id")).strip()
            if not player_id or player_id in seen:
                continue
            if _safe_text(row.get("name")) in untouchable_set:
                continue
            role_label = _safe_text(row.get("role"))
            tier_label = _safe_text(row.get("player_tier"))
            if role_label == "Core" or tier_label in {"Elite", "Star", "Core Starter"}:
                continue
            prioritized.append(
                _build_structured_decision_candidate(
                    row,
                    bucket="trade",
                    reason=headline_reason,
                    priority=len(prioritized) + 1,
                    source="headline_trade",
                )
            )
            seen.add(player_id)
            if len(prioritized) >= 3:
                break

    merged = _merge_structured_candidates(prioritized, existing, max_items=3)
    for idx, item in enumerate(merged, start=1):
        item["priority"] = idx
    return merged


def select_my_team_primary_recommendation(
    *,
    roster_limit_context: dict,
    acute_injury_pressure: bool,
    health_flag: str,
    injured_starters: int,
    injury_alert_note: str,
    headline_trade_idea: dict | None,
    trade_summary: dict,
    top_waiver,
    advice_items: list[dict],
    major_needed_positions: list[str],
    trade_candidates: list[dict] | None = None,
    drop_candidates: list[dict] | None = None,
    move_candidates: list[dict] | None = None,
) -> dict:
    move_candidates = list(move_candidates or [])
    trade_candidates = list(trade_candidates or [])
    drop_candidates = list(drop_candidates or [])

    if roster_limit_context.get("over_limit"):
        urgent_move = (move_candidates or trade_candidates or drop_candidates)
        top_candidate = urgent_move[0] if urgent_move else {}
        top_note = _safe_text(top_candidate.get("reason") or top_candidate.get("note"))
        if not top_note and top_candidate:
            top_note = _structured_candidate_note(top_candidate)
        fallback_note = (
            f"Clear {int(roster_limit_context.get('over_by') or 0)} active roster slot"
            + ("s" if int(roster_limit_context.get("over_by") or 0) != 1 else "")
            + " before making any optional add or trade."
        )
        return {
            "value": "Clear roster limit first",
            "note": top_note or fallback_note,
            "tone": "risk",
            "source": "roster_limit",
        }

    if acute_injury_pressure:
        waiver_name = player_display_name(top_waiver) if isinstance(top_waiver, pd.Series) and not top_waiver.empty else ""
        waiver_note = _safe_text(top_waiver.get("injury_replacement_note")) if isinstance(top_waiver, pd.Series) and not top_waiver.empty else ""
        if waiver_name and waiver_note and not is_injury_status(top_waiver):
            return {
                "value": f"Add {waiver_name}",
                "note": waiver_note,
                "tone": "waiver",
                "source": "injury_waiver",
            }
        if headline_trade_idea is not None:
            target_name = _safe_text(headline_trade_idea.get("their_player"), trade_summary.get("buy_low"))
            partner_name = _safe_text(headline_trade_idea.get("partner_team_name"), trade_summary.get("partner"))
            if target_name:
                return {
                    "value": f"Target {target_name}",
                    "note": f"Injury pressure is acute. {partner_name} is the cleanest current trade path. {_truncate_text(_safe_text(trade_summary.get('rationale')), 120)}",
                    "tone": "trade",
                    "source": "injury_trade",
                }
        return {
            "value": "Stabilize injured starters",
            "note": injury_alert_note or f"{health_flag} is the main roster issue right now.",
            "tone": "risk",
            "source": "injury_priority",
        }

    if headline_trade_idea is not None and trade_candidates:
        top_trade = trade_candidates[0]
        outgoing_name = _safe_text(top_trade.get("player_name"), trade_summary.get("outgoing_player"))
        target_name = _safe_text(headline_trade_idea.get("their_player"), trade_summary.get("buy_low"))
        partner_name = _safe_text(headline_trade_idea.get("partner_team_name"), trade_summary.get("partner"))
        if outgoing_name and target_name:
            return {
                "value": f"Shop {outgoing_name}",
                "note": f"Best current path: {outgoing_name} toward {target_name} with {partner_name}. {_truncate_text(_safe_text(trade_summary.get('rationale')), 120)}",
                "tone": "trade",
                "source": "headline_trade",
            }

    first_advice = advice_items[0] if advice_items else {}
    first_title = _safe_text(first_advice.get("title"))
    first_body = _safe_text(first_advice.get("body"))
    if first_title:
        return {
            "value": first_title,
            "note": first_body or "No urgent roster action is standing out right now.",
            "tone": "trade" if _safe_text(first_advice.get("label")).lower() == "priority" else "need",
            "source": "advice",
        }

    if not major_needed_positions:
        return {
            "value": "Roster is stable",
            "note": "No major weakness is standing out right now. Protect core value and stay flexible.",
            "tone": "draft",
            "source": "balanced",
        }

    need_label = " / ".join(major_needed_positions[:2])
    return {
        "value": f"Attack {need_label}",
        "note": "Those rooms are the clearest current pressure points on the roster.",
        "tone": "need",
        "source": "need",
    }


def select_best_sell_candidate(
    my_team_df: pd.DataFrame,
    role_map: dict[str, str],
    untouchables: list[str],
    strengths: list[str],
    score_field: str,
    injury_context: dict | None = None,
) -> dict | None:
    if my_team_df.empty:
        return None
    df = my_team_df.copy()
    df["role"] = df["player_id"].astype(str).map(lambda pid: role_map.get(str(pid), "Flex"))
    df["age_num"] = pd.to_numeric(df.get("age", pd.Series(float("nan"), index=df.index)), errors="coerce").fillna(0)
    df["score_num"] = pd.to_numeric(
        df[score_field] if score_field in df.columns else df.get("value_score", 0),
        errors="coerce",
    ).fillna(0)
    injury_context = dict(injury_context or {})
    active_positions = (
        injury_context.get("active_injury_positions")
        if "active_injury_positions" in injury_context
        else injury_context.get("injured_positions")
    )
    injury_positions = _injury_position_set(
        injury_context.get("injury_need_positions") or active_positions or []
    )
    acute_injury_pressure = injury_ui.is_acute_injury_pressure(injury_context)
    df["injury_level_key"] = df.apply(
        lambda row: injury_level(row.get("status"), row.get("injury_status")),
        axis=1,
    )
    df["injury_flag"] = df["injury_level_key"].ne("healthy")
    untouchable_set = {str(name) for name in untouchables or []}
    strengths_set = {str(pos).upper() for pos in strengths or []}
    df["sell_score"] = 0.0
    df.loc[df["name"].astype(str).isin(untouchable_set), "sell_score"] -= 100
    df.loc[df["role"].eq("Core"), "sell_score"] -= 35
    df.loc[df["role"].eq("Bench"), "sell_score"] += 18
    df.loc[df["role"].eq("Flex"), "sell_score"] += 10
    df.loc[df["position"].astype(str).str.upper().isin(strengths_set), "sell_score"] += 16
    df.loc[df["age_num"].ge(30), "sell_score"] += 18
    df.loc[df["age_num"].between(27, 29, inclusive="both"), "sell_score"] += 10
    max_score = float(df["score_num"].max() or 0)
    if max_score > 0:
        df["sell_score"] += (df["score_num"] / max_score) * 8
    if acute_injury_pressure:
        if injury_positions:
            healthy_cover_mask = (
                df["position"].astype(str).str.upper().isin(injury_positions)
                & ~df["injury_flag"]
            )
            df.loc[healthy_cover_mask, "sell_score"] -= 70
        df.loc[df["injury_level_key"].eq("major"), "sell_score"] -= 55
        df.loc[df["injury_level_key"].eq("moderate"), "sell_score"] -= 40
        df.loc[df["injury_level_key"].eq("minor"), "sell_score"] -= 16
    else:
        df.loc[df["injury_level_key"].eq("major"), "sell_score"] -= 24
        df.loc[df["injury_level_key"].eq("moderate"), "sell_score"] -= 12
    candidates = df.sort_values(["sell_score", "score_num"], ascending=[False, False])
    if candidates.empty:
        return None
    top = candidates.iloc[0]
    if float(top.get("sell_score") or 0) <= 0:
        return None
    return top.to_dict()


def franchise_future_outlook(
    team_row: pd.Series | dict | None,
    intel_row: pd.Series | dict | None,
    strategy: str,
) -> tuple[str, str]:
    if isinstance(team_row, dict):
        team = team_row
    elif team_row is not None and hasattr(team_row, "to_dict"):
        team = team_row.to_dict()
    else:
        team = {}
    if isinstance(intel_row, dict):
        intel = intel_row
    elif intel_row is not None and hasattr(intel_row, "to_dict"):
        intel = intel_row.to_dict()
    else:
        intel = {}

    starter_rank = _safe_positive_int(team.get("starter_rank"), 99)
    bench_rank = _safe_positive_int(team.get("bench_rank"), 99)
    age_rank = _safe_positive_int(team.get("age_rank"), 99)
    draft_rank = _safe_positive_int(team.get("draft_capital_rank"), 99)
    top_heavy_ratio = _safe_float(intel.get("top_heavy_ratio"), 0.0)
    strategy_key = normalize_team_strategy(strategy)

    if strategy_key in {"contender", "fringe_contender"} and starter_rank <= 4:
        one_year = "Your roster is built to compete right now. Keep leaning into starter upgrades while protecting just enough depth to survive injuries."
    elif strategy_key == "retool":
        one_year = "You have a workable core, but the next year should focus on turning surplus pieces into one or two cleaner starter advantages."
    else:
        one_year = "Short-term results matter less than preserving flexibility. Prioritize value retention, youth, and future picks over patching weekly holes."

    if _has_meaningful_team_injury_impact(intel):
        one_year += " Current value-weighted injury pressure is the main short-term risk."
    elif top_heavy_ratio > 3.4 and bench_rank >= 8:
        one_year += " The main risk is fragility if a starter goes down."

    if strategy_key in {"rebuild", "tank"} and draft_rank <= 4 and age_rank <= 4:
        three_year = "The three-year outlook is strong if you stay disciplined. Your age profile and draft capital give you room to build a durable contender window."
    elif strategy_key in {"contender", "fringe_contender"} and age_rank >= 8 and draft_rank >= 8:
        three_year = "The long-range outlook is shakier than the current window. You may need to recycle older value into picks or younger starters before the roster ages out."
    elif draft_rank <= 5:
        three_year = "Your future outlook is helped by above-average draft capital. You have enough optionality to pivot between buying and rebuilding if the season shifts."
    else:
        three_year = "The long-term outlook is balanced but not insulated. Improving future pick depth or younger starter quality would make the roster more stable over multiple seasons."

    return one_year, three_year


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_league_summary(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
) -> pd.DataFrame:
    with performance.time_block("league_summary_generation", category="analysis"):
        return build_league_summary(
            df_players,
            league_id,
            score_field=score_field,
            current_score_field="value_score",
            lineup_settings=lineup_settings,
        )


def _normalize_draft_status(status: str) -> str:
    text = _safe_text(status).strip().lower().replace("-", "_").replace(" ", "_")
    if text in {"complete", "completed"}:
        return "complete"
    if text in {"drafting", "in_progress", "inprogress", "started"}:
        return "in_progress"
    if text in {"pre_draft", "predraft", "scheduled", "setup"}:
        return "pre_draft"
    if text == "paused":
        return "paused"
    return text or "unknown"


def _draft_round_count(draft: dict) -> int:
    settings = draft.get("settings") if isinstance(draft.get("settings"), dict) else {}
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    return max(
        0,
        _safe_positive_int(
            settings.get("rounds")
            or settings.get("round_count")
            or metadata.get("rounds")
            or draft.get("rounds"),
            0,
        ),
    )


def _draft_pick_player_id(pick: dict) -> str:
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return _safe_text(
        pick.get("player_id")
        or metadata.get("player_id")
        or metadata.get("picked_player_id")
    )


def _draft_pick_roster_id(pick: dict) -> int:
    metadata = pick.get("metadata") if isinstance(pick.get("metadata"), dict) else {}
    return _safe_positive_int(
        pick.get("roster_id")
        or metadata.get("roster_id")
        or metadata.get("owner_id"),
        0,
    )


def _detect_startup_draft_candidate(
    league_id: str,
    league: dict,
    rosters: list[dict],
) -> dict:
    drafts = get_league_drafts(league_id) or []
    rookie_rounds = _safe_positive_int(
        (league.get("settings") or {}).get("draft_rounds"),
        4,
    )
    league_season = _safe_positive_int(league.get("season"), 0)
    roster_sizes = [len(roster.get("players", []) or []) for roster in rosters or []]
    sparse_rosters = (pd.Series(roster_sizes).median() if roster_sizes else 0) < 4

    candidates = []
    for draft_stub in drafts:
        draft_id = _safe_text(draft_stub.get("draft_id") or draft_stub.get("id"))
        draft = get_draft(draft_id) if draft_id else {}
        merged = dict(draft_stub or {})
        merged.update(draft or {})
        rounds = _draft_round_count(merged)
        season = _safe_positive_int(merged.get("season"), league_season or 0)
        status = _normalize_draft_status(merged.get("status"))
        start_time = _safe_positive_int(merged.get("start_time"), 0)

        startup_score = 0
        if rounds >= max(8, rookie_rounds + 4):
            startup_score += 4
        if status in {"pre_draft", "in_progress", "paused"}:
            startup_score += 2
        if season >= max(league_season - 1, 0):
            startup_score += 1
        if sparse_rosters:
            startup_score += 1

        candidates.append(
            {
                "draft_id": draft_id,
                "draft": merged,
                "rounds": rounds,
                "season": season,
                "status": status,
                "startup_score": startup_score,
                "start_time": start_time,
            }
        )

    if not candidates:
        return {}

    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("startup_score", 0),
            item.get("season", 0),
            item.get("start_time", 0),
            item.get("rounds", 0),
        ),
        reverse=True,
    )
    best = candidates[0]
    if best.get("startup_score", 0) >= 4:
        return best
    if sparse_rosters and best.get("startup_score", 0) >= 2:
        return best
    return {}


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_startup_draft_context(
    league_id: str,
    my_roster_id: int | None,
    league_settings_items: tuple[tuple[str, object], ...] = (),
) -> dict:
    with performance.time_block("startup_draft_context_generation", category="draft"):
        return _cached_startup_draft_context_impl(
            league_id,
            my_roster_id,
            league_settings_items=league_settings_items,
        )


def _cached_startup_draft_context_impl(
    league_id: str,
    my_roster_id: int | None,
    league_settings_items: tuple[tuple[str, object], ...] = (),
) -> dict:
    default = {
        "startup_mode": False,
        "league_id": league_id,
        "draft_available": False,
        "draft_completed": False,
        "draft_status": "unknown",
        "draft_year": 0,
        "draft_rounds": 0,
        "picks_made": 0,
        "total_picks": 0,
        "drafted_player_ids": [],
        "my_drafted_player_ids": [],
        "my_draft_slot": 0,
        "league_size": 0,
        "rostered_players": 0,
        "median_roster_size": 0,
        "expected_roster_size": 0,
        "reason": "",
        "draft_id": "",
        "current_year_pick_status": "",
    }
    if not league_id:
        return default

    league = get_league(league_id)
    rosters = get_rosters(league_id) or []
    league_settings = dict(league_settings_items or ())
    league_size = max(_safe_positive_int(league_settings.get("league_size"), 0), len(rosters))
    starter_count = _safe_positive_int(league_settings.get("starter_count"), 9)
    bench_count = _safe_positive_int(league_settings.get("bench_count"), 0)
    taxi_count = _safe_positive_int(league_settings.get("taxi_count"), 0)
    expected_roster_size = max(starter_count + bench_count + taxi_count, starter_count + 6)
    roster_sizes = [len(roster.get("players", []) or []) for roster in rosters]
    rostered_players = int(sum(roster_sizes))
    median_roster_size = int(round(pd.Series(roster_sizes).median())) if roster_sizes else 0
    sparse_rosters = median_roster_size < max(4, min(expected_roster_size, 10))

    candidate = _detect_startup_draft_candidate(league_id, league, rosters)
    draft_id = _safe_text(candidate.get("draft_id"))
    draft = candidate.get("draft") or {}
    draft_status = _normalize_draft_status(candidate.get("status") or draft.get("status"))
    draft_year = _safe_positive_int(candidate.get("season") or draft.get("season"), _safe_positive_int(league.get("season"), 0))
    draft_rounds = _safe_positive_int(candidate.get("rounds") or _draft_round_count(draft), 0)
    draft_picks = get_draft_picks(draft_id) if draft_id else []
    drafted_player_ids = sorted(
        {
            player_id
            for player_id in (_draft_pick_player_id(pick) for pick in draft_picks or [])
            if player_id
        }
    )
    picks_made = len(drafted_player_ids)
    total_picks = max(0, draft_rounds * max(league_size, 1))
    draft_completed = (
        draft_status == "complete"
        or (total_picks > 0 and picks_made >= total_picks)
    )

    my_drafted_player_ids = []
    if my_roster_id:
        my_drafted_player_ids = sorted(
            {
                _draft_pick_player_id(pick)
                for pick in draft_picks or []
                if _draft_pick_roster_id(pick) == int(my_roster_id) and _draft_pick_player_id(pick)
            }
        )

    my_draft_slot = 0
    draft_order = draft.get("draft_order") if isinstance(draft.get("draft_order"), dict) else {}
    if my_roster_id and draft_order:
        my_draft_slot = _safe_positive_int(draft_order.get(str(my_roster_id)) or draft_order.get(my_roster_id), 0)
    metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
    slot_map = metadata.get("slot_to_roster_id") if isinstance(metadata.get("slot_to_roster_id"), dict) else {}
    if not my_draft_slot and my_roster_id and slot_map:
        for slot_key, roster_value in slot_map.items():
            if str(roster_value) == str(my_roster_id):
                my_draft_slot = _safe_positive_int(slot_key, 0)
                break

    startup_mode = False
    reason = ""
    if draft_id and not draft_completed and draft_status in {"pre_draft", "in_progress", "paused"}:
        startup_mode = True
        reason = "Startup draft is still active or has not started yet."
    elif sparse_rosters and draft_id and not draft_completed:
        startup_mode = True
        reason = "Rosters are still sparse and the startup draft does not appear complete."
    elif sparse_rosters and not draft_id:
        startup_mode = True
        reason = "This league does not have populated rosters yet, so startup draft mode is safer than the normal team dashboard."

    current_year_pick_status = (
        "Current-year startup picks are still active."
        if startup_mode
        else "Startup draft appears complete; normal roster tools are active."
    )

    return {
        **default,
        "startup_mode": bool(startup_mode),
        "draft_available": bool(draft_id),
        "draft_completed": bool(draft_completed),
        "draft_status": draft_status,
        "draft_year": draft_year,
        "draft_rounds": draft_rounds,
        "picks_made": picks_made,
        "total_picks": total_picks,
        "drafted_player_ids": drafted_player_ids,
        "my_drafted_player_ids": my_drafted_player_ids,
        "my_draft_slot": my_draft_slot,
        "league_size": league_size,
        "rostered_players": rostered_players,
        "median_roster_size": median_roster_size,
        "expected_roster_size": expected_roster_size,
        "reason": reason,
        "draft_id": draft_id,
        "current_year_pick_status": current_year_pick_status,
    }


def _detect_rookie_draft_candidate(league_id: str, league: dict) -> dict:
    drafts = get_league_drafts(league_id) or []
    rookie_rounds = _safe_positive_int(
        (league.get("settings") or {}).get("draft_rounds"),
        4,
    )
    league_season = _safe_positive_int(league.get("season"), 0) or datetime.now().year
    candidates = []

    for draft_stub in drafts:
        draft_id = _safe_text(draft_stub.get("draft_id") or draft_stub.get("id"))
        draft = get_draft(draft_id) if draft_id else {}
        merged = dict(draft_stub or {})
        merged.update(draft or {})
        rounds = _draft_round_count(merged)
        season = _safe_positive_int(merged.get("season"), league_season)
        status = _normalize_draft_status(merged.get("status"))
        start_time = _safe_positive_int(merged.get("start_time"), 0)
        max_rookie_rounds = max(rookie_rounds + 2, 6)
        if rounds <= 0 or rounds > max_rookie_rounds:
            continue
        score = 0
        if rounds == rookie_rounds:
            score += 4
        elif rounds <= max_rookie_rounds:
            score += 2
        if season == league_season:
            score += 4
        elif season == league_season + 1:
            score += 1
        if status in {"pre_draft", "in_progress", "paused", "complete"}:
            score += 1
        candidates.append(
            {
                "draft_id": draft_id,
                "draft": merged,
                "rounds": rounds,
                "season": season,
                "status": status,
                "score": score,
                "start_time": start_time,
            }
        )

    if not candidates:
        return {}
    candidates = sorted(
        candidates,
        key=lambda item: (
            item.get("score", 0),
            item.get("season", 0),
            item.get("start_time", 0),
            -abs(_safe_positive_int(item.get("rounds"), 0) - rookie_rounds),
        ),
        reverse=True,
    )
    best = candidates[0]
    return best if best.get("score", 0) >= 5 else {}


def rookie_draft_status_items(draft_status: dict | None = None) -> tuple[tuple[str, object], ...]:
    status = draft_status if isinstance(draft_status, dict) else {}
    keys = (
        "draft_available",
        "draft_completed",
        "draft_status",
        "draft_year",
        "current_year_picks_active",
        "current_year_pick_status",
    )
    return tuple((key, status.get(key)) for key in keys)


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_rookie_draft_context(
    league_id: str,
    league_settings_items: tuple[tuple[str, object], ...] = (),
) -> dict:
    with performance.time_block("rookie_draft_context_generation", category="draft"):
        return _cached_rookie_draft_context_impl(
            league_id,
            league_settings_items=league_settings_items,
        )


def _cached_rookie_draft_context_impl(
    league_id: str,
    league_settings_items: tuple[tuple[str, object], ...] = (),
) -> dict:
    default = {
        "league_id": league_id,
        "draft_available": False,
        "draft_completed": False,
        "draft_status": "unknown",
        "draft_year": _safe_positive_int(datetime.now().year, datetime.now().year),
        "draft_rounds": 0,
        "picks_made": 0,
        "total_picks": 0,
        "current_year_picks_active": True,
        "current_year_pick_status": "Current-year rookie picks are still active.",
        "draft_id": "",
        "reason": "No current rookie draft was detected from Sleeper data, so current-year picks stay active.",
    }
    if not league_id:
        return default

    league = get_league(league_id)
    rosters = get_rosters(league_id) or []
    league_settings = dict(league_settings_items or ())
    league_size = max(_safe_positive_int(league_settings.get("league_size"), 0), len(rosters))
    league_season = _safe_positive_int(league.get("season"), datetime.now().year) or datetime.now().year
    candidate = _detect_rookie_draft_candidate(league_id, league)
    draft_id = _safe_text(candidate.get("draft_id"))
    draft = candidate.get("draft") or {}
    draft_status = _normalize_draft_status(candidate.get("status") or draft.get("status"))
    draft_year = _safe_positive_int(candidate.get("season") or draft.get("season"), league_season)
    draft_rounds = _safe_positive_int(candidate.get("rounds") or _draft_round_count(draft), 0)
    draft_picks = get_draft_picks(draft_id) if draft_id else []
    picks_made = len(draft_picks)
    total_picks = max(0, draft_rounds * max(league_size, 1))
    draft_completed = draft_status == "complete" or (total_picks > 0 and picks_made >= total_picks)
    current_year_picks_active = not draft_completed
    if draft_id:
        current_year_pick_status = (
            "Current-year rookie picks are inactive because the rookie draft is complete."
            if draft_completed
            else "Current-year rookie picks are still active because the rookie draft is not complete."
        )
        reason = (
            "Sleeper rookie-draft data shows the current draft is complete."
            if draft_completed
            else "Sleeper rookie-draft data shows the current draft is still active or upcoming."
        )
    else:
        current_year_pick_status = default["current_year_pick_status"]
        reason = default["reason"]

    return {
        **default,
        "draft_available": bool(draft_id),
        "draft_completed": bool(draft_completed),
        "draft_status": draft_status,
        "draft_year": draft_year,
        "draft_rounds": draft_rounds,
        "picks_made": picks_made,
        "total_picks": total_picks,
        "current_year_picks_active": bool(current_year_picks_active),
        "current_year_pick_status": current_year_pick_status,
        "draft_id": draft_id,
        "reason": reason,
    }


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_draft_pick_assets(
    league_id: str,
    df_summary: pd.DataFrame,
    league_settings_items: tuple[tuple[str, object], ...] = (),
    draft_status_items: tuple[tuple[str, object], ...] = (),
) -> list[dict]:
    with performance.time_block("draft_pick_assets_generation", category="draft"):
        status_items = draft_status_items
        if not status_items and league_id:
            status_items = rookie_draft_status_items(
                cached_rookie_draft_context(
                    league_id,
                    league_settings_items=league_settings_items,
                )
            )
        return list_draft_pick_assets(
            league_id,
            df_summary,
            league_settings=dict(league_settings_items or ()),
            draft_status=dict(status_items or ()),
        )


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_trade_ideas(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    untouchables: tuple[str, ...],
    role_items: tuple[tuple[str, str], ...],
    score_field: str,
    pick_score_multiplier: float,
    team_strategy: str,
    team_archetype: str = "",
    league_settings_items: tuple[tuple[str, object], ...] = (),
    draft_status_items: tuple[tuple[str, object], ...] = (),
    max_ideas: int = 8,
) -> list[dict]:
    with performance.time_block("trade_hub_board_generation", category="analysis"):
        status_items = draft_status_items
        if not status_items and league_id:
            status_items = rookie_draft_status_items(
                cached_rookie_draft_context(
                    league_id,
                    league_settings_items=league_settings_items,
                )
            )
        return build_trade_ideas(
            df_players=df_players,
            league_id=league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            trade_block_names=[],
            untouchable_names=list(untouchables),
            role_map=dict(role_items),
            max_ideas=max_ideas,
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            team_strategy=team_strategy,
            team_archetype=team_archetype,
            league_settings=dict(league_settings_items or ()),
            draft_status=dict(status_items or ()),
        )


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_dashboard_trade_headline(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    untouchables: tuple[str, ...],
    role_items: tuple[tuple[str, str], ...],
    score_field: str,
    pick_score_multiplier: float,
    team_strategy: str,
    league_settings_items: tuple[tuple[str, object], ...] = (),
    maturity_context: dict | None = None,
) -> list[dict]:
    """Build and cache a small raw pool for the Dashboard trade headline."""
    with performance.time_block("dashboard_trade_headline_generation", category="analysis"):
        return cached_trade_ideas(
            df_players=df_players,
            league_id=league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            untouchables=untouchables,
            role_items=role_items,
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            team_strategy=team_strategy,
            league_settings_items=league_settings_items,
            max_ideas=2,
        )


def build_trade_trust_context(
    *,
    league_id: str,
    df_summary: pd.DataFrame,
    roster_player_map: dict[str, tuple[str, ...]] | None,
) -> TradeTrustContext:
    ownership_by_player: dict[str, int] = {}
    valid_roster_ids: set[int] = set()
    for roster_id_value, player_ids in (roster_player_map or {}).items():
        try:
            roster_id = int(roster_id_value)
        except (TypeError, ValueError):
            continue
        if not roster_id:
            continue
        valid_roster_ids.add(roster_id)
        for player_id in player_ids or ():
            ownership_by_player[str(player_id)] = roster_id

    team_name_to_roster: dict[str, int] = {}
    if df_summary is not None and not df_summary.empty:
        for _, row in df_summary.iterrows():
            try:
                roster_id = int(row.get("roster_id") or 0)
            except (TypeError, ValueError):
                continue
            team_name = _safe_text(row.get("team_name")).casefold()
            if roster_id and team_name:
                team_name_to_roster[team_name] = roster_id

    return TradeTrustContext(
        ownership_by_player=tuple(ownership_by_player.items()),
        valid_roster_ids=frozenset(valid_roster_ids),
        team_name_to_roster=tuple(team_name_to_roster.items()),
        league_context_valid=bool(league_id and valid_roster_ids),
    )


def enforce_cached_trade_ideas(
    ideas: list[dict] | tuple[dict, ...],
    *,
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    untouchables: tuple[str, ...] = (),
    trust_context: TradeTrustContext | None = None,
) -> list[dict]:
    """Apply Trust enforcement to raw cached output at the production boundary."""

    canonical_players: dict[str, dict] = {}
    player_enforcement = {}
    candidate_player_ids = {
        _safe_text(asset.get("player_id"))
        for idea in ideas or ()
        for side in ("send_assets", "receive_assets")
        for asset in idea.get(side) or ()
        if isinstance(asset, dict)
        and _safe_text(asset.get("asset_type")).casefold() == "player"
        and _safe_text(asset.get("player_id"))
    }
    if df_players is not None and not df_players.empty:
        candidate_players = df_players[
            df_players["player_id"].astype(str).isin(candidate_player_ids)
        ]
        for _, row in candidate_players.iterrows():
            player = row.to_dict()
            player_id = _safe_text(player.get("player_id"))
            if not player_id:
                continue
            canonical_players[player_id] = player
            result = enforcement_from_player_annotations(player)
            if result is not None:
                player_enforcement[player_id] = result

    if trust_context is None:
        with performance.time_block("trust_context_construction", category="analysis"):
            loaded_rosters = get_rosters(league_id) or []
            roster_player_map = _build_roster_player_map(loaded_rosters)
            trust_context = build_trade_trust_context(
                league_id=league_id,
                df_summary=df_summary,
                roster_player_map=roster_player_map,
            )

    ownership_by_player = dict(trust_context.ownership_by_player)
    team_name_to_roster = dict(trust_context.team_name_to_roster)
    with performance.time_block("trust_trade_board_enforcement", category="analysis"):
        board = enforce_trade_board(
            ideas or (),
            canonical_players=canonical_players,
            player_enforcement=player_enforcement,
            ownership_by_player=ownership_by_player,
            valid_roster_ids=trust_context.valid_roster_ids,
            my_roster_id=int(my_roster_id),
            team_name_to_roster=team_name_to_roster,
            league_context_valid=bool(
                trust_context.league_context_valid
                and int(my_roster_id) in trust_context.valid_roster_ids
            ),
            untouchable_names=frozenset(
                _safe_text(name).casefold() for name in untouchables if _safe_text(name)
            ),
        )
    performance.record_trust_diagnostics(board.diagnostics)
    return list(board.recommendations)


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_player_trade_hub_ideas(
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    untouchables: tuple[str, ...],
    role_items: tuple[tuple[str, str], ...],
    score_field: str,
    pick_score_multiplier: float,
    team_strategy: str,
    mode: str,
    selected_player_id: str,
    team_archetype: str = "",
    league_settings_items: tuple[tuple[str, object], ...] = (),
    draft_status_items: tuple[tuple[str, object], ...] = (),
    max_ideas: int = 8,
) -> dict:
    with performance.time_block("player_trade_hub_generation", category="analysis"):
        status_items = draft_status_items
        if not status_items and league_id:
            status_items = rookie_draft_status_items(
                cached_rookie_draft_context(
                    league_id,
                    league_settings_items=league_settings_items,
                )
            )
        return build_player_trade_hub_ideas(
            df_players=df_players,
            league_id=league_id,
            df_summary=df_summary,
            my_roster_id=my_roster_id,
            role_map=dict(role_items),
            untouchable_names=list(untouchables),
            mode=mode,
            selected_player_id=selected_player_id,
            max_ideas=max_ideas,
            score_field=score_field,
            pick_score_multiplier=pick_score_multiplier,
            team_strategy=team_strategy,
            team_archetype=team_archetype,
            league_settings=dict(league_settings_items or ()),
            draft_status=dict(status_items or ()),
        )


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_trade_search_pool(df_players: pd.DataFrame) -> pd.DataFrame:
    pool = normalize_player_ids(df_players)
    for column in [
        "name",
        "team",
        "position",
        "status",
        "injury_status",
        "player_tier",
        "opportunity_label",
        "opportunity_score",
        "opportunity_explanation",
        "value_score",
        "dynasty_score",
        "rebuild_score",
        "age",
    ]:
        if column not in pool.columns:
            pool[column] = 0 if column in {"value_score", "dynasty_score", "rebuild_score", "age", "opportunity_score"} else ""
    pool = pool[
        [
            column
            for column in [
                "player_id",
                "name",
                "team",
                "position",
                "status",
                "injury_status",
                "player_tier",
                "opportunity_label",
                "opportunity_score",
                "opportunity_explanation",
                "value_score",
                "dynasty_score",
                "rebuild_score",
                "age",
            ]
            if column in pool.columns
        ]
    ].copy()
    pool["name"] = pool["name"].fillna("").astype(str)
    pool["team"] = pool["team"].fillna("").astype(str)
    pool["position"] = pool["position"].fillna("").astype(str)
    pool["player_tier"] = pool["player_tier"].fillna("").astype(str)
    pool["opportunity_label"] = pool["opportunity_label"].fillna("").astype(str)
    pool["opportunity_explanation"] = pool["opportunity_explanation"].fillna("").astype(str)
    pool["search_name"] = pool["name"].str.lower()
    pool["search_team"] = pool["team"].str.lower()
    pool["search_position"] = pool["position"].str.lower()
    pool["search_blob"] = (
        pool["search_name"]
        + " "
        + pool["search_team"]
        + " "
        + pool["search_position"]
    ).str.strip()
    pool["value_score"] = pd.to_numeric(pool["value_score"], errors="coerce").fillna(0)
    pool["dynasty_score"] = pd.to_numeric(pool["dynasty_score"], errors="coerce").fillna(0)
    pool["rebuild_score"] = pd.to_numeric(pool["rebuild_score"], errors="coerce").fillna(0)
    pool["opportunity_score"] = pd.to_numeric(pool["opportunity_score"], errors="coerce").fillna(0)
    return pool


def player_search_results(
    df_players: pd.DataFrame,
    query: str,
    score_field: str = "value_score",
    owned_player_ids: set[str] | None = None,
    only_owned: bool = False,
    exclude_owned: bool = False,
    limit: int = 8,
) -> pd.DataFrame:
    if not query or not isinstance(query, str):
        return pd.DataFrame()

    q = query.strip().lower()
    if len(q) < 2:
        return pd.DataFrame()

    pool = cached_trade_search_pool(df_players)
    mask = pool["search_blob"].str.contains(q, regex=False)
    results = pool.loc[mask].copy()
    if results.empty:
        return results

    if only_owned or exclude_owned:
        owned_player_ids = owned_player_ids or set()
        player_ids = results["player_id"].astype(str)
        if only_owned:
            results = results[player_ids.isin(owned_player_ids)].copy()
        elif exclude_owned:
            results = results[~player_ids.isin(owned_player_ids)].copy()
        if results.empty:
            return results

    query_tokens = [token for token in q.split() if token]
    results["exact_name_match"] = (results["search_name"] == q).astype(int)
    results["starts_name_match"] = results["search_name"].str.startswith(q).astype(int)
    results["team_match"] = results["search_team"].eq(q).astype(int)
    results["token_hits"] = results["search_blob"].apply(
        lambda blob: sum(token in str(blob) for token in query_tokens)
    )
    results["query_match_score"] = (
        (results["exact_name_match"] * 120)
        + (results["starts_name_match"] * 45)
        + (results["team_match"] * 20)
        + (results["token_hits"] * 6)
    )
    sort_fields = ["query_match_score", "exact_name_match", "starts_name_match", "team_match"]
    if score_field in results.columns:
        sort_fields.append(score_field)
    sort_fields.extend(["dynasty_score", "value_score"])
    sort_fields = list(dict.fromkeys(sort_fields))
    results = results.sort_values(
        sort_fields,
        ascending=[False] * len(sort_fields),
    ).head(limit)
    return results.drop(
        columns=[
            "search_name",
            "search_team",
            "search_position",
            "search_blob",
            "exact_name_match",
            "starts_name_match",
            "team_match",
            "token_hits",
        ],
        errors="ignore",
    )


def search_trade_assets(
    df_players: pd.DataFrame,
    draft_picks: list[dict],
    query: str,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    owned_player_ids: set[str] | None = None,
    only_owned: bool = False,
    exclude_owned: bool = False,
    allowed_player_ids: set[str] | None = None,
    asset_filter: str = "All",
    pick_year=None,
    pick_round=None,
    partner_roster_id=None,
    player_owner_map: dict[str, dict] | None = None,
    limit: int = 8,
) -> pd.DataFrame:
    if query is None or not isinstance(query, str):
        return pd.DataFrame()

    asset_filter = _safe_text(asset_filter, "All")
    include_players = asset_filter in {"All", "Players"}
    include_picks = asset_filter in {"All", "Picks"}
    q = query.strip().lower()
    pick_query = _parse_pick_query(query)
    if asset_filter == "All" and _query_requires_pick_focus(query):
        include_players = False
        include_picks = True

    player_results = pd.DataFrame()
    if include_players:
        if len(q) >= 2:
            player_results = player_search_results(
                df_players,
                query,
                score_field=score_field,
                owned_player_ids=owned_player_ids,
                only_owned=only_owned,
                exclude_owned=exclude_owned,
                limit=max(limit, 24),
            )
        elif allowed_player_ids:
            pool = cached_trade_search_pool(df_players).copy()
            player_ids = pool["player_id"].astype(str)
            player_results = pool[player_ids.isin({str(pid) for pid in allowed_player_ids})].copy()
            if only_owned or exclude_owned:
                owned_player_ids = owned_player_ids or set()
                if only_owned:
                    player_results = player_results[player_results["player_id"].astype(str).isin(owned_player_ids)].copy()
                elif exclude_owned:
                    player_results = player_results[~player_results["player_id"].astype(str).isin(owned_player_ids)].copy()

        if not player_results.empty:
            player_results = player_results.copy()
            player_results["asset_type"] = "player"
            player_results["label"] = player_results["name"]
            player_results["position"] = player_results["position"].fillna("")
            player_results["team"] = player_results["team"].fillna("")
            player_results["name"] = player_results["name"].fillna("")
            player_results["player_id"] = player_results["player_id"].astype(str)
            player_results["score"] = pd.to_numeric(
                player_results.get(score_field, player_results.get("value_score", 0)),
                errors="coerce",
            ).fillna(0)
            owner_lookup = player_owner_map or {}
            player_results["owner_roster_id"] = player_results["player_id"].map(
                lambda pid: owner_lookup.get(str(pid), {}).get("owner_roster_id")
            )
            player_results["owner_team_name"] = player_results["player_id"].map(
                lambda pid: owner_lookup.get(str(pid), {}).get("owner_team_name", "")
            )
            if partner_roster_id not in (None, "", "All Teams"):
                player_results = player_results[
                    player_results["owner_roster_id"].astype(str) == str(partner_roster_id)
                ].copy()
            if "query_match_score" not in player_results.columns:
                player_results["query_match_score"] = 0
            if q:
                query_tokens = [token for token in q.split() if token]
                player_results["owner_match_score"] = (
                    player_results["owner_team_name"]
                    .fillna("")
                    .astype(str)
                    .str.lower()
                    .apply(lambda owner: sum(token in owner for token in query_tokens))
                )
                player_results["query_match_score"] = (
                    pd.to_numeric(player_results["query_match_score"], errors="coerce").fillna(0)
                    + (player_results["owner_match_score"] * 4)
                )

    pick_rows = []
    requested_year = None if pick_year in (None, "", "Any") else _safe_positive_int(pick_year, 0)
    requested_round = None if pick_round in (None, "", "Any") else _safe_positive_int(pick_round, 0)
    if requested_year is None and pick_query.get("year") is not None:
        requested_year = _safe_positive_int(pick_query.get("year"), 0)
    if requested_round is None and pick_query.get("round") is not None:
        requested_round = _safe_positive_int(pick_query.get("round"), 0)
    allow_pick_browse = (
        len(q) >= 2
        or requested_year is not None
        or requested_round is not None
        or partner_roster_id not in (None, "", "All Teams")
        or only_owned
        or bool(allowed_player_ids)
    )
    if include_picks and allow_pick_browse:
        for pick in draft_picks or []:
            label = str(pick.get("label", ""))
            if partner_roster_id not in (None, "", "All Teams") and str(pick.get("owner_roster_id")) != str(partner_roster_id):
                continue
            if requested_year and _safe_positive_int(pick.get("season"), 0) != requested_year:
                continue
            if requested_round and _safe_positive_int(pick.get("round"), 0) != requested_round:
                continue
            if len(q) >= 2 and not _pick_matches_query(pick, q):
                continue
            pick_score = max(0, int(round(float(pick.get("score", 0) or 0) * pick_score_multiplier)))
            match_score = _pick_match_score(pick, q) if len(q) >= 2 else 0
            pick_rows.append(
                {
                    "asset_type": "pick",
                    "player_id": "",
                    "name": label,
                    "label": label,
                    "position": "PICK",
                    "team": "",
                    "score": pick_score,
                    "value_score": int(pick.get("score", 0)),
                    "season": pick.get("season"),
                    "round": pick.get("round"),
                    "owner_roster_id": pick.get("owner_roster_id"),
                    "owner_team_name": pick.get("owner_team_name", ""),
                    "original_team_name": pick.get("original_team_name", ""),
                    "query_match_score": match_score,
                }
            )

    pick_results = pd.DataFrame(pick_rows)
    combined = pd.concat([player_results, pick_results], ignore_index=True, sort=False) if not pick_results.empty else player_results
    if combined.empty:
        return combined

    if "query_match_score" not in combined.columns:
        combined["query_match_score"] = 0
    combined["query_match_score"] = pd.to_numeric(combined["query_match_score"], errors="coerce").fillna(0)
    combined["value_score"] = pd.to_numeric(combined["value_score"], errors="coerce").fillna(0)
    if "dynasty_score" in combined.columns:
        combined["dynasty_score"] = pd.to_numeric(
            combined["dynasty_score"], errors="coerce"
        ).fillna(0)
    else:
        combined["dynasty_score"] = 0
    combined["score"] = pd.to_numeric(combined.get("score", combined["value_score"]), errors="coerce").fillna(0)
    combined["query_prefers_pick"] = (
        combined["asset_type"].eq("pick").astype(int) if pick_query.get("is_pick_query") else 0
    )
    if asset_filter == "Picks":
        combined["season_sort"] = pd.to_numeric(combined.get("season"), errors="coerce").fillna(9999)
        combined["round_sort"] = pd.to_numeric(combined.get("round"), errors="coerce").fillna(99)
        combined = combined.sort_values(
            ["query_match_score", "season_sort", "round_sort", "score", "label"],
            ascending=[False, True, True, False, True],
        )
    else:
        sort_fields = ["query_prefers_pick", "query_match_score", "score", "dynasty_score", "value_score"]
        combined = combined.sort_values(sort_fields, ascending=[False, False, False, False, False])
    return combined.head(limit)


def search_trade_assets_for_side(
    df_players: pd.DataFrame,
    draft_picks: list[dict],
    query: str,
    score_field: str = "value_score",
    pick_score_multiplier: float = 1.0,
    owned_player_ids: set[str] | None = None,
    only_owned: bool = False,
    exclude_owned: bool = False,
    allowed_player_ids: set[str] | None = None,
    asset_filter: str = "All",
    pick_year=None,
    pick_round=None,
    partner_roster_id=None,
    player_owner_map: dict[str, dict] | None = None,
    limit: int = 8,
) -> pd.DataFrame:
    results = search_trade_assets(
        df_players,
        draft_picks,
        query,
        score_field=score_field,
        pick_score_multiplier=pick_score_multiplier,
        owned_player_ids=owned_player_ids,
        only_owned=only_owned,
        exclude_owned=exclude_owned,
        allowed_player_ids=allowed_player_ids,
        asset_filter=asset_filter,
        pick_year=pick_year,
        pick_round=pick_round,
        partner_roster_id=partner_roster_id,
        player_owner_map=player_owner_map,
        limit=limit,
    )
    if results.empty:
        return results

    if only_owned or exclude_owned:
        owned_player_ids = owned_player_ids or set()
        asset_type = results["asset_type"].fillna("").astype(str)
        player_ids = results["player_id"].fillna("").astype(str)
        is_player = asset_type.eq("player")
        is_owned = player_ids.isin({str(player_id) for player_id in owned_player_ids})
        keep_mask = (~is_player) | (is_owned if only_owned else ~is_owned)
        results = results.loc[keep_mask].copy()
    return results


def team_logo_html(avatar_url: str, team_name: str, css_class: str = "team-logo-wrap") -> str:
    if avatar_url:
        return f"<div class='{css_class}'><img src='{escape(avatar_url, quote=True)}' alt='{escape(team_name)} logo' loading='lazy'></div>"
    return f"<div class='{css_class}'>{escape(_team_initials(team_name))}</div>"


def render_sidebar_franchise_card(
    *,
    team_name: str,
    league_name: str,
    owner_name: str = "",
    avatar_url: str = "",
    startup_mode: bool = False,
):
    title = _safe_text(team_name, brand_identity.PRODUCT_NAME)
    subtitle = _safe_text(league_name, "Select a league")
    owner_line = _safe_text(owner_name, "")
    eyebrow = "Startup Mode" if startup_mode else "Active Franchise"
    logo = team_logo_html(avatar_url, title, css_class="sidebar-logo-wrap")
    meta = " | ".join(part for part in [subtitle, owner_line] if part)
    st.sidebar.markdown(
        "<div class='platform-sidebar-card'>"
        + "<div class='platform-sidebar-top'>"
        + logo
        + "<div>"
        + f"<div class='platform-sidebar-eyebrow'>{escape(eyebrow)}</div>"
        + f"<div class='platform-sidebar-name'>{escape(title)}</div>"
        + f"<div class='platform-sidebar-meta'>{escape(meta or 'Main-page launch flow is the fastest way to get started. Optional setup controls stay below.')}</div>"
        + "</div></div></div>",
        unsafe_allow_html=True,
    )


def render_executive_profile_control(
    *,
    account_label: str,
    entitlement_label: str,
    key_prefix: str = "executive_profile",
    current_page: str = "dashboard",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> None:
    with st.container(key=f"executive_command_cell_profile_{key_prefix}"):
        with st.popover("You", help="Account, Premium, and Feedback"):
            render_html_fragment(
                "<div class='dg-profile-panel'>"
                f"<div class='dg-profile-panel__title'>{escape(brand_identity.PRODUCT_NAME)}</div>"
                "<div class='dg-profile-panel__meta'>"
                f"{escape(_safe_text(account_label, 'Guest'))} · "
                f"{escape(_safe_text(entitlement_label, 'Free'))} · "
                f"{escape(brand_identity.FOUNDER_BETA_LABEL)}"
                "</div></div>"
            )
            st.caption("Account, Premium, and Feedback.")
            st.button(
                "Open Premium",
                key=f"{key_prefix}_open_premium",
                use_container_width=True,
                on_click=_commit_platform_destination,
                args=("premium",),
                kwargs={"source": "profile_premium"},
            )
            active_context = st.session_state.get("active_league_context", {})
            if not isinstance(active_context, dict):
                active_context = {}
            feedback_roster_id = (
                my_roster_id
                if my_roster_id is not None
                else active_context.get("my_roster_id")
            )
            render_global_feedback_entry(
                current_page=current_page or "dashboard",
                selected_league_id=selected_league_id,
                selected_league_name=selected_league_name,
                my_roster_id=feedback_roster_id,
                key_prefix=f"{key_prefix}_feedback",
                placement="profile",
            )

def render_platform_topbar(
    *,
    page_title: str,
    page_note: str,
    selected_league_id: str = "",
    selected_league_name: str = "",
    team_profile: dict | None = None,
    platform: str = "",
    account_label: str = "",
    entitlement_label: str = "",
    strategy_label: str = "",
    archetype_label: str = "",
    power_rank=None,
    franchise_rank=None,
):
    profile = team_profile if isinstance(team_profile, dict) else {}
    current_page = _safe_text(st.session_state.get("platform_nav_page"))
    notifications = notification_center.list_founder_beta_notifications(
        session=st.session_state
    )
    unread = notification_center.unread_count(notifications)
    inject_global_styles(EXECUTIVE_COMMAND_HEADER_CSS)
    with st.container(key="executive_workspace_shell"):
        st.markdown(
            application_shell.executive_workspace_shell_html(
                application_shell.ExecutiveWorkspaceShell(
                    page_title=_safe_text(page_title),
                    page_note=_safe_text(page_note),
                    league_name=_safe_text(selected_league_name),
                    team_name=_safe_text(
                        profile.get("team_name"),
                        _safe_text(profile.get("username"), "Current team"),
                    ),
                    platform=_safe_text(platform, "Sleeper"),
                    account_label=_safe_text(account_label, "Guest"),
                    entitlement_label=_safe_text(entitlement_label, "Free"),
                    has_league=bool(selected_league_id),
                    avatar_url=_safe_text(profile.get("avatar_url")),
                    authenticated=_safe_text(account_label).casefold() != "guest",
                    metrics=(),
                    notification_unread=unread,
                )
            ),
            unsafe_allow_html=True,
        )
        with st.container(key="executive_command_actions"):
            league_col, alerts_col, profile_col = st.columns(
                list(COMMAND_COLUMN_WEIGHTS),
                gap="small",
            )
            with league_col:
                render_top_league_identity_header(
                    selected_league_id=selected_league_id,
                    selected_league_name=selected_league_name,
                    team_profile=profile,
                    platform=platform,
                    current_page=current_page,
                )
            with alerts_col:
                notification_center.render_notification_center(
                    items=notifications,
                    on_open_item=_open_notification_item,
                    key_prefix=f"executive_notifications_{current_page or 'home'}",
                )
            with profile_col:
                render_executive_profile_control(
                    account_label=account_label,
                    entitlement_label=entitlement_label,
                    key_prefix=f"executive_profile_{current_page or 'home'}",
                    current_page=current_page or "dashboard",
                    selected_league_id=selected_league_id,
                    selected_league_name=selected_league_name,
                )
    st.session_state["_executive_command_header_mounted"] = True
    league_switch_ack = st.session_state.pop("_league_switch_ack", None)
    if isinstance(league_switch_ack, dict):
        ack_name = _safe_text(league_switch_ack.get("league_name"), "Selected league")
        ack_phase = _safe_text(league_switch_ack.get("phase"), "ready").casefold()
        if ack_phase == "loading":
            st.markdown(
                application_shell.shell_ack_html(
                    label="Switching league",
                    message=f"Loading {ack_name}…",
                ),
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                application_shell.shell_ack_html(
                    label="League ready",
                    message=f"Loaded {ack_name}.",
                ),
                unsafe_allow_html=True,
            )
        league_switch_first_useful.mark_league_switch_milestone("league_switch_first_useful")


def _query_param_page() -> str:
    try:
        raw_value = st.query_params.get("page", "")
    except Exception:
        return ""
    if isinstance(raw_value, list):
        return str(raw_value[0]) if raw_value else ""
    return str(raw_value or "")


def _normalize_platform_page(page_key: str, *, startup_mode: bool) -> str:
    normalized = _safe_text(page_key).strip()
    if startup_mode and normalized == "draft_summary":
        return "startup_draft_center"
    if not startup_mode and normalized == "startup_draft_center":
        return "draft_summary"
    return normalized


def _queue_platform_route(
    page_key: str,
    *,
    force_scroll: bool = False,
    source: str = "destination_navigation",
) -> None:
    requested = queue_destination_navigation(
        st.session_state,
        page_key,
        current_destination=st.session_state.get("platform_nav_page"),
        source=source,
        force_scroll=force_scroll,
    )
    if requested:
        performance.mark_interaction("destination_navigation_render", lightweight=False)
        performance.record_timing(
            "navigation_scroll_reset_request",
            0.0,
            category="navigation",
        )


def _commit_platform_destination(page_key: str, *, source: str) -> None:
    performance.mark_interaction("destination_navigation_render", lightweight=False)
    requested = commit_destination_navigation(
        st.session_state,
        page_key,
        current_destination=st.session_state.get("platform_nav_page"),
        source=source,
    )
    if requested:
        performance.record_timing(
            "navigation_scroll_reset_request",
            0.0,
            category="navigation",
        )


def _open_trade_hub_from_live_draft_rank(player_id: str) -> None:
    """Commit Trade Hub focus from Live Draft without an explicit second rerun."""

    focus_player_id = _safe_text(player_id).strip()
    league_id = _safe_text(st.session_state.get("selected_league_id")).strip()
    # Keep the legacy handoff key and the league-scoped focus key in sync.
    st.session_state["trade_hub_player_id"] = focus_player_id
    if league_id and focus_player_id:
        st.session_state[f"trade_hub_focus_player_id_{league_id}"] = focus_player_id
        st.session_state[f"trade_hub_focus_mode_{league_id}"] = "target_player"
    _capture_workflow_handoff(
        "trade_hub",
        origin_page="live_draft",
        origin_label="Live Draft",
        note="Continue evaluating this target in Trade Hub.",
        league_id=league_id,
        handoff_source="live_draft_rank",
    )
    _commit_platform_destination("trade_hub", source="live_draft_rank")


def _render_navigation_scroll_reset(current_page: str, *, league_id: str = "") -> None:
    previous_destination = _safe_text(st.session_state.get(LAST_DESTINATION_KEY))
    changed = synchronize_destination_change(st.session_state, current_page)
    # First destination assignment in a session is a real entry (not a rerun).
    route_entry = bool(changed or (current_page and not previous_destination))
    try:
        from modules import launch_analytics

        if league_id:
            launch_analytics.set_league_scope(st.session_state, league_id)
        launch_analytics.track_route_opened(
            current_page,
            state=st.session_state,
            changed=route_entry,
        )
    except Exception:
        pass
    scope = scroll_storage_scope(st.session_state, league_id=league_id)
    pending = consume_scroll_reset(st.session_state, current_page)
    if pending:
        performance.record_timing(
            "navigation_scroll_reset_consume",
            0.0,
            category="navigation",
        )
        token = int(pending.get("token") or 0)
        mode = _safe_text(pending.get("mode"), "reset") or "reset"
        NAVIGATION_SCROLL_RESET_COMPONENT(
            key=f"navigation_scroll_reset_{token}",
            data={
                "token": token,
                "destination": current_page,
                "scope": scope,
                "mode": mode,
            },
            width=1,
            height=1,
        )
    elif _safe_text(st.session_state.get("selected_league_id")):
        NAVIGATION_SCROLL_RESET_COMPONENT(
            key=f"navigation_scroll_track_{current_page}_{scope}",
            data={
                "token": 0,
                "destination": current_page,
                "scope": scope,
                "mode": "track",
            },
            width=1,
            height=1,
        )


LEAGUE_SWITCH_TRANSIENT_STATE_KEYS = (
    "player_detail_player_id",
    "player_detail_return_page",
    "player_detail_source_label",
    "selected_team_roster_id",
    "selected_team_name",
    "_pending_selected_team_roster_id",
    "role_map",
    "trade_hub_player_id",
    canonical_recommendation_narrative.NARRATIVE_SESSION_KEY,
    workflow_continuity.WORKFLOW_RETURN_KEY,
    "_cached_live_draft_active",
    live_draft.LIVE_DRAFT_DISCOVERY_AT_KEY,
    live_draft.LIVE_DRAFT_DISCOVERY_LEAGUE_KEY,
)

# Global scoring overrides must not bleed across leagues. Reset to Auto so the
# next league re-derives settings from Sleeper detection + the active lens.
LEAGUE_SETTINGS_OVERRIDE_KEYS = (
    "league_format_override",
    "league_scoring_override",
    "league_qb_override",
    "league_te_premium_override",
    "league_rb_count_override",
    "league_wr_count_override",
    "league_te_count_override",
    "league_starters_override",
    "league_flex_override",
    "league_bench_override",
    "league_taxi_override",
    "league_ir_override",
    "league_size_override",
)
PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY = "_pending_league_settings_override_reset"


def _clear_league_namespaced_trade_hub_focus(league_id: str) -> None:
    league_key = _safe_text(league_id).strip()
    if not league_key:
        return
    for suffix in (
        "trade_hub_focus_player_id_",
        "trade_hub_focus_mode_",
        "trade_hub_home_source_label_",
        "trade_hub_home_source_note_",
    ):
        st.session_state.pop(f"{suffix}{league_key}", None)


def _reset_league_settings_overrides() -> None:
    """Schedule Auto defaults for league settings widgets.

    Must not assign widget-backed keys after those widgets are instantiated in
    the current Streamlit run (sidebar overrides render before the header
    switcher callback). Defaults are applied by
    ``_apply_pending_league_settings_override_reset`` before widget construction.
    """

    st.session_state[PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY] = True


def _apply_pending_league_settings_override_reset() -> None:
    """Apply scheduled Auto defaults before override widgets instantiate."""

    if not st.session_state.pop(PENDING_LEAGUE_SETTINGS_OVERRIDE_RESET_KEY, False):
        return
    for key in LEAGUE_SETTINGS_OVERRIDE_KEYS:
        st.session_state[key] = "Auto"


def _clear_league_switch_transient_state(*, previous_league_id: str = "") -> None:
    """Drop route-local and derived state that must not survive a league change."""

    cleared_keys = list(LEAGUE_SWITCH_TRANSIENT_STATE_KEYS)
    for key in LEAGUE_SWITCH_TRANSIENT_STATE_KEYS:
        st.session_state.pop(key, None)
    _clear_player_quick_view()
    cleared_keys.extend(
        [
            "player_quick_view_player_id",
            "player_quick_view_source_label",
            "player_quick_view_source_note",
            "player_quick_view_status_label",
        ]
    )
    _clear_league_switch_workflow_state(previous_league_id=previous_league_id)
    # Close any open Trade Hub detail so the prior league's package cannot linger.
    trade_detail_navigation.close(st.session_state)
    cleared_keys.extend(["dg_trade_detail_active", "dg_trade_detail_view", "dg_trade_detail_player"])
    st.session_state["_mobile_destination_sheet_open"] = False
    _clear_league_namespaced_trade_hub_focus(previous_league_id)
    # Trade Analyzer packages are not league-keyed; clear so identical valuation
    # fingerprints cannot revive the prior league's send/receive assets.
    session_integrity.clear_trade_analyzer_package(st.session_state)
    notification_center.clear_notification_league_snapshot(st.session_state)
    decision_change_history.clear_decision_history(st.session_state)
    decision_memory.clear_decision_memory_session(st.session_state)
    gm_targets.clear_gm_targets_session(st.session_state)
    # Keep the valued+ranked frame when its scoring/lens signature remains valid.
    # Clear league-scoped shell/shared/Trade Hub memos so League A football
    # outputs cannot flash under a League B shell.
    with league_switch_first_useful.stage_timer("transient_state_cleanup"):
        prepared_player_frame.clear_league_scoped_prepared_memos(
            st.session_state,
            previous_league_id=previous_league_id,
        )
    _reset_league_settings_overrides()
    league_switch_first_useful.note_cleanup_keys(st.session_state, cleared_keys)
    league_switch_first_useful.mark_cleanup_complete(st.session_state)

def _open_notification_destination(destination: str) -> None:
    """Legacy route-only helper kept for tests; prefer _open_notification_item."""

    _open_notification_item(
        notification_center.NotificationItem(
            id=f"legacy:{_safe_text(destination)}",
            category="League",
            title=_safe_text(destination),
            body="Opened from the notification center.",
            href_hint=_safe_text(destination),
            provenance="legacy_route",
            source_kind="canonical",
            league_id=_safe_text(st.session_state.get("selected_league_id")),
        )
    )


def _open_notification_item(item) -> None:
    """Deep-link a canonical inbox item into the matching workflow."""

    if item is None:
        return
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "notification_center_opened",
            props=launch_analytics.build_context_props(
                st.session_state, source_surface="notification_center"
            ),
            once_key="inbox_engaged",
            state=st.session_state,
        )
        launch_analytics.track_event(
            "notification_item_opened",
            props=launch_analytics.build_context_props(
                st.session_state,
                source_surface="notification_center",
                extra={
                    "destination": _safe_text(getattr(item, "href_hint", "")),
                    "item_kind": _safe_text(getattr(item, "category", "")),
                },
            ),
            state=st.session_state,
        )
    except Exception:
        pass
    current_league = _safe_text(st.session_state.get("selected_league_id"))
    resolved = notification_center.validate_notification_for_open(
        item,
        session=st.session_state,
        current_league_id=current_league,
    )
    notification_center.mark_notification_read(
        st.session_state,
        resolved.id,
        league_id=current_league or _safe_text(getattr(resolved, "league_id", "")),
    )
    if resolved.stale:
        st.session_state["_notification_open_notice"] = _safe_text(
            resolved.stale_reason,
            "No longer active",
        )
        return

    destination = _safe_text(getattr(resolved, "href_hint", "")).strip()
    if not destination:
        return

    player_id = _safe_text(getattr(resolved, "player_id", ""))
    narrative = getattr(resolved, "recommendation_narrative", None)
    note = _safe_text(getattr(resolved, "body", "")) or "Opened from the notification center."

    # Preserve overlays only when opening PQV; otherwise clear competing detail.
    if destination == "player_quick_view":
        if not player_id:
            st.session_state["_notification_open_notice"] = "Player is no longer available"
            return
        trade_detail_navigation.close(st.session_state)
        st.session_state["_mobile_destination_sheet_open"] = False
        open_player_quick_view(
            player_id,
            source_label="Notifications",
            source_note=note,
            recommendation_narrative=narrative,
        )
        _capture_workflow_handoff(
            "dashboard",
            origin_page="notification_center",
            origin_label="Notifications",
            note=note,
            league_id=current_league,
            handoff_source="notification_center",
        )
        return

    _clear_player_quick_view()
    trade_detail_navigation.close(st.session_state)
    st.session_state["_mobile_destination_sheet_open"] = False

    if narrative is not None:
        canonical_recommendation_narrative.bind_narrative(
            st.session_state,
            narrative,
        )

    if destination == "trade_hub" and current_league:
        focus_mode = (
            _safe_text(getattr(resolved, "focus_mode", ""))
            or _safe_text(getattr(resolved, "destination_detail", ""))
            or "target_player"
        )
        if player_id:
            st.session_state[f"trade_hub_focus_player_id_{current_league}"] = player_id
            st.session_state[f"trade_hub_focus_mode_{current_league}"] = focus_mode
        st.session_state[f"trade_hub_home_source_label_{current_league}"] = "Notifications"
        st.session_state[f"trade_hub_home_source_note_{current_league}"] = note

    if destination == "waivers" and player_id:
        st.session_state["waivers_focus_player_id"] = player_id

    route_key = "rankings" if destination == "league_overview" else destination
    _capture_workflow_handoff(
        route_key,
        origin_page="notification_center",
        origin_label="Notifications",
        note=note,
        league_id=current_league,
        handoff_source="notification_center",
    )
    _queue_platform_route(route_key, source="notification_center")


def _reset_selected_league_for_import() -> None:
    st.session_state["selected_league_id"] = None
    st.session_state["selected_league_name"] = ""
    st.session_state["_league_selection_established"] = False
    st.session_state["supabase_auto_resume_suppressed"] = True
    st.session_state["_sync_sidebar_league_select"] = True
    _queue_platform_route(
        "dashboard",
        force_scroll=True,
        source="league_import",
    )


def _saved_league_team_label(row: dict) -> str:
    for key in ("team_name", "roster_name", "owner_name"):
        value = _safe_text(row.get(key)).strip()
        if value:
            return value
    roster_id = _safe_text(row.get("roster_id") or row.get("team_id")).strip()
    return f"Team {roster_id}" if roster_id else ""


def _saved_league_switcher_rows() -> tuple[list[dict], str]:
    cached_rows = st.session_state.get("account_saved_leagues_cache")
    if isinstance(cached_rows, list):
        return cached_rows, ""

    config = _supabase_config()
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not auth_supabase.is_configured(config) or not user_id or not access_token:
        return [], ""

    rows, error = account_store.fetch_saved_leagues(config, access_token, user_id=user_id)
    if not error:
        st.session_state["account_saved_leagues_cache"] = rows
    return rows, error


def _league_switch_row_html(row: dict, *, is_current: bool) -> str:
    league_name = _safe_text(row.get("league_name"), "Saved league")
    season = _safe_text(row.get("season") or row.get("league_season"))
    platform = _safe_text(row.get("platform"), "Sleeper")
    team_name = _saved_league_team_label(row)
    meta_bits = [part for part in [f"S{season}" if season else "", platform, team_name] if part]
    current_badge = "<span class='league-switch-current-badge'>Current</span>" if is_current else ""
    default_badge = "<span class='league-switch-default-badge'>Default</span>" if row.get("is_default") else ""
    return (
        f"<div class='league-switch-row {'league-switch-row-current' if is_current else ''}'>"
        "<div class='league-switch-row-copy'>"
        f"<div class='league-switch-row-title'>{escape(league_name)}</div>"
        f"<div class='league-switch-row-meta'>{escape(' | '.join(meta_bits) or 'Saved league')}</div>"
        "</div>"
        f"<div class='league-switch-row-badges'>{current_badge}{default_badge}</div>"
        "</div>"
    )


def _switch_to_saved_league(row: dict, *, current_page: str = "") -> None:
    switch_started = time.perf_counter()
    sleeper_username = _safe_text(row.get("sleeper_username")).strip()
    league_id = _safe_text(row.get("league_id")).strip()
    league_name = _safe_text(row.get("league_name"), "Saved league").strip()
    if not league_id:
        return
    preserved_page = preserved_league_switch_destination(
        current_page,
        session_page=st.session_state.get("platform_nav_page"),
        query_page=_query_param_page(),
    )
    if sleeper_username and _safe_text(st.session_state.get("username")).strip() != sleeper_username:
        load_leagues_for_username(sleeper_username)
    set_selected_league(
        league_id,
        league_name,
        route_to_dashboard=False,
    )
    # set_selected_league already invalidates active context and transient state.
    try:
        st.session_state["platform_nav_page"] = preserved_page
        st.session_state["current_page"] = preserved_page
        st.session_state["_pending_platform_route"] = preserved_page
        request_scroll_reset(
            st.session_state,
            preserved_page,
            reason="league_switch",
            force=True,
        )
        performance.record_timing(
            "navigation_scroll_reset_request",
            0.0,
            category="navigation",
        )
        st.query_params["page"] = preserved_page
    except Exception:
        st.session_state["platform_nav_page"] = "dashboard"
        st.session_state["current_page"] = "dashboard"
        st.session_state["_pending_platform_route"] = "dashboard"
        request_scroll_reset(
            st.session_state,
            "dashboard",
            reason="league_switch_fallback",
            force=True,
        )
        st.query_params["page"] = "dashboard"
    performance.record_timing(
        "league_switch_wall",
        (time.perf_counter() - switch_started) * 1000.0,
        category="navigation",
    )
    st.session_state["_league_actions_epoch"] = (
        int(st.session_state.get("_league_actions_epoch", 0)) + 1
    )
    st.session_state["_league_switch_ack"] = {
        "league_name": league_name,
        "league_id": league_id,
        "ts": time.time(),
        "phase": "loading",
    }
    league_switch_first_useful.mark_league_switch_milestone("league_switch_shell_ready")


def render_header_league_switcher(*, current_league_id: str = "", current_page: str = "") -> None:
    rows, error = _saved_league_switcher_rows()
    if error:
        st.caption("Saved leagues could not be loaded right now.")
        return

    saved_rows = [row for row in rows if isinstance(row, dict) and _safe_text(row.get("league_id")).strip()]
    other_rows = [
        row for row in saved_rows
        if _safe_text(row.get("league_id")).strip() != _safe_text(current_league_id).strip()
    ]
    if not other_rows:
        st.caption("Only one league saved. Import another to switch here.")
        if st.button("Manage / Import Leagues", key="top_header_manage_import_empty", use_container_width=True):
            _reset_selected_league_for_import()
            st.rerun()
        return

    card_rows = []
    rows_by_id = {}
    for row in saved_rows:
        league_id = _safe_text(row.get("league_id")).strip()
        is_current = bool(current_league_id and league_id == _safe_text(current_league_id).strip())
        league_name = _safe_text(row.get("league_name"), "Saved league")
        season = _safe_text(row.get("season") or row.get("league_season"))
        platform = _safe_text(row.get("platform"), "Sleeper")
        team_name = _saved_league_team_label(row)
        meta_bits = [part for part in [f"S{season}" if season else "", platform, team_name] if part]
        rows_by_id[league_id] = row
        card_rows.append(
            {
                "league_id": league_id,
                "title": league_name,
                "meta": " | ".join(meta_bits) or "Saved league",
                "current": is_current,
                "is_default": bool(row.get("is_default")),
            }
        )

    result = LEAGUE_SWITCH_CARD_COMPONENT(
        key="top_header_league_card_switcher",
        data={"cards": card_rows},
        width="stretch",
        height="content",
        on_clicked_change=lambda: None,
    )
    clicked = getattr(result, "clicked", None)
    clicked_id = _safe_text(clicked.get("league_id")).strip() if isinstance(clicked, dict) else ""
    selected_row = rows_by_id.get(clicked_id)
    if selected_row and clicked_id != _safe_text(current_league_id).strip():
        _switch_to_saved_league(selected_row, current_page=current_page)
        st.rerun()


def render_top_league_identity_header(
    *,
    selected_league_id: str | None,
    selected_league_name: str,
    team_profile: dict | None,
    platform: str,
    current_page: str = "",
) -> None:
    profile = team_profile if isinstance(team_profile, dict) else {}
    league_actions_epoch = int(st.session_state.get("_league_actions_epoch", 0))
    with st.container(key=f"executive_command_cell_league_{league_actions_epoch}"):
        with st.popover(
            "Switch League" if selected_league_id else "Select League",
            width="content",
            key=f"top_league_actions_{league_actions_epoch}",
        ):
            interaction_latency.mark_interaction_milestone("league_switcher_open")
            st.markdown("<span class='league-actions-sheet-marker'></span>", unsafe_allow_html=True)
            st.markdown("**Current League**")
            if selected_league_id:
                current_summary = selected_league_name or "Selected league"
                team_label = _safe_text(
                    profile.get("team_name"),
                    _safe_text(profile.get("username"), ""),
                )
                if team_label:
                    current_summary += f" | {team_label}"
                st.caption(current_summary)
            else:
                st.caption("No league selected.")
            if selected_league_id:
                st.markdown("<div class='league-actions-section'><strong>Switch League</strong></div>", unsafe_allow_html=True)
                render_header_league_switcher(
                    current_league_id=_safe_text(selected_league_id),
                    current_page=current_page,
                )
                st.markdown("<div class='league-actions-section'></div>", unsafe_allow_html=True)
                if st.button("Refresh Current League", key="top_header_refresh_current_league", use_container_width=True):
                    st.session_state.pop("active_league_context", None)
                    _clear_player_quick_view()
                    st.rerun()
                if st.button("Manage Leagues", key="top_header_change_league", use_container_width=True):
                    _reset_selected_league_for_import()
                    st.rerun()
            else:
                if st.button("Import League", key="top_header_import_league", use_container_width=True):
                    _queue_platform_route("dashboard")
                    st.rerun()
                st.caption("Sleeper is the recommended import path. ESPN remains experimental.")
            st.caption("Tap a league to switch without leaving this page.")


def _league_display_name(league_name: str = "", season = "", *, league_record: dict | None = None) -> str:
    if isinstance(league_record, dict):
        league_name = _safe_text(league_record.get("name"), league_name)
        season = _safe_text(league_record.get("season"), season)
    name_text = _safe_text(league_name, "Unnamed league").strip() or "Unnamed league"
    season_text = _safe_text(season).strip()
    if season_text and f"(S{season_text})" not in name_text:
        return f"{name_text} (S{season_text})"
    return name_text


def _persist_active_account_context(*, username: str = "", league_id: str = "") -> None:
    username_text = _safe_text(username).strip()
    league_text = _safe_text(league_id).strip()
    if not username_text or not league_text:
        return
    fingerprint = f"{username_text.casefold()}|{league_text}"
    if st.session_state.get("_persisted_account_context_fingerprint") == fingerprint:
        return
    try:
        current_name = _safe_text(get_current_account().get("name")).strip() or "1"
        upsert_account(current_name, league_text, username_text)
        st.session_state["_persisted_account_context_fingerprint"] = fingerprint
    except Exception:
        return


def _supabase_config() -> dict:
    try:
        secrets = st.secrets
    except Exception:
        secrets = None
    return auth_supabase.get_supabase_config(secrets=secrets)


def _safe_supabase_project_ref(config: dict) -> str:
    try:
        host = urlparse(_safe_text(config.get("url"))).hostname or ""
    except Exception:
        host = ""
    parts = host.split(".")
    return parts[0] if len(parts) >= 3 and parts[1] == "supabase" else host


def _safe_secret_flag(name: str) -> bool:
    try:
        secrets = st.secrets
    except Exception:
        secrets = None
    return app_config.config_bool(name, secrets=secrets)


def _destination_visibility_flags() -> dict[str, bool]:
    try:
        secrets = st.secrets
    except Exception:
        secrets = None
    flags = {
        "show_experimental": app_config.config_bool(
            "DYNASTYGM_SHOW_EXPERIMENTAL", secrets=secrets
        ),
        "show_dev": app_config.config_bool(
            "DYNASTYGM_SHOW_DEV_DESTINATIONS", secrets=secrets
        ),
        # Founder ops is intentionally independent of customer-unsafe debug locks.
        "show_founder_ops": founder_ops.founder_ops_enabled(secrets=secrets),
    }
    if not app_config.customer_unsafe_debug_allowed(secrets=secrets):
        # Managed hosts never expose experimental/dev destinations without an
        # explicit DYNASTYGM_ALLOW_PROD_DEBUG escape hatch.
        flags["show_experimental"] = False
        flags["show_dev"] = False
    return flags


def _render_premium_entitlement_diagnostics() -> None:
    try:
        secrets = st.secrets
    except Exception:
        secrets = None
    if not premium.debug_auth_enabled(secrets=secrets):
        return

    config = _supabase_config()
    profile = st.session_state.get("account_profile")
    profile_dict = profile if isinstance(profile, dict) else {}
    entitlement_debug = premium.get_entitlement_debug(
        session_state=st.session_state,
        secrets=secrets,
    )
    safe_payload = {
        "supabase_project_ref": _safe_supabase_project_ref(config),
        "auth_user_id": auth_supabase.current_user_id(st.session_state),
        "auth_email": _safe_text(st.session_state.get(auth_supabase.AUTH_EMAIL_KEY)),
        "account_profile_status": _safe_text(st.session_state.get("account_profile_status")),
        "account_profile_error": _safe_text(st.session_state.get("account_profile_error")),
        "account_profile_keys": sorted(str(key) for key in profile_dict.keys()),
        "account_profile_user_id": _safe_text(profile_dict.get("user_id")),
        "account_profile_entitlement": _safe_text(profile_dict.get("entitlement")),
        "effective_entitlement": entitlement_debug.get("entitlement"),
        "is_premium": bool(entitlement_debug.get("is_premium")),
        "entitlement_source": entitlement_debug.get("source"),
        "entitlement_source_field": entitlement_debug.get("source_field"),
        "entitlement_raw_value": entitlement_debug.get("raw_value"),
        "entitlement_reason": entitlement_debug.get("reason"),
    }
    with st.expander("Developer entitlement diagnostics", expanded=False):
        st.json(safe_payload)


def _persist_supabase_account_context(
    *,
    username: str = "",
    league_id: str = "",
    league_name: str = "",
    roster_id=None,
) -> None:
    config = _supabase_config()
    if not auth_supabase.is_configured(config):
        return
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not user_id or not access_token:
        return
    account_ui.save_current_context(
        config=config,
        access_token=access_token,
        user_id=user_id,
        email=_safe_text(st.session_state.get(auth_supabase.AUTH_EMAIL_KEY)),
        username=username,
        selected_league_id=league_id,
        selected_league_name=league_name,
        my_roster_id=roster_id,
    )


def _resume_saved_supabase_league(saved_league: dict | None) -> None:
    saved = saved_league if isinstance(saved_league, dict) else {}
    sleeper_username = _safe_text(saved.get("sleeper_username")).strip()
    league_id = _safe_text(saved.get("league_id")).strip()
    league_name = _safe_text(saved.get("league_name"), "Saved league").strip()
    if not sleeper_username or not league_id:
        return
    load_leagues_for_username(sleeper_username)
    set_selected_league(
        league_id,
        league_name,
        route_to_dashboard=True,
    )


def _maybe_auto_resume_supabase_league() -> bool:
    if _safe_text(st.session_state.get("selected_league_id")).strip():
        return False
    if st.session_state.get("supabase_auto_resume_suppressed"):
        return False
    config = _supabase_config()
    if not auth_supabase.is_configured(config):
        return False
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not user_id or not access_token:
        return False
    resume_key = f"_supabase_auto_resume_attempted_{user_id}"
    if st.session_state.get(resume_key):
        return False
    st.session_state[resume_key] = True
    saved_rows, error = account_store.fetch_saved_leagues(
        config,
        access_token,
        user_id=user_id,
    )
    if error:
        st.session_state["account_resume_notice"] = error
        return False
    st.session_state["account_saved_leagues_cache"] = saved_rows
    default_league = account_store.default_saved_league(saved_rows, require_default=True)
    if not default_league:
        if saved_rows:
            st.session_state["account_resume_notice"] = "Choose a saved league or add your Sleeper leagues."
        return False
    _resume_saved_supabase_league(default_league)
    st.session_state["account_resume_notice"] = (
        "Loaded saved league: "
        + _safe_text(default_league.get("league_name"), "Saved league")
    )
    return True


def _refresh_supabase_account_profile(*, force: bool = False) -> None:
    config = _supabase_config()
    if not auth_supabase.is_configured(config):
        st.session_state.pop("account_profile", None)
        st.session_state["account_profile_status"] = "accounts_not_configured"
        return
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if not user_id or not access_token:
        st.session_state.pop("account_profile", None)
        st.session_state["account_profile_status"] = "signed_out"
        return
    cache_key = f"_supabase_profile_loaded_{user_id}"
    loaded_at_key = f"{cache_key}_at"
    loaded_at = float(st.session_state.get(loaded_at_key) or 0.0)
    if st.session_state.get(cache_key) and not force and (time.time() - loaded_at) < 60.0:
        return
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "profile_fetch_start",
        once=True,
    )
    auth_restore_lifecycle.record_profile_fetch(st.session_state)
    profile, error = account_store.fetch_profile(
        config,
        access_token,
        user_id=user_id,
        timeout=startup_critical_path.STARTUP_NETWORK_TIMEOUT_SECONDS,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "profile_fetch_complete",
        once=True,
    )
    if error:
        st.session_state["account_profile_status"] = "error"
        st.session_state["account_profile_error"] = error
        return
    st.session_state["account_profile"] = profile
    st.session_state["account_profile_status"] = "loaded" if profile else "missing"
    st.session_state.pop("account_profile_error", None)
    st.session_state[cache_key] = True
    st.session_state[loaded_at_key] = time.time()


def _persist_onboarding_dismissal() -> None:
    """Persist the account-wide onboarding dismissal; fail visibly, never locally."""

    error = user_preferences.persist_authenticated_onboarding(
        config=_supabase_config(),
        session_state=st.session_state,
        dismissed=True,
    )
    if error:
        st.session_state["onboarding_preference_notice"] = (
            "League Orientation could not be hidden permanently. Please try again."
        )
        return
    st.session_state["onboarding_preference_notice"] = "League Orientation hidden."


def resolve_active_league_context() -> dict:
    username = _safe_text(st.session_state.get("username")).strip()
    selected_league_id = _safe_text(st.session_state.get("selected_league_id")).strip()
    selected_league_name = _safe_text(st.session_state.get("selected_league_name")).strip()
    leagues = st.session_state.get("leagues_for_user", [])
    leagues_loaded_for = _safe_text(st.session_state.get("leagues_for_user_username")).strip().casefold()

    # Identity and league ownership are separate. A username submit may restore the
    # matching username, but a stored league is restored only after this session has
    # explicitly selected a league (or accepted the single-league shortcut).
    if (not username or not selected_league_id) and st.session_state.get("_identity_established"):
        current_account = get_current_account()
        if not username:
            restored_username = _safe_text(current_account.get("username")).strip()
            if restored_username:
                username = restored_username
                st.session_state["username"] = restored_username
                st.session_state["_sync_sidebar_username_input"] = True
                st.session_state["_sync_home_launch_username_input"] = True
        if not selected_league_id and st.session_state.get("_league_selection_established"):
            restored_league_id = _safe_text(current_account.get("league_id")).strip()
            if restored_league_id:
                selected_league_id = restored_league_id
                st.session_state["selected_league_id"] = restored_league_id
                st.session_state["_sync_sidebar_league_select"] = True

    if username and (not isinstance(leagues, list) or leagues_loaded_for != username.casefold()):
        try:
            leagues = get_user_leagues(username)
        except Exception:
            leagues = []
        st.session_state["leagues_for_user"] = leagues
        st.session_state["leagues_for_user_username"] = username

    league_record = None
    if isinstance(leagues, list) and leagues:
        for league in leagues:
            if str(league.get("league_id")) == str(selected_league_id):
                league_record = league
                break
        valid_league_ids = {str(league.get("league_id")) for league in leagues if league.get("league_id")}
        if selected_league_id and valid_league_ids and str(selected_league_id) not in valid_league_ids:
            selected_league_id = ""
            selected_league_name = ""
            st.session_state["selected_league_id"] = None
            st.session_state["selected_league_name"] = ""
            st.session_state["_sync_sidebar_league_select"] = True

    if selected_league_id and not selected_league_name:
        if league_record is None:
            try:
                fallback_league = get_league(selected_league_id) or {}
            except Exception:
                fallback_league = {}
            if isinstance(fallback_league, dict) and fallback_league:
                league_record = {
                    "league_id": selected_league_id,
                    "name": fallback_league.get("name"),
                    "season": fallback_league.get("season"),
                }
        selected_league_name = _league_display_name(league_record=league_record)
        st.session_state["selected_league_name"] = selected_league_name

    if username and selected_league_id:
        _persist_active_account_context(username=username, league_id=selected_league_id)

    my_roster_id = get_user_roster_id(selected_league_id, username) if username and selected_league_id else None
    context = {
        "username": username,
        "selected_league_id": selected_league_id or None,
        "selected_league_name": selected_league_name,
        "leagues_for_user": leagues if isinstance(leagues, list) else [],
        "my_roster_id": my_roster_id,
    }
    st.session_state["active_league_context"] = context
    return context


def load_leagues_for_username(username_raw: str) -> list[dict]:
    username_clean = _safe_text(username_raw).strip()
    previous_username = _safe_text(st.session_state.get("username")).strip()
    previous_league_id = _safe_text(st.session_state.get("selected_league_id")).strip()
    st.session_state["league_lookup_attempted"] = True
    st.session_state["_sync_sidebar_username_input"] = True
    st.session_state["_sync_home_launch_username_input"] = True
    st.session_state["_sync_sidebar_league_select"] = True
    if not username_clean:
        st.session_state["username"] = ""
        st.session_state["leagues_for_user"] = []
        st.session_state["leagues_for_user_username"] = ""
        st.session_state["selected_league_id"] = None
        st.session_state["selected_league_name"] = ""
        st.session_state["last_league_option_id"] = ""
        st.session_state["_league_selection_established"] = False
        st.session_state["league_lookup_status"] = "empty_username"
        return []

    # Username submission establishes identity, but not league ownership. Multiple
    # leagues remain unselected until the user chooses a card or Continue.
    st.session_state["_identity_established"] = True
    st.session_state["username"] = username_clean
    lookup = lookup_user_leagues(username_clean)
    st.session_state["league_lookup_status"] = lookup.status
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "league_import_started",
            props=launch_analytics.build_context_props(
                st.session_state, source_surface="league_lookup"
            ),
            once_key="session",
            state=st.session_state,
        )
    except Exception:
        pass
    leagues = onboarding_ui.eligible_leagues(lookup.leagues)
    st.session_state["leagues_for_user"] = leagues
    st.session_state["leagues_for_user_username"] = username_clean
    try:
        current_account = get_current_account()
    except Exception:
        current_account = {}
    last_league_id = onboarding_ui.last_league_option(
        username=username_clean,
        leagues=leagues,
        account=current_account,
        current_league_id=previous_league_id,
        current_username=previous_username,
    )
    st.session_state["last_league_option_id"] = last_league_id
    st.session_state["selected_league_id"] = None
    st.session_state["selected_league_name"] = ""
    st.session_state["_league_selection_established"] = False
    st.session_state.pop("active_league_context", None)
    _clear_league_switch_transient_state(previous_league_id=previous_league_id)
    if len(leagues) == 1:
        only_league = leagues[0]
        set_selected_league(
            _safe_text(only_league.get("league_id")),
            _safe_text(only_league.get("name"), "Unnamed league"),
            route_to_dashboard=True,
        )
    return leagues


def set_selected_league(league_id: str, league_name: str, *, route_to_dashboard: bool = False) -> None:
    previous_league_id = _safe_text(st.session_state.get("selected_league_id")).strip()
    selected_league_id = _safe_text(league_id).strip()
    leagues = st.session_state.get("leagues_for_user", [])
    league_record = next(
        (league for league in leagues if str(league.get("league_id")) == selected_league_id),
        None,
    ) if isinstance(leagues, list) else None
    if previous_league_id and previous_league_id != selected_league_id:
        league_switch_first_useful.begin_switch_guard(
            st.session_state,
            previous_league_id=previous_league_id,
            next_league_id=selected_league_id,
            next_league_name=_safe_text(league_name),
            preserved_route=_safe_text(st.session_state.get("platform_nav_page")),
        )
    st.session_state["selected_league_id"] = selected_league_id or None
    st.session_state["selected_league_name"] = _league_display_name(
        _safe_text(league_name),
        league_record.get("season") if isinstance(league_record, dict) else "",
        league_record=league_record,
    )
    st.session_state["_sync_sidebar_league_select"] = True
    if previous_league_id and previous_league_id != selected_league_id:
        st.session_state.pop("active_league_context", None)
        with league_switch_first_useful.stage_timer("active_league_context_invalidated"):
            _clear_league_switch_transient_state(previous_league_id=previous_league_id)
    # Explicit card/Continue selection (or the single-league shortcut) establishes
    # league ownership for subsequent reruns in this Streamlit session.
    st.session_state["_identity_established"] = True
    st.session_state["_league_selection_established"] = True
    st.session_state.pop("supabase_auto_resume_suppressed", None)
    st.session_state["last_league_option_id"] = selected_league_id
    if selected_league_id and not previous_league_id:
        try:
            from modules import launch_analytics

            launch_analytics.track_event(
                "league_import_completed",
                props=launch_analytics.build_context_props(
                    st.session_state,
                    league_id=selected_league_id,
                    source_surface="league_import",
                    extra={"action": "route_dashboard" if route_to_dashboard else "select"},
                ),
                once_key=selected_league_id,
                state=st.session_state,
            )
            launch_analytics.set_league_scope(st.session_state, selected_league_id)
        except Exception:
            pass
    with league_switch_first_useful.stage_timer("selected_league_persisted"):
        _persist_active_account_context(
            username=_safe_text(st.session_state.get("username")).strip(),
            league_id=selected_league_id,
        )
        active_username = _safe_text(st.session_state.get("username")).strip()
        _persist_supabase_account_context(
            username=active_username,
            league_id=selected_league_id,
            league_name=st.session_state.get("selected_league_name", ""),
            roster_id=(
                get_user_roster_id(selected_league_id, active_username)
                if active_username and selected_league_id
                else None
            ),
        )
    if route_to_dashboard:
        _queue_platform_route(
            "dashboard",
            force_scroll=True,
            source="league_selection",
        )

def _open_mobile_destination_sheet() -> None:
    performance.mark_interaction("open_gm", lightweight=True)
    interaction_latency.mark_interaction_milestone("gm_menu_open")
    st.session_state["_mobile_destination_sheet_open"] = True


def _close_mobile_destination_sheet() -> None:
    performance.mark_interaction("close_gm", lightweight=True)
    st.session_state["_mobile_destination_sheet_open"] = False


def _navigate_from_mobile_destination(page_key: str) -> None:
    performance.mark_interaction("select_destination", lightweight=False)
    st.session_state["_mobile_destination_sheet_open"] = False
    _commit_platform_destination(page_key, source="gm_destination")


def render_mobile_destination_sheet(
    *,
    current_page: str,
    startup_mode: bool = False,
    enabled_experimental: tuple[str, ...] = (),
):
    if not bool(st.session_state.get("_mobile_destination_sheet_open")):
        return

    visibility = _destination_visibility_flags()
    visibility["enabled_experimental"] = enabled_experimental
    all_pages = current_platform_destinations(startup_mode, **visibility)
    if not all_pages:
        return

    button_labels = {
        "rankings": "League Overview",
        "teams": "Teams",
        "weekly_report": "Weekly Report",
        "draft_summary": "Draft Center",
        "startup_draft_center": "Startup Draft Center",
        "news": "News",
        "archetypes": "Archetypes",
        "manager_tendencies": "Manager Tendencies",
        "players": "Players",
        "gm_targets": "GM Targets",
        "trade_analyzer": "Trade Analyzer",
        "live_draft": "Live Draft",
    }

    with st.container():
        st.markdown(
            "<div class='mobile-gm-sheet-marker'></div>"
            "<div class='mobile-gm-destination-panel'>"
            "<div class='mobile-gm-panel-header'>"
            f"<div class='mobile-gm-sheet-kicker'>{escape(brand_identity.PRODUCT_NAME)}</div>"
            "<div class='mobile-gm-sheet-title'>Where to go</div>"
            f"<div class='mobile-gm-current-page'>Current: {escape(_safe_text(button_labels.get(current_page, current_page.replace('_', ' ').title())))}</div>"
            "</div>"
            f"<div class='mobile-gm-sheet-note'>{escape(brand_identity.FOUNDER_BETA_LABEL)} · Core routes first. "
            "Experimental routes are early access when enabled.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.button(
            "Close destinations",
            key="mobile_sheet_close",
            use_container_width=True,
            on_click=_close_mobile_destination_sheet,
        )

        category_labels = (
            ("CORE", "Core"),
            ("SUPPORT", "Support"),
            ("EXPERIMENTAL", brand_identity.experimental_caption("Experimental")),
            ("DEV_ONLY", "Developer"),
        )
        for category, heading in category_labels:
            category_pages = [page for page in all_pages if page.category == category]
            if not category_pages:
                continue
            st.caption(heading)
            if category == "EXPERIMENTAL":
                st.markdown(
                    "<div class='mobile-gm-experimental-note'>"
                    f"{escape(brand_identity.EXPERIMENTAL_NOTE)}. Available when enabled for your account."
                    "</div>",
                    unsafe_allow_html=True,
                )
            for page in category_pages:
                button_label = button_labels.get(page.key, page.label)
                suffix = ""
                if page.category == "EXPERIMENTAL":
                    suffix = f" {brand_identity.EXPERIMENTAL_LABEL}"
                elif page.category == "DEV_ONLY":
                    suffix = " [DEV]"
                command_label = f"{button_label}{suffix}"
                button_type = "primary" if page.key == current_page else "secondary"
                st.button(
                    command_label,
                    key=f"mobile_sheet_nav_{page.key}",
                    use_container_width=True,
                    type=button_type,
                    on_click=_navigate_from_mobile_destination,
                    args=(page.key,),
                )


def render_mobile_navigation_shell(
    *,
    current_page: str,
    current_page_definition,
    destination_definitions,
    startup_mode: bool = False,
):
    with st.container(key=f"mobile_gm_sheet_trigger_{current_page}"):
        render_html_fragment(brand_identity.gm_orb_floating_trigger_html())
        st.button(
            brand_identity.GM_ORB_ARIA_LABEL,
            help=brand_identity.GM_ORB_HELP,
            type="primary",
            key=f"mobile_gm_sheet_open_{current_page}",
            on_click=_open_mobile_destination_sheet,
        )


def safe_pick_value(pick: dict) -> int:
    value = _safe_positive_int(pick.get("score"), 0)
    if value > 0:
        return value
    base_score = _safe_positive_int(pick.get("base_score"), 0)
    if base_score > 0:
        future_discount = max(0.1, _safe_float(pick.get("future_discount"), 1.0))
        team_modifier = max(0.5, _safe_float(pick.get("team_modifier"), 1.0))
        format_multiplier = max(0.3, _safe_float(pick.get("format_multiplier"), 1.0))
        class_strength_multiplier = max(0.5, _safe_float(pick.get("class_strength_multiplier"), 1.0))
        prospect_strength_multiplier = max(0.5, _safe_float(pick.get("prospect_strength_multiplier"), 1.0))
        return int(
            round(
                base_score
                * future_discount
                * team_modifier
                * format_multiplier
                * class_strength_multiplier
                * prospect_strength_multiplier
            )
        )
    round_num = _safe_positive_int(pick.get("round"), 4)
    default_values = {
        1: 6500,
        2: 3200,
        3: 1400,
        4: 650,
    }
    return default_values.get(round_num, max(150, 650 - ((round_num - 4) * 150)))


def build_draft_capital_summary(
    df_summary: pd.DataFrame,
    draft_picks: list[dict],
) -> pd.DataFrame:
    if df_summary.empty:
        return pd.DataFrame()

    capital_rows = df_summary[
        [column for column in ["roster_id", "team_name", "owner_name", "avatar_url", "mode"] if column in df_summary.columns]
    ].copy()
    capital_rows["roster_id_key"] = pd.to_numeric(capital_rows["roster_id"], errors="coerce").astype("Int64")

    totals: dict[int, int] = {}
    pick_counts: dict[int, int] = {}
    first_rounders: dict[int, int] = {}
    second_rounders: dict[int, int] = {}
    third_rounders: dict[int, int] = {}
    yearly_values: dict[tuple[int, int], int] = {}
    seasons: set[int] = set()
    for pick in draft_picks or []:
        owner_id = pd.to_numeric(pd.Series([pick.get("owner_roster_id")]), errors="coerce").iloc[0]
        if pd.isna(owner_id):
            continue
        owner_key = int(owner_id)
        pick_value = safe_pick_value(pick)
        totals[owner_key] = totals.get(owner_key, 0) + pick_value
        pick_counts[owner_key] = pick_counts.get(owner_key, 0) + 1
        round_num = int(pick.get("round") or 0)
        if round_num == 1:
            first_rounders[owner_key] = first_rounders.get(owner_key, 0) + 1
        elif round_num == 2:
            second_rounders[owner_key] = second_rounders.get(owner_key, 0) + 1
        elif round_num == 3:
            third_rounders[owner_key] = third_rounders.get(owner_key, 0) + 1
        season = _safe_positive_int(pick.get("season"), 0)
        if season:
            seasons.add(season)
            yearly_values[(owner_key, season)] = yearly_values.get((owner_key, season), 0) + pick_value

    capital_rows["draft_capital"] = capital_rows["roster_id_key"].map(totals).fillna(0).astype(int)
    capital_rows["pick_count"] = capital_rows["roster_id_key"].map(pick_counts).fillna(0).astype(int)
    capital_rows["first_rounders"] = capital_rows["roster_id_key"].map(first_rounders).fillna(0).astype(int)
    capital_rows["second_rounders"] = capital_rows["roster_id_key"].map(second_rounders).fillna(0).astype(int)
    capital_rows["third_rounders"] = capital_rows["roster_id_key"].map(third_rounders).fillna(0).astype(int)
    for season in sorted(seasons):
        column = f"pick_value_{season}"
        capital_rows[column] = (
            capital_rows["roster_id_key"]
            .map(lambda roster_id: yearly_values.get((int(roster_id), season), 0) if pd.notna(roster_id) else 0)
            .fillna(0)
            .astype(int)
        )
    capital_rows["draft_capital_rank"] = (
        capital_rows["draft_capital"].rank(method="dense", ascending=False).astype(int)
    )
    return capital_rows.sort_values(["draft_capital_rank", "draft_capital", "team_name"], ascending=[True, False, True]).reset_index(drop=True)


def build_league_display_frame(
    df_summary: pd.DataFrame,
    draft_capital_summary: pd.DataFrame,
    include_picks: bool,
) -> pd.DataFrame:
    df_display = df_summary.copy()
    if draft_capital_summary is not None and not draft_capital_summary.empty:
        draft_cols_to_merge = [
            "roster_id",
            "draft_capital",
            "pick_count",
            "first_rounders",
            "second_rounders",
            "third_rounders",
            "draft_capital_rank",
        ]
        draft_cols_to_merge.extend(
            [column for column in draft_capital_summary.columns if column.startswith("pick_value_")]
        )
        draft_cols = draft_capital_summary[draft_cols_to_merge].copy()
        df_display = df_display.merge(draft_cols, on="roster_id", how="left")
    for column in ["draft_capital", "pick_count", "first_rounders", "second_rounders", "third_rounders", "draft_capital_rank"]:
        if column not in df_display.columns:
            df_display[column] = 0
    for column in [column for column in df_display.columns if column.startswith("pick_value_")]:
        df_display[column] = pd.to_numeric(df_display[column], errors="coerce").fillna(0).astype(int)
    df_display["draft_capital"] = pd.to_numeric(df_display["draft_capital"], errors="coerce").fillna(0).astype(int)
    df_display["power_score"] = pd.to_numeric(df_display["total_score"], errors="coerce").fillna(0)
    df_display["power_rank"] = df_display["power_score"].rank(method="dense", ascending=False).astype(int)
    raw_roster_score = pd.to_numeric(df_display.get("raw_roster_score"), errors="coerce").fillna(df_display["power_score"])
    df_display["franchise_score"] = raw_roster_score + df_display["draft_capital"]
    df_display["franchise_rank"] = df_display["franchise_score"].rank(method="dense", ascending=False).astype(int)
    if include_picks:
        df_display["overall_score"] = df_display["franchise_score"]
        df_display["overall_rank"] = df_display["franchise_rank"]
    else:
        df_display["overall_score"] = df_display["power_score"]
        df_display["overall_rank"] = df_display["power_rank"]
    df_display["rank_points"] = len(df_display) - df_display["power_rank"] + 1
    if "strategy_label" in df_display.columns:
        df_display["strategy_display"] = df_display["strategy_label"].fillna("").astype(str)
    else:
        df_display["strategy_display"] = df_display["mode"].apply(lambda value: team_strategy_label(value))
    return df_display.sort_values(["power_rank", "power_score", "team_name"], ascending=[True, False, True]).reset_index(drop=True)


def _enrich_league_display_with_roster_profiles(
    df_display: pd.DataFrame,
    roster_profiles: dict | None,
) -> pd.DataFrame:
    if df_display.empty:
        return df_display

    profiles = roster_profiles if isinstance(roster_profiles, dict) else {}
    enriched = df_display.copy()
    default_avatar_series = enriched.get("avatar_url")
    if not isinstance(default_avatar_series, pd.Series):
        default_avatar_series = pd.Series([""] * len(enriched), index=enriched.index)
    else:
        default_avatar_series = default_avatar_series.reindex(enriched.index, fill_value="")

    enriched["owner_username"] = enriched["roster_id"].astype(str).map(
        lambda rid: _safe_text(profiles.get(str(rid), {}).get("username"))
    )
    enriched["team_name"] = enriched.apply(
        lambda row: _safe_text(
            profiles.get(str(row["roster_id"]), {}).get("team_name"),
            _safe_text(
                row.get("team_name"),
                _safe_text(row.get("owner_username"), row.get("owner_name")),
            ),
        ),
        axis=1,
    )
    enriched["avatar_url"] = enriched["roster_id"].astype(str).map(
        lambda rid: _safe_text(profiles.get(str(rid), {}).get("avatar_url"))
    ).where(
        lambda series: series != "",
        default_avatar_series,
    )
    return enriched


@runtime_trace.traced("ownership_map_construction", phase="roster_normalization")
def _build_roster_player_map(rosters: list[dict] | None) -> dict[str, tuple[str, ...]]:
    roster_player_map: dict[str, tuple[str, ...]] = {}
    for roster in rosters or []:
        roster_id = _safe_text(roster.get("roster_id")).strip()
        if not roster_id:
            continue
        roster_player_map[roster_id] = tuple(
            str(pid)
            for pid in (roster.get("players", []) or [])
            if pid is not None
        )
    return roster_player_map


def draft_year_columns(df: pd.DataFrame) -> list[str]:
    return sorted(
        [column for column in df.columns if str(column).startswith("pick_value_")],
        key=lambda column: int(str(column).replace("pick_value_", "") or 0),
    )


def build_draft_workspace_frame(
    draft_capital_summary: pd.DataFrame,
    df_intel: pd.DataFrame,
    *,
    draft_year: int | None = None,
) -> pd.DataFrame:
    if draft_capital_summary is None or draft_capital_summary.empty:
        return pd.DataFrame()

    current_draft_year = _safe_positive_int(draft_year, datetime.now().year) or datetime.now().year
    summary = draft_capital_summary.copy()
    for column in ["draft_capital", "pick_count", "first_rounders", "second_rounders", "third_rounders", "draft_capital_rank"]:
        if column not in summary.columns:
            summary[column] = 0
        summary[column] = pd.to_numeric(summary.get(column), errors="coerce").fillna(0)

    year_cols = draft_year_columns(summary)
    future_year_cols = [
        column
        for column in year_cols
        if _safe_positive_int(str(column).replace("pick_value_", ""), 0) > current_draft_year
    ]
    summary["future_draft_capital"] = (
        summary[future_year_cols].sum(axis=1)
        if future_year_cols
        else 0
    )
    summary["future_draft_capital_rank"] = (
        pd.to_numeric(summary["future_draft_capital"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )

    if df_intel is not None and not df_intel.empty:
        intel_cols = [
            "roster_id",
            "team_name",
            "owner_name",
            "owner_username",
            "power_rank",
            "franchise_rank",
            "age_rank",
            "avg_age",
            "strategy_display",
            "trading_style",
            "roster_philosophy",
            "asset_behavior",
            "activity_level",
            "manager_tendencies_summary",
            "manager_trade_implication",
        ]
        available_cols = [column for column in intel_cols if column in df_intel.columns]
        intel_frame = df_intel[available_cols].copy()
        rename_map = {}
        for column in [column for column in available_cols if column != "roster_id" and column in summary.columns]:
            rename_map[column] = f"intel_{column}"
        if rename_map:
            intel_frame = intel_frame.rename(columns=rename_map)
        summary = summary.merge(intel_frame, on="roster_id", how="left")
        for base_column in ["team_name", "owner_name"]:
            intel_column = f"intel_{base_column}"
            if intel_column in summary.columns:
                summary[base_column] = summary[intel_column].where(
                    summary[intel_column].fillna("").astype(str).str.strip() != "",
                    summary.get(base_column),
                )

    numeric_defaults = {
        "draft_capital_rank": len(summary),
        "future_draft_capital_rank": len(summary),
        "power_rank": len(summary),
        "franchise_rank": len(summary),
        "age_rank": len(summary),
        "avg_age": 0.0,
        "future_draft_capital": 0.0,
    }
    for column, default in numeric_defaults.items():
        if column not in summary.columns:
            summary[column] = default
        summary[column] = pd.to_numeric(summary.get(column), errors="coerce").fillna(default)

    if "strategy_display" not in summary.columns:
        summary["strategy_display"] = ""
    if "mode" not in summary.columns:
        summary["mode"] = ""
    summary["strategy_display"] = summary.apply(
        lambda row: _safe_text(row.get("strategy_display")) or team_strategy_label(row.get("mode")),
        axis=1,
    )

    for column, default in [
        ("trading_style", "Unknown"),
        ("roster_philosophy", "Balanced"),
        ("asset_behavior", "Balanced Asset Manager"),
        ("activity_level", "Average Activity"),
        ("manager_tendencies_summary", ""),
        ("manager_trade_implication", ""),
    ]:
        if column not in summary.columns:
            summary[column] = default
        summary[column] = summary[column].fillna(default).astype(str)

    summary["strategy_key"] = summary.apply(
        lambda row: normalize_team_strategy(row.get("strategy") or row.get("mode")),
        axis=1,
    )
    return summary.sort_values(["draft_capital_rank", "draft_capital", "team_name"], ascending=[True, False, True]).reset_index(drop=True)


_draft_rank_cutoffs = draft_center_ui._draft_rank_cutoffs
_draft_posture_profile = draft_center_ui._draft_posture_profile
_draft_workspace_team_lines = draft_center_ui._draft_workspace_team_lines
render_your_draft_posture = draft_center_ui.render_your_draft_posture
build_draft_decision_cards = draft_center_ui.build_draft_decision_cards
build_draft_partner_cards = draft_center_ui.build_draft_partner_cards


def render_draft_summary_section(
    draft_context: dict,
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
):
    return draft_center_ui.render_draft_summary_section(
        draft_context,
        draft_capital_summary,
        draft_picks,
        draft_year_columns=draft_year_columns,
    )


def render_draft_capital_dashboard(
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
):
    return draft_center_ui.render_draft_capital_dashboard(
        draft_capital_summary,
        draft_picks,
        draft_year_columns=draft_year_columns,
        render_draft_team_cards=render_draft_team_cards,
        team_tap_markup=_team_tap_markup,
        render_team_card_tap_grid=_render_team_card_tap_grid,
        open_league_team_from_tap=_open_league_team_from_tap,
        team_logo_html=team_logo_html,
    )


def render_team_pick_expanders(
    draft_capital_summary: pd.DataFrame,
    draft_picks: list[dict],
):
    return draft_center_ui.render_team_pick_expanders(
        draft_capital_summary,
        draft_picks,
        safe_pick_value=safe_pick_value,
    )

def add_league_detail_ranks(df_display: pd.DataFrame) -> pd.DataFrame:
    if df_display.empty:
        return df_display
    ranked = df_display.copy()
    ranked["roster_value_rank"] = (
        pd.to_numeric(ranked["raw_roster_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["current_roster_rank"] = (
        pd.to_numeric(ranked.get("current_roster_score"), errors="coerce")
        .fillna(pd.to_numeric(ranked["starter_score"], errors="coerce").fillna(0) + pd.to_numeric(ranked["bench_score"], errors="coerce").fillna(0))
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["starter_rank"] = (
        pd.to_numeric(ranked["starter_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["bench_rank"] = (
        pd.to_numeric(ranked["bench_score"], errors="coerce")
        .fillna(0)
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    ranked["age_rank"] = (
        pd.to_numeric(ranked["avg_age"], errors="coerce")
        .fillna(999)
        .rank(method="dense", ascending=True)
        .astype(int)
    )
    return ranked


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_trade_activity_summary(league_id: str) -> pd.DataFrame:
    if not league_id:
        return pd.DataFrame(columns=["roster_id", "trade_count", "trade_asset_total"])

    league = get_league(league_id)
    _, _, last_round = _league_history_window(league)

    trade_counts: dict[int, int] = {}
    trade_assets: dict[int, int] = {}

    for round_num in range(1, last_round + 1):
        for transaction in get_transactions(league_id, round_num) or []:
            tx_type = _safe_text(transaction.get("type")).strip().lower()
            tx_status = _safe_text(transaction.get("status")).strip().lower()
            if tx_type != "trade" or tx_status not in {"complete", "accepted", "processed"}:
                continue

            roster_ids = []
            for roster_id in transaction.get("roster_ids", []) or []:
                try:
                    roster_ids.append(int(roster_id))
                except Exception:
                    continue
            roster_ids = sorted(set(roster_ids))
            if not roster_ids:
                continue

            adds = transaction.get("adds") if isinstance(transaction.get("adds"), dict) else {}
            drops = transaction.get("drops") if isinstance(transaction.get("drops"), dict) else {}
            draft_picks = transaction.get("draft_picks") if isinstance(transaction.get("draft_picks"), list) else []
            asset_total = len(adds) + len(drops) + len(draft_picks)
            if asset_total <= 0:
                asset_total = max(1, len(roster_ids))

            for roster_id in roster_ids:
                trade_counts[roster_id] = trade_counts.get(roster_id, 0) + 1
                trade_assets[roster_id] = trade_assets.get(roster_id, 0) + asset_total

    rows = [
        {
            "roster_id": roster_id,
            "trade_count": trade_counts.get(roster_id, 0),
            "trade_asset_total": trade_assets.get(roster_id, 0),
        }
        for roster_id in sorted(set(trade_counts) | set(trade_assets))
    ]
    return pd.DataFrame(rows, columns=["roster_id", "trade_count", "trade_asset_total"])


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_manager_behavior_summary(league_id: str) -> pd.DataFrame:
    columns = [
        "roster_id",
        "transaction_count",
        "waiver_moves",
        "trade_count",
        "trade_asset_total",
        "trade_asset_avg",
        "roster_churn",
        "picks_acquired",
        "picks_sent",
        "firsts_acquired",
        "firsts_sent",
    ]
    if not league_id:
        return pd.DataFrame(columns=columns)

    league = get_league(league_id)
    _, _, last_round = _league_history_window(league)
    buckets: dict[int, dict] = {}

    def ensure_bucket(roster_id: int) -> dict:
        roster_id = _safe_positive_int(roster_id, 0)
        if roster_id <= 0:
            return {}
        if roster_id not in buckets:
            buckets[roster_id] = {
                "roster_id": roster_id,
                "transaction_count": 0,
                "waiver_moves": 0,
                "trade_count": 0,
                "trade_asset_total": 0,
                "roster_churn": 0,
                "picks_acquired": 0,
                "picks_sent": 0,
                "firsts_acquired": 0,
                "firsts_sent": 0,
            }
        return buckets[roster_id]

    for round_num in range(1, last_round + 1):
        for transaction in get_transactions(league_id, round_num) or []:
            tx_type = _safe_text(transaction.get("type")).strip().lower()
            tx_status = _safe_text(transaction.get("status")).strip().lower()
            if tx_status not in {"complete", "accepted", "processed"}:
                continue

            roster_ids = set()
            for roster_id in transaction.get("roster_ids", []) or []:
                roster_value = _safe_positive_int(roster_id, 0)
                if roster_value > 0:
                    roster_ids.add(roster_value)

            adds = transaction.get("adds") if isinstance(transaction.get("adds"), dict) else {}
            drops = transaction.get("drops") if isinstance(transaction.get("drops"), dict) else {}
            draft_picks = transaction.get("draft_picks") if isinstance(transaction.get("draft_picks"), list) else []

            for roster_id in list(adds.values()) + list(drops.values()):
                roster_value = _safe_positive_int(roster_id, 0)
                if roster_value > 0:
                    roster_ids.add(roster_value)

            add_drop_count = len(adds) + len(drops)
            asset_total = add_drop_count + len(draft_picks)
            if tx_type == "trade" and asset_total <= 0:
                asset_total = max(1, len(roster_ids))

            for roster_id in sorted(roster_ids):
                bucket = ensure_bucket(roster_id)
                if not bucket:
                    continue
                bucket["transaction_count"] += 1
                if tx_type == "trade":
                    bucket["trade_count"] += 1
                    bucket["trade_asset_total"] += asset_total
                elif tx_type in {"waiver", "free_agent"}:
                    bucket["waiver_moves"] += 1
                    bucket["roster_churn"] += add_drop_count
                else:
                    bucket["roster_churn"] += add_drop_count

            for pick in draft_picks:
                new_owner = _safe_positive_int(
                    pick.get("owner_id") or pick.get("roster_id") or pick.get("new_owner_id"),
                    0,
                )
                previous_owner = _safe_positive_int(
                    pick.get("previous_owner_id") or pick.get("old_owner_id"),
                    0,
                )
                round_value = _safe_positive_int(pick.get("round"), 0)
                if new_owner > 0:
                    bucket = ensure_bucket(new_owner)
                    if bucket:
                        bucket["picks_acquired"] += 1
                        if round_value == 1:
                            bucket["firsts_acquired"] += 1
                if previous_owner > 0:
                    bucket = ensure_bucket(previous_owner)
                    if bucket:
                        bucket["picks_sent"] += 1
                        if round_value == 1:
                            bucket["firsts_sent"] += 1

    rows = []
    for roster_id, bucket in buckets.items():
        trade_count = int(bucket.get("trade_count") or 0)
        trade_asset_total = int(bucket.get("trade_asset_total") or 0)
        row = dict(bucket)
        row["trade_asset_avg"] = (trade_asset_total / trade_count) if trade_count > 0 else 0.0
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def _classify_manager_tendencies(enriched: pd.DataFrame) -> pd.DataFrame:
    if enriched.empty:
        return enriched

    df = enriched.copy()
    league_size = max(len(df), 1)
    top_cut = max(2, int(round(league_size * 0.33)))
    bottom_cut = max(top_cut + 1, int(round(league_size * 0.67)))

    transaction_series = pd.to_numeric(df.get("transaction_count", 0), errors="coerce").fillna(0)
    trade_series = pd.to_numeric(df.get("trade_count", 0), errors="coerce").fillna(0)
    waiver_series = pd.to_numeric(df.get("waiver_moves", 0), errors="coerce").fillna(0)
    churn_series = pd.to_numeric(df.get("roster_churn", 0), errors="coerce").fillna(0)
    trade_avg_series = pd.to_numeric(df.get("trade_asset_avg", 0), errors="coerce").fillna(0.0)
    tx_high = float(transaction_series.quantile(0.75)) if len(transaction_series) > 1 else float(transaction_series.max() or 0)
    tx_low = float(transaction_series.quantile(0.25)) if len(transaction_series) > 1 else float(transaction_series.min() or 0)
    trade_high = float(trade_series.quantile(0.75)) if len(trade_series) > 1 else float(trade_series.max() or 0)
    trade_avg_high = float(trade_avg_series.quantile(0.75)) if len(trade_avg_series) > 1 else float(trade_avg_series.max() or 0)
    churn_high = float(churn_series.quantile(0.75)) if len(churn_series) > 1 else float(churn_series.max() or 0)

    def classify_row(row: pd.Series) -> pd.Series:
        trade_count = _safe_positive_int(row.get("trade_count"), 0)
        trade_asset_total = _safe_positive_int(row.get("trade_asset_total"), 0)
        trade_asset_avg = _safe_float(row.get("trade_asset_avg"), 0.0)
        transaction_count = _safe_positive_int(row.get("transaction_count"), 0)
        waiver_moves = _safe_positive_int(row.get("waiver_moves"), 0)
        roster_churn = _safe_positive_int(row.get("roster_churn"), 0)
        picks_acquired = _safe_positive_int(row.get("picks_acquired"), 0)
        picks_sent = _safe_positive_int(row.get("picks_sent"), 0)
        firsts_acquired = _safe_positive_int(row.get("firsts_acquired"), 0)
        firsts_sent = _safe_positive_int(row.get("firsts_sent"), 0)
        power_rank = _safe_positive_int(row.get("power_rank"), league_size)
        franchise_rank = _safe_positive_int(row.get("franchise_rank"), league_size)
        draft_rank = _safe_positive_int(row.get("draft_capital_rank"), league_size)
        age_rank = _safe_positive_int(row.get("age_rank"), league_size)
        bench_rank = _safe_positive_int(row.get("bench_rank"), league_size)
        strategy = normalize_team_strategy(row.get("strategy") or row.get("mode"))

        if trade_count >= max(4, int(round(trade_high))) and trade_asset_avg >= max(5.0, trade_avg_high):
            trading_style = "Deal Maker"
        elif trade_count >= max(3, int(round(trade_high))):
            trading_style = "Aggressive Trader"
        elif trade_count <= 1:
            trading_style = "Passive Trader"
        else:
            trading_style = "Negotiator"

        if strategy in {"contender", "fringe_contender"} and (age_rank >= bottom_cut or (power_rank + 1 < franchise_rank and draft_rank >= bottom_cut)):
            roster_philosophy = "Win-Now"
        elif age_rank <= top_cut and strategy in {"rebuild", "tank", "retool", "fringe_contender"}:
            roster_philosophy = "Youth Builder"
        elif age_rank >= bottom_cut and draft_rank >= bottom_cut:
            roster_philosophy = "Veteran Collector"
        else:
            roster_philosophy = "Balanced"

        if firsts_acquired - firsts_sent >= 1 or (draft_rank <= top_cut and strategy in {"rebuild", "tank"}):
            asset_behavior = "Pick Hoarder"
        elif firsts_sent > firsts_acquired or (draft_rank >= bottom_cut and strategy in {"contender", "fringe_contender"}):
            asset_behavior = "Pick Seller"
        elif age_rank <= top_cut and draft_rank <= top_cut and strategy in {"rebuild", "tank", "retool"}:
            asset_behavior = "Prospect Chaser"
        elif trade_count >= max(3, int(round(trade_high))) and bench_rank <= top_cut and draft_rank >= top_cut:
            asset_behavior = "Consolidator"
        else:
            asset_behavior = "Balanced Asset Manager"

        if transaction_count >= max(6, int(round(tx_high))) or roster_churn >= max(12, int(round(churn_high))):
            activity_level = "Highly Active"
        elif transaction_count <= max(1, int(round(tx_low))) and waiver_moves <= 1 and trade_count <= 1:
            activity_level = "Quiet Manager"
        else:
            activity_level = "Average Activity"

        evidence = [
            f"{trade_count} completed trades | {trade_asset_total} tracked trade assets",
            f"{transaction_count} total moves | {waiver_moves} waivers | {roster_churn} churn",
            f"Power {_format_rank(power_rank)} | Franchise {_format_rank(franchise_rank)} | Draft {_format_rank(draft_rank)} | Age {_format_rank(age_rank)}",
        ]
        if firsts_acquired or firsts_sent:
            evidence.append(f"{firsts_acquired} future 1sts acquired | {firsts_sent} future 1sts sent")
        elif picks_acquired or picks_sent:
            evidence.append(f"{picks_acquired} picks acquired | {picks_sent} picks sent in tracked deals")

        implication_parts = []
        if trading_style == "Passive Trader":
            implication_parts.append("Keep offers simple and direct.")
        elif trading_style == "Aggressive Trader":
            implication_parts.append("Multi-piece offers should get engagement.")
        elif trading_style == "Deal Maker":
            implication_parts.append("Larger packages and clear win conditions are more likely to land.")
        else:
            implication_parts.append("Expect counteroffers and iterative negotiation.")

        if roster_philosophy == "Youth Builder":
            implication_parts.append("Younger return pieces and future picks will land better than veteran-only offers.")
        elif roster_philosophy == "Win-Now":
            implication_parts.append("Immediate starter points should matter more than long-range flexibility.")
        elif roster_philosophy == "Veteran Collector":
            implication_parts.append("Productive veterans can move this manager more than speculative upside.")

        if asset_behavior == "Pick Hoarder":
            implication_parts.append("Future 1sts and pick insulation carry extra weight.")
        elif asset_behavior == "Pick Seller":
            implication_parts.append("Pick-heavy offers need a clear current-roster payoff.")
        elif asset_behavior == "Prospect Chaser":
            implication_parts.append("Rookies, youthful depth, and future shots are real leverage.")
        elif asset_behavior == "Consolidator":
            implication_parts.append("Two-for-one upgrades are a better fit than pure depth swaps.")

        return pd.Series(
            {
                "trading_style": trading_style,
                "roster_philosophy": roster_philosophy,
                "asset_behavior": asset_behavior,
                "activity_level": activity_level,
                "manager_tendencies_summary": " | ".join([trading_style, roster_philosophy, asset_behavior, activity_level]),
                "manager_evidence": evidence[:4],
                "manager_evidence_text": " | ".join(evidence[:2]),
                "manager_trade_implication": " ".join(implication_parts[:3]),
            }
        )

    tendency_df = df.apply(classify_row, axis=1)
    for column in tendency_df.columns:
        df[column] = tendency_df[column]
    return df


def _league_history_window(league: dict) -> tuple[int, int, int]:
    settings = league.get("settings", {}) if isinstance(league.get("settings"), dict) else {}
    current_leg = _safe_positive_int(settings.get("leg"), 0)
    playoff_week_start = _safe_positive_int(settings.get("playoff_week_start"), 15)
    regular_season_end = max(1, playoff_week_start - 1) if playoff_week_start > 1 else max(1, current_leg)
    # Sleeper has no useful transaction or matchup data for future weeks.
    # Offseason leagues use round 1; active leagues stop at the current leg.
    max_history_week = max(1, min(18, current_leg if current_leg > 0 else 1))
    return current_leg, regular_season_end, max_history_week


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_matchup_history_frame(league_id: str) -> pd.DataFrame:
    if not league_id:
        return pd.DataFrame(columns=["week", "roster_id", "matchup_id", "points"])

    league = get_league(league_id)
    _, _, max_history_week = _league_history_window(league)
    rows: list[dict] = []
    for week in range(1, max_history_week + 1):
        for matchup in get_matchups(league_id, week) or []:
            roster_id = _safe_positive_int(matchup.get("roster_id"), 0)
            if roster_id <= 0:
                continue
            rows.append(
                {
                    "week": week,
                    "roster_id": roster_id,
                    "matchup_id": _safe_positive_int(matchup.get("matchup_id"), 0),
                    "points": _safe_float(
                        matchup.get("points"),
                        _safe_float(matchup.get("custom_points"), 0.0),
                    ),
                }
            )
    return pd.DataFrame(rows, columns=["week", "roster_id", "matchup_id", "points"])


def _player_transaction_detail(player_lookup: dict[str, dict], player_id: str, score_field: str) -> dict:
    key = str(player_id or "")
    player = player_lookup.get(key, {})
    return {
        "player_id": key,
        "name": _safe_text(player.get("name"), f"Player {key}"),
        "position": _safe_text(player.get("position")),
        "tier": _safe_text(player.get("player_tier"), "Developmental"),
        "score": _safe_float(player.get(score_field, player.get("value_score", 0)), 0.0),
    }


def _transaction_pick_label(pick: dict) -> str:
    season = _safe_text(pick.get("season"))
    round_num = _safe_text(pick.get("round"))
    owner_id = _safe_text(pick.get("owner_id"))
    owner_text = f"Team {owner_id} " if owner_id else ""
    if season and round_num:
        return f"{owner_text}{season} R{round_num}".strip()
    if season:
        return f"{owner_text}{season} pick".strip()
    if round_num:
        return f"{owner_text}Round {round_num} pick".strip()
    return "Future pick"


def _load_weekly_rank_snapshots() -> dict:
    if not os.path.exists(WEEKLY_RANK_SNAPSHOT_PATH):
        return {}
    try:
        with open(WEEKLY_RANK_SNAPSHOT_PATH, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_weekly_rank_snapshots(data: dict):
    try:
        os.makedirs(os.path.dirname(WEEKLY_RANK_SNAPSHOT_PATH), exist_ok=True)
        with open(WEEKLY_RANK_SNAPSHOT_PATH, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=True, indent=2)
    except Exception:
        return


def build_weekly_rank_movement(
    snapshot_rows: list[dict],
    league_id: str,
    report_week: int,
) -> dict:
    if not snapshot_rows or not league_id or report_week <= 0:
        return {
            "available": False,
            "note": "Power and Franchise rank movement will appear once the report has at least one saved prior-week snapshot.",
            "previous_week": None,
            "rows": [],
        }

    snapshots = _load_weekly_rank_snapshots()
    league_key = str(league_id)
    league_snapshots = snapshots.get(league_key, {}) if isinstance(snapshots.get(league_key), dict) else {}
    previous_week = None
    for week_key in league_snapshots.keys():
        try:
            week_value = int(week_key)
        except Exception:
            continue
        if week_value < report_week and (previous_week is None or week_value > previous_week):
            previous_week = week_value

    current_snapshot = {
        str(_safe_positive_int(row.get("roster_id"), 0)): {
            "team_name": _safe_text(row.get("team_name")),
            "power_rank": _safe_positive_int(row.get("power_rank"), 0),
            "franchise_rank": _safe_positive_int(row.get("franchise_rank"), 0),
        }
        for row in snapshot_rows
        if _safe_positive_int(row.get("roster_id"), 0) > 0
    }

    rows: list[dict] = []
    if previous_week is not None:
        previous_snapshot = league_snapshots.get(str(previous_week), {})
        if isinstance(previous_snapshot, dict):
            for roster_key, current in current_snapshot.items():
                previous = previous_snapshot.get(roster_key, {})
                if not isinstance(previous, dict):
                    continue
                power_before = _safe_positive_int(previous.get("power_rank"), 0)
                franchise_before = _safe_positive_int(previous.get("franchise_rank"), 0)
                power_after = _safe_positive_int(current.get("power_rank"), 0)
                franchise_after = _safe_positive_int(current.get("franchise_rank"), 0)
                if power_before <= 0 or franchise_before <= 0 or power_after <= 0 or franchise_after <= 0:
                    continue
                rows.append(
                    {
                        "roster_id": _safe_positive_int(roster_key, 0),
                        "team_name": _safe_text(current.get("team_name"), _safe_text(previous.get("team_name"))),
                        "power_delta": power_before - power_after,
                        "franchise_delta": franchise_before - franchise_after,
                        "power_before": power_before,
                        "power_after": power_after,
                        "franchise_before": franchise_before,
                        "franchise_after": franchise_after,
                    }
                )

    league_snapshots[str(report_week)] = current_snapshot
    snapshots[league_key] = league_snapshots
    _write_weekly_rank_snapshots(snapshots)

    if not rows:
        return {
            "available": False,
            "note": "Power and Franchise rank movement will appear once the report has at least one saved prior-week snapshot.",
            "previous_week": previous_week,
            "rows": [],
        }

    movement_df = pd.DataFrame(rows)
    power_riser = movement_df.sort_values(["power_delta", "team_name"], ascending=[False, True]).iloc[0]
    power_faller = movement_df.sort_values(["power_delta", "team_name"], ascending=[True, True]).iloc[0]
    franchise_riser = movement_df.sort_values(["franchise_delta", "team_name"], ascending=[False, True]).iloc[0]
    franchise_faller = movement_df.sort_values(["franchise_delta", "team_name"], ascending=[True, True]).iloc[0]
    return {
        "available": True,
        "note": f"Changes are measured against the last saved weekly snapshot from Week {previous_week}.",
        "previous_week": previous_week,
        "rows": movement_df.sort_values(["power_delta", "franchise_delta", "team_name"], ascending=[False, False, True]).to_dict("records"),
        "power_riser": power_riser.to_dict(),
        "power_faller": power_faller.to_dict(),
        "franchise_riser": franchise_riser.to_dict(),
        "franchise_faller": franchise_faller.to_dict(),
    }


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_weekly_league_report(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
) -> dict:
    empty_report = {
        "available": False,
        "message": "No weekly league data is available yet.",
        "report_week": 0,
        "report_label": "",
        "snapshot_rows": [],
        "highlights": [],
        "trend_cards": [],
        "activity_tiles": [],
        "trade_cards": [],
        "waiver_cards": [],
        "move_cards": [],
        "team_note_cards": [],
    }
    if not league_id:
        return empty_report

    df_summary = cached_team_direction_summary(
        df_players,
        league_id,
        score_field=score_field,
        lineup_settings=lineup_settings,
    )
    if df_summary.empty:
        return empty_report

    draft_picks = cached_draft_pick_assets(
        league_id,
        df_summary,
        league_settings_items=draft_pick_valuation_settings_items(lineup_settings),
    )
    draft_capital_summary = build_draft_capital_summary(df_summary, draft_picks)
    df_display = build_league_display_frame(df_summary, draft_capital_summary, include_picks=True)
    roster_profiles = get_league_roster_profiles(league_id)
    df_display["owner_username"] = df_display["roster_id"].astype(str).map(
        lambda rid: _safe_text(roster_profiles.get(str(rid), {}).get("username"))
    )
    df_display["team_name"] = df_display.apply(
        lambda row: _safe_text(
            roster_profiles.get(str(row["roster_id"]), {}).get("team_name"),
            _safe_text(row.get("team_name"), _safe_text(row.get("owner_username"), row.get("owner_name"))),
        ),
        axis=1,
    )
    df_display["avatar_url"] = df_display["roster_id"].astype(str).map(
        lambda rid: _safe_text(roster_profiles.get(str(rid), {}).get("avatar_url"))
    ).where(
        lambda s: s != "",
        df_display.get("avatar_url", pd.Series([""] * len(df_display))),
    )
    df_display = add_league_detail_ranks(df_display)
    df_intel = cached_league_intelligence_frame(
        df_players,
        league_id,
        df_display,
        score_field,
        lineup_settings,
    )
    if df_intel.empty:
        return empty_report

    team_lookup = {
        _safe_positive_int(row.get("roster_id"), 0): row.to_dict()
        for _, row in df_intel.iterrows()
        if _safe_positive_int(row.get("roster_id"), 0) > 0
    }

    matchup_history = cached_matchup_history_frame(league_id)
    report_week = 0
    if not matchup_history.empty:
        weekly_counts = (
            matchup_history.groupby("week")["roster_id"]
            .count()
            .reset_index()
            .sort_values(["week"], ascending=[False])
        )
        for _, week_row in weekly_counts.iterrows():
            week_value = _safe_positive_int(week_row.get("week"), 0)
            if week_value > 0 and _safe_positive_int(week_row.get("roster_id"), 0) >= 2:
                report_week = week_value
                break
    report_label = f"Week {report_week}" if report_week > 0 else "No completed week yet"

    weekly_rows = pd.DataFrame(columns=["week", "roster_id", "matchup_id", "points"])
    if report_week > 0:
        weekly_rows = matchup_history[matchup_history["week"] == report_week].copy()
        weekly_rows["weekly_rank"] = (
            pd.to_numeric(weekly_rows["points"], errors="coerce")
            .fillna(0)
            .rank(method="dense", ascending=False)
            .astype(int)
        )

    paired_matchups: list[dict] = []
    season_results: dict[int, list[dict]] = {}
    if not matchup_history.empty:
        for week_value, week_frame in matchup_history.groupby("week"):
            for matchup_id, matchup_frame in week_frame.groupby("matchup_id"):
                if _safe_positive_int(matchup_id, 0) <= 0 or len(matchup_frame) < 2:
                    continue
                ordered = matchup_frame.sort_values(["points", "roster_id"], ascending=[False, True]).head(2).reset_index(drop=True)
                team_a = ordered.iloc[0]
                team_b = ordered.iloc[1]
                score_a = _safe_float(team_a.get("points"), 0.0)
                score_b = _safe_float(team_b.get("points"), 0.0)
                roster_a = _safe_positive_int(team_a.get("roster_id"), 0)
                roster_b = _safe_positive_int(team_b.get("roster_id"), 0)
                if roster_a <= 0 or roster_b <= 0:
                    continue
                if score_a > score_b:
                    result_a, result_b = "W", "L"
                elif score_b > score_a:
                    result_a, result_b = "L", "W"
                else:
                    result_a = result_b = "T"
                season_results.setdefault(roster_a, []).append({"week": int(week_value), "result": result_a, "points": score_a, "points_against": score_b})
                season_results.setdefault(roster_b, []).append({"week": int(week_value), "result": result_b, "points": score_b, "points_against": score_a})
                if int(week_value) == report_week:
                    winner = team_a if score_a >= score_b else team_b
                    loser = team_b if score_a >= score_b else team_a
                    paired_matchups.append(
                        {
                            "matchup_id": _safe_positive_int(matchup_id, 0),
                            "winner_roster_id": _safe_positive_int(winner.get("roster_id"), 0),
                            "loser_roster_id": _safe_positive_int(loser.get("roster_id"), 0),
                            "winner_points": max(score_a, score_b),
                            "loser_points": min(score_a, score_b),
                            "margin": abs(score_a - score_b),
                        }
                    )

    streak_rows: list[dict] = []
    for roster_id, team_row in team_lookup.items():
        results = sorted(season_results.get(roster_id, []), key=lambda item: int(item.get("week") or 0))
        wins_last_three = sum(1 for item in results[-3:] if item.get("result") == "W")
        losses_last_three = sum(1 for item in results[-3:] if item.get("result") == "L")
        streak = 0
        if results:
            last_result = _safe_text(results[-1].get("result"))
            if last_result in {"W", "L"}:
                streak = 1 if last_result == "W" else -1
                for result_item in reversed(results[:-1]):
                    if _safe_text(result_item.get("result")) != last_result:
                        break
                    streak += 1 if last_result == "W" else -1
        streak_rows.append(
            {
                "roster_id": roster_id,
                "current_streak": streak,
                "wins_last_three": wins_last_three,
                "losses_last_three": losses_last_three,
            }
        )
    streak_df = pd.DataFrame(streak_rows)
    if not streak_df.empty:
        df_intel = df_intel.merge(streak_df, on="roster_id", how="left")
    for column in ["current_streak", "wins_last_three", "losses_last_three"]:
        if column not in df_intel.columns:
            df_intel[column] = 0
        df_intel[column] = pd.to_numeric(df_intel[column], errors="coerce").fillna(0).astype(int)

    highlights: list[dict] = []
    if not weekly_rows.empty:
        highest = weekly_rows.sort_values(["points", "roster_id"], ascending=[False, True]).iloc[0]
        lowest = weekly_rows.sort_values(["points", "roster_id"], ascending=[True, True]).iloc[0]
        highest_team = team_lookup.get(_safe_positive_int(highest.get("roster_id"), 0), {})
        lowest_team = team_lookup.get(_safe_positive_int(lowest.get("roster_id"), 0), {})

        highlights.extend(
            [
                {
                    "label": "Highest Score",
                    "value": _safe_text(highest_team.get("team_name"), "Team"),
                    "note": _format_score(highest.get("points")),
                    "tone": "strength",
                },
                {
                    "label": "Lowest Score",
                    "value": _safe_text(lowest_team.get("team_name"), "Team"),
                    "note": _format_score(lowest.get("points")),
                    "tone": "risk",
                },
            ]
        )

        if paired_matchups:
            closest = min(paired_matchups, key=lambda item: (item.get("margin", 0), item.get("matchup_id", 0)))
            blowout = max(paired_matchups, key=lambda item: (item.get("margin", 0), -item.get("matchup_id", 0)))
            closest_winner = team_lookup.get(int(closest["winner_roster_id"]), {})
            closest_loser = team_lookup.get(int(closest["loser_roster_id"]), {})
            blowout_winner = team_lookup.get(int(blowout["winner_roster_id"]), {})
            blowout_loser = team_lookup.get(int(blowout["loser_roster_id"]), {})
            highlights.extend(
                [
                    {
                        "label": "Closest Matchup",
                        "value": f"{_safe_text(closest_winner.get('team_name'))} over {_safe_text(closest_loser.get('team_name'))}",
                        "note": f"{_format_score(closest['winner_points'])}-{_format_score(closest['loser_points'])} | {closest['margin']:.2f} pts",
                    },
                    {
                        "label": "Largest Blowout",
                        "value": f"{_safe_text(blowout_winner.get('team_name'))} over {_safe_text(blowout_loser.get('team_name'))}",
                        "note": f"{blowout['margin']:.2f} point margin",
                        "tone": "opportunity",
                    },
                ]
            )

            upset_candidates = []
            for matchup in paired_matchups:
                winner_row = team_lookup.get(int(matchup["winner_roster_id"]), {})
                loser_row = team_lookup.get(int(matchup["loser_roster_id"]), {})
                winner_power = _safe_positive_int(winner_row.get("power_rank"), 99)
                loser_power = _safe_positive_int(loser_row.get("power_rank"), 99)
                if winner_power > loser_power:
                    upset_candidates.append(
                        {
                            "winner_team": _safe_text(winner_row.get("team_name")),
                            "loser_team": _safe_text(loser_row.get("team_name")),
                            "gap": winner_power - loser_power,
                            "margin": matchup["margin"],
                            "winner_points": matchup["winner_points"],
                            "loser_points": matchup["loser_points"],
                        }
                    )
            if upset_candidates:
                biggest_upset = max(upset_candidates, key=lambda item: (item["gap"], item["margin"]))
                highlights.append(
                    {
                        "label": "Biggest Upset",
                        "value": f"{biggest_upset['winner_team']} over {biggest_upset['loser_team']}",
                        "note": f"Beat a team ranked {biggest_upset['gap']} spots higher in Power Rank",
                        "tone": "power",
                    }
                )

        team_of_week = weekly_rows.sort_values(["points", "weekly_rank", "roster_id"], ascending=[False, True, True]).iloc[0]
        team_of_week_row = team_lookup.get(_safe_positive_int(team_of_week.get("roster_id"), 0), {})
        disappointment_frame = weekly_rows.copy()
        disappointment_frame["power_rank"] = disappointment_frame["roster_id"].map(
            lambda rid: _safe_positive_int(team_lookup.get(_safe_positive_int(rid, 0), {}).get("power_rank"), len(team_lookup) or 12)
        )
        disappointment_frame["weekly_rank"] = pd.to_numeric(disappointment_frame["weekly_rank"], errors="coerce").fillna(len(disappointment_frame)).astype(int)
        disappointment_frame["disappointment_score"] = (len(team_lookup) - disappointment_frame["power_rank"] + 1) - (len(disappointment_frame) - disappointment_frame["weekly_rank"] + 1)
        disappointment = disappointment_frame.sort_values(
            ["disappointment_score", "points", "power_rank"],
            ascending=[False, True, True],
        ).iloc[0]
        disappointment_row = team_lookup.get(_safe_positive_int(disappointment.get("roster_id"), 0), {})
        highlights.extend(
            [
                {
                    "label": "Team of the Week",
                    "value": _safe_text(team_of_week_row.get("team_name"), "Team"),
                    "note": f"{_format_score(team_of_week.get('points'))} points | Power {_format_rank(team_of_week_row.get('power_rank'))}",
                    "tone": "strength",
                },
                {
                    "label": "Disappointment",
                    "value": _safe_text(disappointment_row.get("team_name"), "Team"),
                    "note": f"{_format_score(disappointment.get('points'))} points after entering at Power {_format_rank(disappointment_row.get('power_rank'))}",
                    "tone": "risk",
                },
            ]
        )

    positive_streaks = df_intel[df_intel["current_streak"] > 0].sort_values(
        ["current_streak", "wins_last_three", "power_rank", "team_name"],
        ascending=[False, False, True, True],
    )
    negative_streaks = df_intel[df_intel["current_streak"] < 0].sort_values(
        ["current_streak", "losses_last_three", "power_rank", "team_name"],
        ascending=[True, False, True, True],
    )
    hottest = positive_streaks.iloc[0] if not positive_streaks.empty else None
    coldest = negative_streaks.iloc[0] if not negative_streaks.empty else None
    win_streak_items = [
        f"{_safe_text(row.get('team_name'))}: {int(row.get('current_streak') or 0)} straight wins"
        for _, row in positive_streaks.head(4).iterrows()
    ]
    loss_streak_items = [
        f"{_safe_text(row.get('team_name'))}: {abs(int(row.get('current_streak') or 0))} straight losses"
        for _, row in negative_streaks.head(4).iterrows()
    ]
    trend_cards = [
        {
            "label": "Hottest Team",
            "title": _safe_text(hottest.get("team_name"), "No clear leader") if hottest is not None else "No clear leader",
            "tone": "strength",
            "items": [
                f"{int(hottest.get('current_streak') or 0)}-game win streak",
                f"Power Rank {_format_rank(hottest.get('power_rank'))}",
                f"Strategy: {_safe_text(hottest.get('strategy_display'))}",
            ] if hottest is not None else ["Need completed matchup history first."],
        },
        {
            "label": "Coldest Team",
            "title": _safe_text(coldest.get("team_name"), "No clear skid") if coldest is not None else "No clear skid",
            "tone": "risk",
            "items": [
                f"{abs(int(coldest.get('current_streak') or 0))}-game losing streak",
                f"Power Rank {_format_rank(coldest.get('power_rank'))}",
                f"Strategy: {_safe_text(coldest.get('strategy_display'))}",
            ] if coldest is not None else ["Need completed matchup history first."],
        },
        {
            "label": "Win Streaks",
            "title": "Current heaters",
            "tone": "opportunity",
            "items": win_streak_items or ["No active win streaks yet."],
        },
        {
            "label": "Losing Streaks",
            "title": "Teams under pressure",
            "tone": "weakness",
            "items": loss_streak_items or ["No active losing streaks yet."],
        },
    ]

    player_lookup = {
        str(row.get("player_id")): row.to_dict()
        for _, row in normalize_player_ids(df_players).iterrows()
        if _safe_text(row.get("player_id"))
    }
    transaction_rows: list[dict] = []
    activity_totals: dict[int, dict] = {}
    max_transaction_week = report_week if report_week > 0 else 0
    for week in range(1, max_transaction_week + 1):
        for transaction in get_transactions(league_id, week) or []:
            tx_type = _safe_text(transaction.get("type")).strip().lower()
            tx_status = _safe_text(transaction.get("status")).strip().lower()
            if tx_status not in {"complete", "accepted", "processed"}:
                continue
            roster_ids = []
            for roster_id in transaction.get("roster_ids", []) or []:
                roster_value = _safe_positive_int(roster_id, 0)
                if roster_value > 0 and roster_value not in roster_ids:
                    roster_ids.append(roster_value)
            adds = transaction.get("adds") if isinstance(transaction.get("adds"), dict) else {}
            drops = transaction.get("drops") if isinstance(transaction.get("drops"), dict) else {}
            draft_picks = transaction.get("draft_picks") if isinstance(transaction.get("draft_picks"), list) else []
            for roster_value in list(adds.values()) + list(drops.values()):
                roster_int = _safe_positive_int(roster_value, 0)
                if roster_int > 0 and roster_int not in roster_ids:
                    roster_ids.append(roster_int)

            added_players = sorted(
                [_player_transaction_detail(player_lookup, player_id, score_field) for player_id in adds.keys()],
                key=lambda item: (item.get("score", 0.0), item.get("name", "")),
                reverse=True,
            )
            dropped_players = sorted(
                [_player_transaction_detail(player_lookup, player_id, score_field) for player_id in drops.keys()],
                key=lambda item: (item.get("score", 0.0), item.get("name", "")),
                reverse=True,
            )
            pick_labels = [_transaction_pick_label(pick) for pick in draft_picks]
            asset_count = len(added_players) + len(dropped_players) + len(pick_labels)
            best_added = added_players[0] if added_players else {}
            team_names = [
                _safe_text(team_lookup.get(roster_id, {}).get("team_name"), f"Team {roster_id}")
                for roster_id in roster_ids
            ]
            headline = ""
            if tx_type == "trade":
                headline = " / ".join(team_names[:2]) if team_names else "League trade"
            elif team_names:
                headline = team_names[0]
            significant_names = [item.get("name") for item in added_players[:3] + dropped_players[:2] if _safe_text(item.get("name"))]
            transaction_rows.append(
                {
                    "week": week,
                    "type": tx_type,
                    "headline": headline,
                    "teams": team_names,
                    "roster_ids": roster_ids,
                    "asset_count": asset_count,
                    "best_added_name": _safe_text(best_added.get("name")),
                    "best_added_score": _safe_float(best_added.get("score"), 0.0),
                    "best_added_tier": _safe_text(best_added.get("tier")),
                    "adds_count": len(added_players),
                    "drops_count": len(dropped_players),
                    "pick_count": len(pick_labels),
                    "player_names": significant_names,
                    "pick_labels": pick_labels[:3],
                    "summary": ", ".join(significant_names[:4] + pick_labels[:2]) or "No player details returned",
                }
            )

            for roster_id in roster_ids:
                bucket = activity_totals.setdefault(
                    roster_id,
                    {
                        "roster_id": roster_id,
                        "transaction_count": 0,
                        "waiver_moves": 0,
                        "trade_count": 0,
                        "roster_churn": 0,
                    },
                )
                bucket["transaction_count"] += 1
                if tx_type == "trade":
                    bucket["trade_count"] += 1
                elif tx_type in {"waiver", "free_agent"}:
                    bucket["waiver_moves"] += 1
                    bucket["roster_churn"] += len(added_players) + len(dropped_players)
                else:
                    bucket["roster_churn"] += len(added_players) + len(dropped_players)

    transaction_df = pd.DataFrame(transaction_rows)
    activity_df = pd.DataFrame(activity_totals.values())
    if activity_df.empty:
        activity_df = pd.DataFrame(columns=["roster_id", "transaction_count", "waiver_moves", "trade_count", "roster_churn"])
    if not activity_df.empty:
        activity_df["team_name"] = activity_df["roster_id"].map(
            lambda rid: _safe_text(team_lookup.get(_safe_positive_int(rid, 0), {}).get("team_name"), f"Team {rid}")
        )

    def _leader_row(frame: pd.DataFrame, sort_columns: list[str], ascending: list[bool]):
        if frame.empty:
            return None
        return frame.sort_values(sort_columns, ascending=ascending).iloc[0]

    most_active = _leader_row(activity_df, ["transaction_count", "roster_churn", "trade_count", "team_name"], [False, False, False, True])
    most_waiver_moves = _leader_row(activity_df, ["waiver_moves", "roster_churn", "team_name"], [False, False, True])
    most_trades = _leader_row(activity_df, ["trade_count", "transaction_count", "team_name"], [False, False, True])
    most_churn = _leader_row(activity_df, ["roster_churn", "transaction_count", "team_name"], [False, False, True])
    activity_tiles = [
        {
            "label": "Most Active Manager",
            "value": _safe_text(most_active.get("team_name"), "No activity yet") if most_active is not None else "No activity yet",
            "note": (
                f"{int(most_active.get('transaction_count') or 0)} completed moves"
                if most_active is not None
                else "Need transaction history first."
            ),
        },
        {
            "label": "Most Waiver Moves",
            "value": _safe_text(most_waiver_moves.get("team_name"), "No waivers yet") if most_waiver_moves is not None else "No waivers yet",
            "note": (
                f"{int(most_waiver_moves.get('waiver_moves') or 0)} waiver/free-agent claims"
                if most_waiver_moves is not None
                else "Need transaction history first."
            ),
        },
        {
            "label": "Most Trades",
            "value": _safe_text(most_trades.get("team_name"), "No trades yet") if most_trades is not None else "No trades yet",
            "note": (
                f"{int(most_trades.get('trade_count') or 0)} completed trades"
                if most_trades is not None
                else "Need transaction history first."
            ),
        },
        {
            "label": "Most Roster Churn",
            "value": _safe_text(most_churn.get("team_name"), "No churn yet") if most_churn is not None else "No churn yet",
            "note": (
                f"{int(most_churn.get('roster_churn') or 0)} add/drop moves"
                if most_churn is not None
                else "Need transaction history first."
            ),
        },
    ]

    week_transactions = transaction_df[transaction_df["week"] == report_week].copy() if report_week > 0 and not transaction_df.empty else pd.DataFrame()
    trade_cards = []
    for _, row in week_transactions[week_transactions["type"] == "trade"].sort_values(
        ["pick_count", "asset_count", "best_added_score", "headline"],
        ascending=[False, False, False, True],
    ).head(4).iterrows():
        teams = row.get("teams") or []
        trade_cards.append(
            {
                "label": "Trade",
                "title": " / ".join(str(team) for team in teams[:2]) or _safe_text(row.get("headline"), "League trade"),
                "tone": "opportunity",
                "items": [
                    f"{int(row.get('asset_count') or 0)} tracked assets moved",
                    _safe_text(row.get("summary"), "No player details returned"),
                ],
            }
        )
    waiver_cards = []
    waiver_mask = week_transactions["type"].isin(["waiver", "free_agent"]) if not week_transactions.empty else pd.Series(dtype=bool)
    for _, row in week_transactions[waiver_mask].sort_values(
        ["best_added_score", "adds_count", "headline"],
        ascending=[False, False, True],
    ).head(4).iterrows():
        added_name = _safe_text(row.get("best_added_name"), "Roster add")
        waiver_cards.append(
            {
                "label": "Waiver",
                "title": f"{_safe_text(row.get('headline'), 'Roster')} added {added_name}",
                "tone": "strength",
                "items": [
                    f"{_safe_text(row.get('best_added_tier'), 'Developmental')} add under the current valuation lens",
                    _safe_text(row.get("summary"), "No player details returned"),
                ],
            }
        )
    move_cards = []
    if report_week > 0 and not week_transactions.empty:
        churn_by_team = (
            week_transactions.explode("roster_ids")
            .dropna(subset=["roster_ids"])
            .assign(roster_ids=lambda frame: pd.to_numeric(frame["roster_ids"], errors="coerce").fillna(0).astype(int))
        )
        if not churn_by_team.empty:
            churn_by_team["move_count"] = pd.to_numeric(churn_by_team["adds_count"], errors="coerce").fillna(0) + pd.to_numeric(churn_by_team["drops_count"], errors="coerce").fillna(0)
            team_churn = (
                churn_by_team.groupby("roster_ids", as_index=False)
                .agg(move_count=("move_count", "sum"))
                .sort_values(["move_count", "roster_ids"], ascending=[False, True])
            )
            for _, row in team_churn.head(4).iterrows():
                roster_id = _safe_positive_int(row.get("roster_ids"), 0)
                if roster_id <= 0 or int(row.get("move_count") or 0) <= 0:
                    continue
                move_cards.append(
                    {
                        "label": "Roster Churn",
                        "title": _safe_text(team_lookup.get(roster_id, {}).get("team_name"), f"Team {roster_id}"),
                        "tone": "weakness",
                        "items": [f"{int(row.get('move_count') or 0)} add/drop moves in {report_label.lower()}"],
                    }
                )

    note_buckets = {
        "Surging": [],
        "Fading": [],
        "Assets": [],
        "Needs": [],
        "Health": [],
    }
    for _, team_row in df_intel.sort_values(["power_rank", "team_name"]).iterrows():
        roster_id = _safe_positive_int(team_row.get("roster_id"), 0)
        metrics = get_team_vs_league(df_summary, roster_id) or {}
        strategy = normalize_team_strategy(team_row.get("strategy") or team_row.get("mode"))
        streak = int(team_row.get("current_streak") or 0)
        weaknesses = [str(pos).upper() for pos in (metrics.get("weaknesses") or []) if _safe_text(pos)]
        strengths = [str(pos).upper() for pos in (metrics.get("strengths") or []) if _safe_text(pos)]
        team_name = _safe_text(team_row.get("team_name"), f"Team {roster_id}")
        meaningful_health = _has_meaningful_team_injury_impact(team_row)
        acute_health = injury_ui.is_acute_injury_pressure(team_row)
        note = ""
        bucket = "Needs"
        if strategy in {"contender", "fringe_contender"} and streak >= 2 and _safe_positive_int(team_row.get("power_rank"), 99) <= 4:
            note = "This contender is surging."
            bucket = "Surging"
        elif strategy in {"contender", "fringe_contender"} and (
            streak <= -2 or acute_health
        ):
            note = "This contender may be fading."
            bucket = "Fading"
        elif strategy in {"rebuild", "tank"} and _safe_positive_int(team_row.get("draft_capital_rank"), 99) <= 4:
            note = "This rebuild is accumulating assets."
            bucket = "Assets"
        elif meaningful_health:
            note = f"{_team_injury_display_label(team_row)} is shaping current roster decisions."
            bucket = "Health"
        elif weaknesses:
            note = f"This team needs {weaknesses[0]} help."
            bucket = "Needs"
        elif _safe_positive_int(team_row.get("franchise_rank"), 99) <= 4 and _safe_positive_int(team_row.get("power_rank"), 99) >= 7:
            note = "This roster carries more long-term value than immediate weekly punch."
            bucket = "Assets"
        elif strengths:
            note = f"This roster's edge still runs through {strengths[0]}."
            bucket = "Surging"
        else:
            note = "This roster is sitting in the middle and needs a cleaner direction."
            bucket = "Needs"
        note_buckets.setdefault(bucket, []).append(f"{team_name}: {note}")

    team_note_cards = []
    tone_map = {
        "Surging": "strength",
        "Fading": "risk",
        "Assets": "opportunity",
        "Needs": "weakness",
        "Health": "risk",
    }
    title_map = {
        "Surging": "Momentum teams",
        "Fading": "Warning signs",
        "Assets": "Future-building signals",
        "Needs": "Roster pressure points",
        "Health": "Injury-driven notes",
    }
    for bucket in ["Surging", "Fading", "Assets", "Needs", "Health"]:
        items = note_buckets.get(bucket) or []
        if not items:
            continue
        team_note_cards.append(
            {
                "label": bucket,
                "title": title_map.get(bucket, bucket),
                "tone": tone_map.get(bucket, "risk"),
                "items": items[:6],
            }
        )

    snapshot_rows = df_intel[
        [
            "roster_id",
            "team_name",
            "power_rank",
            "franchise_rank",
        ]
    ].to_dict("records")
    return {
        "available": True,
        "message": "",
        "report_week": report_week,
        "report_label": report_label,
        "snapshot_rows": snapshot_rows,
        "highlights": highlights,
        "trend_cards": trend_cards,
        "activity_tiles": activity_tiles,
        "trade_cards": trade_cards,
        "waiver_cards": waiver_cards,
        "move_cards": move_cards,
        "team_note_cards": team_note_cards,
        "matchup_history_available": not matchup_history.empty,
        "transaction_history_available": not transaction_df.empty,
    }


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_league_intelligence_frame(
    df_players: pd.DataFrame,
    league_id: str,
    df_display: pd.DataFrame,
    score_field: str,
    lineup_settings: dict,
) -> pd.DataFrame:
    if df_display.empty or not league_id:
        return pd.DataFrame()

    players = normalize_player_ids(df_players)
    rosters = get_rosters(league_id)
    if players.empty or not rosters:
        enriched = df_display.copy()
        for column in [
            "current_score_total",
            "market_total",
            "starter_current_score",
            "bench_current_score",
            "starter_share",
            "top_heavy_ratio",
            "impact_tier_starters",
            "elite_tier_count",
            "injured_count",
            "major_absences",
            "injured_starters",
            "injured_bench_players",
            "major_injury_count",
            "major_injured_starters",
            "injury_risk_total",
            "injury_burden",
            "injury_impact_score",
            "injury_value_impact",
            "undervalued_gap",
            "trade_count",
            "trade_asset_total",
            "rebuild_index",
        ]:
            enriched[column] = 0
        enriched["health_flag"] = "Stable"
        enriched["injury_impact_flag"] = "Injury Data Unavailable"
        enriched["injury_data_quality"] = "missing"
        enriched["injury_data_note"] = "League roster injury data is unavailable."
        enriched["key_injuries_summary"] = ""
        enriched["top_injury_impact_summary"] = ""
        enriched["top_injury_impact_players"] = [[] for _ in range(len(enriched))]
        enriched["actionable_injury_summary"] = ""
        enriched["actionable_injury_players"] = [[] for _ in range(len(enriched))]
        enriched["injury_role_context"] = [{} for _ in range(len(enriched))]
        return enriched

    player_lookup = players.set_index("player_id", drop=False)
    roster_rows: list[dict] = []
    for roster in rosters:
        try:
            roster_id = int(roster.get("roster_id"))
        except Exception:
            continue

        player_ids = [str(pid) for pid in roster.get("players", []) or [] if pid is not None]
        if not player_ids:
            roster_rows.append(
                {
                    "roster_id": roster_id,
                    "current_score_total": 0.0,
                    "market_total": 0.0,
                    "starter_current_score": 0.0,
                    "bench_current_score": 0.0,
                    "starter_share": 0.0,
                    "top_heavy_ratio": 0.0,
                    "impact_tier_starters": 0,
                    "elite_tier_count": 0,
                    "injured_count": 0,
                    "major_absences": 0,
                    "injured_starters": 0,
                    "injured_bench_players": 0,
                    "major_injury_count": 0,
                    "major_injured_starters": 0,
                    "injury_risk_total": 0.0,
                    "injury_burden": 0.0,
                    "injury_impact_score": 0.0,
                    "injury_value_impact": 0.0,
                    "injury_impact_flag": "Injury Data Unavailable",
                    "injury_data_quality": "missing",
                    "injury_data_note": "No roster players are available for injury assessment.",
                    "health_flag": "Stable",
                    "key_injuries_summary": "",
                    "top_injury_impact_summary": "",
                    "top_injury_impact_players": [],
                    "actionable_injury_summary": "",
                    "actionable_injury_players": [],
                    "injury_role_context": {},
                }
            )
            continue

        team_df = player_lookup.loc[player_lookup.index.isin(player_ids)].copy()
        if team_df.empty:
            roster_rows.append(
                {
                    "roster_id": roster_id,
                    "current_score_total": 0.0,
                    "market_total": 0.0,
                    "starter_current_score": 0.0,
                    "bench_current_score": 0.0,
                    "starter_share": 0.0,
                    "top_heavy_ratio": 0.0,
                    "impact_tier_starters": 0,
                    "elite_tier_count": 0,
                    "injured_count": 0,
                    "major_absences": 0,
                    "injured_starters": 0,
                    "injured_bench_players": 0,
                    "major_injury_count": 0,
                    "major_injured_starters": 0,
                    "injury_risk_total": 0.0,
                    "injury_burden": 0.0,
                    "injury_impact_score": 0.0,
                    "injury_value_impact": 0.0,
                    "injury_impact_flag": "Injury Data Unavailable",
                    "injury_data_quality": "missing",
                    "injury_data_note": "Roster players could not be matched to injury metadata.",
                    "health_flag": "Stable",
                    "key_injuries_summary": "",
                    "top_injury_impact_summary": "",
                    "top_injury_impact_players": [],
                    "actionable_injury_summary": "",
                    "actionable_injury_players": [],
                    "injury_role_context": {},
                }
            )
            continue

        if "value_score" in team_df.columns:
            team_df["value_score"] = pd.to_numeric(team_df["value_score"], errors="coerce").fillna(0)
        else:
            team_df["value_score"] = pd.to_numeric(
                team_df[score_field] if score_field in team_df.columns else team_df.get("dynasty_score", 0),
                errors="coerce",
            ).fillna(0)
        lineup_df = suggest_optimal_lineup(team_df, lineup_settings)
        starter_mask = lineup_df["suggested_starter"].fillna(False) if "suggested_starter" in lineup_df.columns else pd.Series(False, index=lineup_df.index)
        injury_flags = lineup_df.apply(is_injury_status, axis=1) if not lineup_df.empty else pd.Series(dtype=bool)

        status_series = lineup_df.get("status", pd.Series("", index=lineup_df.index)).fillna("").astype(str).str.strip().str.lower()
        injury_series = lineup_df.get("injury_status", pd.Series("", index=lineup_df.index)).fillna("").astype(str).str.strip().str.lower()
        major_flags = (
            status_series.isin({"out", "doubtful", "injured reserve", "ir", "pup", "nfi"})
            | injury_series.isin({"out", "doubtful", "injured reserve", "ir", "pup", "nfi"})
        )

        current_score_total = float(pd.to_numeric(lineup_df["value_score"], errors="coerce").fillna(0).sum())
        starter_current_score = float(pd.to_numeric(lineup_df.loc[starter_mask, "value_score"], errors="coerce").fillna(0).sum())
        bench_current_score = float(pd.to_numeric(lineup_df.loc[~starter_mask, "value_score"], errors="coerce").fillna(0).sum())
        injury_context = summarize_team_injuries(team_df, lineup_df)
        injured_count = int(injury_context.get("injured_roster") or 0)
        major_absences = int(injury_context.get("major_absences") or 0)
        injured_starters = int(injury_context.get("injured_starters") or 0)
        starter_share = starter_current_score / current_score_total if current_score_total else 0.0
        top_heavy_ratio = starter_current_score / max(bench_current_score, 1.0)
        starter_tiers = (
            lineup_df.loc[starter_mask, "player_tier"].fillna("").astype(str)
            if "player_tier" in lineup_df.columns
            else pd.Series("", index=lineup_df.index)
        )
        roster_tiers = (
            team_df.get("player_tier", pd.Series("", index=team_df.index)).fillna("").astype(str)
            if not team_df.empty
            else pd.Series(dtype="object")
        )
        impact_tier_starters = int(starter_tiers.isin({"Elite", "Star", "Core Starter"}).sum())
        elite_tier_count = int(roster_tiers.isin({"Elite", "Star"}).sum())
        injury_risk_total = float(injury_context.get("injury_risk_total") or 0.0)
        injury_burden = float(injury_context.get("injury_burden") or 0.0)
        injured_bench_players = int(injury_context.get("injured_bench_players") or 0)
        major_injury_count = int(injury_context.get("major_injury_count") or 0)
        major_injured_starters = int(injury_context.get("major_injured_starters") or 0)
        injury_impact_score = float(injury_context.get("injury_impact_score") or 0.0)
        injury_value_impact = float(injury_context.get("injury_value_impact") or injury_impact_score)
        injury_impact_flag = _safe_text(injury_context.get("injury_impact_flag"), "Stable")
        injury_data_quality = _safe_text(injury_context.get("injury_data_quality"), "uncertain")
        injury_data_note = _safe_text(injury_context.get("injury_data_note"))
        health_flag = _safe_text(injury_context.get("health_flag"), "Stable")
        actionable_players = list(injury_context.get("actionable_injury_players") or [])
        key_injuries_summary = ", ".join(
            _safe_text(item.get("name"))
            for item in actionable_players
            if _safe_text(item.get("name"))
        )
        top_injury_impact_summary = _safe_text(injury_context.get("top_injury_impact_summary"))
        top_injury_impact_players = list(injury_context.get("top_injury_impact_players") or [])
        actionable_injury_summary = _safe_text(injury_context.get("actionable_injury_summary"))
        actionable_injury_players = actionable_players

        roster_rows.append(
            {
                "roster_id": roster_id,
                "current_score_total": current_score_total,
                "market_total": float(pd.to_numeric(team_df.get("market_score", 0), errors="coerce").fillna(0).sum()),
                "starter_current_score": starter_current_score,
                "bench_current_score": bench_current_score,
                "starter_share": starter_share,
                "top_heavy_ratio": top_heavy_ratio,
                "impact_tier_starters": impact_tier_starters,
                "elite_tier_count": elite_tier_count,
                "injured_count": injured_count,
                "major_absences": major_absences,
                "injured_starters": injured_starters,
                "injured_bench_players": injured_bench_players,
                "major_injury_count": major_injury_count,
                "major_injured_starters": major_injured_starters,
                "injury_risk_total": injury_risk_total,
                "injury_burden": injury_burden,
                "injury_impact_score": injury_impact_score,
                "injury_value_impact": injury_value_impact,
                "injury_impact_flag": injury_impact_flag,
                "injury_data_quality": injury_data_quality,
                "injury_data_note": injury_data_note,
                "health_flag": health_flag,
                "key_injuries_summary": key_injuries_summary,
                "top_injury_impact_summary": top_injury_impact_summary,
                "top_injury_impact_players": top_injury_impact_players,
                "actionable_injury_summary": actionable_injury_summary,
                "actionable_injury_players": actionable_injury_players,
                "injury_role_context": injury_context,
            }
        )

    roster_metrics = pd.DataFrame(roster_rows)
    trade_activity = cached_trade_activity_summary(league_id)
    manager_behavior = cached_manager_behavior_summary(league_id)

    enriched = df_display.copy()
    enriched = enriched.merge(roster_metrics, on="roster_id", how="left")
    if not trade_activity.empty:
        enriched = enriched.merge(trade_activity, on="roster_id", how="left")
    if not manager_behavior.empty:
        behavior_merge = manager_behavior.drop(columns=[col for col in ["trade_count", "trade_asset_total"] if col in manager_behavior.columns], errors="ignore")
        enriched = enriched.merge(behavior_merge, on="roster_id", how="left")

    fill_zero_cols = [
        "current_score_total",
        "market_total",
        "starter_current_score",
        "bench_current_score",
        "starter_share",
        "top_heavy_ratio",
        "impact_tier_starters",
        "elite_tier_count",
        "injured_count",
        "major_absences",
        "injured_starters",
        "injured_bench_players",
        "major_injury_count",
        "major_injured_starters",
        "injury_risk_total",
        "injury_burden",
        "injury_impact_score",
        "injury_value_impact",
        "trade_count",
        "trade_asset_total",
        "transaction_count",
        "waiver_moves",
        "trade_asset_avg",
        "roster_churn",
        "picks_acquired",
        "picks_sent",
        "firsts_acquired",
        "firsts_sent",
    ]
    for column in fill_zero_cols:
        if column not in enriched.columns:
            enriched[column] = 0
        enriched[column] = pd.to_numeric(enriched[column], errors="coerce").fillna(0)
    for column, default in [
        ("health_flag", "Stable"),
        ("injury_impact_flag", "Health Status Uncertain"),
        ("injury_data_quality", "uncertain"),
        ("injury_data_note", "Injury data quality could not be confirmed."),
        ("key_injuries_summary", ""),
        ("top_injury_impact_summary", ""),
        ("actionable_injury_summary", ""),
    ]:
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = enriched[column].fillna(default).astype(str)
    for column in ["top_injury_impact_players", "actionable_injury_players"]:
        if column not in enriched.columns:
            enriched[column] = [[] for _ in range(len(enriched))]
        else:
            enriched[column] = enriched[column].apply(
                lambda value: value if isinstance(value, list) else []
            )
    if "injury_role_context" not in enriched.columns:
        enriched["injury_role_context"] = [{} for _ in range(len(enriched))]
    else:
        enriched["injury_role_context"] = enriched["injury_role_context"].apply(
            lambda value: value if isinstance(value, dict) else {}
        )
    for column, default in [
        ("trading_style", "Passive Trader"),
        ("roster_philosophy", "Balanced"),
        ("asset_behavior", "Balanced Asset Manager"),
        ("activity_level", "Average Activity"),
        ("manager_tendencies_summary", ""),
        ("manager_evidence_text", ""),
        ("manager_trade_implication", ""),
    ]:
        if column not in enriched.columns:
            enriched[column] = default
        enriched[column] = enriched[column].fillna(default).astype(str)
    if "manager_evidence" not in enriched.columns:
        enriched["manager_evidence"] = [[] for _ in range(len(enriched))]
    else:
        enriched["manager_evidence"] = enriched["manager_evidence"].apply(
            lambda value: value if isinstance(value, list) else ([str(value)] if _safe_text(value) else [])
        )

    enriched["undervalued_gap"] = enriched["current_score_total"] - enriched["market_total"]
    league_size = max(len(enriched), 1)
    youth_points = league_size - pd.to_numeric(enriched.get("age_rank", 999), errors="coerce").fillna(league_size).clip(lower=1)
    draft_points = league_size - pd.to_numeric(enriched.get("draft_capital_rank", league_size), errors="coerce").fillna(league_size).clip(lower=1)
    roster_points = league_size - pd.to_numeric(enriched.get("roster_value_rank", league_size), errors="coerce").fillna(league_size).clip(lower=1)
    enriched["rebuild_index"] = (draft_points * 0.52) + (youth_points * 0.30) + (roster_points * 0.18)
    return _classify_manager_tendencies(enriched)


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_league_core_context(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
) -> dict:
    empty = {
        "league_summary": pd.DataFrame(),
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": pd.DataFrame(),
        "league_detail_ranks": pd.DataFrame(),
        "league_intelligence_frame": pd.DataFrame(),
    }
    if not league_id:
        return empty

    base_summary = cached_league_summary(
        df_players,
        league_id,
        score_field=score_field,
        lineup_settings=lineup_settings,
    )
    if base_summary.empty:
        return {**empty, "league_summary": base_summary}

    draft_picks = cached_draft_pick_assets(
        league_id,
        base_summary,
        league_settings_items=draft_pick_valuation_settings_items(lineup_settings),
    )
    draft_capital_summary = build_draft_capital_summary(base_summary, draft_picks)
    df_display = build_league_display_frame(base_summary, draft_capital_summary, include_picks=True)
    df_detail = add_league_detail_ranks(df_display)
    df_intel = cached_league_intelligence_frame(
        df_players,
        league_id,
        df_detail,
        score_field,
        lineup_settings,
    )
    return {
        "league_summary": base_summary,
        "draft_pick_assets": draft_picks,
        "draft_capital_summary": draft_capital_summary,
        "league_display_frame": df_display,
        "league_detail_ranks": df_detail,
        "league_intelligence_frame": df_intel,
    }


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_team_direction_summary(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
) -> pd.DataFrame:
    core_context = cached_league_core_context(
        df_players,
        league_id,
        score_field=score_field,
        lineup_settings=lineup_settings,
    )
    base_summary = core_context.get("league_summary", pd.DataFrame())
    if base_summary.empty:
        return base_summary

    df_intel = core_context.get("league_intelligence_frame", pd.DataFrame())
    if df_intel.empty:
        return base_summary

    refined = refine_team_directions(df_intel)
    merge_cols = [
        col
        for col in [
            "roster_id",
            "mode",
            "strategy",
            "strategy_label",
            "archetype",
            "archetype_label",
            "archetype_explanation",
            "injured_count",
            "major_absences",
            "injured_starters",
            "injured_bench_players",
            "major_injury_count",
            "major_injured_starters",
            "injury_risk_total",
            "injury_burden",
            "injury_impact_score",
            "injury_value_impact",
            "injury_impact_flag",
            "injury_data_quality",
            "injury_data_note",
            "health_flag",
            "key_injuries_summary",
            "top_injury_impact_summary",
            "top_heavy_ratio",
            "trading_style",
            "roster_philosophy",
            "asset_behavior",
            "activity_level",
            "manager_tendencies_summary",
            "manager_evidence_text",
            "manager_trade_implication",
        ]
        if col in refined.columns
    ]
    if len(merge_cols) < 4:
        return base_summary

    refined_strategy = refined[merge_cols].copy()
    refined_strategy["roster_id_key"] = pd.to_numeric(refined_strategy["roster_id"], errors="coerce")

    output = base_summary.copy()
    output["roster_id_key"] = pd.to_numeric(output["roster_id"], errors="coerce")
    output = output.drop(columns=[col for col in ["mode", "strategy", "strategy_label"] if col in output.columns])
    output = output.merge(
        refined_strategy.drop(columns=["roster_id"]),
        on="roster_id_key",
        how="left",
    )
    output = output.drop(columns=["roster_id_key"], errors="ignore")
    output["strategy"] = output["strategy"].fillna(base_summary.get("strategy"))
    output["strategy_label"] = output["strategy_label"].fillna(base_summary.get("strategy_label"))
    output["mode"] = output["mode"].fillna(base_summary.get("mode"))
    return output


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_league_shell_context(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
) -> dict:
    """Return only stable workspace identity and rank data.

    Global page chrome does not need league intelligence, transaction history,
    Trust context, or roster maps. Keeping this boundary separate prevents
    secondary routes from paying those costs before their own content mounts.
    """

    if not league_id:
        return {
            "team_direction_summary": pd.DataFrame(),
            "draft_pick_assets": [],
            "draft_capital_summary": pd.DataFrame(),
            "league_display_frame": pd.DataFrame(),
            "league_detail_ranks": pd.DataFrame(),
            "roster_profiles": {},
        }
    # Use base league summary only — never team_direction/intelligence refine on
    # the first-usable chrome path (that work belongs after loading dismiss).
    team_direction_summary = cached_league_summary(
        df_players,
        league_id,
        score_field=score_field,
        lineup_settings=lineup_settings,
    )
    if team_direction_summary.empty:
        return {
            "team_direction_summary": team_direction_summary,
            "draft_pick_assets": [],
            "draft_capital_summary": pd.DataFrame(),
            "league_display_frame": pd.DataFrame(),
            "league_detail_ranks": pd.DataFrame(),
            "roster_profiles": {},
        }
    draft_pick_assets = cached_draft_pick_assets(
        league_id,
        team_direction_summary,
        league_settings_items=draft_pick_valuation_settings_items(lineup_settings),
    )
    draft_capital_summary = build_draft_capital_summary(
        team_direction_summary,
        draft_pick_assets,
    )
    league_display_frame = build_league_display_frame(
        team_direction_summary,
        draft_capital_summary,
        include_picks=True,
    )
    roster_profiles = get_league_roster_profiles(league_id) or {}
    league_display_frame = _enrich_league_display_with_roster_profiles(
        league_display_frame,
        roster_profiles,
    )
    return {
        "team_direction_summary": team_direction_summary,
        "draft_pick_assets": draft_pick_assets,
        "draft_capital_summary": draft_capital_summary,
        "league_display_frame": league_display_frame,
        "league_detail_ranks": add_league_detail_ranks(league_display_frame),
        "roster_profiles": roster_profiles,
    }


@st.cache_data(ttl=5 * 60, show_spinner=False)
def cached_league_context(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str,
    lineup_settings: dict,
    startup_context: dict | None = None,
    *,
    include_intelligence: bool = True,
    include_roster_map: bool = True,
    include_trust: bool = True,
    include_maturity: bool = True,
) -> dict:
    empty = {
        "league_summary": pd.DataFrame(),
        "team_direction_summary": pd.DataFrame(),
        "draft_pick_assets": [],
        "draft_capital_summary": pd.DataFrame(),
        "league_display_frame": pd.DataFrame(),
        "league_detail_ranks": pd.DataFrame(),
        "league_intelligence_frame": pd.DataFrame(),
        "roster_profiles": {},
        "roster_player_map": {},
        "trade_trust_context": None,
        "league_maturity": league_maturity.build_league_evidence(
            startup_context=startup_context,
        ),
    }
    if not league_id:
        return empty

    core_context = cached_league_core_context(
        df_players,
        league_id,
        score_field=score_field,
        lineup_settings=lineup_settings,
    )
    league_summary = core_context.get("league_summary", pd.DataFrame())
    if league_summary.empty:
        return {**empty, "league_summary": league_summary}

    shell_context = cached_league_shell_context(
        df_players,
        league_id,
        score_field,
        lineup_settings,
    )
    # Shell/summary path: lightweight ranks without archetype refine (#212).
    team_direction_summary = shell_context.get("team_direction_summary", pd.DataFrame())
    if team_direction_summary.empty:
        team_direction_summary = league_summary

    draft_pick_assets = shell_context.get("draft_pick_assets", [])
    draft_capital_summary = shell_context.get("draft_capital_summary", pd.DataFrame())
    league_display_frame = shell_context.get("league_display_frame", pd.DataFrame())
    roster_profiles = shell_context.get("roster_profiles", {})
    league_detail_ranks = shell_context.get("league_detail_ranks", pd.DataFrame())
    league_intelligence_frame = pd.DataFrame()
    if include_intelligence:
        with performance.time_block("league_context_intelligence", category="analysis"):
            # Full intelligence is route-owned (after first usable), never shell-owned.
            # Prefer the core intelligence frame, then apply direction refine so
            # archetype_label / refined strategy columns are part of the intelligence schema.
            raw_intelligence = core_context.get("league_intelligence_frame", pd.DataFrame())
            if raw_intelligence.empty:
                detail_ranks = core_context.get("league_detail_ranks", pd.DataFrame())
                if detail_ranks.empty:
                    detail_ranks = league_detail_ranks
                raw_intelligence = cached_league_intelligence_frame(
                    df_players,
                    league_id,
                    detail_ranks,
                    score_field,
                    lineup_settings,
                )
            if raw_intelligence.empty:
                league_intelligence_frame = raw_intelligence
            else:
                league_intelligence_frame = refine_team_directions(raw_intelligence)
            # Refined direction summary for consumers that read team_direction_summary.
            refined_direction = cached_team_direction_summary(
                df_players,
                league_id,
                score_field=score_field,
                lineup_settings=lineup_settings,
            )
            if not refined_direction.empty:
                team_direction_summary = refined_direction

    loaded_rosters = []
    roster_player_map = {}
    if include_roster_map or include_trust or include_maturity:
        with performance.time_block("league_context_roster_shell", category="analysis"):
            loaded_rosters = get_rosters(league_id) or []
            if include_roster_map or include_trust:
                roster_player_map = _build_roster_player_map(loaded_rosters)

    trade_trust_context = None
    if include_trust:
        with performance.time_block("trust_context_construction", category="analysis"):
            trade_trust_context = build_trade_trust_context(
                league_id=league_id,
                df_summary=team_direction_summary,
                roster_player_map=roster_player_map,
            )

    maturity_context = empty["league_maturity"]
    if include_maturity:
        with performance.time_block("league_context_maturity", category="analysis"):
            maturity_context = league_maturity.build_league_evidence(
                startup_context=startup_context,
                league=get_league(league_id) or {},
                rosters=loaded_rosters,
                league_frame=league_intelligence_frame,
            )
    return {
        "league_summary": league_summary,
        "team_direction_summary": team_direction_summary,
        "draft_pick_assets": draft_pick_assets,
        "draft_capital_summary": draft_capital_summary,
        "league_display_frame": league_display_frame,
        "league_detail_ranks": league_detail_ranks,
        "league_intelligence_frame": league_intelligence_frame,
        "roster_profiles": roster_profiles,
        "roster_player_map": roster_player_map,
        "trade_trust_context": trade_trust_context,
        "league_maturity": maturity_context,
    }


_select_intelligence_row = league_workspace_ui._select_intelligence_row
_intelligence_card = league_workspace_ui._intelligence_card
render_team_rank_cards = league_workspace_ui.render_team_rank_cards
render_team_score_details = league_workspace_ui.render_team_score_details
build_team_partner_context_tiles = league_workspace_ui.build_team_partner_context_tiles


def select_league_frame_columns(
    frame: pd.DataFrame | None,
    columns: list[str],
    *,
    required: list[str] | None = None,
) -> pd.DataFrame | None:
    """Return ``frame[columns]`` only when required schema columns are present.

    Summary/shell frames must not crash consumers that require intelligence-only
    columns such as ``archetype_label``. Missing required columns → None (fail soft).
    """

    if frame is None or getattr(frame, "empty", True):
        return None
    required_columns = list(required or columns)
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        return None
    present = [column for column in columns if column in frame.columns]
    if not present:
        return None
    return frame.loc[:, present].copy()


def build_league_intelligence_cards(
    df_intel: pd.DataFrame,
    score_field: str,
    maturity_context: dict | None = None,
) -> list[dict]:
    return league_workspace_ui.build_league_intelligence_cards(
        df_intel,
        score_field,
        has_meaningful_team_injury_impact=_has_meaningful_team_injury_impact,
        team_injury_display_label=_team_injury_display_label,
        maturity_context=maturity_context,
    )


def _league_overview_team_lines(
    df: pd.DataFrame,
    *,
    limit: int = 3,
    include_power: bool = False,
    include_franchise: bool = False,
    include_draft: bool = False,
    include_strategy: bool = False,
    include_health: bool = False,
) -> list[str]:
    return league_workspace_ui._league_overview_team_lines(
        df,
        limit=limit,
        include_power=include_power,
        include_franchise=include_franchise,
        include_draft=include_draft,
        include_strategy=include_strategy,
        include_health=include_health,
        team_injury_display_label=_team_injury_display_label,
    )


def build_league_overview_decision_cards(
    df_intel: pd.DataFrame,
    maturity_context: dict | None = None,
) -> list[dict]:
    return league_workspace_ui.build_league_overview_decision_cards(
        df_intel,
        team_injury_display_label=_team_injury_display_label,
        maturity_context=maturity_context,
    )


def render_league_intelligence_cards(cards: list[dict]):
    active_context = st.session_state.get("active_league_context", {}) or {}
    return league_workspace_ui.render_league_intelligence_cards(
        cards,
        team_tap_markup=_team_tap_markup,
        render_team_card_tap_grid=_render_team_card_tap_grid,
        open_league_team_from_tap=_open_league_team_from_tap,
        team_logo_html=team_logo_html,
        current_roster_id=active_context.get("my_roster_id"),
    )


def render_power_rankings_board(
    df_display: pd.DataFrame,
    score_label: str,
    rank_column: str = "power_rank",
    score_column: str = "power_score",
):
    active_context = st.session_state.get("active_league_context", {}) or {}
    return league_workspace_ui.render_power_rankings_board(
        df_display,
        score_label,
        rank_column=rank_column,
        score_column=score_column,
        has_meaningful_team_injury_impact=_has_meaningful_team_injury_impact,
        team_injury_display_label=_team_injury_display_label,
        team_tap_markup=_team_tap_markup,
        render_team_card_tap_grid=_render_team_card_tap_grid,
        open_league_team_from_tap=_open_league_team_from_tap,
        team_logo_html=team_logo_html,
        current_roster_id=active_context.get("my_roster_id"),
    )


def render_league_standings_board(standings_bundle: dict):
    active_context = st.session_state.get("active_league_context", {}) or {}
    return league_workspace_ui.render_standings_board(
        standings_bundle,
        team_tap_markup=_team_tap_markup,
        render_team_card_tap_grid=_render_team_card_tap_grid,
        open_league_team_from_tap=_open_league_team_from_tap,
        team_logo_html=team_logo_html,
        current_roster_id=active_context.get("my_roster_id"),
    )

def build_league_team_advice(
    team_df: pd.DataFrame,
    metrics: dict | None,
    draft_row: dict | None,
    league_size: int,
    team_needs_assessment: TeamNeedsAssessment | None = None,
) -> list[dict]:
    advice: list[dict] = []
    metrics = injury_ui.resolve_team_injury_context(metrics or {})
    draft_row = draft_row or {}
    mode = _safe_text(metrics.get("mode"), "competitive")
    strategy = normalize_team_strategy(metrics.get("strategy") or mode)
    strengths = [str(pos).upper() for pos in metrics.get("strengths", []) or []]
    need_presentation = league_workspace_ui.build_team_need_presentation(
        metrics,
        team_needs_assessment,
    )
    true_needs = list(need_presentation["true_needs"])
    covered_relative_weaknesses = list(
        need_presentation["covered_relative_weaknesses"]
    )
    injured_starters = _safe_positive_int(metrics.get("injured_starters"), 0)
    health_flag = injury_ui.team_injury_display_label(
        metrics,
        include_uncertainty=True,
    ) or "Stable"
    injury_data_quality = _safe_text(metrics.get("injury_data_quality"), "available")
    injury_advice_context = injury_ui.team_injury_advice(metrics)
    acute_injury_pressure = injury_ui.is_acute_injury_pressure(metrics)

    if mode == "contender":
        advice.append(
            {
                "label": "Window",
                "title": "Built to push weekly points",
                "body": "This roster profiles as a contender. Priority should be consolidating bench value into one more starter instead of adding replacement-level depth.",
                "primary": True,
            }
        )
    elif mode == "rebuild":
        advice.append(
            {
                "label": "Window",
                "title": "Play the long game",
                "body": "This roster profiles as a rebuild. Moving aging starters for younger pieces or future picks is the cleaner path than paying for short-term points.",
                "primary": True,
            }
        )
    else:
        advice.append(
            {
                "label": "Window",
                "title": "One move could swing the direction",
                "body": "This team sits in the middle tier. Use strengths to attack one weak position, but avoid spending premium capital just to stay average.",
                "primary": True,
            }
        )

    if acute_injury_pressure:
        if strategy in {"contender", "fringe_contender"}:
            body = f"{health_flag} is dragging the short-term outlook. Healthy lineup cover should come before luxury upgrades while {injured_starters} starter{'s are' if injured_starters != 1 else ' is'} compromised."
        elif strategy in {"rebuild", "tank"}:
            body = f"{health_flag} is distorting the weekly picture. This team should protect value and avoid short-term injury patches that do not fit the longer timeline."
        else:
            body = f"{health_flag} is the immediate swing factor. Any move should account for current health drag before leaning on the usual strategy label."
        advice.append(
            {
                "label": "Health",
                "title": "Health owns the near-term recommendation",
                "body": body,
            }
        )
    elif injury_advice_context.get("focus") == "future":
        advice.append(
            {
                "label": "Health",
                "title": injury_advice_context.get("title"),
                "body": injury_advice_context.get("body"),
            }
        )
    elif injury_data_quality != "available":
        advice.append(
            {
                "label": "Health",
                "title": "Health status needs confirmation",
                "body": _safe_text(
                    metrics.get("injury_data_note"),
                    "Current injury status is incomplete or stale, so this team should not be treated as clearly healthy.",
                ),
            }
        )

    if true_needs:
        advice.append(
            {
                "label": "Need",
                "title": "Roster needs: " + " / ".join(true_needs[:3]),
                "body": "Starter and depth coverage identify these as genuine roster deficiencies.",
            }
        )
    if covered_relative_weaknesses:
        advice.append(
            {
                "label": "Relative Weakness",
                "title": "Below league average: "
                + " / ".join(covered_relative_weaknesses[:3]),
                "body": "These covered rooms trail the league comparison baseline, making them upgrade opportunities rather than true roster needs.",
            }
        )
    if strengths:
        advice.append(
            {
                "label": "Surplus",
                "title": "Movable strength: " + " / ".join(strengths[:2]),
                "body": "These positions carry the best leverage if this manager wants to make a move without hurting the starting lineup.",
            }
        )

    draft_rank = int(draft_row.get("draft_capital_rank") or 0)
    draft_capital = int(draft_row.get("draft_capital") or 0)
    if draft_rank and league_size > 1:
        if draft_rank <= max(2, league_size // 3):
            advice.append(
                {
                    "label": "Picks",
                    "title": "Has room to spend or reload",
                    "body": f"This team ranks near the top of the league in draft capital ({draft_capital:,}). It can buy help now or stay patient and let the board come to it.",
                }
            )
        elif draft_capital <= 0:
            advice.append(
                {
                    "label": "Picks",
                    "title": "Thin future capital",
                    "body": "Draft capital is light. Any aggressive win-now move should be paired with protecting at least one meaningful future out.",
                }
            )

    avg_age = metrics.get("avg_age")
    league_age = metrics.get("league_age_mean")
    if avg_age is not None and league_age is not None:
        if avg_age - league_age >= 1.0:
            advice.append(
                {
                    "label": "Age",
                    "title": "Older build than league average",
                    "body": "This roster is aging relative to the league. Equal-value deals should lean toward younger starters or picks.",
                }
            )
        elif league_age - avg_age >= 1.0 and mode != "rebuild":
            advice.append(
                {
                    "label": "Age",
                    "title": "Young enough to buy",
                    "body": "The age curve is still healthy. This manager has room to add one veteran scorer if the price comes from depth or future seconds instead of core assets.",
                }
            )

    if not advice and team_df is not None and not team_df.empty:
        advice.append(
            {
                "label": "View",
                "title": "Balanced roster shape",
                "body": "No single pressure point jumps off the page, so roster decisions should be driven by weekly lineup edge and market value rather than panic needs.",
                "primary": True,
            }
        )
    return advice[:4]


league_score_label = league_workspace_ui.league_score_label


def main():
    module_import_ms = (time.perf_counter() - _APP_MODULE_IMPORT_STARTED) * 1000
    perf_rerun = performance.begin_rerun()
    runtime_trace.record_application_import(module_import_ms)
    if perf_rerun.get("sequence") == 1:
        performance.record_timing(
            "application_module_import",
            module_import_ms,
            category="startup",
        )
    st.set_page_config(
        page_title="FantasyGM Lab",
        page_icon=brand_identity.page_icon_path(),
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    # App subdomain should not compete with the public marketing site for indexing.
    st.markdown(
        '<meta name="robots" content="noindex, nofollow">',
        unsafe_allow_html=True,
    )
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            "landing_viewed",
            props=launch_analytics.build_context_props(st.session_state, route="landing"),
            once_key="session",
            state=st.session_state,
        )
    except Exception:
        pass
    startup = startup_coordinator.StartupCoordinator.begin(st.session_state)
    startup_started_at = startup_coordinator._startup_started_at(st.session_state)
    auth_restore_lifecycle.begin_script_run(st.session_state)

    inject_global_styles(APP_CSS)
    inject_global_styles(FOUNDER_BETA_UX_CSS)
    inject_global_styles(DASHBOARD_WORKFLOW_CSS)
    st.markdown(
        f"""
        <div class="app-hero" data-fgl-shell-ready="1">
            <div class="app-hero-top">
                <div class="app-eyebrow">{brand_identity.FOUNDER_BETA_LABEL}</div>
                {brand_identity.founder_beta_badge_html(compact=True)}
            </div>
            <h1>{brand_identity.PRODUCT_NAME}</h1>
            <p>{brand_identity.PRODUCT_TAGLINE}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    startup.advance(startup_coordinator.StartupPhase.AUTH_RESTORING)
    with performance.time_block("supabase_session_restoration", category="supabase"):
        auth_restore = account_ui.render_durable_auth_bridge(config=_supabase_config())
    runtime_trace.mark("auth_storage_bridge_complete")
    # Log Session restored once when auth identity settles (restored, identical,
    # guest-empty, or already authenticated) — not on every pending stop remount.
    auth_settled = (
        bool(auth_restore.get("restored"))
        or bool(auth_restore.get("identical"))
        or bool(auth_supabase.current_user_id(st.session_state))
        or (
            not auth_restore.get("pending")
            and not auth_restore.get("error")
        )
    )
    if auth_settled and not auth_restore.get("pending"):
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "session_restored",
            started_at=startup_started_at,
            once=True,
        )
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "auth_ready",
            started_at=startup_started_at,
            once=True,
        )
    if auth_restore.get("restored"):
        # Continue this run into profile/entitlement/league. Durable browser save
        # is deferred until after first-usable so restore no longer forces a
        # dedicated Streamlit rerun before the shell can settle.
        startup_critical_path.clear_auth_pending_wait(st.session_state)
    if auth_restore.get("pending") and startup.active:
        if startup_critical_path.should_stop_for_auth_pending(st.session_state):
            # REQUIRED: wait for the browser storage component response.
            st.stop()
        # Hang protection: proceed with a usable signed-out shell rather than an
        # indefinite loading overlay when browser storage never returns.
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "session_restored",
            started_at=startup_started_at,
            once=True,
        )
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "auth_ready",
            started_at=startup_started_at,
            once=True,
        )
    else:
        startup_critical_path.clear_auth_pending_wait(st.session_state)
    if auth_restore.get("error"):
        st.caption(auth_restore["error"])

    startup.advance(startup_coordinator.StartupPhase.PROFILE_LOADING)
    with performance.time_block("supabase_profile_load", category="supabase"):
        _refresh_supabase_account_profile()
    if _safe_text(st.session_state.get("account_profile_status")) == "error":
        st.warning(
            account_store.customer_safe_error(
                st.session_state.get("account_profile_error", ""),
                context="profile",
            )
        )
    runtime_trace.mark("profile_lookup_complete")
    auth_restore_lifecycle.advance_phase(
        st.session_state,
        auth_restore_lifecycle.RestorePhase.PROFILE_RESOLVED,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "profile_loaded",
        started_at=startup_started_at,
        once=True,
    )
    startup.advance(startup_coordinator.StartupPhase.ENTITLEMENT_LOADING)
    refresh_current_user_entitlement()
    runtime_trace.mark("entitlement_lookup_complete")
    auth_restore_lifecycle.advance_phase(
        st.session_state,
        auth_restore_lifecycle.RestorePhase.ENTITLEMENT_RESOLVED,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "entitlements_loaded",
        started_at=startup_started_at,
        once=True,
    )
    runtime_trace.mark("authentication_complete")
    startup.advance(startup_coordinator.StartupPhase.LEAGUE_RESTORING)
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "league_restore_start",
        started_at=startup_started_at,
        once=True,
    )
    with performance.time_block("saved_league_restoration", category="supabase"):
        # Resume mutates selected_league_id before resolve_active_league_context /
        # player load in this same run — no explicit league rerun required.
        _maybe_auto_resume_supabase_league()
    runtime_trace.mark("league_restore_complete")
    auth_restore_lifecycle.advance_phase(
        st.session_state,
        auth_restore_lifecycle.RestorePhase.LEAGUE_RESTORED,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "league_restored",
        started_at=startup_started_at,
        once=True,
    )
    with performance.time_block("active_league_context_restoration", category="analysis"):
        resolve_active_league_context()
    runtime_trace.mark("session_initialization_complete")

    # Defer public player / valuation work until after identity shell dismiss.
    # Cold DB+FantasyCalc rebuilds must not own the global loading overlay.
    selected_league_present = bool(
        _safe_text(st.session_state.get("selected_league_id")).strip()
    )
    if selected_league_present:
        startup_cold_path.mark_football_pending(st.session_state, True)
        df_players_base = pd.DataFrame()
        runtime_trace.mark("public_player_load_deferred")
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "players_deferred",
            started_at=startup_started_at,
            once=True,
        )
    else:
        startup_cold_path.mark_football_ready(st.session_state)
        df_players_base = pd.DataFrame()
        runtime_trace.mark("public_player_load_deferred")
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "players_deferred",
            started_at=startup_started_at,
            once=True,
        )

    startup.advance(startup_coordinator.StartupPhase.ROUTE_RESTORING)

    # SIDEBAR
    with st.sidebar:
        # Apply league-switch Auto defaults before any override widgets exist.
        _apply_pending_league_settings_override_reset()
        st.header("Sleeper Setup")
        if not _safe_text(st.session_state.get("selected_league_id")).strip():
            st.caption(
                "Fastest path: use the main-page launch flow. These sidebar controls stay available for desktop power users."
            )

        if st.session_state.pop("_sync_sidebar_username_input", False):
            st.session_state["username_input"] = st.session_state.get("username", "")
        elif "username_input" not in st.session_state:
            st.session_state["username_input"] = st.session_state.get("username", "")

        username_input = st.text_input(
            "Sleeper username",
            key="username_input",
            on_change=lambda: load_leagues_for_username(st.session_state.get("username_input", "")),
        )

        if st.button("Load leagues for user"):
            with st.spinner("Loading leagues from Sleeper..."):
                load_leagues_for_username(st.session_state.get("username_input", ""))

        if st.session_state.get("league_lookup_attempted"):
            sidebar_lookup_status = _safe_text(st.session_state.get("league_lookup_status")).strip()
            sidebar_lookup_message = (
                league_lookup_customer_message(sidebar_lookup_status)
                if sidebar_lookup_status != "ok"
                else ""
            )
            if sidebar_lookup_message:
                st.warning(sidebar_lookup_message)

        leagues = st.session_state.get("leagues_for_user", [])
        selected_league_id = None
        selected_league_name = None

        if leagues:
            options = {
                str(lg.get("league_id")): f"{lg.get('name', 'Unnamed league')} (S{lg.get('season', '')})"
                for lg in leagues
            }
            league_ids = list(options.keys())
            current_selected_id = _safe_text(st.session_state.get("selected_league_id")).strip()
            sidebar_league_options = [""] + league_ids
            if st.session_state.pop("_sync_sidebar_league_select", False):
                st.session_state["league_select"] = current_selected_id if current_selected_id in league_ids else ""
            elif "league_select" not in st.session_state:
                st.session_state["league_select"] = current_selected_id if current_selected_id in league_ids else ""

            selected_id = st.selectbox(
                "Select league",
                sidebar_league_options,
                format_func=lambda x: "Choose a league" if not x else options[x],
                key="league_select",
            )
            if selected_id:
                selected_league_id = selected_id
                selected_league_name = options.get(selected_id)
                if str(selected_id) != current_selected_id:
                    set_selected_league(
                        selected_league_id,
                        selected_league_name,
                        route_to_dashboard=not bool(current_selected_id),
                    )
            else:
                selected_league_id = current_selected_id or None
                selected_league_name = _safe_text(st.session_state.get("selected_league_name")) or options.get(current_selected_id)
        else:
            st.caption("Load leagues here if you prefer the sidebar. The same flow is available on the main page.")

        auto_value_settings = (
            st.session_state.get("league_value_settings")
            if startup.active and isinstance(st.session_state.get("league_value_settings"), dict)
            else None
        )
        if not isinstance(auto_value_settings, dict) or not auto_value_settings:
            detect_started = time.perf_counter()
            with performance.time_block("detect_league_value_settings", category="sleeper"):
                auto_value_settings = detect_league_value_settings(selected_league_id)
            startup_cold_path.log_slow_startup_operation(
                "detect_league_value_settings",
                (time.perf_counter() - detect_started) * 1000,
            )
        auto_lens = (
            "Non-Dynasty"
            if auto_value_settings.get("league_format") == "Redraft"
            else "Dynasty"
        )
        if st.session_state.get("league_settings_auto_lens_id") != selected_league_id:
            st.session_state["league_type"] = auto_lens
            st.session_state["league_settings_auto_lens_id"] = selected_league_id

        legacy_lens = st.session_state.get("league_type")
        if legacy_lens == "Redraft / Keeper":
            st.session_state["league_type"] = "Non-Dynasty"
        elif legacy_lens not in {None, "Dynasty", "Rebuild", "Non-Dynasty"}:
            st.session_state["league_type"] = "Dynasty"

        league_value_settings = resolve_league_value_settings(auto_value_settings)
        st.session_state["league_value_settings"] = league_value_settings
        if selected_league_id:
            # During startup, keep identity + valuation lens only. Scoring override
            # expanders and sidebar news are not required to dismiss loading.
            if startup.active:
                league_type = _safe_text(st.session_state.get("league_type"), auto_lens)
                if league_type not in {"Dynasty", "Rebuild", "Non-Dynasty"}:
                    league_type = auto_lens
                st.session_state["league_type"] = league_type
                st.caption(f"Using values for: {format_league_value_settings(league_value_settings)}")
            else:
                league_type = st.selectbox(
                    "Valuation lens",
                    ("Dynasty", "Rebuild", "Non-Dynasty"),
                    key="league_type",
                    help="Choose whether values should lean long-term, future-focused, or current-season.",
                )
                st.caption(
                    "Dynasty keeps balanced long-term value, Rebuild boosts youth and picks, and Non-Dynasty leans current-season production."
                )

                with st.expander("League scoring overrides", expanded=False):
                    st.caption(f"Auto-detected: {format_league_value_settings(auto_value_settings)}")
                    st.caption(format_defaulted_league_settings(auto_value_settings))
                    st.selectbox(
                        "League format",
                        ("Auto", "Dynasty", "Redraft"),
                        key="league_format_override",
                    )
                    st.selectbox(
                        "Scoring",
                        ("Auto", "PPR", "Half-PPR", "Standard"),
                        key="league_scoring_override",
                    )
                    st.selectbox(
                        "QB format",
                        ("Auto", "1QB", "Superflex", "2QB"),
                        key="league_qb_override",
                    )
                    st.selectbox(
                        "TE Premium",
                        ("Auto", "No", "Yes"),
                        key="league_te_premium_override",
                    )
                    st.selectbox(
                        "RB starters",
                        ("Auto", *[str(n) for n in range(0, 6)]),
                        key="league_rb_count_override",
                    )
                    st.selectbox(
                        "WR starters",
                        ("Auto", *[str(n) for n in range(0, 7)]),
                        key="league_wr_count_override",
                    )
                    st.selectbox(
                        "TE starters",
                        ("Auto", *[str(n) for n in range(0, 4)]),
                        key="league_te_count_override",
                    )
                    st.selectbox(
                        "Starting lineup size",
                        ("Auto", *[str(n) for n in range(6, 16)]),
                        key="league_starters_override",
                    )
                    st.selectbox(
                        "Flex spots",
                        ("Auto", *[str(n) for n in range(0, 8)]),
                        key="league_flex_override",
                    )
                    st.selectbox(
                        "Bench size",
                        ("Auto", *[str(n) for n in range(0, 16)]),
                        key="league_bench_override",
                    )
                    st.selectbox(
                        "Taxi size",
                        ("Auto", *[str(n) for n in range(0, 11)]),
                        key="league_taxi_override",
                    )
                    st.selectbox(
                        "IR spots",
                        ("Auto", *[str(n) for n in range(0, 11)]),
                        key="league_ir_override",
                    )
                    st.selectbox(
                        "League size",
                        ("Auto", *[str(n) for n in range(8, 18)]),
                        key="league_size_override",
                    )

                st.caption(f"Using values for: {format_league_value_settings(league_value_settings)}")

                st.markdown("<div class='sidebar-desktop-only'>", unsafe_allow_html=True)
                st.markdown("---")

                st.header("Data & Tools")

                if st.button("Refresh player data"):
                    df_players_base = normalize_player_ids(build_players_table(DB_PATH, refresh=True))
                    st.success(f"Loaded {len(df_players_base)} players.")

                st.subheader("Global News")
                if "news" in st.session_state and st.session_state["news"]:
                    for item in st.session_state["news"][:6]:
                        st.write(f"- [{item['title']}]({item['link']})")
                else:
                    st.info("News loads automatically when you open My Players' News.")
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            league_type = _safe_text(st.session_state.get("league_type"), auto_lens)
            if league_type not in {"Dynasty", "Rebuild", "Non-Dynasty"}:
                league_type = auto_lens
            st.session_state["league_type"] = league_type
            st.caption(
                "League tools, valuation controls, and data utilities will open here after you choose a league from the main launch flow."
            )

        account_actions = account_ui.render_account_panel(
            config=_supabase_config(),
            username=_safe_text(st.session_state.get("username")).strip(),
            selected_league_id=_safe_text(st.session_state.get("selected_league_id")).strip(),
            selected_league_name=_safe_text(st.session_state.get("selected_league_name")).strip(),
            my_roster_id=(
                (
                    st.session_state.get("active_league_context") or {}
                ).get("my_roster_id")
                if _safe_text(st.session_state.get("selected_league_id")).strip()
                and _safe_text(st.session_state.get("username")).strip()
                else None
            ),
        )
        if account_actions.get("resume_league"):
            _resume_saved_supabase_league(account_actions["resume_league"])
            st.rerun()

    league_value_settings = st.session_state.get(
        "league_value_settings",
        dict(DEFAULT_LEAGUE_VALUE_SETTINGS),
    )
    score_field = valuation_score_field(league_type)
    pick_score_multiplier = draft_pick_score_multiplier(league_type, league_value_settings)
    valuation_profile = (
        load_profile_key(
            _safe_text(st.session_state.get("username")).strip(),
            _safe_text(st.session_state.get("selected_league_id")).strip(),
        )
        if _safe_text(st.session_state.get("username")).strip()
        and _safe_text(st.session_state.get("selected_league_id")).strip()
        else {}
    )
    active_valuation_archetype = valuation_archetype_service.resolve_active_archetype(
        league_id=_safe_text(st.session_state.get("selected_league_id")).strip(),
        profile=valuation_profile,
        session_state=st.session_state,
    )
    scoring_rank_context = canonical_player_ranking.resolve_scoring_rank_context(
        league_value_settings,
        override=(
            None
            if _safe_text(st.session_state.get("league_scoring_override"), "Auto") == "Auto"
            else st.session_state.get("league_scoring_override")
        ),
    )
    rank_context_key = (
        f"{score_field}|{league_value_settings_key(league_value_settings)}|"
        f"{scoring_rank_context.scoring_format}|{scoring_rank_context.supported}"
    )
    if st.session_state.get("_canonical_rank_context_key") != rank_context_key:
        canonical_player_ranking.invalidate_rank_columns(st.session_state)
        prepared_player_frame.clear_prepared_player_frame(st.session_state)
        st.session_state["_canonical_rank_context_key"] = rank_context_key
    prepared_rank_season = (
        st.session_state.get("stats_season") or league_value_settings.get("season") or ""
    )
    valuation_context_key = f"{score_field}|{league_value_settings_key(league_value_settings)}"
    if st.session_state.get("trade_asset_score_field") != valuation_context_key:
        st.session_state["trade_send_assets"] = []
        st.session_state["trade_receive_assets"] = []
        st.session_state["trade_asset_score_field"] = valuation_context_key

    workspace_identity = workspace_context.WorkspaceIdentity.from_mapping(
        resolve_active_league_context(),
        fallback_league_name=selected_league_name,
        platform=_safe_text(st.session_state.get("active_platform"), "sleeper"),
    )
    username = workspace_identity.username
    selected_league_id = workspace_identity.league_id or None
    selected_league_name = workspace_identity.league_name
    my_roster_id = workspace_identity.roster_id

    # Defer startup draft detection off the global loader. Use prior-session cache.
    startup_context = st.session_state.get("_cached_startup_draft_context") or {}
    if not isinstance(startup_context, dict):
        startup_context = {}
    startup_mode = bool(
        st.session_state.get("_cached_startup_mode", startup_context.get("startup_mode"))
    )
    rookie_draft_context: dict | None = None
    df_players = pd.DataFrame()
    prepared_frame_signature = "identity"
    shared_league_contexts: dict[tuple[bool, bool, bool, bool], dict] = {}
    shell_league_context: dict | None = None

    def get_rookie_draft_context() -> dict:
        nonlocal rookie_draft_context
        if rookie_draft_context is None:
            rookie_draft_context = (
                cached_rookie_draft_context(
                    selected_league_id,
                    league_settings_items=tuple(
                        sorted((str(k), v) for k, v in league_value_settings.items())
                    ),
                )
                if selected_league_id
                else {}
            )
        return rookie_draft_context

    def get_shell_league_context() -> dict:
        """Rank/profile context for chrome — only after football frame exists."""

        nonlocal shell_league_context
        if shell_league_context is not None:
            return shell_league_context
        if df_players.empty or startup_cold_path.football_context_pending(st.session_state):
            return {}

        def _build_shell() -> dict:
            if not selected_league_id or startup_mode:
                return {}
            shell_started = time.perf_counter()
            with performance.time_block("workspace_shell_context_generation", category="analysis"):
                startup_coordinator.log_startup_milestone(
                    st.session_state,
                    "shell_summary_start",
                    started_at=startup_started_at,
                    once=True,
                )
                built = cached_league_shell_context(
                    df_players,
                    selected_league_id,
                    score_field,
                    league_value_settings,
                )
            startup_cold_path.log_slow_startup_operation(
                "workspace_shell_context_generation",
                (time.perf_counter() - shell_started) * 1000,
            )
            startup_coordinator.log_startup_milestone(
                st.session_state,
                "shell_summary_complete",
                started_at=startup_started_at,
                once=True,
            )
            return built

        shell_sig = prepared_player_frame.build_shell_signature(
            frame_signature=prepared_frame_signature,
            league_id=selected_league_id,
            roster_id=my_roster_id,
            score_field=score_field,
            league_settings_key=league_value_settings_key(league_value_settings),
            startup_mode=bool(startup_mode),
        )
        shell_league_context, _ = prepared_player_frame.get_or_build_shared_league_context(
            st.session_state,
            signature=f"shell|{shell_sig}",
            flags=(False, False, False, False),
            builder=_build_shell,
        )
        return shell_league_context

    def get_shared_league_context(
        *,
        include_intelligence: bool = True,
        include_roster_map: bool = True,
        include_trust: bool = True,
        include_maturity: bool = True,
    ) -> dict:
        context_key = (
            include_intelligence,
            include_roster_map,
            include_trust,
            include_maturity,
        )
        if context_key in shared_league_contexts:
            return shared_league_contexts[context_key]
        if df_players.empty:
            return {}

        def _build_shared() -> dict:
            if not selected_league_id or startup_mode:
                return {}
            with performance.time_block("shared_league_context_generation", category="analysis"):
                return cached_league_context(
                    df_players,
                    selected_league_id,
                    score_field,
                    league_value_settings,
                    startup_context=startup_context,
                    include_intelligence=include_intelligence,
                    include_roster_map=include_roster_map,
                    include_trust=include_trust,
                    include_maturity=include_maturity,
                )

        shared_sig = prepared_player_frame.build_shell_signature(
            frame_signature=prepared_frame_signature,
            league_id=selected_league_id,
            roster_id=my_roster_id,
            score_field=score_field,
            league_settings_key=league_value_settings_key(league_value_settings),
            startup_mode=bool(startup_mode),
        )
        context, _shared_hit = prepared_player_frame.get_or_build_shared_league_context(
            st.session_state,
            signature=shared_sig,
            flags=context_key,
            builder=_build_shared,
        )
        shared_league_contexts[context_key] = context
        return context

    def _build_identity_shell_chrome_bundle() -> dict:
        """First-useful chrome: roster identity only — no league summary / valued ranks."""

        profile = {}
        if selected_league_id and my_roster_id is not None:
            with performance.time_block("shell_roster_profile_lookup", category="sleeper"):
                profile = get_roster_profile(selected_league_id, my_roster_id)
            startup_coordinator.log_startup_milestone(
                st.session_state,
                "roster_profiles_ready",
                started_at=startup_started_at,
                once=True,
            )
        strategy = _safe_text(st.session_state.get("active_team_strategy"), "retool") or "retool"
        return shell_chrome_schema.identity_shell_bundle(
            strategy=strategy,
            strategy_label=team_strategy_label(strategy),
            auto_strategy=strategy,
            strategy_override=_safe_text(
                st.session_state.get("team_strategy_override"), "Auto"
            )
            or "Auto",
            profile=profile,
        )

    def _build_shell_chrome_bundle() -> dict:
        """Valued chrome after football frame: strategy + ranks. Never on global loader.

        Roster identity comes from ``my_roster_id`` / roster profile — never from
        assuming ``league_detail_ranks`` already has a ``roster_id`` column.
        Partial/empty/missing-column frames yield identity-safe chrome (no crash).
        """

        strategy = "retool"
        strategy_label = team_strategy_label(strategy)
        auto_strategy = strategy
        strategy_override = "Auto"
        profile = {}
        team_row: dict = {}
        enrichment_pending = True
        if selected_league_id and my_roster_id is not None:
            profile = get_roster_profile(selected_league_id, my_roster_id)
        if (
            selected_league_id
            and username
            and my_roster_id is not None
            and not startup_mode
            and not df_players.empty
        ):
            metrics_started = time.perf_counter()
            shell_context = get_shell_league_context()
            strategy_summary = shell_context.get("team_direction_summary", pd.DataFrame())
            # Schema contract: do not index roster_id unless the valued frame has it.
            strategy_metrics = None
            if shell_chrome_schema.strategy_summary_usable(strategy_summary):
                strategy_metrics = get_team_vs_league(strategy_summary, my_roster_id)
            strategy_profile = load_profile_key(username, selected_league_id)
            auto_strategy, strategy, strategy_override = resolve_team_strategy(
                strategy_metrics,
                strategy_profile,
            )
            strategy_label = team_strategy_label(strategy)
            team_row = shell_chrome_schema.team_row_from_shell_context(
                shell_context,
                my_roster_id,
            )
            enrichment_pending = not bool(team_row)
            startup_cold_path.log_slow_startup_operation(
                "team_metrics_ready",
                (time.perf_counter() - metrics_started) * 1000,
            )
            startup_coordinator.log_startup_milestone(
                st.session_state,
                "team_metrics_ready",
                started_at=startup_started_at,
                once=True,
            )
        return shell_chrome_schema.valued_shell_bundle(
            strategy=strategy,
            strategy_label=strategy_label,
            auto_strategy=auto_strategy,
            strategy_override=strategy_override,
            profile=profile,
            team_row=team_row,
            enrichment_pending=enrichment_pending,
        )

    identity_shell_signature = (
        f"{shell_chrome_schema.IDENTITY_SHELL_PROVENANCE}|{selected_league_id}|"
        f"{my_roster_id}|{league_value_settings_key(league_value_settings)}"
    )
    with performance.time_block("prepared_shell_chrome", category="analysis"):
        with performance.time_block("shell_chrome_bundle_build", category="analysis"):
            shell_chrome, _shell_hit = prepared_player_frame.get_or_build_shell_chrome(
                st.session_state,
                signature=identity_shell_signature,
                builder=_build_identity_shell_chrome_bundle,
            )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "shell_chrome_ready",
        started_at=startup_started_at,
        once=True,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "shell_commit",
        started_at=startup_started_at,
        once=True,
    )
    st.session_state[startup_cold_path.IDENTITY_SHELL_READY_KEY] = True
    auth_restore_lifecycle.advance_phase(
        st.session_state,
        auth_restore_lifecycle.RestorePhase.READY,
    )
    active_team_strategy = _safe_text(shell_chrome.get("active_team_strategy"), "retool") or "retool"
    active_team_strategy_label = _safe_text(
        shell_chrome.get("active_team_strategy_label"),
        team_strategy_label(active_team_strategy),
    )
    auto_team_strategy = _safe_text(shell_chrome.get("auto_team_strategy"), active_team_strategy)
    team_strategy_override = _safe_text(shell_chrome.get("team_strategy_override"), "Auto")
    shell_team_profile = shell_chrome.get("shell_team_profile") or {}
    shell_team_row = shell_chrome.get("shell_team_row") or {}

    st.session_state["active_team_strategy"] = active_team_strategy
    st.session_state["active_team_strategy_label"] = active_team_strategy_label
    strategy_pick_score_multiplier = strategy_adjusted_pick_score_multiplier(
        pick_score_multiplier,
        active_team_strategy,
    )
    strategy_valuation_context_key = f"{valuation_context_key}|{active_team_strategy}"
    if st.session_state.get("trade_asset_strategy_context") != strategy_valuation_context_key:
        st.session_state["trade_send_assets"] = []
        st.session_state["trade_receive_assets"] = []
        st.session_state["trade_asset_strategy_context"] = strategy_valuation_context_key
    runtime_trace.mark("league_data_complete")

    destination_visibility = _destination_visibility_flags()
    # Live Draft discovery is deferred off the first-usable critical path. Use the
    # prior-session cache for nav visibility; refresh after the loading shell exits.
    active_live_draft = bool(st.session_state.get("_cached_live_draft_active"))
    enabled_experimental_keys: list[str] = []
    if active_live_draft:
        enabled_experimental_keys.append("live_draft")
    if gm_targets.experiment_enabled():
        enabled_experimental_keys.append("gm_targets")
    enabled_experimental = tuple(enabled_experimental_keys)
    destination_visibility["enabled_experimental"] = enabled_experimental
    destination_definitions = current_platform_destinations(startup_mode, **destination_visibility)
    destination_lookup = {destination.key: destination for destination in destination_definitions}
    destinations_by_group: dict[str, list] = {}
    for destination in destination_definitions:
        destinations_by_group.setdefault(destination.group, []).append(destination)
    group_order = ["HOME", "ROSTER", "LEAGUE", "TRANSACTIONS", "DRAFT", "INTELLIGENCE", "SUPPORT", "OPS"]
    available_groups = [group for group in group_order if group in destinations_by_group]

    pending_page = _normalize_platform_page(
        _safe_text(st.session_state.pop("_pending_platform_route", "")),
        startup_mode=startup_mode,
    )
    if pending_page in destination_lookup:
        st.session_state["platform_nav_page"] = pending_page
        st.session_state["platform_nav_group"] = destination_lookup[pending_page].group
    else:
        query_page = _normalize_platform_page(_query_param_page(), startup_mode=startup_mode)
        if query_page in destination_lookup:
            st.session_state["platform_nav_page"] = query_page
            st.session_state["platform_nav_group"] = destination_lookup[query_page].group

    normalized_nav_page = _normalize_platform_page(
        _safe_text(st.session_state.get("platform_nav_page")),
        startup_mode=startup_mode,
    )
    if normalized_nav_page:
        st.session_state["platform_nav_page"] = normalized_nav_page
    if "platform_nav_page" not in st.session_state:
        st.session_state["platform_nav_page"] = destination_definitions[0].key if destination_definitions else "dashboard"
    if st.session_state["platform_nav_page"] not in destination_lookup and destination_definitions:
        st.session_state["platform_nav_page"] = destination_definitions[0].key
    if "platform_nav_group" not in st.session_state or st.session_state["platform_nav_group"] not in available_groups:
        fallback_page = destination_lookup.get(st.session_state["platform_nav_page"])
        st.session_state["platform_nav_group"] = fallback_page.group if fallback_page else (available_groups[0] if available_groups else "HOME")

    with st.sidebar:
        st.markdown("---")
        render_sidebar_franchise_card(
            team_name=_safe_text(shell_team_profile.get("team_name"), _safe_text(shell_team_profile.get("username"), brand_identity.PRODUCT_NAME)),
            league_name=_safe_text(selected_league_name, "Select a league"),
            owner_name=owner_handle(shell_team_profile.get("username"), shell_team_profile.get("owner_name", "")),
            avatar_url=_safe_text(shell_team_profile.get("avatar_url")),
            startup_mode=startup_mode,
        )
        st.markdown("<div class='desktop-sidebar-nav'>", unsafe_allow_html=True)
        st.subheader("Navigation")
        current_page = _safe_text(st.session_state.get("platform_nav_page"), "dashboard")
        if current_page not in destination_lookup and destination_definitions:
            current_page = destination_definitions[0].key
            st.session_state["platform_nav_page"] = current_page
        current_page_definition = destination_lookup.get(current_page, destination_definitions[0] if destination_definitions else None)
        for group in available_groups:
            group_destinations = destinations_by_group.get(group, [])
            if not group_destinations:
                continue
            st.caption(group.title())
            for destination in group_destinations:
                st.button(
                    destination.label,
                    key=f"desktop_nav_{destination.key}",
                    use_container_width=True,
                    type="primary" if destination.key == current_page else "secondary",
                    on_click=_commit_platform_destination,
                    args=(destination.key,),
                    kwargs={"source": "sidebar_destination"},
                )
        if current_page_definition is not None:
            st.caption(current_page_definition.purpose)
        st.markdown("</div>", unsafe_allow_html=True)

    if _query_param_page() != current_page:
        st.query_params["page"] = current_page
    st.session_state["current_page"] = current_page
    runtime_trace.mark("route_restore_complete")
    startup.advance(startup_coordinator.StartupPhase.PAGE_READY)
    _render_navigation_scroll_reset(current_page, league_id=_safe_text(selected_league_id))
    page_ready_fingerprint = recommendation_lifecycle.build_context_fingerprint(
        session=st.session_state,
        league_id=_safe_text(selected_league_id),
        roster_id=_safe_text(my_roster_id),
        season=_safe_text(
            st.session_state.get("stats_season") or league_value_settings.get("season")
        ),
        week=_safe_text(league_value_settings.get("week")),
        scoring_format=_safe_text(scoring_rank_context.scoring_format),
        valuation_lens=_safe_text(score_field),
        roster_state_version=_safe_text(
            st.session_state.get(recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY)
        ),
        provider_data_version=league_value_settings_key(league_value_settings),
    )
    recommendation_lifecycle.sync_lifecycle_on_context_change(
        st.session_state,
        page_ready_fingerprint,
        league_id=_safe_text(selected_league_id),
        roster_id=_safe_text(my_roster_id),
        valuation_lens=_safe_text(score_field),
        scoring_format=_safe_text(scoring_rank_context.scoring_format),
    )

    page_note_map = {
        "my_team": "Operational roster management and lineup control.",
        "players": "Canonical player rankings, scanning, and player explanation tools.",
        "gm_targets": "Keep an eye on players you're considering — current rank, ownership, and advice.",
        "player_detail": "Player profile with fit, market, trade, and news context.",
        "rankings": "League Overview for standings, power, franchise value, draft capital, and league insights.",
        "teams": "League team pages for roster comparison, partner context, and league positioning. My Team owns your daily roster decisions.",
        "weekly_report": "Weekly scoreboard, movement, trends, and transaction recap.",
        "trade_hub": "Find realistic trades for your roster — ranked by fit and fairness.",
        "trade_analyzer": "Exact package builder for specific offers once you know the assets.",
        "waivers": "Wire scanning, injury replacements, and lightweight FAAB recommendations.",
        "startup_draft_center": "Draft-first workflow for leagues that are still building rosters.",
        "draft_summary": "Draft Center for rookie status, draft posture, pick strategy, and partner discovery.",
        "live_draft": "Read-only Sleeper live draft assistant for active draft rooms.",
        "news": "Roster-specific news and automatic Sleeper update monitoring.",
        "archetypes": "Supporting franchise identity context for League Overview and Teams.",
        "manager_tendencies": "Supporting manager-behavior context for League Overview and Teams.",
        "premium": "Free and Premium plan preview for FantasyGM Lab.",
        "founder_ops": "Founder-only operational health and read-only diagnostics.",
        "about_disclaimer": "Product information, recommendation limits, and general disclaimer.",
        "terms": "Plain-language terms for using FantasyGM Lab.",
        "privacy": "How FantasyGM Lab may handle usernames, league context, preferences, and feedback.",
        "no_affiliation": "Independent-product and third-party ownership notice.",
    }
    render_platform_topbar(
        page_title=current_page_definition.label,
        page_note=page_note_map.get(current_page, current_page_definition.purpose),
        selected_league_id=_safe_text(selected_league_id),
        selected_league_name=_safe_text(selected_league_name),
        team_profile=shell_team_profile,
        platform=_safe_text(st.session_state.get("active_platform"), "Sleeper"),
        account_label=(
            "Signed in"
            if _safe_text(st.session_state.get(auth_supabase.AUTH_EMAIL_KEY)).strip()
            else "Guest"
        ),
        entitlement_label=current_user_entitlement().title(),
        strategy_label=active_team_strategy_label if not startup_mode else "Startup Mode",
        archetype_label=_safe_text(shell_team_row.get("archetype_label"), "Unclassified" if not startup_mode else "Pre-Roster"),
        power_rank=shell_team_row.get("power_rank") if not startup_mode else None,
        franchise_rank=shell_team_row.get("franchise_rank") if not startup_mode else None,
    )
    if st.session_state.get("account_resume_notice"):
        st.markdown(
            application_shell.shell_ack_html(
                label="Ready",
                message=_safe_text(st.session_state.pop("account_resume_notice")),
            ),
            unsafe_allow_html=True,
        )
    if st.session_state.get("onboarding_preference_notice"):
        st.markdown(
            application_shell.shell_ack_html(
                label="Saved",
                message=_safe_text(st.session_state.pop("onboarding_preference_notice")),
            ),
            unsafe_allow_html=True,
        )
    render_mobile_navigation_shell(
        current_page=current_page,
        current_page_definition=current_page_definition,
        destination_definitions=destination_definitions,
        startup_mode=startup_mode,
    )
    render_mobile_destination_sheet(
        current_page=current_page,
        startup_mode=startup_mode,
        enabled_experimental=enabled_experimental,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "workspace_chrome_ready",
        started_at=startup_started_at,
        once=True,
    )

    # First usable paint: identity shell + navigation are enough. Heavy player /
    # valuation / league-summary work hydrates after the global loader exits.
    startup_critical_path.mark_soft_deadline_if_exceeded(
        st.session_state,
        started_at=startup_started_at,
    )
    degraded_notice = startup_critical_path.consume_degraded_notice(st.session_state)
    if degraded_notice:
        st.caption(degraded_notice)
    if startup.active:
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "loading_dismissed",
            started_at=startup_started_at,
            once=True,
        )
        runtime_trace.mark("first_usable_paint")
        startup.complete()
        if (
            auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in st.session_state
            or auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY in st.session_state
        ) and not st.session_state.get(auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY):
            st.session_state[auth_restore_lifecycle.POST_USABLE_SAVE_RERUN_KEY] = True
            st.rerun()

    # --- Football hydration (after global loading dismiss) ---
    if selected_league_id:
        players_started = time.perf_counter()
        df_players_base = normalize_player_ids(ensure_players(allow_network_refresh=False))
        startup_cold_path.log_slow_startup_operation(
            "ensure_players_startup",
            (time.perf_counter() - players_started) * 1000,
            cache_status="hit" if not df_players_base.empty else "miss",
        )
        runtime_trace.mark("public_player_load_complete")
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "players_ready",
            started_at=startup_started_at,
            once=True,
        )
        if df_players_base.empty:
            st.error("No player data is available. Refresh player data from the sidebar.")
            st.stop()
    else:
        df_players_base = pd.DataFrame()

    prepared_rank_season = (
        st.session_state.get("stats_season") or league_value_settings.get("season") or ""
    )
    prepared_frame_signature = prepared_player_frame.build_frame_signature(
        public_fingerprint=rankings_module.public_player_fingerprint_category(
            rankings_module.public_player_source_fingerprint(DB_PATH)
        ),
        valuation_lens=league_type,
        score_field=score_field,
        league_settings_key=league_value_settings_key(league_value_settings),
        scoring_format=scoring_rank_context.scoring_format,
        scoring_supported=scoring_rank_context.supported,
        archetype_id=getattr(active_valuation_archetype, "id", ""),
        season=prepared_rank_season,
        row_count=len(df_players_base),
    )

    def _build_valued_ranked_players() -> pd.DataFrame:
        valuation_started = time.perf_counter()
        valued = valuation_archetype_service.apply_active_valuation(
            active_valuation_archetype,
            df_players_base,
            league_type,
            league_value_settings,
            engines={
                valuation_archetypes.BALANCED_DYNASTY_ID: apply_valuation_lens,
            },
        )
        startup_cold_path.log_slow_startup_operation(
            "valuation_league_transform_ready",
            (time.perf_counter() - valuation_started) * 1000,
        )
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "valuation_league_transform_ready",
            started_at=startup_started_at,
            once=True,
        )
        ranks_started = time.perf_counter()
        ranked = canonical_player_ranking.attach_canonical_ranks(
            valued,
            scoring_format=scoring_rank_context.scoring_format,
            score_field=score_field,
            season=prepared_rank_season,
            context=scoring_rank_context,
        )
        startup_cold_path.log_slow_startup_operation(
            "ranks_ready",
            (time.perf_counter() - ranks_started) * 1000,
        )
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "ranks_ready",
            started_at=startup_started_at,
            once=True,
        )
        return ranked

    prepared_started = time.perf_counter()
    with performance.time_block("prepared_valued_ranked_frame", category="analysis"):
        df_players, _prepared_frame_hit = prepared_player_frame.get_or_build_valued_ranked_frame(
            st.session_state,
            signature=prepared_frame_signature,
            builder=_build_valued_ranked_players,
        )
    startup_cold_path.log_slow_startup_operation(
        "prepared_valued_ranked_frame",
        (time.perf_counter() - prepared_started) * 1000,
        cache_status="hit" if _prepared_frame_hit else "miss",
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "prepared_frame_ready",
        started_at=startup_started_at,
        once=True,
    )
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "prepared_frame_cache_write",
        started_at=startup_started_at,
        once=True,
    )

    if selected_league_id:
        with performance.time_block("startup_draft_context_lookup", category="analysis"):
            draft_started = time.perf_counter()
            startup_context = cached_startup_draft_context(
                selected_league_id,
                my_roster_id,
                league_settings_items=tuple(
                    sorted((str(k), v) for k, v in league_value_settings.items())
                ),
            )
            startup_cold_path.log_slow_startup_operation(
                "startup_draft_context_lookup",
                (time.perf_counter() - draft_started) * 1000,
            )
        startup_mode = bool(startup_context.get("startup_mode"))
        st.session_state["_cached_startup_draft_context"] = startup_context
        st.session_state["_cached_startup_mode"] = startup_mode
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "startup_draft_context_ready",
            started_at=startup_started_at,
            once=True,
        )

    # Enrich strategy/ranks now that the valued frame exists (post-dismiss).
    if selected_league_id and not df_players.empty and not startup_mode:
        valued_shell_sig = (
            f"{shell_chrome_schema.VALUED_SHELL_PROVENANCE}|"
            + prepared_player_frame.build_shell_signature(
                frame_signature=prepared_frame_signature,
                league_id=selected_league_id,
                roster_id=my_roster_id,
                score_field=score_field,
                league_settings_key=league_value_settings_key(league_value_settings),
                startup_mode=bool(startup_mode),
            )
        )
        with performance.time_block("valued_shell_chrome_enrichment", category="analysis"):
            valued_chrome, _ = prepared_player_frame.get_or_build_shell_chrome(
                st.session_state,
                signature=valued_shell_sig,
                builder=_build_shell_chrome_bundle,
            )
        active_team_strategy = (
            _safe_text(valued_chrome.get("active_team_strategy"), active_team_strategy)
            or active_team_strategy
        )
        active_team_strategy_label = _safe_text(
            valued_chrome.get("active_team_strategy_label"),
            team_strategy_label(active_team_strategy),
        )
        auto_team_strategy = _safe_text(
            valued_chrome.get("auto_team_strategy"), active_team_strategy
        )
        team_strategy_override = _safe_text(
            valued_chrome.get("team_strategy_override"), team_strategy_override
        )
        if valued_chrome.get("shell_team_profile"):
            shell_team_profile = valued_chrome.get("shell_team_profile") or shell_team_profile
        if valued_chrome.get("shell_team_row"):
            shell_team_row = valued_chrome.get("shell_team_row") or shell_team_row
        st.session_state["active_team_strategy"] = active_team_strategy
        st.session_state["active_team_strategy_label"] = active_team_strategy_label
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "shell_bundle_complete",
            started_at=startup_started_at,
            once=True,
        )

    startup_cold_path.mark_football_ready(st.session_state)
    startup_coordinator.log_startup_milestone(
        st.session_state,
        "football_context_ready",
        started_at=startup_started_at,
        once=True,
    )

    # Deferred network player refresh never blocks shell; refresh quietly when queued.
    refreshed_players = startup_cold_path.maybe_refresh_players_after_shell(
        db_path=DB_PATH,
        build_players_table_fn=build_players_table,
        session_state=st.session_state,
    )
    if refreshed_players is not None and not getattr(refreshed_players, "empty", True):
        # Keep this run on the frame already prepared; next run picks up refreshed DB.
        pass
    # League-switch guard: prove cleanup finished before body hydration, then drop.
    if st.session_state.get(league_switch_first_useful.SWITCH_GUARD_KEY):
        league_switch_first_useful.mark_league_switch_milestone("league_switch_first_useful")
        league_switch_first_useful.consume_switch_guard(st.session_state)

    # Refresh Live Draft nav cache after first usable paint (non-blocking for shell).
    # Warm support routes and TTL-fresh sessions skip the Sleeper drafts lookup.
    if (
        selected_league_id
        and _safe_text(st.session_state.get("active_platform"), "sleeper").casefold() == "sleeper"
        and live_draft.should_refresh_live_draft_discovery(
            session=st.session_state,
            league_id=str(selected_league_id),
            current_page=_safe_text(current_page),
        )
    ):
        try:
            with performance.time_block("live_draft_discovery", category="sleeper"):
                discovered_live_draft = live_draft.has_active_live_draft(
                    get_league_drafts(selected_league_id)
                )
            live_draft.mark_live_draft_discovery(
                st.session_state,
                league_id=str(selected_league_id),
                active=discovered_live_draft,
            )
        except Exception:
            st.session_state.setdefault("_cached_live_draft_active", False)

    route_content_started = time.perf_counter()

    # HOME DASHBOARD
    if current_page == "dashboard":
        render_home_dashboard(
            df_players,
            username=username,
            authenticated=bool(auth_supabase.current_user_id(st.session_state)),
            selected_league_id=selected_league_id,
            selected_league_name=selected_league_name,
            my_roster_id=my_roster_id,
            league_settings=league_value_settings,
            score_field=score_field,
            active_team_strategy=active_team_strategy,
            active_team_strategy_label=active_team_strategy_label,
            pick_score_multiplier=pick_score_multiplier,
            startup_mode=startup_mode,
            startup_context=startup_context,
            effective_entitlement=current_user_entitlement(),
            league_context=(
                get_shared_league_context()
                if selected_league_id and my_roster_id is not None and not startup_mode
                else None
            ),
            valuation_archetype=(
                active_valuation_archetype if selected_league_id else None
            ),
        )

    # GM TARGETS (Experimental)
    if current_page == "gm_targets":
        render_page_shell(
            page_key="gm_targets",
            title="GM Targets",
            subtitle="Keep an eye on players you're considering buying, selling, adding, or monitoring.",
            meta_items=[
                ("Experimental", "warning"),
                (selected_league_name or "League", "success"),
            ],
        )
        targets_context = (
            get_shared_league_context(
                include_intelligence=False,
                include_trust=False,
                include_maturity=False,
            )
            if selected_league_id and my_roster_id is not None and not startup_mode
            else {}
        )
        roster_player_map = targets_context.get("roster_player_map", {}) or {}
        my_ids = {
            str(pid)
            for pid in (get_roster_player_ids(selected_league_id, my_roster_id) or [])
        } if selected_league_id and my_roster_id is not None else set()
        team_names: dict[str, str] = {}
        df_summary_local = targets_context.get("df_summary")
        if isinstance(df_summary_local, pd.DataFrame) and not df_summary_local.empty:
            id_col = "roster_id" if "roster_id" in df_summary_local.columns else None
            name_col = (
                "team_name"
                if "team_name" in df_summary_local.columns
                else ("owner" if "owner" in df_summary_local.columns else None)
            )
            if id_col and name_col:
                for _, summary_row in df_summary_local.iterrows():
                    rid = _safe_text(summary_row.get(id_col))
                    tname = _safe_text(summary_row.get(name_col))
                    if rid:
                        team_names[rid] = tname
        scoring_format_label = ""
        try:
            scoring_format_label = _safe_text(scoring_rank_context.scoring_format)
        except Exception:
            scoring_format_label = ""

        def _open_gm_target_player(pid: str) -> None:
            open_player_quick_view(
                pid,
                source_label="GM Targets",
                source_note="Opened from your saved GM Targets.",
            )

        gm_targets_ui.render_gm_targets_workspace(
            session=st.session_state,
            league_id=_safe_text(selected_league_id),
            roster_id=_safe_text(my_roster_id),
            df_players=df_players,
            my_roster_player_ids=my_ids,
            roster_player_map=roster_player_map,
            roster_team_names=team_names,
            scoring_format=scoring_format_label,
            open_player_quick_view=_open_gm_target_player,
            open_destination=lambda key: _commit_platform_destination(
                key, source="gm_targets"
            ),
            cached_headshot_data_url=cached_headshot_data_url,
            render_premium_lock=render_premium_lock,
        )

    # ALL PLAYERS
    if current_page == "players":
        render_page_shell(
            page_key="players",
            title="Players & Picks",
            subtitle="Search the dynasty market, compare ranked players and supported draft capital, then open Player Quick View for deeper context.",
            meta_items=[
                (league_score_label(score_field), "primary"),
                (team_strategy_label(active_team_strategy), "premium"),
            ],
        )
        explorer_context = (
            get_shared_league_context(
                include_intelligence=False,
                include_trust=False,
                include_maturity=False,
            )
            if selected_league_id and my_roster_id is not None and not startup_mode
            else {}
        )
        visible_player_results = player_asset_explorer_ui.render_player_asset_explorer(
            df_players=df_players,
            draft_picks=explorer_context.get("draft_pick_assets", []),
            roster_player_map=explorer_context.get("roster_player_map", {}),
            score_field=score_field,
            score_label=league_score_label(score_field),
            search_assets=search_trade_assets,
            render_player_scan_cards=render_player_scan_cards,
            is_injury_status=is_injury_status,
            pick_score_multiplier=pick_score_multiplier,
            current_draft_year=(
                get_rookie_draft_context().get("draft_year")
                if selected_league_id
                else None
            ),
        )

        with st.expander("Detailed player table", expanded=False):
            detail_section_id = f"players_detailed_table_{selected_league_id or 'public'}"
            if render_deferred_section_gate(
                detail_section_id,
                button_label="Load detailed table",
                note="Load the full table only when you need row-level comparison.",
            ):
                with performance.time_block("players_deferred_detailed_table", category="render"):
                    display_cols = [
                        column
                        for column in [
                            "name",
                            "player_tier",
                            "opportunity_label",
                            "position",
                            "team",
                            "age",
                            "market_score",
                            "dynasty_score",
                            "value_score",
                        ]
                        if column in visible_player_results.columns
                    ]
                    if visible_player_results.empty:
                        st.caption("No visible player results are available for the detailed table.")
                    else:
                        st.dataframe(
                            style_tier_table(
                                format_score_columns(
                                    visible_player_results[display_cols]
                                ).rename(
                                    columns={
                                        "player_tier": "Tier",
                                        "opportunity_label": "Opportunity",
                                    }
                                )
                            ),
                            width="stretch",
                            hide_index=True,
                        )

        with st.expander("Player Explainer", expanded=False):
            explainer_section_id = f"players_explainer_{selected_league_id or 'public'}"
            if render_deferred_section_gate(
                explainer_section_id,
                button_label="Load Player Explainer",
                note="Load explanation controls only when you want a player-specific rationale.",
            ):
                explainer_df = apply_strategy_age_curve(
                    df_players,
                    active_team_strategy,
                    score_field,
                )
                st.caption(
                    f"Uses the shared player model under "
                    f"{league_score_label(score_field).lower()} and the active "
                    f"{team_strategy_label(active_team_strategy).lower()} strategy lens."
                )
                target_name = st.selectbox(
                    "Player",
                    explainer_df["name"].dropna().unique(),
                    key="players_explain_player_sb",
                )
            else:
                target_name = ""
                explainer_df = pd.DataFrame()
            if target_name and st.button("Explain Player", key="players_explain_player_btn"):
                row = explainer_df[explainer_df["name"] == target_name].iloc[0]
                st.caption(
                    f"Tier: {_safe_text(row.get('player_tier'), 'Developmental')} | "
                    f"Opportunity: {_safe_text(row.get('opportunity_label'), 'Unknown')} | "
                    f"{league_score_label(score_field)}: "
                    f"{int(row[score_field]) if pd.notnull(row[score_field]) else 0}"
                )
                text = explain_player_decision(
                    player_name=row["name"],
                    age=int(row["age"]) if pd.notnull(row["age"]) else 0,
                    value=int(row[score_field]) if pd.notnull(row[score_field]) else 0,
                    league_format=compact_league_value_settings(
                        league_value_settings
                    ),
                    player=row.to_dict(),
                    score_field=score_field,
                    score_label=league_score_label(score_field),
                    strategy_label=team_strategy_label(active_team_strategy),
                    context=(
                        f"{league_score_label(score_field)}: "
                        f"{int(row[score_field])} | "
                        f"Dynasty: {int(row.get('dynasty_score', 0))} | "
                        f"Rebuild: {int(row.get('rebuild_score', 0))} | "
                        f"Market score: "
                        f"{int(row.get('market_score', row.get('value', 0)))} | "
                        f"Scarcity score: {int(row.get('scarcity_score', 0))} | "
                        f"Role score: {int(row.get('role_score', 0))} | "
                        f"Opportunity score: "
                        f"{int(row.get('opportunity_score', 0))} | "
                        f"Age penalty: {int(row['age_penalty'])} | "
                        f"Injury: {_safe_text(row.get('injury_level'), 'healthy')} | "
                        f"News factor: {row.get('news_factor', 0.0)}"
                    ),
                )
                st.text(text)

    if current_page == "player_detail":
        render_player_detail_page(
            df_players=df_players,
            username=username,
            selected_league_id=selected_league_id,
            selected_league_name=selected_league_name,
            my_roster_id=my_roster_id,
            league_settings=league_value_settings,
            score_field=score_field,
            active_team_strategy=active_team_strategy,
            pick_score_multiplier=pick_score_multiplier,
        )

    # WAIVERS & FAAB
    if current_page == "waivers":
            render_workflow_continuity_bar(
                "waivers",
                selected_league_id=_safe_text(selected_league_id),
            )
            # Page title lives in the executive command bar.

            platform_adapter = get_sleeper_adapter()
            startup_waiver_blocked = startup_mode and bool(selected_league_id)
            waiver_roster_player_map: dict[str, tuple[str, ...]] = {}
            if startup_waiver_blocked:
                st.info("Startup Draft Center is active for this league. Waiver and FAAB tools unlock after the startup draft completes and rosters are populated.")
                free_agents = pd.DataFrame(columns=df_players.columns)
            elif (
                st.session_state.get("active_platform") == "espn"
                and st.session_state.get("espn_limited_mode")
                and not selected_league_id
            ):
                render_section_header(
                    "ESPN limited review mode",
                    kicker="ESPN Import",
                    note="Waivers are gated for ESPN until free-agent and transaction paths are validated.",
                )
                st.markdown(
                    "<div class='app-degraded-state'>Sleeper remains the full Waivers path. ESPN imports can currently show mapping review and limited status, but they do not yet unlock waiver recommendations or FAAB guidance.</div>",
                    unsafe_allow_html=True,
                )
                free_agents = pd.DataFrame(columns=df_players.columns)
            elif not username or not selected_league_id:
                render_onboarding_handoff(
                    username=username,
                    selected_league_id=selected_league_id,
                    note="Import your Sleeper league to scan waivers, best adds, and FAAB recommendations.",
                )
                st.stop()
            else:
                rosters = platform_adapter.get_rosters(selected_league_id)
                waiver_roster_player_map = _build_roster_player_map(rosters)
                rostered_ids = {
                    str(pid)
                    for player_ids in waiver_roster_player_map.values()
                    for pid in player_ids
                    if pid is not None
                }
                free_agents = df_players[
                    ~df_players["player_id"].astype(str).isin(rostered_ids)
                ].copy()
                free_agents = filter_current_fantasy_players(
                    free_agents,
                    surface="waiver_free_agents",
                )

                free_agents["stale_free_agent"] = False
                if not free_agents.empty:
                    free_agents["stale_free_agent"] = free_agents.apply(
                        is_probably_stale_free_agent,
                        axis=1,
                    )
                    free_agents.loc[
                        free_agents["stale_free_agent"],
                        ["dynasty_score", "value_score"],
                    ] = 0
                    free_agents = free_agents.sort_values(
                        ["stale_free_agent", score_field],
                        ascending=[True, False],
                    )

            avg_wire = (
                int(free_agents[score_field].mean())
                if not free_agents.empty
                else 0
            )
            league_note = (
                f"League ID: {selected_league_id}"
                if selected_league_name
                else "Import a league to rank available players."
            )
            executive_table_ui.render_executive_metric_tiles(
                [
                    {
                        "label": "Available players",
                        "value": str(len(free_agents)),
                        "note": "Current free-agent pool after rostered filters",
                    },
                    {
                        "label": f"Avg Wire {league_score_label(score_field)}",
                        "value": str(avg_wire),
                        "note": "Mean dynasty score across available players",
                    },
                    {
                        "label": "League selected",
                        "value": selected_league_name or "None",
                        "note": league_note,
                    },
                ]
            )

            top_free = []
            for pos in ["QB", "RB", "WR", "TE"]:
                group = free_agents[free_agents["position"] == pos].copy()
                if not group.empty:
                    top_free.append(
                        group.sort_values(score_field, ascending=False).head(20)
                    )
            kickers = free_agents[free_agents["position"] == "K"].copy()
            if not kickers.empty:
                top_free.append(kickers.sort_values(score_field, ascending=False))

            if top_free:
                df_free_display = pd.concat(top_free, ignore_index=True)
            else:
                df_free_display = free_agents.copy()

            free_agents_ranked = free_agents.copy()
            if not free_agents_ranked.empty:
                if "canonical_overall_rank" not in free_agents_ranked.columns and "overall_rank" in free_agents_ranked.columns:
                    free_agents_ranked["canonical_overall_rank"] = free_agents_ranked["overall_rank"]
                if "canonical_position_rank" not in free_agents_ranked.columns and "position_rank" in free_agents_ranked.columns:
                    free_agents_ranked["canonical_position_rank"] = free_agents_ranked["position_rank"]
                stale_series = (
                    free_agents_ranked["stale_free_agent"].fillna(False)
                    if "stale_free_agent" in free_agents_ranked.columns
                    else pd.Series(False, index=free_agents_ranked.index, dtype="bool")
                )
                score_series = pd.to_numeric(
                    free_agents_ranked.get(score_field, 0),
                    errors="coerce",
                ).fillna(0)
                # FA-relative ranks for waiver logic only; canonical_* stay league-global.
                free_agents_ranked["position_rank"] = (
                    free_agents_ranked.groupby("position")[score_field]
                    .rank(method="first", ascending=False)
                    .fillna(0)
                    .astype(int)
                )
                free_agents_ranked["overall_rank"] = (
                    score_series.rank(method="first", ascending=False).fillna(0).astype(int)
                )
                featured_free_agents = free_agents_ranked[
                    (~stale_series) & (score_series > 0)
                ].copy()
                if featured_free_agents.empty:
                    eligible_only = free_agents_ranked[
                        free_agents_ranked.get("is_current_fantasy_eligible", pd.Series(True, index=free_agents_ranked.index))
                        .fillna(False)
                        .astype(bool)
                    ]
                    featured_free_agents = eligible_only[
                        (~eligible_only.get("stale_free_agent", pd.Series(False, index=eligible_only.index)).fillna(False))
                        & (pd.to_numeric(eligible_only.get(score_field), errors="coerce").fillna(0) > 0)
                    ].copy()
            else:
                featured_free_agents = free_agents_ranked.copy()

            waiver_needed_positions: list[str] = []
            free_agent_injury_positions: set[str] = set()
            free_agent_injured_starters = 0
            injury_team_df = pd.DataFrame()
            if selected_league_id and my_roster_id is not None:
                injury_player_ids = {
                    str(pid)
                    for pid in waiver_roster_player_map.get(str(my_roster_id), ())
                    if pid is not None
                }
                if not injury_player_ids:
                    injury_player_ids = {
                        str(pid)
                        for pid in platform_adapter.get_roster_player_ids(
                            selected_league_id, my_roster_id
                        )
                        or []
                        if pid is not None
                    }
                injury_team_df = df_players[df_players["player_id"].astype(str).isin(injury_player_ids)].copy()
                injury_lineup_df = suggest_optimal_lineup(
                    injury_team_df,
                    league_value_settings,
                )
                if not injury_team_df.empty:
                    waiver_summary = cached_team_direction_summary(
                        df_players,
                        selected_league_id,
                        score_field=score_field,
                        lineup_settings=league_value_settings,
                    )
                    waiver_metrics = get_team_vs_league(waiver_summary, my_roster_id)
                    waiver_team_needs = build_team_needs_assessment(
                        injury_team_df,
                        waiver_metrics,
                        league_value_settings,
                        lineup_df=injury_lineup_df,
                    )
                    waiver_needed_positions = get_needed_positions(
                        injury_team_df,
                        waiver_metrics,
                        league_value_settings,
                        include_fallback=False,
                        assessment=waiver_team_needs,
                    )
                injury_context = roster_injury_context(injury_team_df, injury_lineup_df)
                free_agent_injury_positions = {
                    str(pos).upper()
                    for pos in (injury_context.get("injury_need_positions") or set())
                    if str(pos).upper() in {"QB", "RB", "WR", "TE", "K"}
                }
                free_agent_injured_starters = int(injury_context.get("injured_starters") or 0)

            def _annotate_injury_replacement(source_df: pd.DataFrame) -> pd.DataFrame:
                if source_df is None or source_df.empty:
                    return source_df
                annotated = source_df.copy()
                score_fit = pd.to_numeric(annotated.get(score_field, 0), errors="coerce").fillna(0) > 0
                stale_fit = ~annotated.get(
                    "stale_free_agent",
                    pd.Series(False, index=annotated.index, dtype="bool"),
                ).fillna(False)
                fit_mask = (
                    annotated.get("position", pd.Series("", index=annotated.index))
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .isin(free_agent_injury_positions)
                ) & ~annotated.apply(is_injury_status, axis=1) & score_fit & stale_fit
                annotated["injury_replacement_fit"] = fit_mask
                annotated["injury_replacement_note"] = annotated.apply(
                    lambda row: (
                        f"Healthy cover for your injury-hit {str(row.get('position') or '').upper()} room."
                        if bool(row.get("injury_replacement_fit"))
                        else ""
                    ),
                    axis=1,
                )
                return annotated

            featured_free_agents = _annotate_injury_replacement(featured_free_agents)
            df_free_display = _annotate_injury_replacement(df_free_display)
            if not featured_free_agents.empty and "injury_replacement_fit" in featured_free_agents.columns:
                featured_free_agents = featured_free_agents.sort_values(
                    ["injury_replacement_fit", score_field],
                    ascending=[False, False],
                )
            waiver_display_cols = [
                "name",
                "player_tier",
                "opportunity_label",
                "position",
                "team",
                "age",
                "market_score",
                "age_penalty",
                "scarcity_score",
                "role_score",
                "dynasty_score",
                "value_score",
                score_field,
                "injury_replacement_fit",
            ]
            waiver_display_cols = [
                column_name
                for column_name in waiver_display_cols
                if column_name in df_free_display.columns
            ]
            waiver_display_cols = list(dict.fromkeys(waiver_display_cols))

            st.caption(
                "Showing the best available players not currently on a roster in this league. "
                "Only active NFL players are shown; stale or retired profiles are pushed to the bottom and scored at zero."
            )

            if not startup_waiver_blocked and selected_league_id and not free_agents_ranked.empty:
                is_premium = current_user_is_premium()
                if is_premium:
                    stash_candidates = featured_free_agents[
                        (pd.to_numeric(featured_free_agents.get("age"), errors="coerce").fillna(99) <= 24)
                        | featured_free_agents.get("opportunity_label", pd.Series("", index=featured_free_agents.index)).fillna("").isin(["Backup With Upside", "Starter At Risk", "Committee Back"])
                    ].drop_duplicates(subset=["player_id"])
                    watchlist_candidates = featured_free_agents[
                        ~featured_free_agents["player_id"].astype(str).isin(
                            set(featured_free_agents.head(6)["player_id"].astype(str))
                        )
                    ].copy()
                    faab_targets = free_agents_ranked[
                        (~free_agents_ranked.get("stale_free_agent", pd.Series(False, index=free_agents_ranked.index, dtype="bool")).fillna(False))
                        & (pd.to_numeric(free_agents_ranked.get(score_field, 0), errors="coerce").fillna(0) > 0)
                    ].sort_values(score_field, ascending=False)
                else:
                    stash_candidates = featured_free_agents.iloc[0:0].copy()
                    watchlist_candidates = featured_free_agents.iloc[0:0].copy()
                    faab_targets = free_agents_ranked.iloc[0:0].copy()
                priority_adds = waivers_ui.rank_priority_add_candidates(
                    featured_free_agents,
                    score_field=score_field,
                    needed_positions=waiver_needed_positions,
                    league_settings=league_value_settings,
                    roster_df=injury_team_df,
                    max_items=6,
                )
                waivers_ui.render_waiver_workspace_sections(
                    free_agents_ranked=free_agents_ranked,
                    featured_free_agents=featured_free_agents,
                    priority_adds=priority_adds,
                    stash_candidates=stash_candidates,
                    watchlist_candidates=watchlist_candidates,
                    faab_targets=faab_targets,
                    df_free_display=df_free_display,
                    waiver_display_cols=waiver_display_cols,
                    score_field=score_field,
                    selected_league_id=selected_league_id,
                    needed_positions=waiver_needed_positions,
                    injury_positions=free_agent_injury_positions,
                    injured_starters=free_agent_injured_starters,
                    render_free_agent_summary_cards=render_free_agent_summary_cards,
                    render_free_agent_cards=render_free_agent_cards,
                    add_injury_markers=add_injury_markers,
                    format_score_columns=format_score_columns,
                    is_premium=is_premium,
                    render_premium_lock=render_premium_lock,
                )

                if not is_premium:
                    render_premium_lock(
                        "FAAB Helper",
                        "Bid ranges and injury-adjusted context so you spend FAAB on the right Priority Adds.",
                        feature="Premium Waivers",
                    )
                else:
                    with st.expander("FAAB Helper", expanded=False):
                        st.caption("Use this after choosing a bid target from the priority adds or secondary waiver board.")
                        if not selected_league_id:
                            st.info("Select a league before using the FAAB helper.")
                        else:
                            faab_injury_positions = set(free_agent_injury_positions)
                            faab_injured_starters = int(free_agent_injured_starters or 0)

                            faab_pool = free_agents.copy()
                            if "stale_free_agent" in faab_pool.columns:
                                faab_pool = faab_pool[~faab_pool["stale_free_agent"]].copy()
                            faab_pool = faab_pool[
                                pd.to_numeric(faab_pool["score"], errors="coerce").fillna(0) > 0
                            ].copy()
                            faab_pool = faab_pool.sort_values(score_field, ascending=False)

                            if faab_pool.empty:
                                st.info("No active waiver options with positive FAAB value were found.")
                            else:
                                faab_player_names = faab_pool["name"].dropna().unique()
                                sel_player = st.selectbox(
                                    "Player for FAAB bid",
                                    faab_player_names,
                                    key="faab_player",
                                )
                                faab_starter = st.checkbox(
                                    "Projected starter?", value=False, key="faab_starter"
                                )
                                if st.button("Recommend FAAB"):
                                    row = faab_pool[faab_pool["name"] == sel_player].iloc[0]
                                    faab_score_field = score_field if score_field in row.index else "score"
                                    score = int(row[faab_score_field]) if pd.notnull(row[faab_score_field]) else 0
                                    pos = row.get("position", "")
                                    bid = recommend_faab(
                                        player_score=score,
                                        position=pos,
                                        is_starter=faab_starter,
                                        budget=100,
                                        league_settings=league_value_settings,
                                        status=row.get("status", ""),
                                        injury_status=row.get("injury_status", ""),
                                        injury_need_match=str(pos).upper() in faab_injury_positions and not is_injury_status(row),
                                        team_injury_pressure=faab_injured_starters,
                                    )
                                    st.write(f"Suggested FAAB bid: **${bid}** out of $100.")
                                    if str(pos).upper() in faab_injury_positions and not is_injury_status(row):
                                        st.caption("This healthy add also matches a position where your current starters are injured.")

    # MY TEAM
    if current_page == "my_team":
        startup_team_blocked = False
        if startup_mode and selected_league_id:
            startup_team_blocked = True
            render_page_shell(
                page_key="my_team",
                title="My Team",
                subtitle="Startup Draft Center is now its own destination. My Team unlocks once the startup draft is complete and rosters are populated.",
                meta_items=[
                    ("Startup Mode", "warning"),
                    ("Roster Ops", "primary"),
                ],
            )
            st.info("Use the Startup Draft Center page from the Draft group while the league is still drafting.")
        else:
            render_page_shell(
                page_key="my_team",
                title="My Team",
                subtitle="Roster construction, pressure points, and the next handoff — inspect players in Quick View.",
                meta_items=[
                    (active_team_strategy_label, "premium"),
                    (_safe_text(selected_league_name, "League"), "primary"),
                ],
            )

        if startup_team_blocked:
            pass
        elif (
            st.session_state.get("active_platform") == "espn"
            and st.session_state.get("espn_limited_mode")
            and not selected_league_id
        ):
            render_section_header(
                "ESPN limited review mode",
                kicker="ESPN Import",
                note="My Team is gated for ESPN until roster mapping and page support are fully validated.",
            )
            st.markdown(
                "<div class='app-degraded-state'>Sleeper remains the full My Team path. ESPN imports can currently show mapping review and limited status, but they do not yet unlock roster-management recommendations.</div>",
                unsafe_allow_html=True,
            )
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to open roster decisions, lineup depth, and team outlook.",
            )
        elif my_roster_id is None:
            st.error(
                f"Could not find a roster for username '{username}' in the selected league."
            )
        else:
            render_workflow_continuity_bar(
                "my_team",
                selected_league_id=_safe_text(selected_league_id),
            )
            league_context_my_team = get_shared_league_context()
            roster_player_map_my_team = league_context_my_team.get("roster_player_map") or {}
            player_ids = [
                str(pid)
                for pid in roster_player_map_my_team.get(str(my_roster_id), ())
                if pid is not None
            ]
            if not player_ids:
                player_ids = [
                    str(pid)
                    for pid in get_roster_player_ids(selected_league_id, my_roster_id) or []
                ]
            if not player_ids:
                st.warning("No players found on this roster (Sleeper returned none).")
            else:
                my_team_df = df_players[df_players["player_id"].isin(player_ids)].copy()
                profile = load_profile_key(username, selected_league_id)
                roles_state = {str(k): v for k, v in profile.get("roles", {}).items()}
                role_options = ["Core", "Flex", "Bench"]
                role_weights = {"Core": 1.1, "Flex": 1.0, "Bench": 0.9}

                df_summary_my_team = league_context_my_team.get("team_direction_summary", pd.DataFrame())
                team_metrics = get_team_vs_league(df_summary_my_team, my_roster_id)
                team_profile = get_roster_profile(selected_league_id, my_roster_id)
                auto_team_strategy, active_team_strategy, team_strategy_override = resolve_team_strategy(
                    team_metrics,
                    profile,
                )
                strategy_key = f"team_strategy_select_{selected_league_id}_{my_roster_id}"
                strategy_choice = _safe_text(
                    st.session_state.get(strategy_key, team_strategy_override),
                    team_strategy_override,
                )
                if strategy_choice not in STRATEGY_SELECTOR_OPTIONS:
                    strategy_choice = team_strategy_override
                if strategy_choice != team_strategy_override:
                    team_strategy_override = strategy_choice
                active_team_strategy = (
                    auto_team_strategy
                    if strategy_choice == "Auto"
                    else normalize_team_strategy(strategy_choice, default=auto_team_strategy)
                )
                active_team_strategy_label = team_strategy_label(active_team_strategy)
                st.session_state["active_team_strategy"] = active_team_strategy
                st.session_state["active_team_strategy_label"] = active_team_strategy_label
                profile["strategy_override"] = strategy_choice
                team_metrics = apply_strategy_to_metrics(team_metrics, active_team_strategy)

                player_names = my_team_df["name"].tolist()
                untouchables_state = [
                    n for n in profile.get("untouchables", []) if n in player_names
                ]
                untouchables_key = f"untouchables_ms_{selected_league_id}"
                untouchables = st.session_state.get(untouchables_key, untouchables_state)
                untouchables = [name for name in untouchables if name in player_names]

                for _, row in my_team_df.iterrows():
                    pid = str(row["player_id"])
                    current_role = roles_state.get(pid, "Flex")
                    if current_role not in role_options:
                        current_role = "Flex"
                    role_key = f"role_{pid}"
                    roles_state[pid] = _safe_text(
                        st.session_state.get(role_key, current_role),
                        current_role,
                    )
                    if roles_state[pid] not in role_options:
                        roles_state[pid] = "Flex"

                adjusted_scores = []
                roles_final = []
                for _, row in my_team_df.iterrows():
                    base = row[score_field]
                    role_value = roles_state.get(str(row["player_id"]), "Flex")
                    weight = role_weights.get(role_value, 1.0)
                    adjusted_scores.append(round(base * weight))
                    roles_final.append(role_value)

                my_team_df["role"] = roles_final
                my_team_df["value_score"] = adjusted_scores
                lineup_df = suggest_optimal_lineup(my_team_df, league_value_settings)
                starters = lineup_df[lineup_df["suggested_starter"]].copy()
                bench = lineup_df[~lineup_df["suggested_starter"]].copy()

                profile["roles"] = {str(pid): role for pid, role in roles_state.items()}
                profile["untouchables"] = untouchables
                save_profile_key(username, selected_league_id, profile)

                role_map = {str(pid): role for pid, role in roles_state.items()}
                st.session_state["role_map"] = role_map

                team_needs_assessment = build_team_needs_assessment(
                    my_team_df,
                    team_metrics,
                    league_value_settings,
                    lineup_df=lineup_df,
                )
                major_needed_positions = get_needed_positions(
                    my_team_df,
                    team_metrics,
                    league_value_settings,
                    include_fallback=False,
                    assessment=team_needs_assessment,
                )
                needed_positions = (
                    major_needed_positions
                    if major_needed_positions
                    else get_needed_positions(
                        my_team_df,
                        team_metrics,
                        league_value_settings,
                        include_fallback=True,
                        assessment=team_needs_assessment,
                    )
                )
                with st.spinner("Loading roster analysis..."):
                    with performance.time_block("my_team_advice_generation", category="analysis"):
                        advice_items = build_my_team_advice(
                            my_team_df,
                            lineup_df,
                            team_metrics,
                            league_value_settings,
                            needed_positions=major_needed_positions,
                            assessment=team_needs_assessment,
                        )
                df_display = league_context_my_team.get("league_detail_ranks", pd.DataFrame())
                df_intel = league_context_my_team.get("league_intelligence_frame", pd.DataFrame())
                team_row = df_display[df_display["roster_id"].astype(str) == str(my_roster_id)]
                team_row = team_row.iloc[0] if not team_row.empty else pd.Series(dtype="object")
                intel_row = df_intel[df_intel["roster_id"].astype(str) == str(my_roster_id)]
                intel_row = intel_row.iloc[0] if not intel_row.empty else pd.Series(dtype="object")

                advisor_trade_df = apply_strategy_age_curve(df_players, active_team_strategy, score_field)
                advisor_trade_pool = advisor_trade_df[
                    advisor_trade_df["player_id"].astype(str).isin([str(pid) for pid in player_ids])
                ].copy()
                advisor_pick_multiplier = strategy_adjusted_pick_score_multiplier(
                    pick_score_multiplier,
                    active_team_strategy,
                )
                ideas = cached_trade_ideas(
                    df_players=advisor_trade_df,
                    league_id=selected_league_id,
                    df_summary=df_summary_my_team,
                    my_roster_id=my_roster_id,
                    untouchables=tuple(sorted(str(name) for name in untouchables)),
                    role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
                    score_field=score_field,
                    pick_score_multiplier=advisor_pick_multiplier,
                    team_strategy=active_team_strategy,
                    league_settings_items=draft_pick_valuation_settings_items(league_value_settings),
                    max_ideas=6,
                )
                ideas = enforce_cached_trade_ideas(
                    ideas,
                    df_players=advisor_trade_df,
                    league_id=selected_league_id,
                    df_summary=df_summary_my_team,
                    my_roster_id=my_roster_id,
                    untouchables=tuple(sorted(str(name) for name in untouchables)),
                    trust_context=league_context_my_team.get("trade_trust_context"),
                )

                my_injury_context = roster_injury_context(my_team_df, lineup_df)
                injury_display_context = injury_ui.resolve_team_injury_context(
                    my_injury_context
                )
                injured_starters = _safe_nonnegative_int(
                    injury_display_context.get("active_injured_starters"),
                    _safe_nonnegative_int(
                        injury_display_context.get("injured_starters"),
                        0,
                    ),
                )
                health_flag = injury_ui.team_injury_display_label(
                    injury_display_context,
                    include_uncertainty=True,
                ) or "Stable"
                injury_advice_context = injury_ui.team_injury_advice(
                    injury_display_context
                )
                key_injuries_summary = _safe_text(
                    intel_row.get("key_injuries_summary") or ", ".join(my_injury_context.get("key_injuries") or [])
                )
                injury_need_positions = [
                    str(pos).upper()
                    for pos in (my_injury_context.get("injury_need_positions") or set())
                    if str(pos).upper()
                ]
                acute_injury_pressure = injury_ui.is_acute_injury_pressure(
                    injury_display_context
                )
                trade_summary = franchise_trade_summary(
                    ideas,
                    injury_positions=injury_need_positions,
                    acute_injury_pressure=acute_injury_pressure,
                )
                sell_candidate = select_best_sell_candidate(
                    my_team_df,
                    role_map,
                    untouchables,
                    team_metrics.get("strengths", []),
                    score_field,
                    injury_context=my_injury_context,
                )
                one_year, three_year = franchise_future_outlook(team_row, intel_row, active_team_strategy)
                my_roster_limit = roster_limit_status(
                    league_id=selected_league_id,
                    roster_id=my_roster_id,
                    roster_df=my_team_df,
                    lineup_df=lineup_df,
                    league_settings=league_value_settings,
                    score_field=score_field,
                    active_team_strategy=active_team_strategy,
                    needed_positions=major_needed_positions,
                    surplus_positions=team_metrics.get("strengths", []),
                    untouchables=untouchables,
                )
                free_agent_preview, _, _ = build_home_dashboard_free_agent_preview(
                    df_players,
                    selected_league_id,
                    my_roster_id,
                    score_field,
                    league_value_settings,
                )
                top_waiver = select_top_waiver_opportunity(
                    free_agent_preview,
                    my_team_df,
                    league_value_settings,
                    score_field,
                    needed_positions=major_needed_positions,
                )
                move_candidates_structured = list(my_roster_limit.get("move_candidates_structured") or [])
                trade_candidates_structured = list(my_roster_limit.get("trade_candidates_structured") or [])
                hold_candidates_structured = list(my_roster_limit.get("keep_candidates_structured") or [])
                drop_candidates_structured = list(my_roster_limit.get("drop_candidates_structured") or [])
                headline_trade_idea = _headline_trade_idea(
                    ideas,
                    injury_positions=injury_need_positions,
                    acute_injury_pressure=acute_injury_pressure,
                )
                trade_candidates_structured = prioritize_trade_candidates_with_headline(
                    trade_candidates_structured,
                    headline_idea=headline_trade_idea,
                    my_team_df=my_team_df,
                    untouchables=untouchables,
                )
                if not trade_candidates_structured and sell_candidate:
                    sell_reason = "Most movable asset without weakening your current core too much."
                    trade_candidates_structured = [
                        _build_structured_decision_candidate(
                            sell_candidate,
                            bucket="trade",
                            reason=sell_reason,
                            priority=1,
                            source="sell_candidate",
                        )
                    ]

                roster_notes = []
                if len(my_team_df) >= 6:
                    positions = my_team_df["position"].value_counts().to_dict()
                    if positions.get("QB", 0) < 1:
                        roster_notes.append("You do not currently have a starting QB; add one if required by your league.")
                    if positions.get("RB", 0) < 3:
                        roster_notes.append("Consider adding another RB to improve starting depth and flex coverage.")
                    if positions.get("WR", 0) < 4:
                        roster_notes.append("Add another WR to support WR and flex needs.")
                    if positions.get("TE", 0) < 1:
                        roster_notes.append("You currently lack a TE; adding one gives your roster more lineup flexibility.")
                    if positions.get("K", 0) < 1:
                        roster_notes.append("Add a kicker if your league counts one for starting lineups.")

                    bench_value = float(bench["value_score"].sum())
                    team_value = float(my_team_df["value_score"].sum())
                    if team_value and bench_value / team_value < 0.20:
                        roster_notes.append(
                            "Your bench value is low relative to starters; keep some developmental or upside assets for trades."
                        )
                    if injury_need_positions:
                        roster_notes.append(
                            "Injury-driven weakness: current starter health is pressuring "
                            + " / ".join(injury_need_positions[:2])
                            + " more than the raw talent snapshot alone suggests."
                        )
                    elif injury_advice_context.get("focus") == "future":
                        roster_notes.append(injury_advice_context.get("body"))

                if not roster_notes:
                    roster_notes.append(
                        "Your roster shape appears balanced. Continue monitoring age, bye weeks, and positional value trends."
                    )
                strengths = team_metrics.get("strengths") or []
                weaknesses = [
                    position
                    for position in major_needed_positions
                    if (
                        team_needs_assessment.for_position(position) is not None
                        and team_needs_assessment.for_position(
                            position
                        ).classification
                        == "short_term_need"
                        and not team_needs_assessment.for_position(
                            position
                        ).temporary_injury_pressure
                    )
                ]
                first_advice = advice_items[0] if advice_items else {}
                my_team_need_display = team_need_display(team_needs_assessment)
                biggest_need_label = my_team_need_display["label"].replace(
                    "Biggest Team Need",
                    "Biggest Need",
                )
                biggest_need_value = my_team_need_display["value"]
                biggest_need_note = my_team_need_display["note"]
                trade_target_value = _safe_text(
                    (headline_trade_idea or {}).get("their_player"),
                    trade_summary["buy_low"],
                ) or "No clear trade path"
                trade_target_row = _recommendation_player_row(
                    df_players,
                    player_name=trade_target_value,
                )
                trade_opportunity_note = (
                    (
                        f"Send {_safe_text(trade_summary.get('outgoing_player'))} to {_safe_text(trade_summary['partner'])} for {trade_target_value}. "
                        if _safe_text(trade_summary.get("outgoing_player")) and trade_target_value != "No clear trade path"
                        else f"Partner: {_safe_text(trade_summary['partner'])}. "
                    )
                    + _truncate_text(trade_summary["rationale"], 110)
                )
                waiver_value = player_display_name(top_waiver) if not top_waiver.empty else "No urgent add"
                waiver_note = _safe_text(
                    top_waiver.get("injury_replacement_note")
                    or top_waiver.get("opportunity_explanation")
                    or top_waiver.get("opportunity_label"),
                    "The wire is stable enough that no immediate move is forced.",
                )
                injury_alert = injury_ui.my_team_injury_alert(
                    injury_display_context
                )
                injury_alert_value = injury_alert["value"]
                injury_alert_note = injury_alert["note"]
                roster_limit_value = (
                    f"Over by {int(my_roster_limit.get('over_by') or 0)}"
                    if my_roster_limit.get("over_limit")
                    else f"{int(my_roster_limit.get('current_roster_size') or 0)} / {int(my_roster_limit.get('max_roster_size') or 0)}"
                )
                roster_counted = int(my_roster_limit.get("current_roster_size") or 0)
                roster_total = int(my_roster_limit.get("total_rostered_players") or roster_counted)
                roster_exempt = int(my_roster_limit.get("exempt_player_count") or 0)
                roster_exempt_parts = []
                if int(my_roster_limit.get("taxi_count") or 0) > 0:
                    roster_exempt_parts.append(f"{int(my_roster_limit.get('taxi_count') or 0)} taxi")
                if int(my_roster_limit.get("reserve_count") or 0) > 0:
                    roster_exempt_parts.append(f"{int(my_roster_limit.get('reserve_count') or 0)} IR")
                roster_limit_note = (
                    (
                        f"Sleeper is counting {roster_counted} active players from {roster_total} total rostered."
                        + (
                            f" {roster_exempt} exempt via "
                            + " / ".join(roster_exempt_parts)
                            + "."
                            if roster_exempt > 0 and roster_exempt_parts
                            else ""
                        )
                        + " Use exempt moves first, then trade or cut from surplus depth."
                    )
                    if my_roster_limit.get("over_limit")
                    else (
                        (
                            f"Sleeper is counting {roster_counted} active players"
                            + (
                                f" from {roster_total} total rostered; {roster_exempt} are exempt."
                                if roster_exempt > 0
                                else "."
                            )
                            + " Surplus: "
                            + ", ".join(my_roster_limit.get("strongest_surplus_positions") or ["None"])
                            + " | Thin: "
                            + ", ".join(my_roster_limit.get("thinnest_positions") or ["None"])
                        )
                    )
                )
                immediate_value = _safe_text(first_advice.get("title"), "Roster is stable")
                immediate_note = _safe_text(
                    first_advice.get("body"),
                    "No urgent roster action is standing out right now.",
                )
                primary_recommendation = select_my_team_primary_recommendation(
                    roster_limit_context=my_roster_limit,
                    acute_injury_pressure=acute_injury_pressure,
                    health_flag=health_flag,
                    injured_starters=injured_starters,
                    injury_alert_note=injury_alert_note,
                    headline_trade_idea=headline_trade_idea,
                    trade_summary=trade_summary,
                    top_waiver=top_waiver,
                    advice_items=advice_items,
                    major_needed_positions=major_needed_positions,
                    trade_candidates=trade_candidates_structured,
                    drop_candidates=drop_candidates_structured,
                    move_candidates=move_candidates_structured,
                )
                immediate_value = _safe_text(primary_recommendation.get("value"), immediate_value)
                immediate_note = _safe_text(primary_recommendation.get("note"), immediate_note)
                immediate_tone = _safe_text(primary_recommendation.get("tone"), "trade")

                core_assets_df = my_team_df[
                    my_team_df["role"].astype(str).eq("Core")
                    | my_team_df["name"].astype(str).isin(untouchables)
                    | my_team_df.get("player_tier", pd.Series("", index=my_team_df.index)).fillna("").isin(["Elite", "Star", "Core Starter"])
                ].drop_duplicates(subset=["player_id"]).sort_values("value_score", ascending=False)
                untouchables_df = _rows_for_candidate_names(my_team_df, untouchables).sort_values("value_score", ascending=False)
                decision_candidate_rows = list(my_roster_limit.get("candidate_player_rows") or [])
                decision_candidate_df = pd.DataFrame(decision_candidate_rows) if decision_candidate_rows else my_team_df.copy()
                if decision_candidate_df.empty:
                    decision_candidate_df = my_team_df.copy()

                trade_note_map = _structured_candidate_note_map(trade_candidates_structured)
                trade_candidates_df = _rows_for_candidate_player_ids(
                    decision_candidate_df,
                    [item.get("player_id") for item in trade_candidates_structured],
                )

                hold_note_map = _structured_candidate_note_map(hold_candidates_structured)
                hold_candidates_df = _rows_for_candidate_player_ids(
                    decision_candidate_df,
                    [item.get("player_id") for item in hold_candidates_structured],
                )

                drop_note_map = _structured_candidate_note_map(drop_candidates_structured)
                drop_candidates_df = _rows_for_candidate_player_ids(
                    decision_candidate_df,
                    [item.get("player_id") for item in drop_candidates_structured],
                )

                key_backups_df = bench.sort_values("value_score", ascending=False).head(6).copy()
                top_n = my_team_df.sort_values("value_score", ascending=False).head(8).copy()
                draft_watch_needs = draft_watch_positions(
                    needed_positions,
                    my_team_df,
                    lineup_df,
                    injury_context=my_injury_context,
                    league_settings=league_value_settings,
                    team_strategy=active_team_strategy,
                )

                my_team_trade_narrative = None
                if headline_trade_idea is not None:
                    my_team_trade_narrative = (
                        canonical_recommendation_narrative.build_trade_narrative(
                            headline_trade_idea,
                            league_id=_safe_text(selected_league_id),
                            roster_id=_safe_text(my_roster_id),
                            valuation_lens=_safe_text(score_field),
                            source_surface="my_team",
                            target_reason=_trade_target_reason(headline_trade_idea),
                            partner_reason=_trade_partner_reason(headline_trade_idea),
                            confidence_reason=_trade_confidence_reason(headline_trade_idea),
                            confidence_label=_trade_display_confidence_label(
                                headline_trade_idea
                            ),
                            value_verdict=trade_value_verdict(
                                int(headline_trade_idea.get("trade_gain") or 0)
                            ),
                            health_context=_trade_idea_injury_display_context(
                                headline_trade_idea
                            ),
                        )
                    )
                my_team_waiver_narrative = None
                if isinstance(top_waiver, pd.Series) and not top_waiver.empty:
                    waiver_action, _ = waivers_ui.waiver_recommendation_label(
                        top_waiver,
                        _safe_positive_int(top_waiver.get("position_rank"), 99) or 99,
                    )
                    my_team_waiver_narrative = (
                        canonical_recommendation_narrative.build_waiver_narrative(
                            top_waiver,
                            action=waiver_action,
                            reason=waiver_note,
                            league_id=_safe_text(selected_league_id),
                            roster_id=_safe_text(my_roster_id),
                            valuation_lens=_safe_text(score_field),
                            source_surface="my_team",
                        )
                    )
                my_team_next_move_narrative = None
                if (
                    _safe_text(primary_recommendation.get("source"))
                    in {"injury_trade", "headline_trade", "trade"}
                    and my_team_trade_narrative is not None
                ):
                    my_team_next_move_narrative = my_team_trade_narrative
                elif (
                    _safe_text(primary_recommendation.get("source"))
                    in {"injury_waiver", "waiver"}
                    and my_team_waiver_narrative is not None
                ):
                    my_team_next_move_narrative = my_team_waiver_narrative

                my_team_ui.render_my_team_workspace(
                    biggest_need_label=biggest_need_label,
                    biggest_need_value=biggest_need_value,
                    biggest_need_note=biggest_need_note,
                    trade_target_value=trade_target_value,
                    trade_opportunity_note=trade_opportunity_note,
                    trade_target_row=trade_target_row,
                    trade_recommendation_narrative=(
                        my_team_trade_narrative.to_dict()
                        if my_team_trade_narrative is not None
                        else None
                    ),
                    waiver_value=waiver_value,
                    waiver_note=waiver_note,
                    top_waiver=top_waiver,
                    waiver_recommendation_narrative=(
                        my_team_waiver_narrative.to_dict()
                        if my_team_waiver_narrative is not None
                        else None
                    ),
                    next_move_recommendation_narrative=(
                        my_team_next_move_narrative.to_dict()
                        if my_team_next_move_narrative is not None
                        else None
                    ),
                    roster_limit_value=roster_limit_value,
                    roster_limit_note=roster_limit_note,
                    injury_alert_value=injury_alert_value,
                    injury_alert_note=injury_alert_note,
                    immediate_value=immediate_value,
                    immediate_note=immediate_note,
                    immediate_tone=immediate_tone,
                    my_roster_limit=my_roster_limit,
                    core_assets_df=core_assets_df,
                    untouchables_df=untouchables_df,
                    trade_candidates_df=trade_candidates_df,
                    hold_candidates_df=hold_candidates_df,
                    drop_candidates_df=drop_candidates_df,
                    trade_note_map=trade_note_map,
                    hold_note_map=hold_note_map,
                    drop_note_map=drop_note_map,
                    starters=starters,
                    key_backups_df=key_backups_df,
                    strengths=strengths,
                    weaknesses=weaknesses,
                    team_row=team_row,
                    active_team_strategy_label=active_team_strategy_label,
                    auto_team_strategy=auto_team_strategy,
                    health_flag=health_flag,
                    injured_starters=injured_starters,
                    key_injuries_summary=key_injuries_summary,
                    league_rank_rows=df_intel,
                    selected_league_id=selected_league_id,
                    my_roster_id=my_roster_id,
                    score_field=score_field,
                    render_home_command_tiles=render_home_command_tiles,
                    render_roster_limit_alert=render_roster_limit_alert,
                    render_player_scan_cards=render_player_scan_cards,
                    render_roster_utility_debug=render_roster_utility_debug,
                    render_no_team_player_debug=render_no_team_player_debug,
                    render_summary_tiles=render_summary_tiles,
                    player_display_name=player_display_name,
                    format_score=_format_score,
                    format_rank=_format_rank,
                    truncate_text=_truncate_text,
                    team_strategy_label=team_strategy_label,
                    is_premium=current_user_is_premium(),
                    render_premium_lock=render_premium_lock,
                    team_needs_assessment=team_needs_assessment,
                    draft_pick_assets=list(
                        league_context_my_team.get("draft_pick_assets") or []
                    ),
                    league_settings=league_value_settings,
                    advice_items=advice_items,
                )
                with st.expander("Deep Analysis", expanded=False):
                    if not current_user_is_premium():
                        render_premium_lock(
                            "Deep Analysis",
                            "Manual controls, tables, and watchlists when the primary roster workspace is not enough detail.",
                            feature="Premium My Team",
                        )
                    else:
                        render_section_header(
                            "Deep Analysis",
                            kicker="Manual controls & detail",
                            note="Use this section for manual overrides, detailed tables, watchlists, and long-form context.",
                        )

                        strategy_cols = st.columns([1, 1], gap="small")
                        with strategy_cols[0]:
                            st.selectbox(
                                "Team strategy",
                                STRATEGY_SELECTOR_OPTIONS,
                                index=STRATEGY_SELECTOR_OPTIONS.index(strategy_choice),
                                key=strategy_key,
                                help="Auto follows your team's evaluated direction. Manual choices only change how recommendations are ranked.",
                            )
                        with strategy_cols[1]:
                            st.multiselect(
                                "Untouchables",
                                player_names,
                                default=untouchables,
                                key=untouchables_key,
                            )

                        with st.expander("Edit Roles (Core / Flex / Bench)", expanded=False):
                            for _, row in my_team_df.sort_values("value_score", ascending=False).iterrows():
                                pid = str(row["player_id"])
                                current_role = roles_state.get(pid, "Flex")
                                if current_role not in role_options:
                                    current_role = "Flex"
                                st.selectbox(
                                    f"{row['name']} ({row['position']}) role",
                                    role_options,
                                    index=role_options.index(current_role),
                                    key=f"role_{pid}",
                                )

                        with st.expander("1-Year and 3-Year Outlook", expanded=False):
                            outlook_cols = st.columns(2)
                            with outlook_cols[0]:
                                st.markdown("#### 1-Year Outlook")
                                st.write(one_year)
                            with outlook_cols[1]:
                                st.markdown("#### 3-Year Outlook")
                                st.write(three_year)

                        render_section_header(
                            "Draft Watch",
                            kicker="Prospect watchlist",
                            note="Prospects to monitor based on your current roster needs.",
                            compact=True,
                        )
                        render_prospect_watchlist(draft_watch_needs)

                        my_team_display = my_team_df[
                            [
                                "name",
                                "player_tier",
                                "opportunity_label",
                                "position",
                                "team",
                                "age",
                                "value",
                                "market_score",
                                "age_penalty",
                                "scarcity_score",
                                "role_score",
                                "score",
                                "news_factor",
                                "dynasty_score",
                                "role",
                                "value_score",
                            ]
                        ]
                        with st.expander("Detailed Roster Table", expanded=False):
                            st.dataframe(
                                style_tier_table(
                                    add_injury_markers(format_score_columns(my_team_display), my_team_df)
                                    .rename(columns={"player_tier": "Tier", "opportunity_label": "Opportunity"})
                                    .sort_values("value_score", ascending=False)
                                    .reset_index(drop=True)
                                ),
                                width="stretch",
                                hide_index=True,
                            )
                            render_player_detail_picker(
                                my_team_df.sort_values("value_score", ascending=False).reset_index(drop=True),
                                key_prefix=f"my_team_roster_{selected_league_id}_{my_roster_id}",
                                return_page="my_team",
                                source_label="My Team Roster",
                                label="Open a roster player profile",
                                score_field_for_label=score_field,
                            )

                        slot_order = ["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX", "WR/RB", "K", "BENCH"]
                        starters["slot"] = pd.Categorical(starters["slot"], categories=slot_order, ordered=True)
                        with st.expander("Detailed Lineup Tables", expanded=False):
                            starters_display = starters[
                                [
                                    "slot",
                                    "name",
                                    "player_tier",
                                    "opportunity_label",
                                    "position",
                                    "team",
                                    "age",
                                    "dynasty_score",
                                    "value_score",
                                ]
                            ]
                            st.markdown("**Starters**")
                            st.dataframe(
                                add_injury_markers(starters_display, starters)
                                .rename(columns={"player_tier": "Tier", "opportunity_label": "Opportunity"})
                                .sort_values(["slot", "value_score"], ascending=[True, False])
                                .reset_index(drop=True),
                                width="stretch",
                                hide_index=True,
                            )
                            render_player_detail_picker(
                                starters.sort_values(["slot", "value_score"], ascending=[True, False]).reset_index(drop=True),
                                key_prefix=f"my_team_starters_{selected_league_id}_{my_roster_id}",
                                return_page="my_team",
                                source_label="My Team Starters",
                                label="Open a starter profile",
                                score_field_for_label=score_field,
                            )

                            bench_display = bench[
                                [
                                    "name",
                                    "player_tier",
                                    "opportunity_label",
                                    "position",
                                    "team",
                                    "age",
                                    "dynasty_score",
                                    "value_score",
                                ]
                            ]
                            st.markdown("**Bench**")
                            st.dataframe(
                                add_injury_markers(bench_display, bench)
                                .rename(columns={"player_tier": "Tier", "opportunity_label": "Opportunity"})
                                .sort_values("value_score", ascending=False)
                                .reset_index(drop=True),
                                width="stretch",
                                hide_index=True,
                            )
                            render_player_detail_picker(
                                bench.sort_values("value_score", ascending=False).reset_index(drop=True),
                                key_prefix=f"my_team_bench_{selected_league_id}_{my_roster_id}",
                                return_page="my_team",
                                source_label="My Team Bench",
                                label="Open a bench player profile",
                                score_field_for_label=score_field,
                            )

                        render_player_detail_button_grid(
                            top_n,
                            key_prefix=f"my_team_top_players_{selected_league_id}_{my_roster_id}",
                            return_page="my_team",
                            source_label="My Team Top Players",
                            title="Top player profiles",
                            max_buttons=6,
                        )
                        render_trade_workflow_handoff(
                            key_prefix=f"my_team_trade_routes_{selected_league_id}_{my_roster_id}",
                            note="Trade discovery now lives in Trade Hub. Use Trade Analyzer only when you already know the exact package you want to test.",
                        )

    # STARTUP DRAFT CENTER
    if current_page == "startup_draft_center":
        if not selected_league_id:
            render_section_header(
                "Startup Draft Center",
                kicker="Draft Workspace",
                note="Pick a league to check whether startup draft mode is active.",
            )
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to open the draft workspace.",
            )
        elif startup_mode:
            render_startup_draft_center(
                df_players,
                startup_context,
                league_value_settings,
                score_field,
                league_type,
            )
        else:
            render_section_header(
                "Startup Draft Center",
                kicker="Draft Workspace",
                note="This destination is only active before a league has finished its startup draft.",
            )
            render_summary_tiles(
                [
                    {
                        "label": "Status",
                        "value": "Inactive",
                        "note": "Normal roster management is already live for this league.",
                        "tone": "power",
                    },
                    {
                        "label": "Current Mode",
                        "value": "Post-Startup",
                        "note": "Use Dashboard, My Team, and Draft Center for ongoing franchise work.",
                        "tone": "strategy",
                    },
                ]
            )

    # LIVE DRAFT
    if current_page == "live_draft":
        render_page_shell(
            page_key="live_draft",
            title="Live Draft",
            subtitle="Read-only Sleeper draft-room assistant. Picks and recommendations update without submitting anything to Sleeper.",
            meta_items=[
                ("Read Only", "primary"),
                ("[EXPERIMENTAL]", "warning"),
            ],
        )
        if st.session_state.get("active_platform") == "espn":
            st.info("Live Draft is Sleeper-only. ESPN remains limited to import and review.")
        elif not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Load a Sleeper league to open the live draft assistant.",
            )
        else:
            live_rosters = get_rosters(selected_league_id) or []
            live_roster_ids = {
                str(pid)
                for pid in (
                    next(
                        (
                            roster.get("players", [])
                            for roster in live_rosters
                            if str(roster.get("roster_id")) == str(my_roster_id)
                        ),
                        [],
                    )
                    or []
                )
                if pid is not None
            }
            live_roster_df = (
                df_players[df_players["player_id"].astype(str).isin(live_roster_ids)].copy()
                if live_roster_ids
                else pd.DataFrame(columns=df_players.columns)
            )
            live_draft_ui.render_live_draft_page(
                selected_league_id=selected_league_id,
                selected_league_name=selected_league_name,
                username=username,
                my_roster_id=my_roster_id,
                df_players=df_players,
                roster_df=live_roster_df,
                rosters=live_rosters,
                roster_profiles=get_league_roster_profiles(selected_league_id) or {},
                league_settings=league_value_settings,
                score_field=score_field,
                score_label=league_score_label(score_field),
                fetch_league_drafts=get_league_drafts,
                fetch_draft=get_draft,
                fetch_draft_picks=live_draft.fetch_sleeper_draft_picks,
                render_tappable_player_html=_render_tappable_player_html,
                open_player_quick_view=open_player_quick_view,
                open_trade_hub_for_player=_open_trade_hub_from_live_draft_rank,
            )

    # LEAGUE OVERVIEW
    if current_page in {"rankings", "teams", "draft_summary", "manager_tendencies", "archetypes"}:
        startup_league_blocked = False
        forced_league_section = {
            "rankings": "Rankings",
            "teams": "Teams",
            "draft_summary": "Draft",
            "manager_tendencies": "Tendencies",
            "archetypes": "Archetypes",
        }.get(current_page, "Rankings")
        if startup_mode and selected_league_id:
            startup_league_blocked = True
            render_page_shell(
                page_key=current_page,
                title=current_page_definition.label,
                subtitle="League-wide pages unlock after the startup draft completes.",
                meta_items=[
                    ("League Pulse", "primary"),
                    ("Startup Mode", "warning"),
                ],
            )
            st.info("Startup Draft Center is active for this league. League Overview, team pages, and supporting league views unlock automatically after the startup draft is complete.")
        else:
            render_page_shell(
                page_key=current_page,
                title=current_page_definition.label,
                subtitle=page_note_map.get(current_page, "League-wide context and roster comparison."),
                meta_items=[
                    ("League Pulse", "primary"),
                    (selected_league_name or "League", "success"),
                ],
            )

        if startup_league_blocked:
            pass
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to compare teams, draft capital, and current power across the league.",
            )
        else:
            league_context = get_shared_league_context(include_trust=False)
            league_summary_df = league_context.get("team_direction_summary", pd.DataFrame())
            df_summary = league_summary_df
            if league_summary_df.empty:
                st.warning("No rosters found for this league.")
            else:
                draft_picks = league_context.get("draft_pick_assets", [])
                draft_capital_summary = league_context.get("draft_capital_summary", pd.DataFrame())
                df_display = league_context.get("league_detail_ranks", pd.DataFrame())
                # Full intelligence frame (includes archetype refine when available).
                # Do not confuse with shell/summary ranks from first-useful chrome.
                league_intelligence_df = league_context.get(
                    "league_intelligence_frame",
                    pd.DataFrame(),
                )
                df_intel = league_intelligence_df
                maturity_context = league_context.get("league_maturity", {})
                roster_profiles = league_context.get("roster_profiles", {})
                roster_player_map = league_context.get("roster_player_map", {})
                league_section = forced_league_section
                intelligence_ready = bool(
                    select_league_frame_columns(
                        league_intelligence_df,
                        ["roster_id", "archetype_label"],
                        required=["roster_id", "archetype_label"],
                    )
                    is not None
                )

                if league_section == "Draft":
                    render_section_header(
                        "Draft Workspace",
                        kicker="Pick Strategy",
                        note="Start with your own draft posture, then scan likely buyers, sellers, and partner types before opening the full ownership tables.",
                        compact=True,
                    )
                elif league_section != "Rankings":
                    render_section_header(
                        "Teams Snapshot",
                        kicker="League Board",
                        note="Scan the league in layers: standings and power first, then franchise value, draft capital, and insights.",
                        compact=True,
                    )

                if league_section == "Rankings":
                    standings_bundle = league_standings.build_league_standings_bundle(
                        rosters=get_rosters(selected_league_id) or [],
                        roster_profiles=roster_profiles,
                        league=get_league(selected_league_id) or {},
                        team_frame=df_intel,
                    )
                    season_label = _safe_text(standings_bundle.get("season"))
                    week_label = _safe_text(standings_bundle.get("week_label"))
                    standings_note_bits = [
                        "Actual results from league matchups — separate from Power Rankings strength.",
                    ]
                    if week_label:
                        standings_note_bits.insert(0, week_label)
                    standings_title = (
                        f"{season_label} Standings" if season_label else "Standings"
                    )
                    render_section_header(
                        standings_title,
                        kicker="Where you stand",
                        note=" ".join(standings_note_bits),
                    )
                    render_league_standings_board(standings_bundle)
                    st.caption(
                        "Standings = actual results. Boards below = roster strength, dynasty value, and draft capital."
                    )
                    render_section_header(
                        "Power Rankings",
                        kicker="Who is strongest",
                        note="Who is best equipped to win games right now — not who has the best record.",
                    )
                    render_power_rankings_board(
                        df_intel,
                        "Starter-Weighted Score",
                        rank_column="power_rank",
                        score_column="power_score",
                    )
                    render_section_header(
                        "Franchise Value",
                        kicker="Dynasty value",
                        note="Total roster value plus owned draft capital — the long-term asset base.",
                    )
                    render_power_rankings_board(
                        df_intel,
                        "Roster Value + Draft Capital",
                        rank_column="franchise_rank",
                        score_column="franchise_score",
                    )
                    render_section_header(
                        "Draft Capital",
                        kicker="Future capital",
                        note="Who controls upcoming picks. Open Draft Center for pick-by-pick ownership.",
                    )
                    render_power_rankings_board(
                        df_intel,
                        "Draft Capital Score",
                        rank_column="draft_capital_rank",
                        score_column="draft_capital",
                    )
                    concept_items = [
                                {
                                    "label": "Standings",
                                    "title": "Actual results",
                                    "body": "Wins, losses, ties, and points for/against come from league matchup results.",
                                    "tone": "strategy",
                                },
                                {
                                    "label": "Power Rank",
                                    "title": "Current strength",
                                    "body": "Starter quality and usable depth — who can win now.",
                                    "tone": "power",
                                },
                                {
                                    "label": "Franchise Rank",
                                    "title": "Dynasty asset base",
                                    "body": "Full roster value plus owned draft capital.",
                                    "tone": "franchise",
                                },
                                {
                                    "label": "Draft Capital",
                                    "title": "Future picks",
                                    "body": "Relative pick leverage across the league — not a weekly ranking.",
                                    "tone": "opportunity",
                                },
                                {
                                    "label": "Strategy",
                                    "title": "Direction, not ranking",
                                    "body": "What a roster should do next — compete, retool, or rebuild.",
                                    "tone": "strategy",
                                },
                            ]
                    disclosure_html = workspace_ui.client_disclosure_html(
                        "How to read these boards",
                        workspace_ui.concept_band_html(concept_items),
                        css_class="league-overview-how-to-read",
                    )
                    if disclosure_html:
                        st.markdown(disclosure_html, unsafe_allow_html=True)

                    if (
                        maturity_context.get("maturity")
                        == league_maturity.LeagueMaturity.NEW_STARTUP.value
                    ):
                        render_section_header(
                            "Post-Draft Roster Read",
                            kicker="New Startup",
                            note="Current roster construction only. No transaction or matchup history is inferred.",
                        )
                        render_summary_tiles(
                            league_maturity.build_startup_roster_insights(df_intel)
                        )
                    else:
                        render_section_header(
                            "League Insights",
                            kicker="Worth noticing",
                            note="Pressure, direction, and partner posture first — then the clearest league extremes.",
                        )
                        decision_cards = build_league_overview_decision_cards(
                            df_intel,
                            maturity_context,
                        )
                        if decision_cards:
                            st.caption("Primary signals")
                            render_analysis_cards(decision_cards)
                        else:
                            ui_primitives.render_empty_state_panel(
                                "No league signals yet",
                                "Pressure, stuck-middle, and partner posture notes appear here once roster context is available.",
                                kind="no-data",
                                recovery_guidance="Import or refresh the league if this stays empty.",
                            )
                        leader_cards = league_workspace_ui.filter_league_insight_leader_cards(
                            build_league_intelligence_cards(
                                df_intel,
                                score_field,
                                maturity_context,
                            ),
                            omit_labels=(
                                "Most Draft Capital",
                                "Least Draft Capital",
                            ),
                        )
                        if leader_cards:
                            st.caption("Supporting extremes")
                            render_league_intelligence_cards(leader_cards)

                trade_tendencies_available = league_maturity.insight_is_available(
                    "trade_tendencies",
                    maturity_context,
                )
                if league_section == "Tendencies" and not trade_tendencies_available:
                    render_section_header(
                        "Manager Tendencies",
                        kicker="League Behavior",
                        note="Historical behavior is intentionally withheld until repeated completed trades exist.",
                    )
                    st.info(
                        league_maturity.evidence_status(
                            "trade_tendencies",
                            maturity_context,
                        )["message"]
                    )

                if league_section == "Tendencies" and trade_tendencies_available:
                    render_section_header(
                        "Manager Tendencies",
                        kicker="League Behavior",
                        note="Read how each manager tends to trade, build, and use picks before you decide how to approach them.",
                    )
                    st.caption("Supporting context only. Use League Overview for the league-wide state and Teams when you want this behavior applied to one specific roster.")
                    tendencies_table = select_league_frame_columns(
                        league_intelligence_df,
                        [
                            "team_name",
                            "owner_name",
                            "trading_style",
                            "roster_philosophy",
                            "asset_behavior",
                            "activity_level",
                            "manager_evidence_text",
                            "manager_trade_implication",
                        ],
                        required=["team_name", "trading_style"],
                    )
                    if tendencies_table is None:
                        st.info(
                            "Manager tendency detail needs the full league intelligence frame. "
                            "Refresh after league intelligence finishes loading."
                        )
                    else:
                        tendencies_table = tendencies_table.rename(
                            columns={
                                "team_name": "Team",
                                "owner_name": "Owner",
                                "trading_style": "Trading Style",
                                "roster_philosophy": "Roster Philosophy",
                                "asset_behavior": "Asset Behavior",
                                "activity_level": "Activity",
                                "manager_evidence_text": "Evidence",
                                "manager_trade_implication": "Trade Implication",
                            }
                        )
                        executive_table_ui.render_executive_table_disclosure(
                            tendencies_table.reset_index(drop=True),
                            title="Manager tendencies by team",
                            primary_column="Team",
                            secondary_columns=("Trading Style", "Roster Philosophy"),
                            meta_column="Trade Implication",
                            badge_column="Activity",
                            max_summary_rows=12,
                            expander_label="Full manager tendencies table",
                            key_suffix=f"manager_tendencies_{selected_league_id}",
                        )

                        tendency_selector_df = league_intelligence_df.copy()
                        tendency_selector_df["selector_label"] = tendency_selector_df.apply(
                            lambda row: (
                                f"{_safe_text(row.get('team_name'))} | "
                                f"{owner_handle(row.get('owner_username'), row.get('owner_name', 'Owner'))}"
                            ),
                            axis=1,
                        )
                        selected_tendency_label = st.selectbox(
                            "Inspect manager",
                            tendency_selector_df["selector_label"].tolist(),
                            key=f"manager_tendency_select_{selected_league_id}",
                        )
                        selected_tendency_row = tendency_selector_df[
                            tendency_selector_df["selector_label"] == selected_tendency_label
                        ].iloc[0]
                        render_manager_tendencies_summary(
                            selected_tendency_row,
                            compact=True,
                            maturity_context=maturity_context,
                        )

                if league_section == "Archetypes":
                    render_section_header(
                        "League Archetypes",
                        kicker="Franchise Identity",
                        note="This view groups every roster into a more specific dynasty subtype without changing the underlying strategy labels.",
                    )
                    st.caption("Supporting context only. Use League Overview for the league state and Teams when you want archetype context attached to a specific roster.")
                    if not intelligence_ready:
                        st.info(
                            "League archetype detail requires the refined intelligence frame "
                            "(including archetype labels). It is not available from shell/summary context alone."
                        )
                    else:
                        archetype_table = select_league_frame_columns(
                            league_intelligence_df,
                            [
                                "power_rank",
                                "franchise_rank",
                                "team_name",
                                "owner_name",
                                "strategy_display",
                                "archetype_label",
                                "archetype_explanation",
                            ],
                            required=["archetype_label", "team_name"],
                        )
                        if archetype_table is None:
                            st.info("Archetype columns are unavailable for this league frame.")
                        else:
                            archetype_table = archetype_table.rename(
                                columns={
                                    "power_rank": "Power Rank",
                                    "franchise_rank": "Franchise Rank",
                                    "team_name": "Team",
                                    "owner_name": "Owner",
                                    "strategy_display": "Strategy",
                                    "archetype_label": "Archetype",
                                    "archetype_explanation": "Explanation",
                                }
                            )
                            executive_table_ui.render_executive_table_disclosure(
                                archetype_table.reset_index(drop=True),
                                title="Franchise archetypes by team",
                                primary_column="Team",
                                secondary_columns=("Archetype", "Strategy"),
                                meta_column="Explanation",
                                badge_column="Power Rank",
                                max_summary_rows=12,
                                expander_label="Full archetype table",
                                key_suffix=f"archetypes_{selected_league_id}",
                            )

                            archetype_selector_df = league_intelligence_df.copy()
                            archetype_selector_df["selector_label"] = archetype_selector_df.apply(
                                lambda row: (
                                    f"{_safe_text(row.get('team_name'))} | "
                                    f"{_safe_text(row.get('archetype_label'), 'Unclassified')}"
                                ),
                                axis=1,
                            )
                            selected_archetype_label = st.selectbox(
                                "Inspect franchise archetype",
                                archetype_selector_df["selector_label"].tolist(),
                                key=f"archetype_select_{selected_league_id}",
                            )
                            selected_archetype_row = archetype_selector_df[
                                archetype_selector_df["selector_label"] == selected_archetype_label
                            ].iloc[0]
                            render_archetype_summary(selected_archetype_row, compact=True)

                if league_section == "Teams":
                    render_section_header(
                        "Team Pages",
                        kicker="Drill Down",
                        note="Open any roster to compare power, franchise value, strategy, draft capital, and partner context. My Team owns your daily roster decisions.",
                    )
                if "selected_team_roster_id" not in st.session_state:
                    st.session_state["selected_team_roster_id"] = None
                    st.session_state["selected_team_name"] = ""

                def set_selected_team(roster_id, team_name):
                    st.session_state["selected_team_roster_id"] = str(roster_id)
                    st.session_state["selected_team_name"] = str(team_name)

                if league_section == "Teams":
                    team_selector_df = df_display.copy().sort_values(
                        ["power_rank", "franchise_rank", "team_name"],
                        ascending=[True, True, True],
                    )
                    team_selector_df["selector_label"] = team_selector_df.apply(
                        lambda row: (
                            f"P{_format_rank(row.get('power_rank'))} "
                            f"F{_format_rank(row.get('franchise_rank'))} "
                            f"{row['team_name']} | {owner_handle(row.get('owner_username'), row.get('owner_name', 'Owner'))}"
                        ),
                        axis=1,
                    )
                    team_select_key = f"league_team_select_{selected_league_id}"
                    pending_team_roster_id = _safe_text(
                        st.session_state.pop("_pending_selected_team_roster_id", "")
                    ).strip()
                    if pending_team_roster_id:
                        pending_team_rows = team_selector_df[
                            team_selector_df["roster_id"].astype(str).eq(pending_team_roster_id)
                        ]
                        if not pending_team_rows.empty:
                            st.session_state[team_select_key] = _safe_text(
                                pending_team_rows.iloc[0].get("selector_label")
                            )
                    default_roster_id = str(
                        st.session_state.get("selected_team_roster_id")
                        or team_selector_df.iloc[0]["roster_id"]
                    )
                    default_idx = 0
                    for idx, row in team_selector_df.reset_index(drop=True).iterrows():
                        if str(row["roster_id"]) == default_roster_id:
                            default_idx = idx
                            break
                    selected_team_label = st.selectbox(
                        "Choose a team page",
                        team_selector_df["selector_label"].tolist(),
                        index=default_idx,
                        key=team_select_key,
                    )
                    selected_team_row = team_selector_df[
                        team_selector_df["selector_label"] == selected_team_label
                    ].iloc[0]
                    set_selected_team(selected_team_row["roster_id"], selected_team_row["team_name"])
                    st.caption("Choose a team to open its roster and strategy page.")

                    selected_roster_id = st.session_state.get("selected_team_roster_id")
                    selected_team_name = st.session_state.get("selected_team_name")
                    if selected_roster_id:
                        selected_roster_key = str(selected_roster_id)
                        if selected_roster_key not in roster_player_map:
                            st.warning("Could not find that team roster for this league.")
                        else:
                            player_ids = [
                                str(pid)
                                for pid in roster_player_map.get(selected_roster_key, ())
                                if pid is not None
                            ]
                            team_players = df_players[df_players["player_id"].isin(player_ids)].copy()
                            if team_players.empty:
                                st.warning("This roster has no players in the current player database.")
                            else:
                                selected_roster_int = int(pd.to_numeric(pd.Series([selected_roster_id]), errors="coerce").fillna(0).iloc[0])
                                team_metrics = get_team_vs_league(df_summary, selected_roster_int)
                                selected_team_summary = df_intel[
                                    df_intel["roster_id"].astype(str) == str(selected_roster_id)
                                ]
                                selected_team_summary = selected_team_summary.iloc[0].to_dict() if not selected_team_summary.empty else {}
                                selected_draft_row = draft_capital_summary[
                                    draft_capital_summary["roster_id"].astype(str) == str(selected_roster_id)
                                ]
                                selected_draft_row = selected_draft_row.iloc[0].to_dict() if not selected_draft_row.empty else {}
                                selected_profile = roster_profiles.get(str(selected_roster_id), {})
                                is_my_roster_page = my_roster_id is not None and str(selected_roster_id) == str(my_roster_id)

                                team_view = team_players.copy()
                                if "value_score" in team_view.columns:
                                    team_view["value_score"] = pd.to_numeric(team_view["value_score"], errors="coerce").fillna(0)
                                elif score_field in team_view.columns:
                                    team_view["value_score"] = pd.to_numeric(team_view[score_field], errors="coerce").fillna(0)
                                team_profile = {
                                    "team_name": selected_profile.get("team_name") or selected_team_summary.get("team_name", selected_team_name),
                                    "owner_name": selected_profile.get("owner_name") or selected_team_summary.get("owner_name", ""),
                                    "username": selected_profile.get("username") or selected_team_summary.get("owner_username", ""),
                                    "avatar_url": selected_profile.get("avatar_url") or selected_team_summary.get("avatar_url", ""),
                                }
                                selected_injured_starters = _safe_positive_int(selected_team_summary.get("injured_starters"), 0)
                                selected_key_injuries = _safe_text(selected_team_summary.get("key_injuries_summary"))
                                selected_health_label = _team_injury_display_label(selected_team_summary)

                                advice_items = []
                                starters = pd.DataFrame()
                                bench = pd.DataFrame()
                                starters_display = pd.DataFrame()
                                bench_display = pd.DataFrame()
                                team_pick_rows = []
                                roster_score_field = score_field if score_field in team_players.columns else "value_score"
                                roster_table = pd.DataFrame()
                                team_needs_lineup = suggest_optimal_lineup(
                                    team_view,
                                    league_value_settings,
                                )
                                team_needs_assessment = assess_team_needs(
                                    team_view,
                                    team_needs_lineup,
                                    league_value_settings,
                                    relative_weaknesses=list(
                                        (team_metrics or {}).get("weaknesses", [])
                                        or []
                                    ),
                                )

                                if not is_my_roster_page:
                                    advice_items = build_league_team_advice(
                                        team_view,
                                        team_metrics,
                                        selected_draft_row,
                                        len(df_display),
                                        team_needs_assessment,
                                    )
                                    team_view = team_view.sort_values("value_score", ascending=False)
                                    lineup_df = team_needs_lineup
                                    starters = lineup_df[lineup_df["suggested_starter"]].copy()
                                    bench = lineup_df[~lineup_df["suggested_starter"]].copy()
                                    starters_display = starters[
                                        [column for column in ["slot", "name", "player_tier", "opportunity_label", "position", "team", "age", "value_score"] if column in starters.columns]
                                    ]
                                    starters_display = add_injury_markers(starters_display, starters).rename(
                                        columns={
                                            "slot": "Slot",
                                            "name": "Player",
                                            "player_tier": "Tier",
                                            "opportunity_label": "Opportunity",
                                            "position": "Pos",
                                            "team": "Team",
                                            "age": "Age",
                                            "value_score": league_score_label(score_field),
                                        }
                                    )
                                    bench_display = bench[
                                        [column for column in ["name", "player_tier", "opportunity_label", "position", "team", "age", "value_score"] if column in bench.columns]
                                    ]
                                    bench_display = (
                                        add_injury_markers(bench_display, bench)
                                        .rename(
                                            columns={
                                                "name": "Player",
                                                "player_tier": "Tier",
                                                "opportunity_label": "Opportunity",
                                                "position": "Pos",
                                                "team": "Team",
                                                "age": "Age",
                                                "value_score": league_score_label(score_field),
                                            }
                                        )
                                        .sort_values(league_score_label(score_field), ascending=False)
                                    )
                                    team_pick_rows = [
                                        {
                                            "Pick": pick["label"],
                                            "Value": safe_pick_value(pick),
                                            "Original Team": pick.get("original_team_name") or "",
                                        }
                                        for pick in draft_picks
                                        if str(pick.get("owner_roster_id")) == str(selected_roster_id)
                                    ]
                                    team_players = team_players.sort_values(roster_score_field, ascending=False)
                                    roster_table = team_players[
                                        [
                                            column
                                            for column in ["name", "player_tier", "opportunity_label", "position", "team", "age", score_field]
                                            if column in team_players.columns
                                        ]
                                    ].copy()
                                    roster_table = add_injury_markers(roster_table, team_players).rename(
                                        columns={
                                            "name": "Player",
                                            "player_tier": "Tier",
                                            "opportunity_label": "Opportunity",
                                            "position": "Pos",
                                            "team": "Team",
                                            "age": "Age",
                                            score_field: league_score_label(score_field),
                                        }
                                    )

                                league_workspace_ui.render_league_team_workspace(
                                    team_profile=team_profile,
                                    selected_league_name=selected_league_name,
                                    selected_team_summary=selected_team_summary,
                                    selected_draft_row=selected_draft_row,
                                    team_metrics=team_metrics,
                                    league_size=len(df_display),
                                    is_my_roster_page=is_my_roster_page,
                                    selected_league_id=selected_league_id,
                                    selected_roster_id=selected_roster_id,
                                    health_label=selected_health_label,
                                    injured_starters=selected_injured_starters,
                                    key_injuries=selected_key_injuries,
                                    advice_items=advice_items,
                                    starters=starters,
                                    bench=bench,
                                    starters_display=starters_display,
                                    bench_display=bench_display,
                                    team_pick_rows=team_pick_rows,
                                    team_players=team_players,
                                    roster_table=roster_table,
                                    roster_score_field=roster_score_field,
                                    team_logo_html=team_logo_html,
                                    format_score=_format_score,
                                    format_rank=_format_rank,
                                    render_summary_tiles=render_summary_tiles,
                                    render_workspace_handoff=render_workspace_handoff,
                                    render_team_score_details=render_team_score_details,
                                    render_advice_cards=render_advice_cards,
                                    render_player_scan_cards=render_player_scan_cards,
                                    team_needs_assessment=team_needs_assessment,
                                )

                if league_section == "Draft":
                    if (
                        st.session_state.get("active_platform") == "espn"
                        and st.session_state.get("espn_limited_mode")
                        and not selected_league_id
                    ):
                        render_section_header(
                            "ESPN limited review mode",
                            kicker="ESPN Import",
                            note="Draft Center is gated for ESPN until draft board and pick-history support are validated.",
                        )
                        st.markdown(
                            "<div class='app-degraded-state'>Sleeper remains the full Draft Center path. ESPN imports can currently show mapping review and limited status, but they do not yet unlock Draft Assistant recommendations, draft boards, or draft-capital tools.</div>",
                            unsafe_allow_html=True,
                        )
                    elif draft_capital_summary.empty:
                        st.info("No draft-capital data is available for this league yet.")
                    else:
                        draft_year = _safe_positive_int(
                            get_rookie_draft_context().get("draft_year"),
                            datetime.now().year,
                        )
                        draft_workspace = build_draft_workspace_frame(
                            draft_capital_summary,
                            df_intel,
                            draft_year=draft_year,
                        )
                        render_draft_summary_section(
                            get_rookie_draft_context(),
                            draft_workspace,
                            draft_picks,
                        )
                        draft_assistant_roster_ids = {
                            str(pid)
                            for pid in roster_player_map.get(str(my_roster_id), [])
                            if pid is not None
                        }
                        draft_assistant_roster_df = (
                            df_players[
                                df_players["player_id"].astype(str).isin(
                                    draft_assistant_roster_ids
                                )
                            ].copy()
                            if draft_assistant_roster_ids
                            else pd.DataFrame(columns=df_players.columns)
                        )
                        draft_assistant_lineup_df = (
                            suggest_optimal_lineup(
                                draft_assistant_roster_df,
                                league_value_settings,
                            )
                            if not draft_assistant_roster_df.empty
                            else pd.DataFrame()
                        )
                        draft_assistant_render_state = draft_center_ui.render_draft_assistant(
                            league_id=selected_league_id,
                            username=username,
                            my_roster_id=my_roster_id,
                            df_players=df_players,
                            roster_df=draft_assistant_roster_df,
                            lineup_df=draft_assistant_lineup_df,
                            league_settings=league_value_settings,
                            score_field=score_field,
                            score_label=league_score_label(score_field),
                            compact_player_row_html=_compact_player_row_html,
                            render_tappable_player_html=_render_tappable_player_html,
                            open_player_quick_view=open_player_quick_view,
                            format_score=_format_score,
                        )
                        posture_expanded = not bool(
                            (draft_assistant_render_state or {}).get("review_mode")
                        )
                        with st.expander("Draft Posture and Capital", expanded=posture_expanded):
                            render_your_draft_posture(
                                draft_workspace,
                                my_roster_id=my_roster_id,
                            )

                            render_section_header(
                                "League Draft Decision Signals",
                                kicker="Buy, Sell, Pivot",
                                note="This layer turns raw capital into action context: who should be buying picks, selling picks, or changing direction.",
                            )
                            render_analysis_cards(
                                build_draft_decision_cards(draft_workspace)
                            )

                            render_section_header(
                                "Draft Partner Discovery",
                                kicker="Who To Call",
                                note="Use these team types to decide who is most likely to move picks, veterans, or future insulation before you open Trade Hub.",
                            )
                            render_analysis_cards(
                                build_draft_partner_cards(draft_workspace)
                            )

                            render_section_header(
                                "Draft Capital Board",
                                kicker="League Ownership",
                                note="Raw capital still matters. Use the board below to confirm who actually controls the most leverage after the posture and partner context above.",
                            )
                            render_draft_capital_dashboard(
                                draft_workspace,
                                draft_picks,
                            )

                            render_section_header(
                                "Team Pick Inventories",
                                kicker="Ownership Detail",
                                note="The pick lists below answer why the posture matters: who owns the premium outs, who is thin, and which teams have room to move.",
                            )
                            render_analysis_cards(
                                [
                                    {
                                        "label": "How To Read It",
                                        "title": "Use the inventory after you identify the team type",
                                        "items": [
                                            "Pick-rich rebuilders can stay patient or use surplus picks to tier up instead of chasing thin upgrades.",
                                            "Capital-constrained contenders should protect remaining firsts unless the return clearly changes the weekly lineup.",
                                            "Pivot teams are the best place to look for veterans-for-picks or picks-for-starters negotiations.",
                                        ],
                                        "tone": "strategy",
                                    }
                                ]
                            )
                            with st.expander("Detailed pick list by team", expanded=False):
                                render_team_pick_expanders(
                                    draft_workspace,
                                    draft_picks,
                                )

                if league_section == "Rankings":
                    # Core ranking metrics are required; archetype/tendency fields are
                    # intelligence enrichments and must not KeyError when absent.
                    league_intel_detail = select_league_frame_columns(
                        league_intelligence_df,
                        [
                            "power_rank",
                            "franchise_rank",
                            "team_name",
                            "owner_name",
                            "archetype_label",
                            "trading_style",
                            "roster_philosophy",
                            "asset_behavior",
                            "activity_level",
                            "power_score",
                            "franchise_score",
                            "draft_capital",
                            "health_flag",
                            "injury_burden",
                            "injured_starters",
                            "total_score",
                            "starter_score",
                            "bench_score",
                            "raw_roster_score",
                            "avg_age",
                            "qb_score",
                            "rb_score",
                            "wr_score",
                            "te_score",
                            "strategy_display",
                        ],
                        required=["team_name", "power_rank"],
                    )
                    if league_intel_detail is None:
                        st.info(
                            "Full team metrics need league intelligence detail. "
                            "Summary/shell ranks alone are not enough for this table."
                        )
                    else:
                        league_intel_detail = league_intel_detail.rename(
                            columns={
                                "power_rank": "Power Rank",
                                "franchise_rank": "Franchise Rank",
                                "team_name": "Team",
                                "owner_name": "Owner",
                                "archetype_label": "Archetype",
                                "trading_style": "Trading Style",
                                "roster_philosophy": "Roster Philosophy",
                                "asset_behavior": "Asset Behavior",
                                "activity_level": "Activity",
                                "power_score": "Power Score",
                                "franchise_score": "Franchise Score",
                                "draft_capital": "Draft Capital",
                                "health_flag": "Health Status",
                                "injury_burden": "Injury Burden",
                                "injured_starters": "Injured Starters",
                                "total_score": "Starter-Weighted Base Score",
                                "starter_score": "Starter Score",
                                "bench_score": "Bench Score",
                                "raw_roster_score": "Raw Roster Score",
                                "avg_age": "Average Age",
                                "qb_score": "QB Score",
                                "rb_score": "RB Score",
                                "wr_score": "WR Score",
                                "te_score": "TE Score",
                                "strategy_display": "Strategy",
                            }
                        )
                        executive_table_ui.render_executive_table_disclosure(
                            league_intel_detail.reset_index(drop=True),
                            title="Full team metrics",
                            primary_column="Team",
                            secondary_columns=("Power Rank", "Franchise Rank", "Strategy"),
                            meta_column="Power Score",
                            max_summary_rows=12,
                            expander_label="Full team metrics table",
                            key_suffix=f"league_intel_{selected_league_id}",
                        )

    # WEEKLY LEAGUE REPORT
    if current_page == "weekly_report":
        render_section_header(
            "Weekly League Report",
            kicker="Weekly Desk",
            note="Automatic league highlights built from Sleeper matchups, transactions, standings context, Power Rank, Franchise Rank, strategy, injuries, and draft capital.",
        )

        if startup_mode and selected_league_id:
            st.info("Startup Draft Center is active for this league. Weekly reporting unlocks after the startup draft completes and standings start moving.")
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to open weekly results, movement, and transactions.",
            )
        else:
            weekly_report = cached_weekly_league_report(
                df_players,
                selected_league_id,
                score_field,
                league_value_settings,
            )
            if not weekly_report.get("available"):
                st.warning(_safe_text(weekly_report.get("message"), "No weekly league data is available yet."))
            else:
                movement = build_weekly_rank_movement(
                    weekly_report.get("snapshot_rows") or [],
                    selected_league_id,
                    _safe_positive_int(weekly_report.get("report_week"), 0),
                )
                weekly_report_ui.render_weekly_report(
                    weekly_report,
                    movement,
                    format_rank=_format_rank,
                    render_section_header=render_section_header,
                    render_summary_tiles=render_summary_tiles,
                    render_analysis_cards=render_analysis_cards,
                )

    # MY PLAYERS' NEWS
    if current_page == "news":
        render_section_header(
            "News",
            kicker="What matters now",
            note="Player news translated into who owns them in your league and what you should do next.",
        )

        if my_roster_id is None or not selected_league_id:
            st.warning("Roster not found for this username in the selected league.")
        else:
            now = time.time()
            refresh_news = st.button("Refresh news")
            news_context = get_shared_league_context(
                include_intelligence=False,
                include_trust=False,
                include_maturity=False,
            )
            news_roster_player_map = news_context.get("roster_player_map") or {}
            if not news_roster_player_map:
                news_rosters = get_rosters(selected_league_id) or []
                news_roster_player_map = _build_roster_player_map(news_rosters)
            news_roster_profiles = (
                news_context.get("roster_profiles")
                or get_league_roster_profiles(selected_league_id)
                or {}
            )
            league_player_ids = {
                str(player_id)
                for roster_players in news_roster_player_map.values()
                for player_id in roster_players
            }
            league_player_frame = df_players[
                df_players["player_id"].astype(str).isin(league_player_ids)
            ]
            league_player_names = league_player_frame["name"].dropna().tolist()
            league_player_teams = (
                league_player_frame["team"].dropna().astype(str).unique().tolist()
            )

            player_ids = [
                str(pid)
                for pid in news_roster_player_map.get(str(my_roster_id), ())
                if pid is not None
            ]
            if not player_ids:
                player_ids = [
                    str(pid)
                    for pid in get_roster_player_ids(selected_league_id, my_roster_id) or []
                ]
            if not player_ids:
                st.warning("No players found on this roster to match news.")
            else:
                my_team_df = df_players[df_players["player_id"].isin(player_ids)].copy()
                my_names = my_team_df["name"].dropna().tolist()
                roster_teams = my_team_df["team"].dropna().astype(str).unique().tolist()

                st.caption(
                    f"Tracking news for {len(my_names)} roster players "
                    f"(e.g. {', '.join(my_names[:5])}{'...' if len(my_names) > 5 else ''})"
                )

                roster_news_key = f"roster_news_{selected_league_id}_{my_roster_id}"
                roster_news_last_fetch_key = f"{roster_news_key}_last_fetch"
                last_roster_fetch = st.session_state.get(roster_news_last_fetch_key, 0)
                if (
                    refresh_news
                    or roster_news_key not in st.session_state
                    or now - last_roster_fetch > 900
                ):
                    with st.spinner("Loading player-specific news..."):
                        st.session_state[roster_news_key] = fetch_roster_news(
                            my_names,
                            force_refresh=refresh_news,
                        )
                        st.session_state[roster_news_last_fetch_key] = now

                roster_news = st.session_state.get(roster_news_key, [])
                all_news = []
                my_news = []
                if not roster_news:
                    last_fetch = st.session_state.get("news_last_fetch", 0)
                    if refresh_news or not st.session_state.get("news") or now - last_fetch > 900:
                        with st.spinner("Checking fallback NFL headlines..."):
                            st.session_state["news"] = fetch_news() or []
                            st.session_state["news_last_fetch"] = now
                    all_news = st.session_state.get("news", [])
                    my_news = filter_news_for_players(all_news, my_names, roster_teams)

                cached_global_news = all_news or st.session_state.get("news", [])
                league_news = (
                    filter_news_for_players(
                        cached_global_news,
                        league_player_names,
                        league_player_teams,
                    )
                    if cached_global_news and league_player_names
                    else []
                )
                display_news = curate_player_news(
                    [*(roster_news or my_news), *league_news],
                    max_items=12,
                )
                sleeper_updates = []
                if not display_news:
                    sleeper_updates = build_sleeper_roster_updates(my_team_df)
                    display_news = sleeper_updates

                news_status = get_news_status()
                if roster_news:
                    if news_status.get("source") == "roster_cache":
                        st.warning("Player-specific headlines are from cache.")
                    elif news_status.get("source") == "roster_live":
                        st.caption("Loaded player-specific headlines.")
                elif my_news:
                    if news_status.get("source") == "cache":
                        st.warning(
                            "Live news feeds could not be reached, so these matched items are from cached headlines."
                        )
                    elif news_status.get("source") == "live":
                        st.caption("Loaded fallback NFL headlines.")
                elif sleeper_updates:
                    if news_status.get("source") in {"empty", "roster_empty"}:
                        st.warning(
                            "Player-specific headlines could not be reached, so this section is showing automatic Sleeper roster updates."
                        )
                    else:
                        st.caption(
                            "No player-specific headlines matched your roster, so this section is showing automatic Sleeper roster updates."
                        )
                elif news_status.get("source") in {"empty", "roster_empty"}:
                    st.error(
                        "Player-specific headlines could not be reached and no Sleeper roster updates were available."
                    )

                if roster_news:
                    st.caption(
                        f"Showing {len(display_news)} league-relevant items, led by player-specific headlines."
                    )
                elif sleeper_updates and not my_news:
                    st.caption(
                        f"Showing {len(display_news)} automatic Sleeper roster updates. "
                        f"External headline pool: {len(all_news)}."
                    )
                else:
                    st.caption(
                        f"Showing {len(display_news)} league-relevant items from {len(cached_global_news)} cached headlines."
                    )

                if not display_news:
                    league_intelligence_ui.render_league_intelligence_feed(
                        league_intelligence_feed.LeagueIntelligenceFeed(
                            items=(),
                            player_rows_by_id={},
                            player_lookup_count=0,
                        ),
                        score_field=score_field,
                        score_label=league_score_label(score_field),
                        player_card_builder=_compact_player_row_html,
                        render_tappable_player_html=_render_tappable_player_html,
                        open_player_quick_view=open_player_quick_view,
                    )
                else:
                    intelligence_feed = league_intelligence_feed.build_league_intelligence_feed(
                        display_news,
                        df_players,
                        roster_player_map=news_roster_player_map,
                        roster_names=league_intelligence_feed.roster_name_index(
                            {"roster_profiles": news_roster_profiles}
                        ),
                        current_roster_id=_safe_text(my_roster_id),
                        summary_builder=build_quick_news_summary,
                        relative_time_builder=relative_news_time,
                        now_timestamp=now,
                    )
                    league_intelligence_ui.render_league_intelligence_feed(
                        intelligence_feed,
                        score_field=score_field,
                        score_label=league_score_label(score_field),
                        player_card_builder=_compact_player_row_html,
                        render_tappable_player_html=_render_tappable_player_html,
                        open_player_quick_view=open_player_quick_view,
                    )

    # TRADE IDEAS
    if current_page == "trade_hub":
        trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_nav_received")
        trade_hub_focus_player_id = (
            _safe_text(st.session_state.get(f"trade_hub_focus_player_id_{selected_league_id}")).strip()
            if selected_league_id
            else ""
        )
        trade_hub_focus_mode = (
            _safe_text(st.session_state.get(f"trade_hub_focus_mode_{selected_league_id}")).strip()
            if selected_league_id
            else ""
        )
        legacy_trade_hub_player_id = _safe_text(
            st.session_state.pop("trade_hub_player_id", None)
        ).strip()
        if selected_league_id and legacy_trade_hub_player_id and not trade_hub_focus_player_id:
            trade_hub_focus_player_id = legacy_trade_hub_player_id
            trade_hub_focus_mode = trade_hub_focus_mode or "target_player"
            st.session_state[f"trade_hub_focus_player_id_{selected_league_id}"] = (
                trade_hub_focus_player_id
            )
            st.session_state[f"trade_hub_focus_mode_{selected_league_id}"] = (
                trade_hub_focus_mode
            )
        # Page title and War Room context live in the executive command bar.
        render_workflow_continuity_bar(
            "trade_hub",
            selected_league_id=_safe_text(selected_league_id),
            extra_note=_safe_text(
                st.session_state.get(f"trade_hub_home_source_note_{selected_league_id}")
            ),
        )

        if startup_mode and selected_league_id:
            st.info("Startup Draft Center is active for this league. Trade discovery unlocks after the startup draft completes.")
        elif (
            st.session_state.get("active_platform") == "espn"
            and st.session_state.get("espn_limited_mode")
            and not selected_league_id
        ):
            trade_hub_ui.render_trade_hub_section_header(
                "ESPN limited review mode",
                eyebrow="ESPN Import",
                subtitle="Trade Hub is gated for ESPN until free-agent, transaction, and trade partner paths are validated.",
            )
            st.markdown(
                "<div class='app-degraded-state'>Sleeper remains the full Trade Hub path. ESPN imports can currently show mapping review and limited status, but they do not yet unlock trade recommendations.</div>",
                unsafe_allow_html=True,
            )
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league to see trade ideas for your roster.",
            )
            st.stop()
        elif my_roster_id is None:
            st.warning(f"Could not find a roster for username '{username}' in the selected league.")
        else:
            # Board path does not consume league intelligence; keep Trust / roster /
            # maturity. Avoid rebuilding intel on cold Trade Hub after Dashboard.
            with trade_hub_first_useful.stage_timer("canonical_context_resolution"):
                trade_hub_context = get_shared_league_context(
                    include_intelligence=False,
                )
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_context_ready")
            df_summary = trade_hub_context.get("team_direction_summary", pd.DataFrame())
            hub_display = trade_hub_context.get("league_detail_ranks", pd.DataFrame())
            roster_profiles = trade_hub_context.get("roster_profiles", {})
            roster_player_map = trade_hub_context.get("roster_player_map", {})
            profile = load_profile_key(username, selected_league_id)
            untouchables = profile.get("untouchables", [])
            role_map = st.session_state.get("role_map", {})
            with trade_hub_first_useful.stage_timer("roster_team_context"):
                metrics = get_team_vs_league(df_summary, my_roster_id)
                _, automatic_trade_hub_strategy, _ = resolve_team_strategy(metrics, profile)
            automatic_trade_hub_archetype = _safe_text(
                (metrics or {}).get("archetype_label")
                or (metrics or {}).get("archetype")
            )
            # Strategy controls paint before board work (first-useful chrome).
            trade_hub_lens = trade_hub_ui.render_trade_strategy_selector(
                automatic_strategy=automatic_trade_hub_strategy,
                automatic_strategy_label=team_strategy_label(automatic_trade_hub_strategy),
                automatic_archetype=automatic_trade_hub_archetype,
                key=f"trade_hub_strategy_lens_{selected_league_id}_{my_roster_id}",
            )
            trade_hub_strategy = trade_hub_lens["strategy"]
            trade_hub_archetype = trade_hub_lens["archetype"]
            trade_hub_lens_label = (
                trade_hub_lens["selection"]
                if trade_hub_lens["manual"]
                else team_strategy_label(trade_hub_strategy)
            )
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_strategy_ready")
            strategy_frame_signature = trade_hub_first_useful.build_strategy_frame_signature(
                frame_signature=prepared_frame_signature,
                strategy=trade_hub_strategy,
                score_field=score_field,
            )
            with trade_hub_first_useful.stage_timer("strategy_lens_resolution"):
                trade_hub_df, _strategy_frame_hit = trade_hub_first_useful.get_or_build_strategy_frame(
                    st.session_state,
                    signature=strategy_frame_signature,
                    builder=lambda: apply_strategy_age_curve(
                        df_players, trade_hub_strategy, score_field
                    ),
                )
            trade_hub_pick_multiplier = strategy_adjusted_pick_score_multiplier(
                pick_score_multiplier,
                trade_hub_strategy,
            )
            trade_player_dossier_renderer = partial(
                render_trade_player_dossier_content,
                df_players=df_players,
                username=username,
                selected_league_id=selected_league_id,
                my_roster_id=my_roster_id,
                league_settings=league_value_settings,
                score_field=score_field,
                active_team_strategy=trade_hub_strategy,
                pick_score_multiplier=trade_hub_pick_multiplier,
            )
            my_player_ids = {
                str(pid)
                for pid in roster_player_map.get(str(my_roster_id), ())
                if pid is not None
            }
            runtime_trace.count("ownership_map_construction")
            owned_player_to_roster = {
                str(pid): roster_id
                for roster_id, player_ids in roster_player_map.items()
                for pid in player_ids
                if pid is not None
            }
            trade_hub_untouchables_key = tuple(sorted(str(name) for name in untouchables))
            trade_hub_role_items = tuple(
                sorted((str(pid), str(role)) for pid, role in role_map.items())
            )
            trade_hub_entitlement = current_user_entitlement()
            lifecycle_fp = recommendation_lifecycle.load_context_fingerprint(st.session_state)
            presentation_board_signature = (
                trade_hub_first_useful.build_presentation_board_signature(
                    lifecycle_digest=_safe_text(
                        getattr(lifecycle_fp, "digest", "") if lifecycle_fp else ""
                    ),
                    account_scope=_safe_text(
                        getattr(lifecycle_fp, "account_scope", "") if lifecycle_fp else ""
                    ),
                    league_id=_safe_text(selected_league_id),
                    roster_id=_safe_text(my_roster_id),
                    season=_safe_text(
                        st.session_state.get("stats_season")
                        or league_value_settings.get("season")
                    ),
                    week=_safe_text(league_value_settings.get("week")),
                    scoring_format=_safe_text(scoring_rank_context.scoring_format),
                    valuation_lens=_safe_text(score_field),
                    roster_state_version=_safe_text(
                        st.session_state.get(
                            recommendation_lifecycle.ROSTER_STATE_VERSION_SESSION_KEY
                        )
                    ),
                    provider_data_version=league_value_settings_key(league_value_settings),
                    frame_signature=prepared_frame_signature,
                    strategy=trade_hub_strategy,
                    archetype=trade_hub_archetype,
                    score_field=score_field,
                    pick_score_multiplier=trade_hub_pick_multiplier,
                    league_settings_key=league_value_settings_key(league_value_settings),
                    untouchables=trade_hub_untouchables_key,
                    role_items=trade_hub_role_items,
                    entitlement=trade_hub_entitlement,
                    max_ideas=8,
                )
            )

            def render_top_trade_opportunities() -> None:
                board_status = st.empty()

                def _build_presentation_board() -> dict:
                    board_status.caption("Building the trade board…")
                    with trade_hub_first_useful.stage_timer("recommendation_generation"):
                        with st.spinner("Loading trade ideas..."):
                            ideas = cached_trade_ideas(
                                df_players=trade_hub_df,
                                league_id=selected_league_id,
                                df_summary=df_summary,
                                my_roster_id=my_roster_id,
                                untouchables=trade_hub_untouchables_key,
                                role_items=trade_hub_role_items,
                                score_field=score_field,
                                pick_score_multiplier=trade_hub_pick_multiplier,
                                team_strategy=trade_hub_strategy,
                                team_archetype=trade_hub_archetype,
                                league_settings_items=draft_pick_valuation_settings_items(
                                    league_value_settings
                                ),
                                max_ideas=8,
                            )
                    with trade_hub_first_useful.stage_timer("trust_approval_filtering"):
                        ideas = enforce_cached_trade_ideas(
                            ideas,
                            df_players=trade_hub_df,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=trade_hub_untouchables_key,
                            trust_context=trade_hub_context.get("trade_trust_context"),
                        )
                    # Manager tendencies are presentation enrichment only; they do
                    # not affect Trust, scores, or ordering. Still applied before
                    # #1 paint so canonical narratives stay identical.
                    ideas = enrich_trade_ideas_with_manager_tendencies(
                        ideas,
                        df_summary,
                        trade_hub_context.get("league_maturity", {}),
                    )
                    if not ideas:
                        return {
                            "eligible_ideas": [],
                            "presentation": None,
                            "ranked_feed": [],
                            "headline_idea": None,
                            "board_inventory": None,
                            "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
                                []
                            ),
                        }
                    primary_ideas, secondary_ideas = split_trade_surface_ideas(ideas)
                    trade_hub_presentation = trade_hub_ui.trade_hub_entitlement_presentation(
                        primary_ideas,
                        secondary_ideas,
                        entitlement=trade_hub_entitlement,
                    )
                    with trade_hub_first_useful.stage_timer("presentation_ordering"):
                        eligible_ideas = trade_hub_ui.order_trade_hub_visible_ideas(
                            trade_hub_presentation["visible_ideas"]
                        )
                    headline_idea = select_trade_hub_headline_idea(eligible_ideas)
                    grouped_ideas = trade_hub_ui.group_trade_hub_ideas(
                        eligible_ideas,
                        headline_idea=headline_idea,
                    )
                    board_inventory = trade_hub_ui.trade_hub_section_inventory(grouped_ideas)
                    if board_inventory["accessible_count"] != trade_hub_presentation["visible_count"]:
                        raise RuntimeError("Trade Hub presentation count mismatch")
                    ranked_feed = trade_hub_ui.annotate_trade_hub_feed_categories(
                        eligible_ideas,
                        headline_idea=headline_idea,
                    )
                    return {
                        "eligible_ideas": eligible_ideas,
                        "presentation": trade_hub_presentation,
                        "ranked_feed": ranked_feed,
                        "headline_idea": headline_idea,
                        "board_inventory": board_inventory,
                        "equivalence_fingerprint": trade_hub_first_useful.idea_equivalence_fingerprint(
                            eligible_ideas
                        ),
                    }

                board_payload, board_cache_hit = (
                    trade_hub_first_useful.get_or_build_presentation_board(
                        st.session_state,
                        signature=presentation_board_signature,
                        builder=_build_presentation_board,
                    )
                )
                board_status.empty()
                if board_cache_hit:
                    runtime_trace.count("trade_hub_warm_board_reuse")

                trade_hub_presentation = board_payload.get("presentation")
                eligible_ideas = list(board_payload.get("eligible_ideas") or [])
                ranked_feed = list(board_payload.get("ranked_feed") or [])
                headline_idea = board_payload.get("headline_idea")
                board_inventory = board_payload.get("board_inventory")

                if not eligible_ideas or trade_hub_presentation is None:
                    trade_hub_ui.render_trade_hub_empty_state()
                    trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_board_ready")
                    return

                is_premium = trade_hub_presentation["is_premium"]
                trade_hub_ui.render_trade_hub_entitlement_summary(
                    trade_hub_presentation,
                    section_count=int((board_inventory or {}).get("section_count") or 1),
                )
                feed_key = (
                    f"trade_hub_unified_feed_{selected_league_id}_{my_roster_id}_"
                    f"{trade_hub_strategy}"
                )
                visible_count_key = f"{feed_key}_visible"
                # Default reveal two approved ideas when inventory allows; never fabricate.
                default_visible = min(2, max(1, len(ranked_feed))) if ranked_feed else 1
                visible_count = max(
                    1,
                    int(st.session_state.get(visible_count_key, default_visible)),
                )
                if ranked_feed:
                    visible_count = min(visible_count, len(ranked_feed))
                trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_rec1_ready")
                if ranked_feed:
                    @st.fragment
                    def _trade_hub_visible_feed() -> None:
                        # Fragment-scoped reveal: Show more must not rebuild Trade Ideas.
                        local_visible = max(
                            1,
                            int(st.session_state.get(visible_count_key, default_visible)),
                        )
                        local_visible = min(local_visible, len(ranked_feed))
                        trade_hub_render_started = time.perf_counter()
                        with trade_hub_first_useful.stage_timer(
                            "canonical_narrative_construction",
                            category="render",
                        ):
                            for idea_idx, display_idea in enumerate(
                                ranked_feed[:local_visible]
                            ):
                                render_trade_idea_card(
                                    display_idea,
                                    idea_idx,
                                    key_prefix="trade_hub_feed",
                                    render_player_dossier=trade_player_dossier_renderer,
                                )
                                if idea_idx == 0:
                                    trade_hub_first_useful.mark_trade_hub_milestone(
                                        "trade_hub_rec1_rendered"
                                    )
                        performance.record_timing(
                            "trade_hub_visible_cards_render",
                            (time.perf_counter() - trade_hub_render_started) * 1000,
                            category="render",
                            result_size=min(len(ranked_feed), local_visible),
                        )
                        if len(ranked_feed) > local_visible:
                            reveal_count = min(3, len(ranked_feed) - local_visible)
                            st.button(
                                f"Show {reveal_count} more",
                                key=f"{visible_count_key}_more",
                                use_container_width=True,
                                on_click=increment_session_counter,
                                args=(visible_count_key, reveal_count, local_visible),
                            )

                    _trade_hub_visible_feed()
                else:
                    trade_hub_ui.render_trade_hub_empty_state()

                trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_board_ready")

                if trade_hub_presentation["show_board_upgrade"]:
                    render_premium_lock(
                        "Full trade idea board",
                        "See every fair trade idea — not just the Free preview — so you can compare partners and packages.",
                        feature="Premium Trade Hub",
                    )
                if is_premium:
                    with st.expander("Search return paths from one of your players", expanded=False):
                        return_section_id = (
                            f"trade_hub_return_paths_{selected_league_id}_{my_roster_id}"
                        )
                        if render_deferred_section_gate(
                            return_section_id,
                            button_label="Load player return search",
                            note="Secondary search tool. Load it after checking the best board-wide ideas above.",
                        ):
                            # Defer owned-pool DataFrame copy until the tool is opened.
                            trade_ideas_pool = trade_hub_df[
                                trade_hub_df["player_id"].astype(str).isin(my_player_ids)
                            ].copy()
                            with performance.time_block(
                                "trade_hub_deferred_return_search",
                                category="analysis",
                            ):
                                render_trade_return_explorer(
                                    all_players_df=trade_hub_df,
                                    owned_player_df=trade_ideas_pool,
                                    league_id=selected_league_id,
                                    df_summary=df_summary,
                                    my_roster_id=my_roster_id,
                                    untouchables=untouchables,
                                    role_map=role_map,
                                    score_field=score_field,
                                    pick_score_multiplier=trade_hub_pick_multiplier,
                                    team_strategy=trade_hub_strategy,
                                    team_archetype=trade_hub_archetype,
                                    team_lens_label=trade_hub_lens_label,
                                    league_settings=league_value_settings,
                                    key_prefix=f"trade_ideas_return_{selected_league_id}_{my_roster_id}",
                                    max_ideas=4,
                                    compact=True,
                                    show_header=False,
                                    card_key_prefix=f"trade_ideas_return_cards_{selected_league_id}_{my_roster_id}",
                                    trust_context=trade_hub_context.get("trade_trust_context"),
                                    render_player_dossier=trade_player_dossier_renderer,
                                )
            def render_search_around_player() -> None:
                trade_hub_ui.render_trade_hub_section_header(
                    "Search Around a Player",
                    eyebrow="Secondary Tool",
                    subtitle="Pick one of your players or any league target to inspect the clearest path around that asset.",
                )
                search_mode_key = f"player_trade_hub_mode_{selected_league_id}"
                if trade_hub_focus_mode == "my_player":
                    st.session_state[search_mode_key] = "Your Player"
                elif trade_hub_focus_mode == "target_player":
                    st.session_state[search_mode_key] = "League Target"
                elif search_mode_key not in st.session_state:
                    st.session_state[search_mode_key] = "Your Player"

                hub_mode_label = st.radio(
                    "Search mode",
                    ["Your Player", "League Target"],
                    horizontal=True,
                    key=search_mode_key,
                )
                hub_mode = "my_player" if hub_mode_label == "Your Player" else "target_player"

                if hub_mode == "my_player":
                    my_trade_pool = trade_hub_df[trade_hub_df["player_id"].astype(str).isin(my_player_ids)].copy()
                    if my_trade_pool.empty:
                        st.info("No roster players are available for player search right now.")
                    else:
                        my_rank_row = hub_display[hub_display["roster_id"].astype(str) == str(my_roster_id)]
                        my_rank_row = my_rank_row.iloc[0] if not my_rank_row.empty else pd.Series(dtype="object")
                        render_summary_tiles(
                            [
                                {
                                    "label": "Team Context",
                                    "value": f"Power {_format_rank(my_rank_row.get('power_rank'))} | Franchise {_format_rank(my_rank_row.get('franchise_rank'))}",
                                    "note": f"Trade lens: {trade_hub_lens_label}.",
                                    "tone": "strategy",
                                },
                            ],
                            compact=True,
                        )
                        render_trade_return_explorer(
                            all_players_df=trade_hub_df,
                            owned_player_df=my_trade_pool,
                            league_id=selected_league_id,
                            df_summary=df_summary,
                            my_roster_id=my_roster_id,
                            untouchables=untouchables,
                            role_map=role_map,
                            score_field=score_field,
                            pick_score_multiplier=trade_hub_pick_multiplier,
                            team_strategy=trade_hub_strategy,
                            team_archetype=trade_hub_archetype,
                            team_lens_label=trade_hub_lens_label,
                            league_settings=league_value_settings,
                            key_prefix=f"player_trade_hub_{selected_league_id}_{my_roster_id}",
                            max_ideas=6,
                            compact=True,
                            show_header=False,
                            preselected_player_id=trade_hub_focus_player_id if trade_hub_focus_mode == "my_player" else "",
                            card_key_prefix=f"player_trade_hub_cards_{selected_league_id}_{my_roster_id}",
                            trust_context=trade_hub_context.get("trade_trust_context"),
                            render_player_dossier=trade_player_dossier_renderer,
                        )
                        if trade_hub_focus_mode == "my_player":
                            st.session_state.pop(f"trade_hub_focus_player_id_{selected_league_id}", None)
                            st.session_state.pop(f"trade_hub_focus_mode_{selected_league_id}", None)
                        render_player_detail_button_grid(
                            my_trade_pool.sort_values(score_field, ascending=False).head(6),
                            key_prefix=f"player_hub_my_targets_{selected_league_id}_{my_roster_id}",
                            return_page="trade_hub",
                            source_label="Trade Hub",
                            title="Quick view one of your players",
                            max_buttons=6,
                            open_mode="quick_view",
                        )
                    return

                target_pool = trade_hub_df[
                    trade_hub_df["player_id"].astype(str).isin(owned_player_to_roster.keys())
                    & ~trade_hub_df["player_id"].astype(str).isin(my_player_ids)
                ].copy()
                target_pool = target_pool[
                    pd.to_numeric(target_pool.get(score_field, 0), errors="coerce").fillna(0) > 0
                ].copy()
                if target_pool.empty:
                    st.info("No valid league targets are available right now.")
                    return

                target_pool = target_pool.sort_values(score_field, ascending=False)
                target_labels = {
                    player_trade_hub_option_label(row, score_field): str(row["player_id"])
                    for _, row in target_pool.iterrows()
                }
                target_options = list(target_labels.keys())
                default_target_index = 0
                if trade_hub_focus_mode == "target_player" and trade_hub_focus_player_id:
                    for idx, label in enumerate(target_options):
                        if target_labels.get(label) == trade_hub_focus_player_id:
                            default_target_index = idx
                            break
                target_selectbox_key = f"player_trade_hub_target_player_{selected_league_id}"
                if trade_hub_focus_mode == "target_player" and target_options:
                    st.session_state[target_selectbox_key] = target_options[default_target_index]
                selected_label = st.selectbox(
                    "Select any league player",
                    target_options,
                    index=default_target_index,
                    key=target_selectbox_key,
                )
                if trade_hub_focus_mode == "target_player":
                    st.session_state.pop(f"trade_hub_focus_player_id_{selected_league_id}", None)
                    st.session_state.pop(f"trade_hub_focus_mode_{selected_league_id}", None)
                selected_player_id = target_labels[selected_label]
                selected_row = target_pool[target_pool["player_id"].astype(str) == selected_player_id].iloc[0]
                target_roster_id = owned_player_to_roster.get(selected_player_id, "")
                target_profile = roster_profiles.get(str(target_roster_id), {})
                target_team_name = _safe_text(target_profile.get("team_name"), "League roster")
                target_owner_name = owner_handle(target_profile.get("username"), target_profile.get("owner_name", "Owner"))
                target_rank_row = hub_display[hub_display["roster_id"].astype(str) == str(target_roster_id)]
                target_rank_row = target_rank_row.iloc[0] if not target_rank_row.empty else pd.Series(dtype="object")

                render_summary_tiles(
                    [
                        {
                            "label": "Selected Target",
                            "value": player_display_name(selected_row),
                            "note": player_trade_hub_selected_summary(selected_row, score_field),
                            "tone": "opportunity",
                        },
                        {
                            "label": "Current Team",
                            "value": target_team_name,
                            "note": (
                                f"{target_owner_name} | Power {_format_rank(target_rank_row.get('power_rank'))} | Franchise {_format_rank(target_rank_row.get('franchise_rank'))}"
                                + (
                                    f" | {_safe_text(target_rank_row.get('manager_tendencies_summary'))}"
                                    if _safe_text(target_rank_row.get('manager_tendencies_summary'))
                                    else ""
                                )
                            ),
                            "tone": "franchise",
                        },
                        {
                            "label": "Current Strategy",
                            "value": trade_hub_lens_label,
                            "note": "This lens shapes which acquisition paths are preferred for your roster.",
                            "tone": "strategy",
                        },
                    ],
                    compact=True,
                )
                render_player_detail_button_grid(
                    [selected_row],
                    key_prefix=f"player_hub_target_{selected_league_id}_{selected_player_id}",
                    return_page="trade_hub",
                    source_label="Trade Hub",
                    title="Quick view the selected target",
                    max_buttons=1,
                    open_mode="quick_view",
                )

                with st.spinner("Searching acquisition paths..."):
                    hub_search_result = cached_player_trade_hub_ideas(
                        df_players=trade_hub_df,
                        league_id=selected_league_id,
                        df_summary=df_summary,
                        my_roster_id=my_roster_id,
                        untouchables=tuple(sorted(untouchables)),
                        role_items=tuple(sorted((str(pid), str(role)) for pid, role in role_map.items())),
                        score_field=score_field,
                        pick_score_multiplier=trade_hub_pick_multiplier,
                        team_strategy=trade_hub_strategy,
                        team_archetype=trade_hub_archetype,
                        mode="target_player",
                        selected_player_id=selected_player_id,
                        league_settings_items=draft_pick_valuation_settings_items(league_value_settings),
                        max_ideas=8,
                    )
                hub_search_result = {
                    **hub_search_result,
                    "ideas": enforce_cached_trade_ideas(
                        hub_search_result.get("ideas") or [],
                        df_players=trade_hub_df,
                        league_id=selected_league_id,
                        df_summary=df_summary,
                        my_roster_id=my_roster_id,
                        untouchables=tuple(sorted(str(name) for name in untouchables)),
                        trust_context=trade_hub_context.get("trade_trust_context"),
                    ),
                }
                hub_ideas = enrich_trade_ideas_with_manager_tendencies(
                    hub_search_result.get("ideas") or [],
                    df_summary,
                    trade_hub_context.get("league_maturity", {}),
                )

                if hub_ideas:
                    trade_hub_ui.render_trade_hub_section_header(
                        "Suggested Paths",
                        eyebrow="Acquisition Board",
                        subtitle="Cheapest realistic paths to the selected target without ignoring your roster needs.",
                    )
                    ordered_hub_ideas = trade_hub_ui.order_trade_hub_visible_ideas(hub_ideas)
                    primary_hub_ideas, secondary_hub_ideas = split_trade_surface_ideas(
                        ordered_hub_ideas
                    )
                    headline_hub_idea = select_trade_hub_headline_idea(ordered_hub_ideas)
                    if headline_hub_idea is not None:
                        render_summary_tiles(
                            [
                                {
                                    "label": "Best Partner",
                                    "value": _safe_text(headline_hub_idea.get("partner_team_name"), target_team_name),
                                    "note": _safe_text(headline_hub_idea.get("hub_partner_reason")),
                                    "tone": "power",
                                },
                                {
                                    "label": "Best Offer Out",
                                    "value": _safe_text(headline_hub_idea.get("my_player"), "Package"),
                                    "note": _safe_text(headline_hub_idea.get("hub_path"), _safe_text(headline_hub_idea.get("tag"))),
                                    "tone": "opportunity",
                                },
                                {
                                    "label": "Confidence",
                                    "value": _trade_display_confidence_label(headline_hub_idea),
                                    "note": _trade_confidence_reason(headline_hub_idea),
                                    "tone": "strategy",
                                },
                            ],
                            compact=True,
                        )
                    elif secondary_hub_ideas:
                        st.info("No clean headline acquisition path cleared the board right now. Secondary paths are still available below if you want thinner market ideas.")

                    for idea_idx, idea in enumerate(primary_hub_ideas):
                        render_player_trade_hub_card(
                            idea,
                            idea_idx,
                            key_prefix=f"target_trade_hub_cards_{selected_league_id}_{selected_player_id}",
                            render_player_dossier=trade_player_dossier_renderer,
                        )
                    if secondary_hub_ideas:
                        with st.expander("Secondary / thin-market acquisition paths", expanded=False):
                            st.caption("These acquisition paths are weaker backups — still possible, but less likely to close than the main board.")
                            base_idx = len(primary_hub_ideas)
                            for offset, idea in enumerate(secondary_hub_ideas):
                                render_player_trade_hub_card(
                                    idea,
                                    base_idx + offset,
                                    key_prefix=f"target_trade_hub_cards_{selected_league_id}_{selected_player_id}",
                                    render_player_dossier=trade_player_dossier_renderer,
                                )
                    return

                st.info("No realistic acquisition paths cleared the current fit and value filters for this target.")
                if hub_search_result.get("fallback_used"):
                    st.caption("Expanded search was used because this player has fewer direct trade matches.")
                if hub_search_result.get("diagnostic_summary"):
                    st.caption("Fewer matching partners for this search — the board was widened. " + _safe_text(hub_search_result.get("diagnostic_summary")))

            if trade_hub_focus_player_id and trade_hub_focus_mode in {"my_player", "target_player"}:
                if current_user_is_premium():
                    render_search_around_player()
                    st.divider()
                else:
                    render_premium_lock(
                        "Player-focused trade search",
                        "Search returns or acquisition paths around a specific player after you spot a board idea worth pursuing.",
                        feature="Premium Trade Hub",
                    )
                render_top_trade_opportunities()
            else:
                render_top_trade_opportunities()
                st.divider()
                if current_user_is_premium():
                    render_search_around_player()
                else:
                    render_premium_lock(
                        "Player-focused trade search",
                        "Search returns or acquisition paths around a specific player after you spot a board idea worth pursuing.",
                        feature="Premium Trade Hub",
                    )
            trade_hub_first_useful.mark_trade_hub_milestone("trade_hub_route_complete")

    # TRADE ANALYZER
    if current_page == "trade_analyzer":
        render_page_shell(
            page_key="trade_analyzer",
            title="Trade Analyzer",
            subtitle="Build and evaluate an exact trade package once you know the pieces.",
            meta_items=[
                ("Exact Builder", "primary"),
                (selected_league_name or "League", "success"),
            ],
        )
        st.caption("Use Trade Hub to discover ideas first. Use Trade Analyzer when you are testing a specific offer.")

        if "trade_send_assets" not in st.session_state:
            st.session_state["trade_send_assets"] = []
        if "trade_receive_assets" not in st.session_state:
            st.session_state["trade_receive_assets"] = []
        trade_fit_evaluation = None

        def trade_result_emoji(score: int) -> str:
            return trade_value_verdict(score)

        if startup_mode and selected_league_id:
            st.info("Startup Draft Center is active for this league. Trade Analyzer unlocks after the startup draft completes and rosters are populated.")
            send_search_results = pd.DataFrame()
            receive_search_results = pd.DataFrame()
        elif not username or not selected_league_id:
            render_onboarding_handoff(
                username=username,
                selected_league_id=selected_league_id,
                note="Import your Sleeper league before building an exact trade package.",
            )
            st.stop()
        elif my_roster_id is None:
            st.warning(f"Could not find a roster for username '{username}' in the selected league.")
            send_search_results = pd.DataFrame()
            receive_search_results = pd.DataFrame()
        else:
            trade_context = get_shared_league_context(
                include_intelligence=False,
                include_trust=False,
                include_maturity=False,
            )
            df_summary_trade = trade_context.get("team_direction_summary", pd.DataFrame())
            draft_picks = trade_context.get("draft_pick_assets", [])
            roster_player_map = trade_context.get("roster_player_map", {})
            trade_profile = load_profile_key(username, selected_league_id)
            trade_metrics = get_team_vs_league(df_summary_trade, my_roster_id)
            _, trade_analyzer_strategy, _ = resolve_team_strategy(trade_metrics, trade_profile)
            trade_analyzer_df = apply_strategy_age_curve(df_players, trade_analyzer_strategy, score_field)
            trade_analyzer_pick_multiplier = strategy_adjusted_pick_score_multiplier(
                pick_score_multiplier,
                trade_analyzer_strategy,
            )
            analyzer_context_key = f"{valuation_context_key}|{trade_analyzer_strategy}"
            if st.session_state.get("trade_asset_strategy_context") != analyzer_context_key:
                st.session_state["trade_send_assets"] = []
                st.session_state["trade_receive_assets"] = []
                st.session_state["trade_asset_strategy_context"] = analyzer_context_key
            my_player_ids = {
                str(pid)
                for pid in roster_player_map.get(str(my_roster_id), ())
                if pid is not None
            }
            my_team_df = trade_analyzer_df[
                trade_analyzer_df["player_id"].astype(str).isin(my_player_ids)
            ].copy()
            owned_picks = [
                pick for pick in draft_picks if str(pick.get("owner_roster_id")) == str(my_roster_id)
            ]
            available_picks = [
                pick for pick in draft_picks if str(pick.get("owner_roster_id")) != str(my_roster_id)
            ]
            team_info_by_roster_id = {
                str(row.get("roster_id")): {
                    "team_name": _safe_text(row.get("team_name"), f"Team {row.get('roster_id')}"),
                    "owner_name": _safe_text(row.get("owner_name"), "Owner"),
                }
                for _, row in df_summary_trade.iterrows()
            }
            roster_player_ids_map: dict[str, set[str]] = {}
            player_owner_map: dict[str, dict] = {}
            for roster_id_key, player_ids_for_roster_tuple in roster_player_map.items():
                player_ids_for_roster = {
                    str(pid) for pid in player_ids_for_roster_tuple if pid is not None
                }
                roster_player_ids_map[roster_id_key] = player_ids_for_roster
                roster_team_name = team_info_by_roster_id.get(roster_id_key, {}).get(
                    "team_name",
                    f"Team {roster_id_key}",
                )
                for pid in player_ids_for_roster:
                    player_owner_map[pid] = {
                        "owner_roster_id": roster_id_key,
                        "owner_team_name": roster_team_name,
                    }
            my_team_name = team_info_by_roster_id.get(str(my_roster_id), {}).get("team_name", "Your roster")
            for package_key in ["trade_send_assets", "trade_receive_assets"]:
                refreshed_assets = []
                for asset in st.session_state.get(package_key, []):
                    refreshed = dict(asset)
                    if refreshed.get("asset_type") == "player":
                        owner_info = player_owner_map.get(str(refreshed.get("player_id") or ""), {})
                        if owner_info:
                            refreshed["owner_roster_id"] = refreshed.get("owner_roster_id") or owner_info.get("owner_roster_id")
                            refreshed["owner_team_name"] = refreshed.get("owner_team_name") or owner_info.get("owner_team_name", "")
                    elif refreshed.get("asset_type") == "pick":
                        owner_roster_id = str(refreshed.get("owner_roster_id") or "")
                        if owner_roster_id and not refreshed.get("owner_team_name"):
                            refreshed["owner_team_name"] = team_info_by_roster_id.get(owner_roster_id, {}).get("team_name", "")
                    refreshed_assets.append(refreshed)
                st.session_state[package_key] = refreshed_assets
            partner_option_map = {"All Teams": ""}
            partner_rows = df_summary_trade[
                df_summary_trade["roster_id"].astype(str) != str(my_roster_id)
            ].sort_values(["team_name", "owner_name"], ascending=[True, True])
            for _, partner_row in partner_rows.iterrows():
                partner_roster_id = str(partner_row.get("roster_id"))
                partner_label = (
                    f"{_safe_text(partner_row.get('team_name'), f'Team {partner_roster_id}')} | "
                    f"{_safe_text(partner_row.get('owner_name'), 'Owner')}"
                )
                if partner_label in partner_option_map:
                    partner_label = f"{partner_label} ({partner_roster_id})"
                partner_option_map[partner_label] = partner_roster_id
            st.caption(f"Package evaluation lens: {team_strategy_label(trade_analyzer_strategy)}")

            send_search_results = pd.DataFrame()
            receive_search_results = pd.DataFrame()
        if "trade_analyzer_df" not in locals():
            trade_analyzer_df = df_players
            trade_analyzer_pick_multiplier = strategy_pick_score_multiplier
            trade_analyzer_strategy = active_team_strategy
            my_team_df = pd.DataFrame()
            team_info_by_roster_id = {}
            roster_player_ids_map = {}
            player_owner_map = {}
            my_team_name = "Your roster"
            partner_option_map = {"All Teams": ""}
        if "trade_receive_notice" not in st.session_state:
            st.session_state["trade_receive_notice"] = ""

        def build_trade_asset_from_row(row):
            if row["asset_type"] == "player":
                owner_info = player_owner_map.get(str(row.get("player_id") or ""), {})
                return {
                    "asset_type": "player",
                    "player_id": str(row["player_id"]),
                    "name": row["label"],
                    "label": row["label"],
                    "position": row["position"],
                    "team": row["team"],
                    "status": row.get("status", ""),
                    "injury_status": row.get("injury_status", ""),
                    "age": row.get("age"),
                    "player_tier": _safe_text(row.get("player_tier")),
                    "opportunity_label": _safe_text(row.get("opportunity_label")),
                    "opportunity_score": int(row.get("opportunity_score", 0) or 0),
                    "opportunity_explanation": _safe_text(row.get("opportunity_explanation")),
                    "value_score": int(row["value_score"]),
                    "score": score_asset_value(row),
                    "owner_roster_id": row.get("owner_roster_id") or owner_info.get("owner_roster_id"),
                    "owner_team_name": row.get("owner_team_name") or owner_info.get("owner_team_name", ""),
                }
            return {
                "asset_type": "pick",
                "label": row["label"],
                "value_score": int(row["value_score"]),
                "score": score_asset_value(row),
                "season": row.get("season"),
                "round": row.get("round"),
                "owner_roster_id": row.get("owner_roster_id"),
                "owner_team_name": row.get("owner_team_name", ""),
                "original_team_name": row.get("original_team_name", ""),
            }

        def current_receive_owner_ids() -> list[str]:
            return sorted(
                {
                    str(asset.get("owner_roster_id"))
                    for asset in st.session_state.get("trade_receive_assets", [])
                    if asset.get("owner_roster_id") not in (None, "")
                }
            )

        def add_trade_asset(row_or_asset, package_key: str, selected_partner_roster_id: str = ""):
            asset = (
                build_trade_asset_from_row(row_or_asset)
                if isinstance(row_or_asset, pd.Series)
                else dict(row_or_asset)
            )
            if package_key == "trade_receive_assets":
                new_owner_id = str(asset.get("owner_roster_id") or "")
                existing_owner_ids = current_receive_owner_ids()
                if selected_partner_roster_id and new_owner_id and new_owner_id != str(selected_partner_roster_id):
                    st.session_state["trade_receive_notice"] = "Selected trade partner does not own that asset."
                    return
                if existing_owner_ids and new_owner_id and new_owner_id not in existing_owner_ids:
                    st.session_state["trade_receive_notice"] = "Receive assets must come from one partner team at a time. Remove the conflicting asset or clear the package."
                    return
                st.session_state["trade_receive_notice"] = ""
            if asset not in st.session_state[package_key]:
                st.session_state[package_key].append(asset)

        def undo_last_trade_asset(package_key: str):
            assets = st.session_state.get(package_key, [])
            if assets:
                assets.pop()
            if package_key == "trade_receive_assets":
                st.session_state["trade_receive_notice"] = ""

        def render_asset_results(
            results: pd.DataFrame,
            package_key: str,
            button_prefix: str,
            selected_partner_roster_id: str = "",
            query: str = "",
        ):
            if results.empty:
                return
            if query.strip():
                best_row = results.reset_index(drop=True).iloc[0]
                best_asset = build_trade_asset_from_row(best_row)
                quick_cols = st.columns([2, 5])
                with quick_cols[0]:
                    if st.button(
                        "Add Best Match",
                        key=f"add_best_{button_prefix}_{best_asset.get('player_id') or best_asset.get('label')}",
                        use_container_width=True,
                    ):
                        add_trade_asset(best_row, package_key, selected_partner_roster_id=selected_partner_roster_id)
                with quick_cols[1]:
                    st.caption(f"Top match: {best_asset.get('label')}")
            for idx, row in results.reset_index(drop=True).iterrows():
                asset = build_trade_asset_from_row(row)
                result_cols = st.columns([5, 1, 1])
                with result_cols[0]:
                    st.markdown(_trade_asset_html(asset), unsafe_allow_html=True)
                with result_cols[1]:
                    if st.button(
                        "Add",
                        key=f"add_{button_prefix}_{idx}_{asset.get('player_id') or asset.get('label')}",
                        use_container_width=True,
                    ):
                        add_trade_asset(row, package_key, selected_partner_roster_id=selected_partner_roster_id)
                with result_cols[2]:
                    if asset.get("asset_type") == "player" and st.button(
                        "Profile",
                        key=f"profile_{button_prefix}_{idx}_{asset.get('player_id')}",
                        use_container_width=True,
                    ):
                        open_player_detail(
                            asset.get("player_id"),
                            return_page="trade_analyzer",
                            source_label="Trade Analyzer",
                        )

        def render_selected_package(package_key: str, button_prefix: str, empty_text: str):
            assets = st.session_state[package_key]
            if not assets:
                st.caption(empty_text)
                return
            st.caption(
                f"{len(assets)} asset{'s' if len(assets) != 1 else ''} | {_format_score(sum(score_asset_value(asset) for asset in assets))} total value"
            )
            for idx, asset in enumerate(assets):
                asset_cols = st.columns([5, 1, 1])
                with asset_cols[0]:
                    st.markdown(_trade_asset_html(asset), unsafe_allow_html=True)
                with asset_cols[1]:
                    if st.button("Remove", key=f"remove_{button_prefix}_asset_{idx}", use_container_width=True):
                        st.session_state[package_key].pop(idx)
                        if package_key == "trade_receive_assets":
                            st.session_state["trade_receive_notice"] = ""
                with asset_cols[2]:
                    if asset.get("asset_type") == "player" and st.button(
                        "Profile",
                        key=f"profile_selected_{button_prefix}_{idx}_{asset.get('player_id')}",
                        use_container_width=True,
                    ):
                        open_player_detail(
                            asset.get("player_id"),
                            return_page="trade_analyzer",
                            source_label="Trade Analyzer",
                        )

        def pick_filter_options(picks: list[dict]) -> tuple[list[str], list[str]]:
            years = sorted(
                {
                    str(_safe_positive_int(pick.get("season"), 0))
                    for pick in picks or []
                    if _safe_positive_int(pick.get("season"), 0) > 0
                }
            )
            rounds = sorted(
                {
                    str(_safe_positive_int(pick.get("round"), 0))
                    for pick in picks or []
                    if _safe_positive_int(pick.get("round"), 0) > 0
                },
                key=lambda value: int(value),
            )
            return ["Any"] + years, ["Any"] + rounds

        toolbar_cols = st.columns(5)
        with toolbar_cols[0]:
            if st.button("Clear Send", key="trade_clear_send", use_container_width=True):
                st.session_state["trade_send_assets"] = []
        with toolbar_cols[1]:
            if st.button("Undo Send", key="trade_undo_send", use_container_width=True):
                undo_last_trade_asset("trade_send_assets")
        with toolbar_cols[2]:
            if st.button("Clear Receive", key="trade_clear_receive", use_container_width=True):
                st.session_state["trade_receive_assets"] = []
                st.session_state["trade_receive_notice"] = ""
        with toolbar_cols[3]:
            if st.button("Undo Receive", key="trade_undo_receive", use_container_width=True):
                undo_last_trade_asset("trade_receive_assets")
        with toolbar_cols[4]:
            if st.button("Reset Trade", key="trade_reset_all", use_container_width=True):
                st.session_state["trade_send_assets"] = []
                st.session_state["trade_receive_assets"] = []
                st.session_state["trade_receive_notice"] = ""
                st.session_state["trade_send_search_query"] = ""
                st.session_state["trade_receive_search_query"] = ""
                st.session_state["trade_send_asset_filter"] = "All"
                st.session_state["trade_receive_asset_filter"] = "All"
                st.session_state["trade_send_pick_year"] = "Any"
                st.session_state["trade_send_pick_round"] = "Any"
                st.session_state["trade_receive_pick_year"] = "Any"
                st.session_state["trade_receive_pick_round"] = "Any"
                st.session_state["trade_receive_partner"] = "All Teams"

        left_col, right_col = st.columns(2)
        receive_owner_ids = current_receive_owner_ids()
        if len(receive_owner_ids) > 1:
            st.warning("Your receive package currently mixes assets from multiple partner teams. Clear the receive side or remove the conflicting asset.")

        with left_col:
            st.markdown("#### Sending")
            if selected_league_id and my_roster_id is not None:
                send_query = st.text_input(
                    "Search assets you are sending",
                    key="trade_send_search_query",
                    placeholder="Search players or picks (for example: 2027 1st)",
                )
                st.caption("Unified search supports player names and pick shorthand like `2027 1st` or `2028 second`.")
                send_asset_filter = "All"
                send_pick_year = "Any"
                send_pick_round = "Any"
                send_year_options, send_round_options = pick_filter_options(owned_picks)
                with st.expander("Optional send filters", expanded=False):
                    send_asset_filter = st.selectbox(
                        "Send asset type",
                        ["All", "Players", "Picks"],
                        key="trade_send_asset_filter",
                    )
                    if send_asset_filter != "Players":
                        if _query_requires_pick_focus(send_query):
                            st.caption("Structured pick query detected. Year and round will be pulled from your search unless you override them here.")
                        filter_cols = st.columns(2)
                        with filter_cols[0]:
                            send_pick_year = st.selectbox(
                                "Send pick year",
                                send_year_options,
                                key="trade_send_pick_year",
                            )
                        with filter_cols[1]:
                            send_pick_round = st.selectbox(
                                "Send pick round",
                                send_round_options,
                                key="trade_send_pick_round",
                            )
                send_search_results = search_trade_assets_for_side(
                    trade_analyzer_df,
                    owned_picks,
                    send_query,
                    score_field=score_field,
                    pick_score_multiplier=trade_analyzer_pick_multiplier,
                    owned_player_ids=my_player_ids,
                    only_owned=True,
                    allowed_player_ids=my_player_ids,
                    asset_filter=send_asset_filter,
                    pick_year=send_pick_year,
                    pick_round=send_pick_round,
                    player_owner_map=player_owner_map,
                    limit=12,
                )
                if send_search_results.empty:
                    if st.session_state.get("trade_send_search_query", "") or send_asset_filter != "All" or send_pick_year != "Any" or send_pick_round != "Any":
                        st.info("No owned assets match that search.")
                    else:
                        st.caption("Leave search blank to browse your strongest movable assets.")
                else:
                    if send_query.strip():
                        st.caption(f"{len(send_search_results)} owned assets found")
                    else:
                        st.caption("Showing top owned assets for the send side.")
                    render_asset_results(
                        send_search_results,
                        "trade_send_assets",
                        "send",
                        query=send_query,
                    )
            else:
                st.info("Select a league and load your roster to search owned assets.")

            st.markdown("**Send Package**")
            render_selected_package(
                "trade_send_assets",
                "send",
                "No assets selected to send.",
            )

        with right_col:
            st.markdown("#### Receiving")
            if selected_league_id and my_roster_id is not None:
                selected_partner_label = st.selectbox(
                    "Trade partner",
                    list(partner_option_map.keys()),
                    key="trade_receive_partner",
                )
                selected_partner_roster_id = str(partner_option_map.get(selected_partner_label, "") or "")
                locked_receive_roster_id = selected_partner_roster_id
                if not locked_receive_roster_id and len(receive_owner_ids) == 1:
                    locked_receive_roster_id = receive_owner_ids[0]
                locked_receive_team_name = team_info_by_roster_id.get(
                    str(locked_receive_roster_id),
                    {},
                ).get("team_name", "")
                if locked_receive_team_name:
                    if selected_partner_roster_id:
                        st.caption(f"Receiving from: {locked_receive_team_name}")
                    else:
                        st.caption(f"Receive package is currently locked to: {locked_receive_team_name}")
                if selected_partner_roster_id and receive_owner_ids and selected_partner_roster_id not in receive_owner_ids:
                    current_locked_name = team_info_by_roster_id.get(receive_owner_ids[0], {}).get("team_name", "another team")
                    st.warning(f"Your current receive package is built from {current_locked_name}. Clear it or remove those assets before switching partners.")

                receive_pick_pool = [
                    pick
                    for pick in available_picks
                    if not locked_receive_roster_id or str(pick.get("owner_roster_id")) == str(locked_receive_roster_id)
                ]
                receive_query = st.text_input(
                    "Search assets you want to receive",
                    key="trade_receive_search_query",
                    placeholder="Search players or picks (for example: Team A 2027 1st)",
                )
                st.caption("You can search players and picks from one box, including team-prefixed pick shorthand.")
                receive_asset_filter = "All"
                receive_pick_year = "Any"
                receive_pick_round = "Any"
                receive_year_options, receive_round_options = pick_filter_options(receive_pick_pool)
                with st.expander("Optional receive filters", expanded=False):
                    receive_asset_filter = st.selectbox(
                        "Receive asset type",
                        ["All", "Players", "Picks"],
                        key="trade_receive_asset_filter",
                    )
                    if receive_asset_filter != "Players":
                        if _query_requires_pick_focus(receive_query):
                            st.caption("Structured pick query detected. Year and round will be pulled from your search unless you override them here.")
                        filter_cols = st.columns(2)
                        with filter_cols[0]:
                            receive_pick_year = st.selectbox(
                                "Receive pick year",
                                receive_year_options,
                                key="trade_receive_pick_year",
                            )
                        with filter_cols[1]:
                            receive_pick_round = st.selectbox(
                                "Receive pick round",
                                receive_round_options,
                                key="trade_receive_pick_round",
                            )
                allowed_receive_player_ids = (
                    roster_player_ids_map.get(str(locked_receive_roster_id), set())
                    if locked_receive_roster_id
                    else None
                )
                receive_search_results = search_trade_assets_for_side(
                    trade_analyzer_df,
                    available_picks,
                    receive_query,
                    score_field=score_field,
                    pick_score_multiplier=trade_analyzer_pick_multiplier,
                    owned_player_ids=my_player_ids,
                    exclude_owned=True,
                    allowed_player_ids=allowed_receive_player_ids,
                    asset_filter=receive_asset_filter,
                    pick_year=receive_pick_year,
                    pick_round=receive_pick_round,
                    partner_roster_id=locked_receive_roster_id,
                    player_owner_map=player_owner_map,
                    limit=12,
                )
                if receive_search_results.empty:
                    if st.session_state.get("trade_receive_search_query", "") or receive_asset_filter != "All" or receive_pick_year != "Any" or receive_pick_round != "Any" or locked_receive_roster_id:
                        st.info("No available assets match that search.")
                    else:
                        st.caption("Pick a trade partner or search the league to start the receive side.")
                else:
                    if receive_query.strip():
                        st.caption(f"{len(receive_search_results)} assets found")
                    elif locked_receive_team_name:
                        st.caption(f"Showing top assets from {locked_receive_team_name}.")
                    else:
                        st.caption("Showing filtered receive assets.")
                    render_asset_results(
                        receive_search_results,
                        "trade_receive_assets",
                        "receive",
                        selected_partner_roster_id=locked_receive_roster_id,
                        query=receive_query,
                    )
                if st.session_state.get("trade_receive_notice"):
                    st.warning(st.session_state["trade_receive_notice"])
            else:
                st.info("Select a league and load your roster to search receive-side assets.")

            st.markdown("**Receive Package**")
            render_selected_package(
                "trade_receive_assets",
                "receive",
                "No assets selected to receive.",
            )

        send_assets = st.session_state["trade_send_assets"]
        receive_assets = st.session_state["trade_receive_assets"]
        gain = trade_gain(send_assets, receive_assets)
        total_send = sum(score_asset_value(asset) for asset in send_assets)
        total_receive = sum(score_asset_value(asset) for asset in receive_assets)
        if selected_league_id and my_roster_id is not None and not my_team_df.empty:
            trade_fit_evaluation = evaluate_trade_analyzer_fit(
                my_team_df=my_team_df,
                all_players_df=trade_analyzer_df,
                send_assets=send_assets,
                receive_assets=receive_assets,
                metrics=trade_metrics if "trade_metrics" in locals() else None,
                strategy=trade_analyzer_strategy,
                lineup_settings=league_value_settings,
                score_field=score_field,
            )

        render_section_header(
            "Trade Result",
            kicker="Evaluation",
            note="Value is only one layer here. The result block also weighs roster fit, lineup impact, injury pressure, and strategy fit.",
        )
        result_label = trade_result_emoji(gain)
        if gain > 0:
            st.success(f"Net win: {result_label}. +{gain} {league_score_label(score_field).lower()}")
        elif gain < 0:
            st.error(f"Net leak: {result_label}. {gain} {league_score_label(score_field).lower()}")
        else:
            st.info(f"Neutral trade: {result_label}.")

        executive_table_ui.render_executive_metric_tiles(
            [
                {
                    "label": f"Send {league_score_label(score_field)}",
                    "value": str(total_send),
                    "note": "Package leaving your roster",
                },
                {
                    "label": f"Receive {league_score_label(score_field)}",
                    "value": str(total_receive),
                    "note": "Package coming onto your roster",
                },
            ]
        )

        render_trade_result_panel(
            send_assets,
            receive_assets,
            league_score_label(score_field),
            trade_analyzer_strategy,
            fit_evaluation=trade_fit_evaluation,
        )

    if current_page == "premium":
        billing_flag = ""
        try:
            billing_flag = str(st.query_params.get("billing", "") or "").strip().casefold()
        except Exception:
            billing_flag = ""
        # Force profile refresh only after checkout return; otherwise honor the 60s cache.
        _refresh_supabase_account_profile(force=billing_flag == "success")
        refresh_current_user_entitlement()
        render_page_shell(
            page_key="premium",
            title="Premium",
            subtitle="Free and Premium plan structure for FantasyGM Lab.",
            meta_items=[
                (f"Current plan: {premium_page.plan_status_label(current_user_entitlement())}", "primary"),
                (brand_identity.FOUNDER_BETA_LABEL, "premium"),
            ],
        )
        premium_page.render_premium_page(entitlement=current_user_entitlement())
        _render_premium_entitlement_diagnostics()

    if current_page == founder_ops.FOUNDER_OPS_PAGE_KEY:
        try:
            secrets = st.secrets
        except Exception:
            secrets = None
        render_page_shell(
            page_key=founder_ops.FOUNDER_OPS_PAGE_KEY,
            title="Founder Ops",
            subtitle="Read-only operational health for FantasyGM Lab founders.",
            meta_items=[
                (brand_identity.FOUNDER_BETA_LABEL, "premium"),
                ("Founder only", "primary"),
            ],
        )
        if not founder_ops.founder_ops_enabled(secrets=secrets):
            founder_ops_ui.render_access_denied()
        else:
            founder_ops_ui.render_founder_ops_dashboard(
                secrets=secrets,
                navigate=_queue_platform_route,
            )

    if current_page in legal_pages.LEGAL_PAGE_KEYS:
        legal_pages.render_legal_page(current_page)

    runtime_trace.mark("page_calculation_complete")
    if current_page != "player_detail":
        with performance.time_block("player_quick_view_render", category="render"):
            render_player_quick_view_modal(
                df_players=df_players,
                username=username,
                selected_league_id=selected_league_id,
                my_roster_id=my_roster_id,
                league_settings=league_value_settings,
                score_field=score_field,
                active_team_strategy=active_team_strategy,
                pick_score_multiplier=pick_score_multiplier,
            )

    legal_pages.render_legal_footer(
        current_page=current_page,
        on_navigate=_queue_platform_route,
    )
    render_global_feedback_entry(
        current_page=current_page,
        selected_league_id=selected_league_id,
        selected_league_name=selected_league_name,
        my_roster_id=my_roster_id,
    )
    performance.record_timing(
        f"page_route_total_{_safe_text(current_page, 'unknown')}",
        (time.perf_counter() - route_content_started) * 1000,
        category="render",
    )
    if st.session_state.pop("_startup_route_render_failed", False):
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "loading_dismissed",
            started_at=startup_started_at,
        )
    # Loading shell is dismissed at first usable paint (before route bodies).
    # Keep a safety complete for any path that skipped early dismiss.
    elif startup.active:
        startup_coordinator.log_startup_milestone(
            st.session_state,
            "loading_dismissed",
            started_at=startup_started_at,
        )
        startup.complete()
    performance.finish_rerun(
        perf_rerun,
        route=_safe_text(current_page, "unknown"),
        label_prefix="app_rerun_total_",
    )
    performance.render_debug_panel(route=_safe_text(current_page, "unknown"))


if __name__ == "__main__":
    main()
