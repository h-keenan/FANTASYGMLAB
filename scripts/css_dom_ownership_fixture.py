"""Production-equivalent DOM/CSS fixture for Orb + PQV ownership proof.

No Streamlit runtime. Injects APP_CSS then PLAYER_QUICK_VIEW_CSS, wraps PQV
in stDialog, and uses vendored Sleeper CDN bytes (PNG served from .jpg URLs).
"""

from __future__ import annotations

from pathlib import Path

from modules.app_styles import APP_CSS
from modules.compact_fantasy_assets import COMPACT_FANTASY_ASSET_CSS, compact_asset_html
from modules.daily_gm_briefing_ui import DAILY_GM_BRIEFING_CSS
from modules.player_images import get_player_headshot_url, headshot_content_type, headshot_data_url
from modules.player_profile_ui import avatar_html
from modules.player_quick_view import pqv_hero_html
from modules.player_quick_view_styles import PLAYER_QUICK_VIEW_CSS
from modules.player_tier_identity import resolve_player_tier_identity
from modules.html_rendering import normalized_style_block
from modules.trade_hub_ui import TRADE_SUMMARY_COMPONENT_CSS


ROOT = Path(__file__).resolve().parents[1]
HEADSHOT_DIR = ROOT / "tests" / "fixtures" / "sleeper_headshots"

REPRESENTATIVE_PLAYERS = (
    ("11655", "Tyrone Tracy", "RB", "NYG", "TT"),
    ("4199", "Aaron Jones", "RB", "MIN", "AJ"),
    ("6794", "Justin Jefferson", "WR", "MIN", "JJ"),
    ("6904", "Jalen Hurts", "QB", "PHI", "JH"),
    ("1466", "Travis Kelce", "TE", "KC", "TK"),
)


def sleeper_fixture_path(sleeper_id: str) -> Path:
    return HEADSHOT_DIR / f"{sleeper_id}.jpg"


def sleeper_fixture_bytes(sleeper_id: str) -> bytes:
    path = sleeper_fixture_path(sleeper_id)
    if not path.is_file():
        raise FileNotFoundError(f"missing vendored Sleeper artwork {path}")
    return path.read_bytes()


def production_headshot_src(sleeper_id: str) -> str:
    return headshot_data_url(sleeper_fixture_bytes(sleeper_id))


def headshot_facts(sleeper_id: str) -> dict[str, object]:
    payload = sleeper_fixture_bytes(sleeper_id)
    return {
        "sleeper_id": sleeper_id,
        "cdn_url": get_player_headshot_url(sleeper_id),
        "bytes": len(payload),
        "content_type": headshot_content_type(payload),
        "magic": payload[:8].hex(),
    }


def _dialog_pqv(sleeper_id: str, name: str, position: str, team: str, initials: str) -> str:
    avatar = avatar_html(
        production_headshot_src(sleeper_id),
        initials,
        "player-detail-avatar player-quick-view-avatar",
    )
    hero = pqv_hero_html(
        avatar_html=avatar,
        name=name,
        position=position,
        team=team,
        age_text="26",
        source_label="Identity",
        role_label="Featured",
        overall_display="#12",
        position_display=f"{position} #5",
        dynasty_value="8,920",
        identity=resolve_player_tier_identity(stored_tier="Elite"),
        include_tier_legend=False,
    )
    return (
        '<div data-testid="stDialog">'
        '<div role="dialog">'
        f"{hero}"
        "</div></div>"
    )


def _orb_row(page_key: str, label: str, *, primary: bool = False) -> str:
    kind = "primary" if primary else "secondary"
    testid = f"stBaseButton-{kind}"
    return (
        f'<div class="st-key-mobile_sheet_row_{page_key}">'
        '<div data-testid="stVerticalBlock">'
        f'<div class="st-key-mobile_sheet_nav_{page_key}">'
        '<div data-testid="stButton">'
        f'<button kind="{kind}" data-testid="{testid}">'
        f"<div><p>{label}</p></div>"
        "</button></div></div></div></div>"
    )


def ownership_document(*, player_id: str = "11655") -> str:
    player = next(row for row in REPRESENTATIVE_PLAYERS if row[0] == player_id)
    sleeper_id, name, position, team, initials = player
    pqv = _dialog_pqv(sleeper_id, name, position, team, initials)
    orb = (
        '<div data-testid="stVerticalBlock">'
        '<div data-testid="stElementContainer"><div class="mobile-gm-sheet-marker"></div></div>'
        + _orb_row("dashboard", "Dashboard", primary=True)
        + _orb_row("my_team", "My Team")
        + _orb_row("trade_hub", "Trade Hub")
        + _orb_row("waivers", "Waivers")
        + "</div>"
    )
    trade = compact_asset_html(
        {
            "asset_type": "player",
            "player_id": "6904",
            "name": "Jalen Hurts",
            "position": "QB",
            "team": "PHI",
            "age": 27,
        },
        size="standard",
        show_value=False,
        show_role=False,
    )
    dashboard_avatar = avatar_html(
        production_headshot_src(sleeper_id),
        initials,
        "dg-compact-asset-avatar",
    )
    scan_avatar = avatar_html(
        production_headshot_src(sleeper_id),
        initials,
        "scan-card-avatar",
    )
    row_avatar = avatar_html(
        production_headshot_src(sleeper_id),
        initials,
        "compact-player-avatar",
    )
    dashboard = (
        '<div class="dg-game-plan-card" data-dashboard-portraits="1">'
        '<div class="dg-gp-identity-row">'
        '<div class="dg-compact-asset dg-compact-asset--standard dg-compact-asset--player">'
        f"{dashboard_avatar}"
        '<div class="dg-compact-asset-copy toa-chip-copy">'
        f'<div class="dg-compact-asset-name toa-chip-name">{name}</div>'
        f'<div class="dg-compact-asset-meta toa-chip-meta">{position} · {team}</div>'
        "</div></div></div>"
        '<div class="home-command-player-card"><div class="scan-card scan-card-compact">'
        f'<div class="scan-card-main">{scan_avatar}</div></div></div>'
        f'<div class="compact-player-row">{row_avatar}</div>'
        "</div>"
    )
    pqv_style = normalized_style_block(PLAYER_QUICK_VIEW_CSS)
    compact_style = normalized_style_block(COMPACT_FANTASY_ASSET_CSS + TRADE_SUMMARY_COMPONENT_CSS)
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{APP_CSS}
{pqv_style}
{compact_style}
{DAILY_GM_BRIEFING_CSS}
<style>body{{margin:0;background:#0b0d12;color:#e5e7eb;font-family:sans-serif}}</style>
</head><body>
{pqv}
{orb}
<div class="trade-summary-assets">{trade}</div>
{dashboard}
</body></html>
"""
