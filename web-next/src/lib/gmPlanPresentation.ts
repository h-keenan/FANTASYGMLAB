/**
 * GM Plan-specific presentation helpers. GET .../gm-plan's `reason` on the
 * quiet/not-ready path is the same classification shared by notReadyMessages.ts
 * (no linked Sleeper username, unresolved roster, etc.) — only the
 * page-specific copy lives here, matching alertsPresentation.ts/
 * tradeHubPresentation.ts's own thin wrappers over that shared classifier.
 */
import { notReadyReasonMessage } from "./notReadyMessages";

export function gmPlanReasonMessage(reason: string): string | null {
  return notReadyReasonMessage(reason, {
    linkAccount: "Link your Sleeper account to see a GM Plan for this league.",
  });
}
