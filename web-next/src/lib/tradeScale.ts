// Pure model for the trade builder's "two-column scale" (coridian_ pick, ui-pass-3 topic 3, V1): Give and Get side by side,
// the fairness meter under them updating live, and the verdict replacing the add buttons once the offer is ready.
// Byte-identical in web-next/src/lib and mobile/src/lib (scripts/check_lib_twins.mjs IDENTICAL).
import type { FairnessMeter, PlayerRef } from "./playerAnatomy";
import { simHeadshotId, simIsPick, simPickLabelText, simProjText, type SimGamePlayer, type SimPickAsset, type SimTradeAsset } from "./simGame";

/**
 * empty    nothing on either side: both columns show their "+" tile.
 * building one side is still empty: the meter says what is missing, the "+" tiles stay.
 * review   both sides filled and the user has not asked to change anything: verdict + Send / Tweak replace the "+" tiles.
 * tweak    both sides filled and the user tapped Tweak: the "+" tiles and remove buttons are back; "Review" returns.
 */
export type TradeScalePhase = "empty" | "building" | "review" | "tweak";

export function tradeScalePhase(input: { giveCount: number; getCount: number; tweaking: boolean }): TradeScalePhase {
  const { giveCount, getCount, tweaking } = input;
  if (giveCount <= 0 && getCount <= 0) return "empty";
  if (giveCount <= 0 || getCount <= 0) return "building";
  return tweaking ? "tweak" : "review";
}

/** What the meter should say while the offer is incomplete ("Add something you get"). Null once both sides have an asset. */
export function tradeScaleMissing(giveCount: number, getCount: number): string | null {
  if (giveCount <= 0 && getCount <= 0) return "Add what you send and what you get";
  if (giveCount <= 0) return "Add something you send";
  if (getCount <= 0) return "Add something you get";
  return null;
}

/** Side header count: "2" or "2 of 6" when the league caps the number of assets per side. */
export function tradeScaleCount(count: number, max?: number | null): string {
  return max && max > 0 ? `${count} of ${max}` : String(count);
}

export type SimScaleDecision = "accept" | "counter" | "decline";

/**
 * The Fantasy Sim's meter: the AI manager's answer in three coarse, plain-word steps (their public decision, never a value).
 * `null` while the answer is still loading. Left is decline, middle is counter, right is accept.
 */
export function simAcceptanceMeter(decision: SimScaleDecision | null): FairnessMeter {
  if (decision === "accept") return { position: 0.83, edge: 0, label: "They would accept", description: "Their answer: they would accept this offer", tone: "success" };
  if (decision === "counter") return { position: 0.5, edge: 0, label: "They would counter", description: "Their answer: they would counter this offer", tone: "warning" };
  if (decision === "decline") return { position: 0.17, edge: 0, label: "They would decline", description: "Their answer: they would decline this offer", tone: "danger" };
  return { position: 0.5, edge: 0, label: "Checking their answer", description: "Their answer is loading", tone: "muted" };
}

/** A scale card without the platform's tap handler (web `onOpen`, app `onPress`), so both platforms map sim assets the same way. */
export interface SimScaleAsset {
  key: string;
  player?: PlayerRef;
  pickLabel?: string;
  detail?: string | null;
  /** The sim player behind the card, for the peek sheet; absent for picks. */
  source?: SimGamePlayer;
}

/** A sim player or pick as a scale card: avatar fields, "KC · Proj 14.2" (projection or "Bye" / "Out", never a rating) and the pick's label. */
export function simScaleAsset(asset: SimTradeAsset): SimScaleAsset {
  if (simIsPick(asset)) {
    const pick = asset as SimPickAsset;
    return { key: pick.id, pickLabel: `${simPickLabelText(pick)}${pick.own === false && pick.orig_team_name ? ` via ${pick.orig_team_name}` : ""}` };
  }
  const p = asset as SimGamePlayer;
  return {
    key: p.id,
    player: { id: p.id, name: p.name, position: p.pos, team: p.team ?? null, age: p.age ?? null, headshotId: simHeadshotId(p) },
    detail: [p.team, simProjText(p)].filter(Boolean).join(" · "),
    source: p,
  };
}
