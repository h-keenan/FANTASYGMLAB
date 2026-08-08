# Marketing assets

## Landing (in-app, lazy)

Real FantasyGM Lab product assets used by the public Founder Beta landing.

| File | Source |
| --- | --- |
| `dashboard.jpg` / `dashboard-desktop.jpg` / `decision-memory.jpg` | `scripts/ui_validation_harness.py` via `scripts/capture_marketing_screenshots.py` |
| `trade-share.jpg` / `waiver-share.jpg` / `player-share.jpg` | Canonical share-card renderer (`modules/share_card_renderer.py`) |
| `trade-hub.jpg` / `waivers.jpg` / `player-quick-view.jpg` | Optional harness captures (regenerate with capture script) |

```bash
python scripts/capture_marketing_screenshots.py
```

## External launch kit

Production-ready distribution pack (not mounted by Streamlit):

`assets/marketing/launch/` — see `docs/founder-beta-launch-marketing-kit.md`

```bash
python scripts/generate_launch_marketing_assets.py
python scripts/generate_launch_marketing_assets.py --capture
```
