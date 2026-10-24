/**
 * Free-trial length shown on logged-out marketing surfaces.
 *
 * The authoritative value is the single TRIAL_DAYS constant in
 * supabase/functions/_shared/config.ts (optionally overridden by the
 * STRIPE_TRIAL_DAYS function secret), served by the public billing-plans
 * Edge Function as `trial_days`. DEFAULT_TRIAL_DAYS below is only the
 * pre-fetch / offline fallback; keep it equal to that constant.
 */
export const DEFAULT_TRIAL_DAYS = 3;

export function trialHeadline(days: number): string {
  if (!Number.isFinite(days) || days <= 0) return "Start free";
  return `Start free for ${days} ${days === 1 ? "day" : "days"}`;
}

/** Trial length from the public billing-plans function (no session needed).
 * Resolves to null on any failure or when the FastAPI rollback backend is
 * selected (that route requires auth), so callers keep the fallback. */
export async function fetchPublicTrialDays(signal?: AbortSignal): Promise<number | null> {
  if (process.env.NEXT_PUBLIC_BILLING_BACKEND === "fastapi") return null;
  const base = (process.env.NEXT_PUBLIC_SUPABASE_URL ?? "").replace(/\/+$/, "");
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
  if (!base || !anonKey) return null;
  try {
    const response = await fetch(`${base}/functions/v1/billing-plans`, {
      headers: { apikey: anonKey },
      signal,
    });
    if (!response.ok) return null;
    const body = (await response.json()) as { trial_days?: unknown };
    const days = typeof body.trial_days === "number" ? Math.trunc(body.trial_days) : NaN;
    return Number.isFinite(days) && days >= 0 && days <= 90 ? days : null;
  } catch {
    return null;
  }
}
