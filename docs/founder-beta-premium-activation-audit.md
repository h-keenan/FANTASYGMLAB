# Founder Beta Premium Value & Activation Audit (PR #161)

| Field | Value |
| --- | --- |
| Baseline | `bda3bc0a0042f97a138aa714f11036a414f908ea` (post Decision Memory #160) |
| Scope | Presentation / discoverability / activation contracts only |
| Explicit non-changes | Football logic, Trust, rankings, valuations, auth math, Stripe price math, Decision Memory persistence semantics |
| Method | Free vs Premium walkthrough of first 2–3 minutes + locked-surface inventory |

## Verdict

Free users get a clear core job (Today's Game Plan → limited Next Moves → session What Changed → Trade/Waiver previews) before any Premium ask. Premium depth is labeled consistently with **Upgrade to Premium**. Decision Memory stays off by default; when enabled it is a restrained teaser **after** Free What Changed — never a replacement paywall. Stripe **test-mode** checkout code is ready; **real Founder Beta charges** still require Ops P0 completion (`docs/founder-beta-ops-activation.md`). Live billing remains explicitly disabled in product copy. Experiments are listed separately and are **not** sold as included-by-default Premium (see `docs/premium-conversion-intent-flow.md`).

## Free vs Premium — what each plan actually sees

| Surface | Free | Premium |
| --- | --- | --- |
| Dashboard Game Plan / Next Moves | Core briefing + limited moves | Expanded next-move stack |
| What Changed | Session transitions (always) | Session + optional Decision Memory when experiment on |
| Decision Memory | Off unless kill switch on; then discovery teaser only | Durable history when experiment on |
| League Pulse | Locked after preview value | Full league-wide posture |
| Trade Hub | Top ideas preview | Full board + player-focused search |
| Waivers | Priority Adds | Full board, FAAB helper, stash/watchlist |
| My Team | Core roster / advice | Advanced decisions, deep analysis, bench insulation |
| Player profile | Accessible profile (not falsely labeled Premium) | Same surface |
| Premium page | Plan inventory + test checkout when configured | Status + Manage Billing when Stripe customer linked |

## First 2–3 minutes — is Premium value obvious?

| Minute | Free path | Premium signal |
| --- | --- | --- |
| 0–1 | Import / open Dashboard; Game Plan answers “what now?” | No gate before first useful content |
| 1–2 | Limited Next Moves + session What Changed | Locks appear **after** useful Free content, with why-it-matters body |
| 2–3 | Trade preview / Priority Adds | Full-board locks explain depth; CTA routes to Premium page |

Premium is obvious as **more depth on the same jobs**, not a separate product. Inventory on the Premium page lists launch-ready included-now tools separately from experimental-when-enabled and possible-future items (Live Draft removed from “possible future” because Live Draft is already shippable elsewhere).

## Decision Memory — discoverable, not annoying

| Condition | Behavior |
| --- | --- |
| Kill switch off (default) | Invisible to Free and Premium |
| Free + on | Session What Changed kept; single quiet teaser + lock afterward |
| Premium + on | “View Decision Memory →” dialog; durable sync |
| Guests | No discovery (auth required) |

Contract: Free history is never replaced by a paywall. See `docs/experimental-decision-memory-contract.md`.

## Locked surfaces — why they matter

Locks use feature titles + one-line bodies that state the **decision job** unlocked (compare partners, spend FAAB well, avoid fragile lineups, etc.). Badge CTA and route button both use **Upgrade to Premium**.

## Upgrade path consistency

| Entry | CTA / route |
| --- | --- |
| `premium.render_premium_lock` badge | Upgrade to Premium |
| `app.render_premium_lock` button | Upgrade to Premium → intent → destination `premium` (auth first when guest) |
| Premium page | Founder Premium Monthly/Annual + Start Founder Premium checkout |
| Billing note | Test mode / no live charge until Ops enables live billing |

## Gates vs understanding

No Premium gate blocks:

- Today's Game Plan
- Limited Next Moves
- Session What Changed
- Trade idea preview
- Priority Adds
- Core roster / Front-Office Advice

Gates sit **after** those Free value moments.

## Founder Beta pricing / CTA coherence

- Kicker: Founder Beta
- Plan name: Founder Premium (Monthly / Annual)
- Checkout: Start Founder Premium checkout
- Honesty: Stripe test mode; no live charge from this flow
- Outcome line above checkout: deeper tools on the same surfaces Free already shows

Dollar amounts come from Stripe price ids (Ops), not hardcoded marketing prices in-app.

## Fresh-account paid-feature transitions

Expected matrix (manual OPS-P0-9; automated contracts below guard copy/routing):

1. Fresh Free → see Free value, locks explain depth, no self-upgrade.
2. Checkout success query → success message; entitlement still webhook-driven.
3. Premium profile → locks suppress; Premium inventory accessible.
4. Cancel / entitlement free → locks return; Decision Memory discovery only if experiment on.

## Stripe test-mode readiness for real Founder Beta payment

| Layer | Status |
| --- | --- |
| Checkout session helpers (`modules/stripe_billing.py`) | Ready |
| Webhook entitlement mapping (`modules/stripe_webhook.py`) | Ready |
| Premium page fail-closed when unconfigured | Ready |
| Live-mode rejection | Ready |
| Ops P0 secrets / SQL / webhook host / lifecycle | **Open** — see `docs/founder-beta-ops-activation.md` |

**Conclusion:** Product code is ready for Founder Beta **test-mode** payment once Ops completes P0. It is **not** cleared for live charges.

## Fixes shipped in this PR

1. Free What Changed retained; Decision Memory discovery is post-value teaser only
2. Lock route CTA aligned to **Upgrade to Premium** (intent-based; see #225)
3. Premium inventory: launch-ready depth only; experiments listed separately
4. Lock bodies tightened to explain why depth matters
5. Player profile no longer falsely labeled Premium-only
6. Checkout outcome sentence + coherent Founder Beta test-mode captions
7. Guest → auth → checkout intent resume; entitlement memo cleared on billing success (#225)

## Rollback boundary

Revert this PR’s presentation/docs/tests only. Does not roll back Decision Memory persistence (#160) or Stripe helpers.
