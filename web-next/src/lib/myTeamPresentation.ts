/**
 * My Team-specific presentation helpers — pure ports of small, PURE
 * composition functions from modules/my_team_ui.py (room_outlook_label,
 * build_construction_observations) and modules/football_assets.py
 * (injury_badge_html's tone resolution). No valuation or need-
 * classification logic lives here: that stays server-side in
 * GET .../my-team-needs (modules.trade_analyzer_fit /
 * modules.roster_needs) — these functions only decide which of a
 * handful of pre-computed fields to show and what tone to color them,
 * the same tier of port Revision 1's formatRank/ageLabel already are.
 */

import type { PositionNeedGroup } from "./api";

export type ObservationTone = "strength" | "need" | "health" | "opportunity";

export interface ConstructionObservation {
  label: string;
  /** Text before the colored room mention(s), e.g. "Address ". Empty when
   * the title has no room mention (e.g. "Draft capital #2"). */
  titlePrefix: string;
  /** Position codes to render colored (via positionTextClass), joined
   * with " / " by the caller — empty when the title has no room mention. */
  rooms: string[];
  /** Text after the colored room mention(s), e.g. " next" or the whole
   * title when `rooms` is empty. */
  titleSuffix: string;
  body: string;
  tone: ObservationTone;
}

/**
 * Up to 3 roster observations — byte-for-byte port of
 * modules/my_team_ui.py's build_construction_observations (minus the
 * title_html/body_html pre-rendering, which the caller does itself with
 * positionTextClass).
 */
export function buildConstructionObservations({
  strengths,
  weaknesses,
  healthFlag,
  draftCapitalRank,
  draftCapitalRankTied,
  showFranchiseConstruction,
  archetypeStrengths,
  archetypeLabel,
  formatRank,
}: {
  strengths: string[];
  weaknesses: string[];
  healthFlag: string | null | undefined;
  draftCapitalRank: number | null;
  draftCapitalRankTied: boolean;
  showFranchiseConstruction: boolean;
  archetypeStrengths?: string[];
  archetypeLabel?: string | null;
  formatRank: (rank: number | null, tied: boolean) => string;
}): ConstructionObservation[] {
  const observations: ConstructionObservation[] = [];

  if (strengths.length > 0) {
    const rooms = strengths.slice(0, 2);
    const roomsText = rooms.join(" / ");
    observations.push({
      label: "Strength",
      titlePrefix: "",
      rooms,
      titleSuffix: " can absorb a send",
      body: `Existing metrics mark ${roomsText} as a relative strength, so this room can support an outgoing trade without becoming the next roster hole.`,
      tone: "strength",
    });
  } else if (archetypeStrengths && archetypeStrengths.length > 0) {
    observations.push({
      label: "Strength",
      titlePrefix: archetypeStrengths[0] || "Construction edge",
      rooms: [],
      titleSuffix: "",
      body: archetypeLabel || "Use this construction read when deciding what to send versus keep.",
      tone: "strength",
    });
  }

  const normalizedHealth = (healthFlag || "").trim().toLowerCase();
  if (weaknesses.length > 0) {
    const rooms = weaknesses.slice(0, 2);
    const roomsText = rooms.join(" / ");
    observations.push({
      label: "Pressure point",
      titlePrefix: "Address ",
      rooms,
      titleSuffix: " next",
      body: `Coverage is thin at ${roomsText}. Treat this as the next waiver add or trade-in posture before it becomes a weekly starter problem.`,
      tone: "need",
    });
  } else if (normalizedHealth && !["stable", "healthy"].includes(normalizedHealth)) {
    observations.push({
      label: "Pressure point",
      titlePrefix: "Injury context is changing posture",
      rooms: [],
      titleSuffix: "",
      body: `${healthFlag} Prefer short-term replacements over selling the depth that currently covers this risk.`,
      tone: "health",
    });
  }

  if (draftCapitalRank !== null && draftCapitalRank > 0 && draftCapitalRank <= 4 && showFranchiseConstruction) {
    observations.push({
      label: "Future flexibility",
      titlePrefix: `Draft capital ${formatRank(draftCapitalRank, draftCapitalRankTied)}`,
      rooms: [],
      titleSuffix: "",
      body: "Above-average owned picks give more roster optionality.",
      tone: "opportunity",
    });
  }

  return observations.slice(0, 3);
}

