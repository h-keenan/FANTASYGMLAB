// The ONE "move this player" menu of the Fantasy Sim (web + mobile twin, byte-identical).
//
// A roster row used to show up to three always-visible controls (a "+" to IR / taxi, swap arrows, a "Cut" link). Now a row
// shows a single Move button; tapping it expands the row in place into an inline strip of ONLY the actions that are possible
// right now, with one primary. This module decides which actions exist (pure, tested); the strip component draws them and the
// screen supplies the handlers.

import { badgeFromTag, type BadgeInput } from "./playerBadges";
import { simBoardProjection, simDraftMeta, simDraftRowChips, simRowBadges } from "./simDraft";
import { simBlockTag } from "./simGame";
import { simGradeOf, simGradeText, type SimGradeInput } from "./simGrade";
import {
  simReserveActions,
  simTaxiSwapCandidates,
  type SimGamePlayer,
  type SimMoveContext,
  type SimSwapTarget,
} from "./simGame";

export type SimMoveKind = "swap" | "roster" | "ir" | "taxi" | "taxi_swap" | "block" | "cut" | "profile";

/** One slot or player to choose after the action button (a lineup slot to swap into, a taxi player to trade places with). */
export interface SimMoveTarget {
  key: string;
  label: string;
  hint?: string;
}

export interface SimMoveSpec {
  kind: SimMoveKind;
  label: string;
  /** The one gold control of the strip (at most one spec has it). */
  primary?: boolean;
  danger?: boolean;
  /** Present = tapping the button reveals these chips and the choice runs the action. */
  targets?: SimMoveTarget[];
  /** Present = the action asks "Cut Name?" with Cut / Keep first. */
  confirm?: string;
}

export interface SimMoveInput {
  player: SimGamePlayer;
  /** Squad rules; omit / null when the game has no IR or taxi squad. */
  reserve?: SimMoveContext | null;
  /** Taxi squad, for the "taxi is full: swap onto it" shortcut. */
  taxi?: readonly SimGamePlayer[];
  /** Bench player: the lineup slots he fits (empty = none fit). Omit for a starter or a player who is not on the roster. */
  swapTargets?: readonly SimSwapTarget[] | null;
  /** Starter: one "Change <slot>" action that opens the slot's candidate list. */
  changeSlot?: string | null;
  lineupLocked?: boolean;
  canCut?: boolean;
  /** Put on / take off the trade block; omit when blocks are off or he is not tradable. */
  block?: { on: boolean } | null;
  profile?: boolean;
}

function surname(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts[parts.length - 1] || name;
}

/** The possible actions for one roster player, in display order, with at most one primary. Impossible moves are omitted. */
export function simMoveSpecs(input: SimMoveInput): SimMoveSpec[] {
  const { player } = input;
  const out: SimMoveSpec[] = [];
  if (!input.lineupLocked) {
    if (input.changeSlot) {
      out.push({ kind: "swap", label: `Change ${input.changeSlot}` });
    } else if (input.swapTargets && input.swapTargets.length > 0) {
      out.push({
        kind: "swap",
        label: "Swap in",
        targets: input.swapTargets.map((t) => ({ key: String(t.index), label: t.label, hint: t.current ? `for ${surname(t.current.name)}` : "empty" })),
      });
    }
  }
  if (input.reserve) {
    for (const action of simReserveActions(player, input.reserve)) {
      if (action.check.ok) {
        out.push({ kind: action.to, label: action.to === "roster" ? action.label : action.to === "ir" ? "To IR" : "To taxi" });
        continue;
      }
      const swaps = simTaxiSwapCandidates(player, action, input.taxi ?? []);
      if (swaps.length > 0) {
        out.push({ kind: "taxi_swap", label: "Swap onto taxi", targets: swaps.map((p) => ({ key: p.id, label: p.name, hint: p.pos })) });
      }
    }
  }
  const first = out.find((s) => s.kind === "swap" || s.kind === "roster" || s.kind === "ir" || s.kind === "taxi" || s.kind === "taxi_swap");
  if (first) first.primary = true;
  if (input.block) out.push({ kind: "block", label: input.block.on ? "Off the block" : "Block" });
  if (input.profile) out.push({ kind: "profile", label: "Profile" });
  if (input.canCut) out.push({ kind: "cut", label: "Cut", danger: true, confirm: `Cut ${surname(player.name)}?` });
  return out;
}

/** True when the row needs a Move button: anything besides the always-available profile. */
export function simHasMove(specs: readonly SimMoveSpec[]): boolean {
  return specs.some((s) => s.kind !== "profile");
}

/** A custom stat a caller wants on the stats line (the recap's "Pts"): anything besides the standard PROJ / grade / ADP. */
export interface SimRowStat {
  key: string;
  label: string;
  value: string;
}

export interface SimAccordionRowModel {
  /** The one stats line under the name: TEAM · Age · Bye · PROJ (bye-soon in the warning tone); a caller stat rides after PROJ. */
  metaParts: { key: string; text: string; tone?: "warning" | "success" | "danger" | "muted" | "accent" }[];
  proj: number;
  adp: number | null;
  /** The letter grade as text ("A-", "B+?") for the expanded facts, and the object for the tile. */
  gradeText: string | null;
  gradeTile: SimGradeInput | null;
  /** Out chip, IR / taxi / rookie / bye, block and status tags, merged into the one badge strip after the name. */
  badges: BadgeInput[];
  /** Tags that are not badges: shown inside the expanded tile, never on the two-line row. */
  textTags: { key: string; label: string; tone?: string }[];
}

/**
 * Everything a sim player row shows, from the player alone. Never a numeric rating: the sim's overall is the letter grade.
 * `stats` are the legacy list stats (simListStats / a custom one): PROJ, the grade and ADP come from the player, anything else
 * is appended to the stats line.
 */
export function simAccordionRowModel(
  player: SimGamePlayer,
  opts: { week?: number | null; stats?: readonly SimRowStat[]; tags?: readonly { key: string; label: string; tone?: string }[] } = {},
): SimAccordionRowModel {
  const parts: SimAccordionRowModel["metaParts"] = simDraftMeta(player, opts.week ?? 0).map((m) => ({ key: m.key, text: m.text, tone: m.tone === "warning" ? "warning" : undefined }));
  const proj = simBoardProjection(player).value;
  parts.push({ key: "proj", text: `PROJ ${Number.isFinite(proj) ? proj.toFixed(1) : "-"}` });
  for (const stat of opts.stats ?? []) {
    if (stat.key === "proj" || stat.key === "ovr" || stat.key === "grade" || stat.key === "adp") continue;
    if (stat.value) parts.push({ key: stat.key, text: `${stat.label} ${stat.value}` });
  }
  const badges: BadgeInput[] = [];
  const chip = simDraftRowChips(player)[0];
  const chipBadge = chip ? badgeFromTag({ label: chip.label }) : null;
  if (chipBadge) badges.push(chipBadge);
  badges.push(...simRowBadges(player));
  const textTags: SimAccordionRowModel["textTags"] = [];
  const block = simBlockTag(player);
  for (const tag of [...(block ? [block] : []), ...(opts.tags ?? [])]) {
    const badge = badgeFromTag(tag);
    if (badge) badges.push(badge);
    else textTags.push(tag);
  }
  const gradeTile = simGradeOf(player);
  return {
    metaParts: parts,
    proj: Number.isFinite(proj) ? proj : 0,
    adp: player.adp != null && Number.isFinite(player.adp) ? player.adp : null,
    gradeText: gradeTile?.grade ? simGradeText(player) : null,
    gradeTile,
    badges,
    textTags,
  };
}
