/**
 * News digest model (docs/audits/ui-pass-3/news-options.html, V1 + the V2 player strip): the roster-first read of the
 * News page. Pure and byte-identical in web and mobile (scripts/check_lib_twins.mjs). Nothing here fetches: the page
 * hands it the roster-matched alerts (GET .../alerts, the only roster-aware news there is) and the general NFL feed
 * (GET /v1/news), and gets back what to draw: player rows with a verdict chip and a "what it means" line, the PFP filter
 * strip, and the league-wide items for the collapsed module. Every word comes from the real item (its headline, its
 * event type, the roster slot the alert already carries); a verdict is never invented for an item with no signal, it
 * is "Hold".
 */

export interface DigestItem {
  title: string | null;
  link: string | null;
  source: string | null;
  summary: string | null;
  published_ts: number | null;
  event_type: string | null;
  speculative: boolean;
  matched_player?: string | null;
  matched_player_id?: string | null;
  matched_player_position?: string | null;
  matched_player_team?: string | null;
  matched_player_tier?: string | null;
  read?: boolean;
  roster_relationship?: "starter" | "bench" | "taxi" | "ir" | null;
}

export type NewsVerdictKey = "start" | "watch" | "hold";
export type NewsVerdictTone = "success" | "warning" | "accent";
export interface NewsVerdict {
  key: NewsVerdictKey;
  label: string;
  tone: NewsVerdictTone;
}

export type NewsFilterKey = "all" | "injury" | "role" | "move";

/** The filter pills under the title. "Roster first" is the default (everything, your players on top). */
export const NEWS_FILTERS: { key: NewsFilterKey; label: string }[] = [
  { key: "all", label: "Roster first" },
  { key: "injury", label: "Injuries" },
  { key: "role", label: "Roles" },
  { key: "move", label: "Moves" },
];

const FILTER_EVENT: Record<Exclude<NewsFilterKey, "all">, string> = {
  injury: "injury/status",
  role: "role/depth chart",
  move: "transaction",
};

export function newsFilterMatches(filter: NewsFilterKey, eventType: string | null | undefined): boolean {
  return filter === "all" || eventType === FILTER_EVENT[filter];
}

const STRONG_NEGATIVE = /\b(out|ruled out|doubtful|questionable|limited|setback|surgery|torn|ir|injured reserve|suspend(?:ed|sion)?|inactive|did not practice|dnp|miss(?:es|ing)?|sidelined|lost for)\b/i;
const NEGATIVE = /\b(injur(?:ed|y)|strain|sprain|benched|demoted|cut|released|waived|traded|arrested|fined|dispute|holdout)\b/i;
const POSITIVE = /\b(full practice|full participant|cleared|returns?|returned|activated|expected to start|named (?:the )?starter|starting|promoted|lead back|workhorse|expects? \d+|boost|healthy|good to go|will play|back in|extension|signed)\b/i;

function text(item: Pick<DigestItem, "title" | "summary">): string {
  return `${item.title ?? ""} ${item.summary ?? ""}`;
}

const VERDICTS: Record<NewsVerdictKey, NewsVerdict> = {
  start: { key: "start", label: "Start", tone: "success" },
  watch: { key: "watch", label: "Watch", tone: "warning" },
  hold: { key: "hold", label: "Hold", tone: "accent" },
};

/**
 * Start / Watch / Hold for one item, from its event type, its wording and (for a rostered player) the slot he holds.
 * Start = good news for a player who can play for you; Watch = something can change his role or availability;
 * Hold = nothing to act on (including every unconfirmed report and anything with no clear signal).
 */
export function newsVerdict(item: DigestItem): NewsVerdict {
  if (item.speculative) return VERDICTS.hold;
  const body = text(item);
  const strong = STRONG_NEGATIVE.test(body);
  const negative = strong || NEGATIVE.test(body);
  const positive = POSITIVE.test(body);
  const slot = item.roster_relationship ?? null;
  const playable = slot !== "ir" && slot !== "taxi";
  switch (item.event_type) {
    case "injury/status":
      if (strong) return VERDICTS.watch;
      return positive && playable ? VERDICTS.start : VERDICTS.hold;
    case "role/depth chart":
      if (negative) return VERDICTS.watch;
      return positive && playable ? VERDICTS.start : VERDICTS.hold;
    case "transaction":
      return negative && slot ? VERDICTS.watch : VERDICTS.hold;
    default:
      return strong && slot ? VERDICTS.watch : VERDICTS.hold;
  }
}

/** The "what it means" line: the verdict spelled out for the slot he holds on your roster. Never claims a number. */
export function newsImpactLine(item: DigestItem, verdict: NewsVerdict): string {
  const slot = item.roster_relationship ?? null;
  if (verdict.key === "start") {
    if (slot === "starter") return "Good news for a starter. Keep him in your lineup.";
    if (slot === "bench") return "Trending up while he sits on your bench. Worth a look for your lineup.";
    return "A positive update. Worth knowing before you set your lineup.";
  }
  if (verdict.key === "watch") {
    if (slot === "starter") return "He is in your starting lineup. Check his status before lineups lock and have a backup ready.";
    if (slot === "bench") return "He is on your bench, so nothing changes this week, but keep an eye on it.";
    if (slot === "ir") return "Already on your IR. This is about his timeline.";
    if (slot === "taxi") return "On your taxi squad. This is about his long-term role, not this week.";
    return "This could change his role or availability. Check back before lineups lock.";
  }
  if (item.speculative) return "Unconfirmed. Hold until there is a second report.";
  return "No lineup change needed right now.";
}

