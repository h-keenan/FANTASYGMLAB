"use client";

import { useState } from "react";

import { trackFeatureUse } from "@/lib/analytics";
import type { ReferralStatusResponse } from "@/lib/api";

/**
 * Account page (2026-10-19) — the referral program's own invite surface.
 * `modules/referrals.py` (a complete per-user invite link, leaguemate-
 * connection tracking, and a capped free-month GM Pro reward) was already
 * fully built, but only ever wired into the legacy Streamlit app — this is
 * its first appearance on web-next. Backed by GET /v1/referrals/my-code;
 * `referral === null && !error` is "still loading", `error` is a failed
 * fetch, and a populated response with `connected_count === 0` is just the
 * normal "share your link" empty state, not a separate layout.
 *
 * Copy-to-clipboard mirrors TradeIdeaCard.tsx's ShareTradeButton — the only
 * other clipboard write in web-next: a real `navigator.clipboard.writeText`
 * call, fail-soft (no Share API fallback needed here, this is a plain copy
 * action) if the browser/permission denies it.
 */
export function ReferralCard({
  referral,
  error,
  onRetry,
}: {
  referral: ReferralStatusResponse | null;
  error: string | null;
  onRetry: () => void;
}) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    if (!referral?.link) return;
    try {
      await navigator.clipboard.writeText(referral.link);
      setCopied(true);
      // `referral_sent` is already in the canonical taxonomy
      // (modules.launch_analytics.TRACKED_EVENTS) and paired server-side
      // with `referral_connected` (modules/referrals.py) -- this invite
      // action itself was never tracked (Founder Analytics audit, 2026-10).
      trackFeatureUse("referral_sent", { dedupe: false, props: { source_surface: "account" } });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // No clipboard permission in this browser -- nothing more to do.
    }
  };

  return (
    <section className="glass-surface p-4 flex flex-col gap-3" aria-labelledby="account-referral-heading">
      <h2
        id="account-referral-heading"
        className="text-xs font-bold uppercase"
        style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
      >
        Invite friends
      </h2>

      {error ? (
        <>
          <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
            {error}
          </p>
          <button
            type="button"
            onClick={onRetry}
            className="px-4 py-2 text-sm font-bold self-start"
            style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
          >
            Retry
          </button>
        </>
      ) : !referral ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Loading your invite link…
        </p>
      ) : (
        <>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            For every {referral.referrals_per_comp_month} friends who connect their Sleeper account through your
            link, you earn a free month of GM Pro, up to {referral.max_comp_months} free months total.
          </p>

          <div className="flex items-center gap-2">
            <input
              type="text"
              readOnly
              value={referral.link}
              aria-label="Your referral link"
              className="flex-1 px-3 py-2 text-sm"
              style={{
                border: "var(--border-width-default) solid var(--color-border)",
                background: "transparent",
                color: "var(--color-text-primary)",
              }}
              onFocus={(event) => event.currentTarget.select()}
            />
            <button
              type="button"
              onClick={handleCopy}
              className="px-4 py-2 text-sm font-bold"
              style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
            >
              {copied ? "Copied!" : "Copy link"}
            </button>
          </div>

          <dl className="flex flex-col gap-2 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt style={{ color: "var(--color-text-secondary)" }}>Friends joined</dt>
              <dd className="font-semibold">
                {referral.connected_count === 0 ? "None yet, share your link" : referral.connected_count}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt style={{ color: "var(--color-text-secondary)" }}>Free months earned</dt>
              <dd className="font-semibold">
                {referral.comp_months_granted} / {referral.max_comp_months}
              </dd>
            </div>
            {referral.comp_is_active ? (
              <div className="flex items-center justify-between gap-3">
                <dt style={{ color: "var(--color-text-secondary)" }}>Reward status</dt>
                <dd className="font-semibold" style={{ color: "var(--color-success)" }}>
                  Active{referral.comp_until ? ` through ${new Date(referral.comp_until).toLocaleDateString()}` : ""}
                </dd>
              </div>
            ) : null}
          </dl>
        </>
      )}
    </section>
  );
}
