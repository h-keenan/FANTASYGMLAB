/**
 * Waivers-specific presentation helpers — pure ports of small, PURE
 * composition functions from modules/waivers_ui.py and modules/faab.py. No
 * valuation, confidence, or FAAB-math logic lives here: free-agent ranking,
 * confidence_label/confidence_reason, recommendation_label/tone, and the
 * faab block are all already computed server-side
 * (GET .../leagues/{id}/waivers) — these functions only decide how to
 * color/format an already-final value, the same tier of port
 * tradeHubPresentation.ts/myTeamPresentation.ts already are for their pages.
 */

import { injuryTone } from "./myTeamPresentation";
import { notReadyReasonMessage } from "./notReadyMessages";
import type { WaiverFaabGuidance, WaiverPlayer } from "./api";

/** Same not-ready `reason` values GET .../leagues/{id}/waivers can return —
 * copy matches mobile's WaiversScreen.tsx `reasonMessage` exactly. Shared
 * classification lives in lib/notReadyMessages.ts. */
export function waiversReasonMessage(reason: string): string | null {
  return notReadyReasonMessage(reason, {
    linkAccount: "Link your Sleeper account and join this league from Home to see waivers.",
    emptyRoster: "Your roster in this league looks empty, so there's nothing to weigh adds against yet.",
  });
}

/** modules.waivers_ui.waiver_recommendation_label's three tones -> this
 * app's existing semantic tokens (same opportunity/information/neutral
 * mapping mobile's recommendationToneColor uses: amber for "Add", cyan for
 * "Stash", muted slate for "Watch"). */
export function recommendationToneColor(tone: string | null | undefined): string {
  if (tone === "opportunity") return "var(--color-premium)";
  if (tone === "information") return "var(--color-accent)";
  return "var(--color-text-secondary)";
}

/** modules.waivers_ui.waiver_confidence_label's High/Medium/Low -> the same
 * tone vocabulary the recommendation pill above uses, so a Priority Add's
 * confidence reads in the same amber/"real signal" register as its Add/
 * Stash/Watch pill rather than a fourth ad hoc color. */
export function confidenceColor(label: string | null | undefined): string {
  const normalized = (label ?? "").trim().toLowerCase();
  if (normalized === "high") return "var(--color-premium)";
  if (normalized === "low") return "var(--color-text-muted)";
  return "var(--color-accent)";
}

/** Byte-for-byte port of modules/faab.py's FaabGuidance.as_label() split
 * into a prominent bid figure + a quieter budget-context caption, mirroring
 * mobile's FAABGuidance.tsx exactly (dollars when the league's remaining
 * budget is known, a percent-of-pool range otherwise) so this never
 * diverges from — or overstates the certainty of — the server's own
 * rule-of-thumb heuristic. */
export function faabIsBid(faab: WaiverFaabGuidance | null | undefined): faab is WaiverFaabGuidance {
  return faab != null && faab.applicable !== false;
}

/** Non-FAAB leagues (Sleeper rolling / reverse-standings waivers): no
 * dollars, only a claim label. Missing guidance renders the same way. */
export function waiverClaimText(faab: WaiverFaabGuidance | null | undefined): { primary: string; secondary: string } {
  const mode = faab?.waiver_mode;
  return {
    primary: "Waiver claim",
    secondary:
      mode === "rolling"
        ? "Rolling waivers · no FAAB"
        : mode === "reverse_standings"
          ? "Reverse-standings waivers · no FAAB"
          : "No FAAB bid",
  };
}

export function faabRangeText(faab: WaiverFaabGuidance | null | undefined): { primary: string; secondary: string } {
  if (!faabIsBid(faab)) return waiverClaimText(faab);
  const hasDollars = faab.dollars_known && faab.remaining != null;
  return {
    primary: hasDollars ? `$${faab.low_bid}–$${faab.high_bid}` : `${faab.pct_low}–${faab.pct_high}%`,
    secondary: hasDollars ? `of $${faab.remaining} remaining` : "of remaining FAAB",
  };
}

/** modules.waivers_ui.priority_adds_section_note's "Current need" framing —
 * the exact copy the UX audit called out as a standout, ported verbatim. */
export function priorityNeedNote(neededPositions: string[]): string {
  const positions = neededPositions.map((pos) => pos.toUpperCase()).filter(Boolean);
  if (positions.length > 0) {
    return `Current need: ${positions.join(" / ")}.`;
  }
  return "No primary positional need — high-value dynasty adds can still be worth a claim.";
}

/** Raw Sleeper injury_status ("questionable"/"out"/"ir"/...) -> a display
 * label + tone, reusing myTeamPresentation.ts's injuryTone (same
 * football_assets.py tone resolution) once the raw code is title-cased into
 * the label that function expects, instead of a second status->tone map. */
export function waiverInjuryDisplay(status: string | null | undefined): {
  label: string | null;
  tone: "warning" | "danger" | "neutral";
} {
  const trimmed = (status ?? "").trim();
  if (!trimmed) return { label: null, tone: "neutral" };
  const label = trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
  return { label, tone: injuryTone(label) };
}

/** modules.waivers_ui.annotate_sleeper_trending_add's pill copy — same
 * "Sleeper," never "in your league" framing (cross-league, last-24h signal,
 * not scoped to this league). */
export function trendingAddLabel(player: {
  sleeper_trending_add: boolean;
  sleeper_trending_add_count: number | null;
}): string | null {
  if (!player.sleeper_trending_add) return null;
  const count = player.sleeper_trending_add_count;
  return count ? `Trending on Sleeper +${count.toLocaleString()}` : "Trending on Sleeper";
}

/** The free-agent row's trailing context line: an injury-replacement note
 * takes priority over the plain opponent/opportunity-label context
 * (mirrors mobile's WaiversScreen.tsx contextLine derivation). */
export function freeAgentContextLine(player: WaiverPlayer): string | null {
  if (player.injury_replacement_fit && player.injury_replacement_note) {
    return player.injury_replacement_note;
  }
  if (player.opponent) {
    return `${player.opponent_is_home ? "vs" : "@"} ${player.opponent}`;
  }
  return player.opportunity_label ?? null;
}

export function formatWaiverScore(score: number | null | undefined): string {
  return score !== null && score !== undefined ? String(Math.round(score)) : "—";
}