export interface PositionGroupItem {
  position: string;
  label: string;
  tone: ObservationTone | "strategy";
  /** " · Superflex" / " · 1QB" / " · TE Premium", or "" — rendered plain
   * (unstyled) after the colored `position` text, matching
   * modules/my_team_ui.py's title_html (only the position itself gets
   * position_text_html's color, the context bits are appended as-is). */
  contextSuffix: string;
  body: string;
}

const LABEL_TONE: Record<string, ObservationTone | "strategy"> = {
  Strength: "strength",
  Thin: "need",
  "Future risk": "need",
  "Upgrade room": "opportunity",
  "Injury pressure": "health",
};

/** Byte-for-byte port of modules/my_team_ui.py's room_outlook_label. */
function roomOutlookLabel({
  position,
  classification,
  strengthSet,
  upgradeOpportunity,
  temporaryInjuryPressure,
}: {
  position: string;
  classification: string;
  strengthSet: Set<string>;
  upgradeOpportunity: boolean;
  temporaryInjuryPressure: boolean;
}): string {
  if (strengthSet.has(position)) return "Strength";
  const kind = (classification || "").trim().toLowerCase();
  if (kind === "short_term_need") return "Thin";
  if (kind === "future_risk") return "Future risk";
  if (upgradeOpportunity) return "Upgrade room";
  if (temporaryInjuryPressure) return "Injury pressure";
  return "Covered";
}

/** Port of modules/my_team_ui.py's _position_groups_items (minus HTML
 * building). */
export function buildPositionGroupItems({
  positionGroups,
  strengths,
  superflex,
  tePremium,
}: {
  positionGroups: PositionNeedGroup[];
  strengths: string[];
  superflex: boolean;
  tePremium: boolean;
}): PositionGroupItem[] {
  const strengthSet = new Set(strengths.map((s) => s.toUpperCase()));
  return positionGroups
    .map((assessment) => {
      const position = (assessment.position || "").toUpperCase();
      if (!position) return null;
      const label = roomOutlookLabel({
        position,
        classification: assessment.classification,
        strengthSet,
        upgradeOpportunity: assessment.upgrade_opportunity,
        temporaryInjuryPressure: assessment.temporary_injury_pressure,
      });
      const contextBits: string[] = [];
      if (position === "QB") contextBits.push(superflex ? "Superflex" : "1QB");
      if (position === "TE" && tePremium) contextBits.push("TE Premium");
      const contextSuffix = contextBits.length > 0 ? ` · ${contextBits.join(" · ")}` : "";
      const body = assessment.reasons[0] || "Existing coverage assessment.";
      const tone = LABEL_TONE[label] ?? "strategy";
      return { position, label, tone, contextSuffix, body };
    })
    .filter((item): item is PositionGroupItem => item !== null);
}

/** Injury pill tone — mirrors modules/football_assets.py's
 * injury_badge_html tone resolution (applied to the already-resolved
 * `injury_label` display string, e.g. "Questionable"/"Out"/"IR", rather
 * than a raw Sleeper status code). */
export function injuryTone(label: string | null | undefined): "warning" | "danger" | "neutral" {
  const normalized = (label || "").trim().toLowerCase();
  if (!normalized) return "neutral";
  if (normalized.includes("quest") || normalized.includes("doubt")) return "warning";
  return "danger";
}

/** Sum of a lineup slice's `score` field — same presentation-only
 * aggregate app.py's My Team route computes for Roster Signals/Roster
 * Core (sum of the exact per-player score already shown on each row). */
export function sumScore(players: { score: number | null }[]): number {
  return players.reduce((sum, player) => sum + (player.score ?? 0), 0);
}

export function formatScore(value: number): string {
  if (!value) return "—";
  return Math.round(value).toLocaleString();
}

/** Same not-ready `reason` values GET .../my-team (and .../dashboard)
 * return, and the same plain-language copy mobile's MyTeamScreen.tsx
 * already shows for each — one source of truth for the empty-state
 * copy instead of a third hand-kept copy here. */
const NO_LEAGUE_REASONS = new Set([
  "no_sleeper_username_linked",
  "sleeper_user_not_found",
  "not_a_member_of_league",
]);

export function myTeamReasonMessage(reason: string): string | null {
  if (NO_LEAGUE_REASONS.has(reason)) {
    return "Link your Sleeper account and join this league from Home to see your lineup.";
  }
  if (reason === "empty_roster") {
    return "Your roster in this league looks empty.";
  }
  if (reason === "no_player_data") {
    return "Player data isn't available right now — try again in a bit.";
  }
  return null;
}
