"use client";

import { useState } from "react";

import type { MeResponse, PushCategory, ReferralStatusResponse } from "@/lib/api";
import { ReferralCard } from "@/components/ReferralCard";
import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import type { ExperienceLevel } from "@/lib/experienceCopy";
import { trialEndLabel } from "@/lib/trialCopy";
import { ButtonLink } from "@/components/Button";
import { OnboardingCarousel } from "@/components/OnboardingCarousel";
import { trackOnboarding } from "@/lib/onboardingAnalytics";

/** Mirrors mobile/src/screens/MoreScreen.tsx's PUSH_CATEGORY_LABELS exactly
 * — same four categories, same copy — so a user who's seen this in the app
 * recognizes it here. Order matches modules.push_triggers.
 * TOGGLEABLE_PUSH_CATEGORIES. */
const PUSH_CATEGORY_LABELS: Array<{ value: PushCategory; label: string; description: string }> = [
  { value: "top_priority", label: "Top Priority moves", description: "The single most urgent recommendation for your roster" },
  { value: "watch", label: "Watch items", description: "Worth knowing, not urgent" },
  { value: "recap", label: "Weekly recaps", description: "When a new League Recap is ready" },
  { value: "injury", label: "Injury updates", description: "A status change on your own roster (Questionable, Out, etc.)" },
];

function SectionHeading({ id, children, color }: { id: string; children: React.ReactNode; color?: string }) {
  return (
    <h2 id={id} className="text-xs font-bold uppercase" style={{ color: color ?? "var(--color-text-muted)", letterSpacing: "0.03em" }}>
      {children}
    </h2>
  );
}

function IdentitySection({ user }: { user: MeResponse["user"] }) {
  return (
    <section className="glass-surface p-4 flex flex-col gap-3" aria-labelledby="account-identity-heading">
      <SectionHeading id="account-identity-heading">Identity</SectionHeading>
      <dl className="flex flex-col gap-2 text-sm">
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--color-text-secondary)" }}>Email</dt>
          <dd className="font-semibold">{user.email || "—"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--color-text-secondary)" }}>Sleeper username</dt>
          <dd className="font-semibold">{user.sleeper_username || "Not linked"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--color-text-secondary)" }}>Plan</dt>
          <dd className="font-semibold" style={{ color: user.entitlement === "premium" ? "var(--color-premium)" : "var(--color-text-primary)" }}>
            {user.entitlement === "premium" ? "Premium" : "Free"}
          </dd>
        </div>
      </dl>
    </section>
  );
}

function BillingSection({
  entitlement,
  trialEndsAt,
  onOpenBillingPortal,
}: {
  entitlement: MeResponse["user"]["entitlement"];
  trialEndsAt?: string;
  onOpenBillingPortal: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <section className="glass-surface p-4 flex flex-col gap-3" aria-labelledby="account-billing-heading">
      <SectionHeading id="account-billing-heading">Billing</SectionHeading>
      {entitlement === "premium" ? (
        <>
          {trialEndLabel(trialEndsAt) ? (
            <p className="text-sm font-semibold">{trialEndLabel(trialEndsAt)}</p>
          ) : null}
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Manage your plan, payment method, or cancel anytime.
          </p>
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError(null);
              onOpenBillingPortal()
                .catch((err) => setError(err instanceof Error ? err.message : "Could not open the billing portal."))
                .finally(() => setBusy(false));
            }}
            className="px-4 py-2 text-sm font-bold self-start"
            style={{ background: "var(--color-premium)", color: "var(--color-bg)", opacity: busy ? "var(--opacity-disabled)" : 1 }}
          >
            {busy ? "Opening…" : "Manage Billing"}
          </button>
        </>
      ) : (
        <>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            You&apos;re on the Free plan.
          </p>
          <ButtonLink
            href="/premium"
          >
            Upgrade to Premium
          </ButtonLink>
        </>
      )}
    </section>
  );
}

const EXPLANATION_OPTIONS: Array<{ value: ExperienceLevel; label: string; description: string }> = [
  {
    value: "beginner",
    label: "Beginner",
    description: "Plain-language explanations of terms like value, tier and trade verdicts",
  },
  { value: "advanced", label: "Advanced", description: "The standard terse copy" },
];

