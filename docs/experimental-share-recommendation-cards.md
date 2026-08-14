# Share Recommendation Cards (#232 graduated Free)

Growth/distribution surface: generate polished FantasyGM Lab share images from
**existing canonical recommendation truth only**.

| Field | Value |
| --- | --- |
| Customer label | Share Recommendation |
| Experiment badge | none (graduated) |
| Kill switch | `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` (default **ON**; set `=0` to disable) |
| Baseline | after #231 (`002e4db8fb80311c4eb2e03741763ba9330c3b3b`) |
| Scope | Presentation only — no football logic, valuations, rankings, Trust, ordering, or lifecycle mutation |
| Entitlement | Free (acquisition) |

## Product goal

A manager sees a useful trade, waiver, or player recommendation → taps Share →
gets a clean 4:5 image suitable for Messages, Discord, Reddit, or X.

## Feature flag

When `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` is `0`/`false`/`off`:

- no Share controls
- no image generation
- no share analytics
- no render cost on normal page paths

## Supported surfaces (v1)

| Surface | Card type | Notes |
| --- | --- | --- |
| Trade Review (Trade Hub detail) | Trade | Primary format |
| Waivers (top 3 visible cards) | Waiver | Add/Stash/Watch only |
| Player Quick View | Player | Only when an **active** canonical recommendation exists |

Deferred: Today's Game Plan item share, My Team roster decision, GM Targets.

## Canonical share model

`ShareRecommendationCard` in `modules/share_recommendation_cards.py`:

- `card_type`, `title`, `action`, `reason`, `confidence`, `value_change`
- `acquire_lines` / `send_lines` (labels + optional player_id for portraits)
- `metrics`, `scoring_format`, `fingerprint`, `generated_at`
- brand footer + `fantasygmlab.com`

Builders:

- `build_trade_share_card(idea)` ← Trade Hub idea + `build_trade_narrative`
- `build_waiver_share_card(row, action=, reason=)` ← waiver board fields
- `build_player_share_card(..., narrative=)` ← active `CanonicalRecommendationNarrative` only

No parallel football interpretation layer.

## Privacy boundary

Share images and public dicts **omit**:

- email, account/user ids, roster id, league id
- league name (default omitted)
- invite info, tokens, provider payloads

Safe to post publicly.

## Rendering architecture

- Server-side deterministic **Pillow** PNG (`modules/share_card_renderer.py`)
- Dimensions: **2160 × 2400** (9:10 at 2× Retina; logical 1080×1200), composed for **320/390px** phone fit-to-screen
- In-app preview is a downscaled thumbnail (320px display); Share/Save uses the full PNG
- Trade cards use **one** bipolar value-edge bar (not two side bars)
- Compact QR footer: Scan to try FantasyGM Lab + FantasyGMLab.com
- On-demand only after Share tap
- Portrait fetch best-effort (2.5s); branded slate fallback on failure
- No AI image generation; no paid external renderer

## Free vs Premium

Sharing is acquisition. Free users may share recommendations **already visible** to Free.
Cards never include Premium-only inventory the user cannot see.

## Stale / neutral handling

- Empty trade packages → not shareable + refresh message
- Neutral PQV (no active recommendation) → not shareable
- Does not resurrect stale recommendation state

## Ordering / Trust / lifecycle

Hard contract: share generation does **not**:

- change Trade Hub order
- change Trust
- mutate recommendation lifecycle
- write football session truth

## Analytics (PR #164)

Events (when launch analytics enabled):

- `share_card_opened`
- `share_card_generated`
- `share_card_shared`
- `share_card_downloaded`

Props: allowlisted only (`item_kind`=card type, `source_surface`, `experiment_share_cards`, entitlement context). No card payload.

## Caching / temp files

- In-process memo by `fingerprint` (15 minute TTL, bounded)
- Temp PNGs under OS temp `fantasygmlab_share_cards/` with cleanup
- No user-controlled paths

## Native share / download

When the browser exposes the Web Share API (typical on iPhone Safari), Share
opens the system share sheet with the PNG file. Desktop and blocked iframes
fall back to **Save image** plus an on-page preview.

**iPhone Safari:** not claimed passing in CI. Manual gate: generate a card,
tap Share, confirm Messages/AirDrop targets, and save image.

v1 still always offers **Save image**.

## QR code

Every share PNG embeds one canonical QR owned by `modules/share_card_qr.py`.

- URL: `https://fantasygmlab.com` only
- High-contrast black-on-white with quiet zone (`border=4`)
- Bottom-right, labeled “Scan to try FantasyGM Lab”
- Not generated per-surface

## Visual design

Dark executive theme; actual FGL Arc Monogram raster (not plain “FGL” text);
Acquire vs Send stacked with proportional value bars; large names;
restrained cyan accent; FantasyGM Lab + QR + fantasygmlab.com footer.
Founder Beta is not used as share-card chrome.


## Tests

`tests/test_share_recommendation_cards.py` covers mapping, flag-off, privacy,
no synthetic player share, ordering non-mutation, cache, renderer smoke,
analytics event registration.

## Enablement

```text
DYNASTYGM_EXPERIMENTAL_SHARE_CARDS=1
```

Optional analytics:

```text
DYNASTYGM_LAUNCH_ANALYTICS=1
```

## Limitations / future

- Game Plan / My Team / GM Targets share surfaces
- Native Web Share / Discord bot posting
- Secure deep-link attribution / referral
- Square crop export convenience
- Multi-player trade overflow beyond 4 assets per side
