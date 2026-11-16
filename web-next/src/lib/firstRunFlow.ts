/**
 * First-run flow state machine, shared by web (landing island) and mobile
 * (RootNavigator / Home). Byte-identical to mobile/src/lib/firstRunFlow.ts
 * (twin check + test).
 *
 * Owner decision 2026-11: "move the paywall after connect". A new account
 * signs in, connects a league and SEES ITS FIRST LEAGUE VIEW before any
 * trial or paywall. The offer is a dismissible card on that view, never a
 * stage of the flow, so no entitlement, trial or purchase status can block
 * a user: `firstRunStage` deliberately has no billing input at all.
 *
 *   sign_in -> intro (skippable, 1 tap) -> connect -> league_home (Today)
 *                                                       `- offer card (armed, dismissible)
 */
export type FirstRunStage = "sign_in" | "intro" | "connect" | "league_home" | "portfolio";

export interface FirstRunInput {
  signedIn: boolean;
  /** The intro carousel was completed or skipped (per account / device). */
  introSeen: boolean;
  /** Saved leagues once known; null while still loading (treated as none). */
  leagueCount: number | null;
}

export function firstRunStage({ signedIn, introSeen, leagueCount }: FirstRunInput): FirstRunStage {
  if (!signedIn) return "sign_in";
  const leagues = leagueCount ?? 0;
  if (leagues >= 2) return "portfolio";
  if (leagues === 1) return "league_home";
  return introSeen ? "connect" : "intro";
}

/** The trial offer's lifecycle for one account: armed on first connect, resolved once dismissed. */
export type TrialOfferState = "idle" | "armed" | "dismissed";

/** Arms the offer on the first league connect only; a dismissed offer never re-arms. */
export function armTrialOffer(state: TrialOfferState): TrialOfferState {
  return state === "idle" ? "armed" : state;
}

export function dismissTrialOffer(): TrialOfferState {
  return "dismissed";
}

/**
 * The offer card shows only on a loaded league home (the first value moment),
 * only while armed, and never to someone who already has Pro.
 */
export function shouldShowTrialOffer(input: { state: TrialOfferState; isPremium: boolean; onLeagueHome: boolean }): boolean {
  return input.state === "armed" && !input.isPremium && input.onLeagueHome;
}

/** Funnel step ids (feature_use onboarding step_viewed). Indexes are positions here. */
export const FIRST_RUN_FUNNEL_STEPS = ["level", "value", "connect", "first_league_view"] as const;
export type FirstRunFunnelStep = (typeof FIRST_RUN_FUNNEL_STEPS)[number];
export function funnelStepIndex(step: FirstRunFunnelStep): number {
  return FIRST_RUN_FUNNEL_STEPS.indexOf(step);
}

/** Offer card copy. Price and trial terms are never typed here: the Pro page shows the real ones before any purchase. */
export const TRIAL_OFFER_TITLE = "Want every move, not just the top few?";
export const TRIAL_OFFER_NOTE = "Free keeps working. Trial length and price are shown before you start anything.";
export const TRIAL_OFFER_CTA = "See Pro plans";
export const TRIAL_OFFER_DISMISS = "Continue free";

/**
 * Today's first-run prompt slot (audit F3). Three self-contained prompts can
 * want the top of Today before the briefing: the Start here checklist, the
 * direction check-in and the trial offer. The slot lets exactly ONE of them
 * render at a time, by this priority, so a brand-new account never stacks a
 * checklist, a direction question and a Pro pitch around its first answer.
 * Each prompt still owns its own "do I want to show" rule (storage, server
 * timing, entitlement); this only arbitrates between the ones that do.
 */
export type FirstRunPrompt = "start_here" | "direction_checkin" | "trial_offer";

/** Highest priority first. */
export const FIRST_RUN_PROMPT_PRIORITY: readonly FirstRunPrompt[] = ["start_here", "direction_checkin", "trial_offer"];

/** The one prompt allowed above the fold (the hard cap is one), or null when none wants the slot. */
export function firstRunPromptSlot(wants: Partial<Record<FirstRunPrompt, boolean>>): FirstRunPrompt | null {
  return FIRST_RUN_PROMPT_PRIORITY.find((kind) => wants[kind] === true) ?? null;
}
