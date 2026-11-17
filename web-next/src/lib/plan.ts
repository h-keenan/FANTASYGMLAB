/**
 * The ONE client-side answer to "is this person on Pro?".
 *
 * The server decides (GET /v1/me: profiles.entitlement from Stripe or
 * RevenueCat webhooks, plus a live referral comp). Every surface that needs a
 * plan reads it through here so web and app cannot drift:
 *   - "pro"     the server says paid access (Pro or Front Office)
 *   - "free"    the server READ the profile and it is Free
 *   - "unknown" the profile read failed; `entitlement` is only a fail-closed
 *               default, so never show a Free paywall or an Upgrade button
 *
 * Mobile twin: mobile/src/lib/plan.ts. Do not compare `entitlement` to a
 * literal anywhere else (lib/plan.test.ts enforces it).
 */
export type Plan = "pro" | "free" | "unknown";

export interface PlanSource {
  entitlement?: string | null;
  profile_status?: string | null;
}

const PAID = new Set(["premium", "pro", "front_office"]);

export function planOf(user: PlanSource | null | undefined): Plan {
  if (!user) return "unknown";
  if (user.profile_status === "error") return "unknown";
  return PAID.has(String(user.entitlement ?? "").toLowerCase()) ? "pro" : "free";
}

/** true / false once the plan is known, null while it is not (loading or unreadable). */
export function isProOrNull(user: PlanSource | null | undefined): boolean | null {
  const plan = planOf(user);
  return plan === "unknown" ? null : plan === "pro";
}

/**
 * Whether paid tabs/rows wear the gold Pro marker: only for a CONFIRMED Free
 * plan, and never for someone the App Store / Play reports as subscribed (their
 * webhook may not have landed in the profile yet). Web has no store, so pass false.
 */
export function showProMarkers(user: PlanSource | null | undefined, storeSubscriber: boolean): boolean {
  return planOf(user) === "free" && !storeSubscriber;
}