/** Stable identity of the player an item is about: his id, else the lowercased name; null when it names no one. */
export function newsPlayerKey(item: Pick<DigestItem, "matched_player" | "matched_player_id">): string | null {
  if (item.matched_player_id) return String(item.matched_player_id);
  const name = item.matched_player?.trim().toLowerCase();
  return name ? name : null;
}

export interface NewsDigestRow {
  key: string;
  item: DigestItem;
  verdict: NewsVerdict;
  impact: string;
  playerKey: string | null;
}

export interface NewsStripPlayer {
  key: string;
  id: string | null;
  name: string;
  position: string | null;
  team: string | null;
  tier: string | null;
  /** True when any of his items is unread (the dot on his avatar). */
  unread: boolean;
  count: number;
}

export interface NewsDigest {
  /** Your players' items, starters first, then the feed's own order. */
  rows: NewsDigestRow[];
  /** One avatar per rostered player with news (the filter strip). */
  strip: NewsStripPlayer[];
  /** League-wide NFL items not already shown as one of your rows. */
  league: DigestItem[];
  /** How many rows are for a player in your starting lineup. */
  lineupCount: number;
}

function itemKey(item: DigestItem, index: number): string {
  return item.link ?? `${item.title ?? "item"}-${item.published_ts ?? 0}-${index}`;
}

export function buildNewsDigest(input: {
  /** Roster-matched alerts (empty when there is no league or no roster). */
  alerts: readonly DigestItem[];
  /** The general NFL feed. */
  general: readonly DigestItem[];
  filter: NewsFilterKey;
  /** A player picked on the strip (his `key`), or null. */
  playerKey: string | null;
}): NewsDigest {
  const { alerts, general, filter, playerKey } = input;
  const strip = new Map<string, NewsStripPlayer>();
  for (const item of alerts) {
    const key = newsPlayerKey(item);
    if (!key || !item.matched_player) continue;
    const seen = strip.get(key);
    if (seen) {
      seen.count += 1;
      seen.unread = seen.unread || item.read === false;
    } else {
      strip.set(key, {
        key,
        id: item.matched_player_id ?? null,
        name: item.matched_player,
        position: item.matched_player_position ?? null,
        team: item.matched_player_team ?? null,
        tier: item.matched_player_tier ?? null,
        unread: item.read === false,
        count: 1,
      });
    }
  }

  const toRow = (item: DigestItem, index: number): NewsDigestRow => {
    const verdict = newsVerdict(item);
    return { key: itemKey(item, index), item, verdict, impact: newsImpactLine(item, verdict), playerKey: newsPlayerKey(item) };
  };

  const alertLinks = new Set(alerts.map((a) => a.link).filter((l): l is string => Boolean(l)));
  const keep = (item: DigestItem) => newsFilterMatches(filter, item.event_type);
  const picked = (item: DigestItem) => !playerKey || newsPlayerKey(item) === playerKey;

  const rows = alerts
    .filter((a) => keep(a) && picked(a))
    .map(toRow)
    .map((row, index) => ({ row, index }))
    .sort((a, b) => Number(b.row.item.roster_relationship === "starter") - Number(a.row.item.roster_relationship === "starter") || a.index - b.index)
    .map(({ row }) => row);

  // A picked player also pulls his league-wide stories into his own list.
  const extra = playerKey ? general.filter((g) => keep(g) && picked(g) && !(g.link && alertLinks.has(g.link))).map((g, i) => toRow(g, alerts.length + i)) : [];
  const shownLinks = new Set(extra.map((r) => r.item.link).filter((l): l is string => Boolean(l)));
  const league = general.filter((g) => keep(g) && !(g.link && (alertLinks.has(g.link) || shownLinks.has(g.link))) && !(playerKey && picked(g)));

  return {
    rows: [...rows, ...extra],
    strip: [...strip.values()],
    league: playerKey ? [] : league,
    lineupCount: rows.filter((r) => r.item.roster_relationship === "starter").length,
  };
}

/** The title-row chip: "3 affect your lineup", "2 on your players", or "" when there is nothing roster-side. */
export function newsHeadlineChip(digest: Pick<NewsDigest, "rows" | "lineupCount">): string {
  if (digest.lineupCount > 0) return `${digest.lineupCount} affect your lineup`;
  if (digest.rows.length > 0) return `${digest.rows.length} on your players`;
  return "";
}

/** The league module's collapsed one-liner: the newest headline and how many more there are. */
export function newsLeaguePreview(league: readonly DigestItem[]): string {
  const first = league[0]?.title?.trim();
  if (!first) return "";
  return league.length > 1 ? `${first} and ${league.length - 1} more` : first;
}
