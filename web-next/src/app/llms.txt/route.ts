import { SITE_URL } from "@/lib/seo/site";

/**
 * /llms.txt: a plain-text, link-first summary for LLM crawlers (llmstxt.org format). Only lists
 * public pages that exist; league-specific and account routes are intentionally absent (and are
 * disallowed in robots.txt). Season-gated pages (playoff SOS, rookie rankings) are described as
 * in-season / post-draft; they are in the sitemap only while they have data.
 */
export const dynamic = "force-static";

const BODY = `# FantasyDesk

> FantasyDesk is a dynasty fantasy football assistant: roster-aware trade verdicts, waiver ideas, lineup help and a weekly game plan built from a connected league. Public pages below use a league-agnostic 12-team PPR dynasty value board and need no account.

## Public tools

- [Free dynasty trade analyzer](${SITE_URL}/trade-analyzer): price a trade with the public value board.
- [Dynasty trade value chart](${SITE_URL}/dynasty-trade-value-chart): every top player's value on one page.
- [Dynasty rankings: QB](${SITE_URL}/dynasty-rankings/qb), [RB](${SITE_URL}/dynasty-rankings/rb), [WR](${SITE_URL}/dynasty-rankings/wr), [TE](${SITE_URL}/dynasty-rankings/te)
- [All dynasty tools](${SITE_URL}/dynasty-tools)
- [Fantasy playoff strength of schedule](${SITE_URL}/fantasy-playoff-strength-of-schedule): opponent points allowed by position for fantasy playoff weeks (in season).
- [Dynasty rookie rankings](${SITE_URL}/dynasty-rookie-rankings): the incoming rookie class (after the NFL draft).

## How values are made

- [Methodology](${SITE_URL}/methodology): how players are valued and what the numbers mean.
- Values blend in FantasyCalc market values; see the credit on each page.

## Player pages

- Each of the top 300 dynasty players has a page at ${SITE_URL}/dynasty-players/{player-name}; the full list is in ${SITE_URL}/sitemap.xml.

## Legal

- [Terms](${SITE_URL}/legal/terms), [Privacy](${SITE_URL}/legal/privacy), [No-affiliation disclaimer](${SITE_URL}/legal/no_affiliation)
`;

export function GET() {
  return new Response(BODY, { headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=3600" } });
}
