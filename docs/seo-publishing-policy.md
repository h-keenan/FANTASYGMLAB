# SEO publishing policy

Guardrails for the public SEO pages (`/dynasty-tools`, `/dynasty-rankings/[position]`,
`/dynasty-trade-value-chart`, `/dynasty-players/[slug]`). Written to stay clear of Google's
scaled content abuse policy: every page must exist because it helps a reader, not because a
template can stamp it out.

## What may be published

A page ships only if all of these hold:

1. **Real data.** Every number and statement comes from a field we have
   (`GET /v1/public/dynasty-values`: value, ranks, age, tier, workload trend, injury/roster
   status). No invented stats, projections, quotes, or claims about a player's future.
2. **Minimum content.** Player pages need at least 4 distinct data-backed facts
   (`MIN_PLAYER_FACTS`), a positive value and a supported position. Rankings pages need at
   least 10 players (`MIN_RANKINGS_PLAYERS`). Anything below the bar returns 404 (and
   `noindex`), never a placeholder.
3. **Unique purpose.** One page per distinct search intent. No near-duplicate variants
   (for example the same list re-titled for many keywords).
4. **Attribution kept.** Every value page renders the FantasyCalc credit link in the initial
   HTML (`ValuesCredit`). Do not remove it, and do not imply endorsement.
5. **No private data.** Pages use only the anonymous default-settings board. Nothing from a
   user's league, roster, or account.
6. **Held topics stay out.** Do not publish content about hosting leagues or the college game
   until legal clears them.

## Rate limits

- **At most 5 new pages (new URL templates or new hand-written content pages) per day** to
  start. The data-driven player/rankings pages are generated from the existing board, so
  the cap applies to *new page types and new editorial pages*, not to daily data refresh of
  existing URLs.
- No mass publication: never add more than ~25 URLs of a brand-new template in one PR.
  Launch a new template with a small batch first.
- Raise the cap only after Search Console shows the earlier batch being indexed and
  getting impressions, and a human signs off.

## Human review

- **First batches are always reviewed by a person** before merge: the first PR of any new
  template, and the first 3 batches after it. Reviewer checks the rendered page (mobile
  width, 390px), the title/H1/meta, JSON-LD, the facts against the source data, and that
  the FantasyCalc credit is present.
- Everything goes through the normal PR flow (branch, PR, CI, merge). There is **no
  automatic publishing to production**, and no job may push to `main`.

## How the daily loop picks opportunities

1. Run `python scripts/seo_opportunities.py` (needs gcloud ADC with Search Console access).
   It writes `artifacts/seo/seo_opportunities.{json,md}` (gitignored): queries at average
   position 5-30 with real impressions, ranked by `impressions * closeness to page one`,
   each with the page that earns it today.
2. A human (or an agent a human is watching) triages the top rows:
   - Query already served by a page we have: improve that page (title, intro, internal links,
     missing real facts) instead of creating another page.
   - Query is a genuinely new intent that our data can answer: propose **one** new page,
     within the daily cap.
   - Query we cannot answer with real data, or that touches a held topic: skip it.
3. If Search Console has no data yet (new properties), the report says so and the loop does
   nothing. Do not fall back to guessing keywords.
4. Each proposed page goes up as a PR with the source fields it uses listed in the
   description. Check indexing and impressions after about 2 weeks before building more of
   the same kind.

## Quality triggers to pause

Stop publishing and investigate if Search Console reports "Crawled, currently not
indexed" or "Duplicate" for a meaningful share of new pages, a manual action appears, or the
value API has been failing (pages would be stale). Thin or stale pages should be removed or
fixed, not left up.
