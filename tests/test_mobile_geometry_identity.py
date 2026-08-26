"""POST-319 mobile geometry, share cutout centering, and leaderboard identity."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from modules import comparative_metrics
from modules import share_card_renderer
from modules import share_recommendation_cards as share
from modules import ui_modal
from modules import workspace_ui
from modules.mobile_interaction_overlay_styles import MOBILE_INTERACTION_OVERLAY_CSS


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_strategy_context_is_a_vertical_stack_not_a_flex_badge():
    styles = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    unify = (ROOT / "modules" / "executive_design_unify_styles.py").read_text(encoding="utf-8")
    ui = (ROOT / "modules" / "valuation_archetype_ui.py").read_text(encoding="utf-8")
    compact = styles.replace(" ", "")
    assert 'key="dashboard_page_context"' in ui
    assert "Valuation:" in ui
    assert "Lens ·" not in ui
    assert "flex-direction:column" in compact or "display:block!important" in compact
    assert "flex:1 1 12rem" not in compact
    assert "white-space:normal!important" in compact
    assert "max-width:100%!important" in compact
    assert "flex-direction:column!important" in unify.replace(" ", "")
    assert "white-space:normal!important" in unify.replace(" ", "")
    assert "position:absolute" not in styles
    assert "overflow-x: hidden" not in styles


def test_game_plan_refresh_is_not_a_fixed_column_shove():
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    compact = briefing.replace(" ", "")
    assert "_refresh_row" in briefing
    assert "_meta_row" not in briefing
    assert briefing.count('"Refresh"') == 1
    assert "st.columns(" not in briefing
    assert "position:absolute" not in briefing
    assert "translate(" not in briefing
    assert "margin-left:-" not in compact
    assert "overflow-x:hidden" not in compact
    assert "flex-wrap:nowrap" not in compact or "stHorizontalBlock" not in briefing
    assert "flex-direction:column" in compact
    assert "@media(min-width:1024px)" in compact
    assert "st.html(" not in briefing
    assert "dg-game-plan-lede" in briefing
    assert "dg-game-plan-utility" in briefing
    header = briefing[
        briefing.index("with st.container(key=f\"{key_prefix}_header\")") : briefing.index(
            "if plan.quiet:"
        )
    ]
    assert header.index("dg-game-plan-lede") < header.index("dg-game-plan-utility")
    assert header.index("dg-game-plan-utility") < header.index("_refresh_row")
    assert "st.markdown(meta_html" in header


def test_mobile_overflow_owners_do_not_force_intrinsic_width():
    styles = (ROOT / "modules" / "dashboard_workflow_styles.py").read_text(encoding="utf-8")
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    modal = (ROOT / "modules" / "ui_modal_styles.py").read_text(encoding="utf-8")
    for source in (styles, briefing, modal):
        assert "min-width: 12rem" not in source
        assert "overflow-x: hidden" not in source
    assert "minmax(0, 1fr)" in modal
    assert "2.75rem minmax(0, 1fr)" in modal


def _right_padded_cutout(*, opaque: bool) -> bytes:
    from PIL import Image, ImageDraw

    canvas = Image.new("RGBA", (400, 220), (12, 14, 18, 0 if not opaque else 255))
    if opaque:
        canvas = Image.new("RGB", (400, 220), (12, 14, 18))
    body = Image.new("RGBA", (140, 200), (40, 90, 140, 255))
    draw = ImageDraw.Draw(body)
    draw.ellipse((35, 10, 105, 90), fill=(220, 190, 160, 255))
    if canvas.mode == "RGB":
        canvas.paste(body.convert("RGB"), (240, 12))
    else:
        canvas.paste(body, (240, 12), body)
    buf = BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def test_share_portrait_preserves_aspect_and_centers_visible_geometry():
    pytest.importorskip("PIL")
    from PIL import Image

    ImageMod, _, _ = share_card_renderer._require_pillow()
    box = 240
    raw = _right_padded_cutout(opaque=False)
    slot, meta = share_card_renderer.normalize_player_cutout_for_box(ImageMod, raw, box, box)
    assert slot.size == (box, box)
    assert meta["algorithm"] == "contain"
    assert meta["fitted_width"] <= box and meta["fitted_height"] <= box
    src_ratio = meta["trimmed_width"] / max(1, meta["trimmed_height"])
    fit_ratio = meta["fitted_width"] / max(1, meta["fitted_height"])
    assert abs(src_ratio - fit_ratio) < 0.02
    center = share_card_renderer.portrait_visible_horizontal_center(slot)
    assert center is not None
    assert abs(center - (box / 2)) <= box * 0.12


def test_share_opaque_cutout_crops_asymmetric_padding():
    pytest.importorskip("PIL")
    ImageMod, _, _ = share_card_renderer._require_pillow()
    box = 240
    raw = _right_padded_cutout(opaque=True)
    slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, raw, box, box)
    assert meta["trimmed_width"] < 360
    center = share_card_renderer.portrait_visible_horizontal_center(slot)
    assert center is not None
    assert abs(center - (box / 2)) <= box * 0.14


def test_missing_portrait_uses_branded_fallback_without_stretch():
    pytest.importorskip("PIL")
    ImageMod, _, _ = share_card_renderer._require_pillow()
    slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, None, 200, 200)
    assert slot.size == (200, 200)
    assert meta["algorithm"] == "contain"
    assert meta["fitted_width"] == 0


def test_named_share_portraits_are_not_visually_right_shifted():
    pytest.importorskip("PIL")
    from PIL import Image

    ImageMod, _, _ = share_card_renderer._require_pillow()
    players = (
        ("11655", "Tyrone Tracy"),
        ("12492", "Pat Bryant"),
        ("9225", "Tank Bigsby"),
        ("12527", "Ashton Jeanty"),
        ("12489", "RJ Harvey"),
    )
    box = 320
    results = {}
    for player_id, name in players:
        raw = share.fetch_portrait_bytes(player_id)
        if not raw:
            raw = _right_padded_cutout(opaque=False)
        slot, meta = share_card_renderer.fit_portrait_into_box(ImageMod, raw, box, box)
        src_ratio = meta["trimmed_width"] / max(1, meta["trimmed_height"])
        fit_ratio = meta["fitted_width"] / max(1, meta["fitted_height"])
        if meta["fitted_width"]:
            assert abs(src_ratio - fit_ratio) < 0.03
        center = share_card_renderer.portrait_visible_horizontal_center(slot)
        assert center is not None
        offset = abs(center - (box / 2)) / box
        results[name] = {"offset": round(offset, 4), "mode": meta["source_mode"]}
        assert offset <= 0.16, f"{name} visible-content offset {offset:.3f}"
    assert "Tyrone Tracy" in results
    assert "Pat Bryant" in results


def test_leaderboard_rows_use_session_avatars_and_initials_fallback():
    frame = pd.DataFrame(
        [
            {
                "roster_id": "1",
                "team_name": "American Njigba Warriors",
                "owner_name": "amatl7",
                "avatar_url": "https://sleepercdn.com/avatars/thumbs/abc123",
                "franchise_score": 133914,
            },
            {
                "roster_id": "2",
                "team_name": "Diddy's Lube Crew",
                "owner_name": "My team",
                "avatar_url": "",
                "franchise_score": 125310,
            },
            {
                "roster_id": "3",
                "team_name": "A Very Long Franchise Name That Must Wrap Cleanly",
                "owner_name": "an-unreasonably-long-owner-handle",
                "avatar_url": "javascript:alert(1)",
                "franchise_score": 110000,
            },
        ]
    )
    payload = comparative_metrics.dashboard_comparison_payloads(frame, "2")["Franchise Rank"]
    content = workspace_ui.canonical_summary_tile_modal_content(
        {"label": "Franchise Rank", "value": "#2", "comparison": payload}
    )
    html = ui_modal.modal_content_html(content, surface="dashboard_league_pulse")
    current = next(item for item in content.list_items if item.highlighted)
    missing = next(item for item in content.list_items if item.title.startswith("A Very Long"))
    first = content.list_items[0]
    assert current.kicker == "YOUR TEAM"
    assert current.title == "Diddy's Lube Crew"
    assert "YOUR TEAM ·" not in current.title
    assert current.avatar_initials == "DL"
    assert first.avatar_url.startswith("https://")
    assert "dg-modal-list-avatar" in html
    assert "dg-modal-list-kicker" in html
    assert "YOUR TEAM" in html
    assert "sleepercdn.com/avatars/thumbs/abc123" in html
    assert "javascript:" not in html
    assert "AN" in html or "AW" in html
    assert missing.avatar_initials == "AV"
    assert "dg-modal-list-row--highlighted" in html
    assert "an-unreasonably-long-owner-handle" in html
    assert "2.75rem" in (ROOT / "modules" / "ui_modal_styles.py").read_text(encoding="utf-8")


def test_orb_owner_and_lifecycle_contracts_are_unchanged():
    overlay = MOBILE_INTERACTION_OVERLAY_CSS
    assert "--dg-mobile-shell-clearance" in overlay
    assert "padding-block-end: var(--dg-mobile-shell-clearance)" in overlay
    assert '[data-testid="stMain"]' in overlay
    stmain = overlay.split('[data-testid="stMain"]', 1)[-1][:900]
    assert not any(
        line.strip().startswith("bottom: var(--dg-mobile-shell-clearance)")
        for line in stmain.splitlines()
    )
    assert "bottom: 0 !important" in overlay
    assert "scroll-padding-bottom: var(--dg-mobile-shell-clearance)" in overlay
    briefing = (ROOT / "modules" / "daily_gm_briefing_ui.py").read_text(encoding="utf-8")
    assert "OWNER_DASHBOARD_HERO" in briefing
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "_sync_platform_query_page(" in app
    from scripts.measure_interaction_rerun_architecture import count_explicit_reruns

    assert count_explicit_reruns() <= 62