/** The onboarding carousel's "How much dynasty experience do you have?"
 * answer, editable later. Reads/writes through ExperienceLevelContext (the
 * same /v1/preferences field), so the change applies across the app right
 * away. An unanswered account (null) shows Advanced, which is how it
 * already behaves. */
function ExplanationsSetting() {
  const { level, setLevel } = useExperienceLevel();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active: ExperienceLevel = level ?? "advanced";

  return (
    <div className="flex flex-col gap-2">
      <span id="account-explanations-label" className="text-sm font-semibold">
        Explanations
      </span>
      <div
        role="radiogroup"
        aria-labelledby="account-explanations-label"
        className="flex flex-col"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        {EXPLANATION_OPTIONS.map((option, index) => {
          const selected = active === option.value;
          return (
            <button
              key={option.value}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={saving}
              onClick={() => {
                if (selected) return;
                setSaving(true);
                setError(null);
                setLevel(option.value)
                  .catch(() => setError("Couldn't save this setting. Try again."))
                  .finally(() => setSaving(false));
              }}
              className="flex items-center justify-between gap-3 p-3 text-left"
              style={{
                borderTop: index === 0 ? "none" : "var(--border-width-default) solid var(--color-border)",
                background: selected ? "var(--color-action-soft)" : "transparent",
              }}
            >
              <span className="flex flex-col gap-0.5">
                <span className="text-sm">{option.label}</span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {option.description}
                </span>
              </span>
              <span
                className="px-2.5 py-1 text-xs font-bold"
                style={{
                  border: "var(--border-width-default) solid var(--color-border)",
                  color: selected ? "var(--color-success)" : "var(--color-text-muted)",
                }}
              >
                {selected ? "On" : "Off"}
              </span>
            </button>
          );
        })}
      </div>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PreferencesSection({
  communityOptedOut,
  onToggleCommunityOptOut,
  pushCategories,
  onTogglePushCategory,
}: {
  communityOptedOut: boolean;
  onToggleCommunityOptOut: (next: boolean) => void;
  pushCategories: Record<PushCategory, boolean> | null;
  onTogglePushCategory: (category: PushCategory, enabled: boolean) => void;
}) {
  const [togglingCommunity, setTogglingCommunity] = useState(false);
  const [togglingPush, setTogglingPush] = useState<PushCategory | null>(null);

  return (
    <section className="glass-surface p-4 flex flex-col gap-4" aria-labelledby="account-preferences-heading">
      <SectionHeading id="account-preferences-heading">Preferences</SectionHeading>

      <ExplanationsSetting />

      <div
        className="flex items-center justify-between gap-3 p-3"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold">Community Trade Feed</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            I don&apos;t want MY trades to appear in this feed
          </span>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={communityOptedOut}
          disabled={togglingCommunity}
          onClick={() => {
            setTogglingCommunity(true);
            Promise.resolve(onToggleCommunityOptOut(!communityOptedOut)).finally(() => setTogglingCommunity(false));
          }}
          className="px-2.5 py-1 text-xs font-bold"
          style={{
            border: "var(--border-width-default) solid var(--color-border)",
            color: communityOptedOut ? "var(--color-danger)" : "var(--color-success)",
          }}
        >
          {communityOptedOut ? "Opted out" : "Opted in"}
        </button>
      </div>

      {pushCategories ? (
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Push notifications</span>
          <div className="flex flex-col" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
            {PUSH_CATEGORY_LABELS.map((item, index) => (
              <div
                key={item.value}
                className="flex items-center justify-between gap-3 p-3"
                style={{
                  borderTop: index === 0 ? "none" : "var(--border-width-default) solid var(--color-border)",
                }}
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-sm">{item.label}</span>
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {item.description}
                  </span>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={pushCategories[item.value]}
                  disabled={togglingPush === item.value}
                  onClick={() => {
                    setTogglingPush(item.value);
                    Promise.resolve(onTogglePushCategory(item.value, !pushCategories[item.value])).finally(() =>
                      setTogglingPush(null),
                    );
                  }}
                  className="px-2.5 py-1 text-xs font-bold"
                  style={{
                    border: "var(--border-width-default) solid var(--color-border)",
                    color: pushCategories[item.value] ? "var(--color-success)" : "var(--color-text-muted)",
                  }}
                >
                  {pushCategories[item.value] ? "On" : "Off"}
                </button>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function AccountActionsSection({
  onExportData,
  onSignOut,
}: {
  onExportData: () => Promise<void>;
  onSignOut: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replaying, setReplaying] = useState(false);

  return (
    <section className="glass-surface p-4 flex flex-col gap-3" aria-labelledby="account-actions-heading">
      <SectionHeading id="account-actions-heading">Account actions</SectionHeading>
      <button
        type="button"
        onClick={() => {
          trackOnboarding("replayed");
          setReplaying(true);
        }}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
      >
        Replay the tour
      </button>
      {replaying ? <OnboardingCarousel replay onDone={() => setReplaying(false)} /> : null}
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          onExportData()
            .catch((err) => setError(err instanceof Error ? err.message : "Could not export your data."))
            .finally(() => setBusy(false));
        }}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{
          border: "var(--border-width-default) solid var(--color-border)",
          color: "var(--color-text-secondary)",
          opacity: busy ? "var(--opacity-disabled)" : 1,
        }}
      >
        {busy ? "Preparing export…" : "Export my data"}
      </button>
      <button
        type="button"
        onClick={onSignOut}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
      >
        Sign out
      </button>
    </section>
  );
}

function DeleteAccountSection({ onDeleteAccount }: { onDeleteAccount: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <section
      className="p-4 flex flex-col gap-3"
      style={{ border: "var(--border-width-default) solid var(--color-danger)" }}
      aria-labelledby="account-danger-heading"
    >
      <SectionHeading id="account-danger-heading" color="var(--color-danger)">
        Delete account
      </SectionHeading>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Permanently deletes your account and all data, saved leagues, GM Targets, trade history. This cannot be
        undone.
      </p>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      {!confirming ? (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="px-4 py-2 text-sm font-bold self-start"
          style={{ background: "var(--color-danger)", color: "var(--color-bg)" }}
        >
          Delete account
        </button>
      ) : (
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setBusy(true);
              setError(null);
              onDeleteAccount().catch((err) => {
                setError(err instanceof Error ? err.message : "Could not delete your account.");
                setBusy(false);
              });
            }}
            className="px-4 py-2 text-sm font-bold"
            style={{ background: "var(--color-danger)", color: "var(--color-bg)", opacity: busy ? "var(--opacity-disabled)" : 1 }}
          >
            {busy ? "Deleting…" : "Confirm delete"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming(false)}
            className="px-4 py-2 text-sm font-bold"
            style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
          >
            Cancel
          </button>
        </div>
      )}
    </section>
  );
}

export function AccountContent({
  user,
  communityOptedOut,
  onToggleCommunityOptOut,
  pushCategories,
  onTogglePushCategory,
  referral,
  referralError,
  onRetryReferral,
  onOpenBillingPortal,
  onExportData,
  onDeleteAccount,
  onSignOut,
}: {
  user: MeResponse["user"];
  communityOptedOut: boolean;
  onToggleCommunityOptOut: (next: boolean) => void;
  pushCategories: Record<PushCategory, boolean> | null;
  onTogglePushCategory: (category: PushCategory, enabled: boolean) => void;
  referral: ReferralStatusResponse | null;
  referralError: string | null;
  onRetryReferral: () => void;
  onOpenBillingPortal: () => Promise<void>;
  onExportData: () => Promise<void>;
  onDeleteAccount: () => Promise<void>;
  onSignOut: () => void;
}) {
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-2xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Account
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Your account</h1>
      </header>

      <IdentitySection user={user} />
      <BillingSection entitlement={user.entitlement} trialEndsAt={user.trial_ends_at} onOpenBillingPortal={onOpenBillingPortal} />
      <ReferralCard referral={referral} error={referralError} onRetry={onRetryReferral} />
      <PreferencesSection
        communityOptedOut={communityOptedOut}
        onToggleCommunityOptOut={onToggleCommunityOptOut}
        pushCategories={pushCategories}
        onTogglePushCategory={onTogglePushCategory}
      />
      <AccountActionsSection onExportData={onExportData} onSignOut={onSignOut} />
      <DeleteAccountSection onDeleteAccount={onDeleteAccount} />
    </main>
  );
}
