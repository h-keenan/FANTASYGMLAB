/** Opponent profile card (GET /v1/leagues/{id}/teams/{roster_id}/profile).
 * Mirrors mobile/src/lib/opponentProfile.ts. Every field is nullable/empty
 * when the server could not compute it; the card shows nothing for those. */

export interface OpponentRoom {
  position: string;
  rank: number;
  of: number;
  score: number;
  classification: string;
  tag: "surplus" | "need" | null;
}

export interface OpponentRank {
  position: string;
  rank: number;
  of: number;
}

export interface OpponentTradeTarget {
  player_id: string;
  name: string;
  position: string;
  team: string;
  /** "receive": ask for their player; "send": offer one of yours. */
  side: "receive" | "send";
}

export interface OpponentProfileResponse {
  ok: boolean;
  reason: string;
  roster_id: string;
  is_me?: boolean;
  direction?: {
    key: string | null;
    label: string | null;
    rank: number | null;
    league_size: number | null;
    record: string | null;
    confidence_label: string | null;
  };
  rooms?: OpponentRoom[];
  strongest?: OpponentRank | null;
  weakest?: OpponentRank | null;
  surplus?: string[];
  needs?: string[];
  starter_bench?: { starter_rank: number; bench_rank: number; of: number; label: string; note: string } | null;
  picks?: {
    rank: number | null;
    of: number;
    pick_count: number | null;
    first_rounders: number | null;
    firsts_acquired: number;
    firsts_sent: number;
  } | null;
  trade_tendency?: { label: string; sell_count: number; buy_count: number; min_trades: number } | null;
  trade_angle?: { text: string; target: OpponentTradeTarget | null } | null;
}

export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1:
      return `${n}st`;
    case 2:
      return `${n}nd`;
    case 3:
      return `${n}rd`;
    default:
      return `${n}th`;
  }
}

/** "RB, 1st of 12". */
export function rankText(item: { position: string; rank: number; of: number }): string {
  return `${item.position}, ${ordinal(item.rank)} of ${item.of}`;
}

export function picksText(picks: NonNullable<OpponentProfileResponse["picks"]>): string {
  const parts: string[] = [];
  if (picks.rank != null) parts.push(`${ordinal(picks.rank)} of ${picks.of} in draft capital`);
  if (picks.pick_count != null) parts.push(`${picks.pick_count} pick${picks.pick_count === 1 ? "" : "s"}`);
  if (picks.first_rounders != null) parts.push(`${picks.first_rounders} first${picks.first_rounders === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

/** Recent 1st-round flow, only when it moved (never "0 in, 0 out"). */
export function firstsFlowText(picks: NonNullable<OpponentProfileResponse["picks"]>): string | null {
  if (!picks.firsts_acquired && !picks.firsts_sent) return null;
  return `Firsts: ${picks.firsts_acquired} acquired, ${picks.firsts_sent} traded away`;
}

export function offerCaption(target: OpponentTradeTarget): string {
  return target.side === "receive"
    ? `Opens the Trade Analyzer asking for ${target.name} (${target.position}).`
    : `Opens the Trade Analyzer offering ${target.name} (${target.position}).`;
}

/** True when there is at least one read worth rendering. */
export function hasProfileContent(profile: OpponentProfileResponse | null | undefined): boolean {
  if (!profile || !profile.ok || profile.reason) return false;
  return Boolean(
    profile.direction?.label ||
      (profile.rooms && profile.rooms.length > 0) ||
      profile.starter_bench ||
      profile.picks ||
      profile.trade_angle,
  );
}
