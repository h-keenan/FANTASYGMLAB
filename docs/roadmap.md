# FantasyDesk roadmap

Living doc for post-launch initiatives — bigger than a bug fix or polish
pass, intentionally deferred until the app is through initial launch and
the current bug-fix/polish cycle. Not an audit snapshot (see
`founder-beta-polish-roadmap.md` for that, a one-time pre-web-next pass) —
this gets added to over time as ideas come up.

## Open initiatives

### Web: full player-profile page (PQV parity gap)
coridian_, 2026-10-19: "the pqv on the app has tabs that the site doesn't.
That's a consistency error." Confirmed real, and not an accidental gap —
web-next's `PlayerQuickView.tsx` modal was deliberately scoped as a
condensed "quick look" (identity, value/rank, health/usage, season stats,
Model chips, awards, bio), with a documented intent at build time for a
separate, bigger "Open Profile" destination carrying what the modal
doesn't: career season-by-season history, news, schedule — matching
mobile's `PlayerDetailScreen.tsx` tabs (stats/trends/schedule/career/
model). That full page was never built. Queued (coridian_: "Queue it").

### Live Draft: needs real testing
Completely untested end-to-end. Not urgent right now (mid-season, nobody's
drafting), but must be verified before the next real draft window opens.

### In-app notifications
Website notifications for news alerts and similar real-time events —
currently nothing surfaces inside the app itself outside of visiting the
Alerts page.

### Social / community layer — SHIPPED 2026-10-19 (PR #1261)
Community Trade Feed: anonymized ("Team A traded with Team B," never real
identity), opt-on by default with a preferences toggle to turn off, reuses
the existing trade-outcome grading as the "interesting" signal rather than
a new heuristic. Reactions are emoji-only, no comments/replies. Surfaced to
everyone for now per coridian_'s call.

Not yet done: extending the same "interesting" framing to draft picks.

### Home screen widget
Mini dashboard widget, filtered to only very-high-priority items so it
doesn't get cluttered.

### Guess-the-player mini game — SHIPPED 2026-10-19 (web PR #1257, mobile PR #1258)
Dashboard card (web) / popup (mobile): "whose stats are these?" using real
last-week stats, full player card shown but photo/name blacked out
(tier/prestige ring still visible), multiple-choice guessing, a surprising
bench-tier stat line mixed into the options. Real persisted per-user
streak/best-streak record (`guess_the_player_streaks` table).

### Become a one-stop-shop platform: host leagues directly
Let people create/host leagues on FantasyDesk itself, not just import from
Sleeper. Needs real legal/regulatory research (fantasy-sports hosting
legality varies by state) and a stats-sourcing plan independent of
Sleeper's API. Big bet, not technically hard once researched, given the
app's infrastructure already exists.

coridian_, 2026-10-19: "we would not have anything to do with the money
aspect if that's the blocker for it" — league buy-ins/payouts would happen
user-to-user, off-platform, not through FantasyDesk. Meaningfully smaller
legal lift than running escrow/payments ourselves (no money-transmission
licensing), but still needs real research, not assumed clean — gambling-law
classification for a fantasy-sports contest can turn on more than who
moves the money (state-by-state skill-vs-chance tests, entry-fee
structuring, etc.).

Pairs with:
- Referral vouchers for whoever creates a league once it hits a join
  threshold — a real growth lever once hosting exists.

---
coridian_, 2026-10-19.
