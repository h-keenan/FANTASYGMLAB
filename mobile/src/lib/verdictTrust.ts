/**
 * Verdict trust surface (web twin: web-next/src/lib/verdictTrust.ts). The
 * block between the SHARED markers is byte-identical to the web file
 * (verdictTrust.test.ts compares them). Pure TS, no imports.
 */

// SHARED BEGIN
export interface VerdictAssumptions {
  /** One sentence: "Assumed: Superflex, PPR, Dynasty values, Contender posture; ...". */
  line: string;
  items: { key: string; label: string; value: string }[];
}

export const VERDICT_FEEDBACK_REASONS = [
  { key: "lineup_wrong", label: "Wrong about my lineup" },
  { key: "injury_wrong", label: "Injury or availability is off" },
  { key: "values_off", label: "Player values look off" },
  { key: "partner_wouldnt", label: "The other manager would never do this" },
  { key: "other", label: "Something else" },
] as const;

export type VerdictFeedbackReason = (typeof VERDICT_FEEDBACK_REASONS)[number]["key"];

export const VERDICT_TRUST_COPY = {
  assumptionsTitle: "What this assumed",
  report: "Report a bad verdict",
  reportPrompt: "What looks wrong?",
  cancel: "Cancel",
  sending: "Sending...",
  thanks: "Thanks, we will review this verdict. No personal details were sent.",
  failed: "Could not send that. Try again in a moment.",
} as const;
// SHARED END

/** What the reporter was looking at, echoed to the server for the reviewer. */
export interface VerdictReportContext {
  surface: "trade_analyzer" | "trade_hub" | "trade_finder";
  platform: "web" | "ios" | "android";
  leagueId: string;
  lens: string;
  strategy: string;
  sendIds: string[];
  receiveIds: string[];
  verdictLabel: string;
  confidence: string;
  valueDelta: number | null;
  assumptionsLine: string;
}
