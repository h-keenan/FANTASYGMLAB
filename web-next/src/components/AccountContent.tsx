"use client";

import { HelpLink } from "@/components/HelpLink";
import { supportMailto } from "@/lib/support";
import { PageTitle } from "@/components/PageTitle";
import { useState } from "react";

import type { MeResponse, PushCategory, ReferralStatusResponse } from "@/lib/api";
import { PillRow } from "@/components/PillRow";
import { ReferralCard } from "@/components/ReferralCard";
import { OptionRadioGroup } from "@/components/OptionRadioGroup";
import { useDisplayPreferences } from "@/context/DisplayPreferencesContext";
import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import { DENSITY_OPTIONS, THEME_OPTIONS } from "@/lib/displayPreferences";
import {
  EXPERIENCE_GOAL_OPTIONS,
  EXPERIENCE_LEVEL_OPTIONS,
  PLAIN_COPY,
  type ExperienceGoal,
  type ExperienceLevel,
} from "@/lib/experienceCopy";
import { trialEndLabel } from "@/lib/trialCopy";
import { Button, ButtonLink } from "@/components/Button";
import { OnboardingCarousel } from "@/components/OnboardingCarousel";
import { trackOnboarding } from "@/lib/onboardingAnalytics";
import { Toggle } from "@/components/Toggle";
import { NotificationControls } from "@/components/NotificationControls";
import { SavedLeaguesSection } from "@/components/SavedLeaguesSection";
import { SleeperUsernameRelink } from "@/components/SleeperUsernameRelink";

/** Mirrors mobile/src/screens/MoreScreen.tsx's PUSH_CATEGORY_LABELS exactly
 * — same ten categories, same copy — so a user who's seen this in the app
 * recognizes it here. Order matches modules.push_triggers.
 * TOGGLEABLE_PUSH_CATEGORIES. */
const PUSH_CATEGORY_LABELS: Array<{ value: PushCategory; label: string; description: string }> = [
  { value: "top_priority", label: "Top Priority moves", description: "The single most urgent recommendation for your roster" },
  { value: "watch", label: "Watch items", description: "Worth knowing, not urgent" },
  { value: "recap", label: "Weekly recaps", description: "When a new League Recap is ready" },
  { value: "injury", label: "Injury updates", description: "A status change on your own roster (Questionable, Out, etc.)" },
  { value: "team_situation", label: "Team Situation reminder", description: "A one-time nudge to set rebuilding, competing, or balanced" },
  { value: "trade_followup", label: "Trade follow-ups", description: "Asking whether a trade you shared actually happened" },
  { value: "lineup_lock", label: "Lineup lock reminders", description: "An empty slot or an injured starter shortly before kickoff" },
  { value: "trade_deadline", label: "Trade deadline", description: "Two weeks out, one week out, and the deadline week itself" },
  { value: "waiver_reminder", label: "Waiver reminders", description: "Before waivers process, only when you have a clear need" },
  { value: "weekly_roundup", label: "Weekly roundup", description: "Tuesday after games: what you left on the bench and whether you could have known" },
];

function SectionHeading({ id, children, color }: { id: string; children: React.ReactNode; color?: string }) {
  return (
    <h2 id={id} className="text-xs font-bold uppercase" style={{ color: color ?? "var(--color-text-muted)", letterSpacing: "0.03em" }}>
      {children}
    </h2>
  );
}

function IdentitySection({ user }: { user: MeResponse["user"] }) {
  const [linkedUsername, setLinkedUsername] = useState<string | null>(null);
  const sleeperUsername = linkedUsername ?? user.sleeper_username;
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
          <dd className="font-semibold">{sleeperUsername || "Not linked"}</dd>
        </div>
        <div className="flex items-center justify-between gap-3">
          <dt style={{ color: "var(--color-text-secondary)" }}>Plan</dt>
          <dd className="font-semibold" style={{ color: user.entitlement === "premium" ? "var(--color-premium)" : "var(--color-text-primary)" }}>
            {user.entitlement === "premium" ? "Pro" : "Free"}
          </dd>
        </div>
      </dl>
      <SleeperUsernameRelink current={sleeperUsername || ""} onLinked={setLinkedUsername} />
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
            <p
              className="text-xs font-extrabold self-start px-2 py-1"
              style={{ color: "var(--color-premium)", background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-premium)", borderRadius: "var(--radius-pill)" }}
            >
              {trialEndLabel(trialEndsAt)}
            </p>
          ) : null}
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Manage your plan, payment method, or cancel anytime.
          </p>
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <Button
            variant="premium"
            type="button"
            loading={busy}
            onClick={() => {
              setBusy(true);
              setError(null);
              onOpenBillingPortal()
                .catch((err) => setError(err instanceof Error ? err.message : "Could not open the billing portal."))
                .finally(() => setBusy(false));
            }}
          >
            {busy ? "Opening…" : "Manage Billing"}
          </Button>
        </>
      ) : (
        <>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            You&apos;re on the Free plan.
          </p>
          <ButtonLink
            href="/premium"
            variant="premium"
          >
            Upgrade to Pro
          </ButtonLink>
        </>
      )}
    </section>
  );
}

/** Same wording the onboarding picker uses (lib/experienceCopy.ts
 * EXPERIENCE_LEVEL_OPTIONS) — previously this spelled its own
 * "Beginner"/"Advanced" labels, which didn't match onboarding's "New to
 * dynasty"/"I know my stuff" for the same two values. Fixed 2026-10-27. */
const EXPLANATION_OPTIONS: Array<{ value: ExperienceLevel; label: string; description: string }> = (
  Object.keys(EXPERIENCE_LEVEL_OPTIONS) as ExperienceLevel[]
).map((value) => ({
  value,
  label: EXPERIENCE_LEVEL_OPTIONS[value].title,
  description: EXPERIENCE_LEVEL_OPTIONS[value].body,
}));

const GOAL_OPTIONS = (Object.keys(EXPERIENCE_GOAL_OPTIONS) as ExperienceGoal[]).map((value) => ({
  value,
  label: EXPERIENCE_GOAL_OPTIONS[value].label,
}));

/** The onboarding carousel's "How much dynasty experience do you have?"
 * answer, editable later. Reads/writes through ExperienceLevelContext (the
 * same /v1/preferences field), so the change applies across the app right
 * away. An unanswered account (null) shows "Not set" with no option
 * selected (it gets beginner-lite help until answered). */
function ExplanationsSetting() {
  const { level, setLevel } = useExperienceLevel();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const active: ExperienceLevel | null = level;

  return (
    <div className="flex flex-col gap-2">
      <span id="account-explanations-label" className="text-sm font-semibold">
        Explanations
        {level === null ? (
          <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>
            {" "}
            · Not set
          </span>
        ) : null}
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

/** The optional "what's your goal this season?" chip, alongside experience
 * level. Skippable — tapping the already-selected chip clears it back to
 * unset. Reads/writes through ExperienceLevelContext, same /v1/preferences
 * field the onboarding carousel's goal chip writes. */
function GoalSetting() {
  const { goal, setGoal } = useExperienceLevel();
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pick = (value: string) => {
    const next = goal === value ? null : (value as ExperienceGoal);
    setSaving(true);
    setError(null);
    setGoal(next)
      .catch(() => setError("Couldn't save this setting. Try again."))
      .finally(() => setSaving(false));
  };

  return (
    <div className="flex flex-col gap-2">
      <span id="account-goal-label" className="text-sm font-semibold">
        {PLAIN_COPY.experienceGoalPrompt}
      </span>
      <PillRow ariaLabel={PLAIN_COPY.experienceGoalPrompt} options={GOAL_OPTIONS} active={goal ?? ""} onSelect={saving ? undefined : pick} />
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Density (Guided/Compact), theme (Night/Day/Auto) and the college
 * football switch. Same options and copy as the app's Account screen;
 * density and theme sync through /v1/preferences, so a choice made in
 * either place follows the account. College is per-browser, like the app. */
function DisplaySettings() {
  const { density, setDensity, themeMode, setThemeMode, collegeInterest, setCollegeInterest } = useDisplayPreferences();
  return (
    <>
      <OptionRadioGroup id="account-density-label" label="Density" options={DENSITY_OPTIONS} value={density} onChange={setDensity} />
      <OptionRadioGroup id="account-theme-label" label="Theme" options={THEME_OPTIONS} value={themeMode} onChange={setThemeMode} />
      <div
        className="flex items-center justify-between gap-3 p-3"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold">College football</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Show College Scouting in the menu
          </span>
        </div>
        <Toggle
          checked={collegeInterest === "on"}
          stateLabel={collegeInterest === "on" ? "On" : "Off"}
          onChange={(next) => setCollegeInterest(next ? "on" : "off")}
        />
      </div>
    </>
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

      <GoalSetting />

      <DisplaySettings />

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
        <Toggle
          tone="danger"
          checked={communityOptedOut}
          disabled={togglingCommunity}
          stateLabel={communityOptedOut ? "Opted out" : "Opted in"}
          onChange={(next) => {
            setTogglingCommunity(true);
            Promise.resolve(onToggleCommunityOptOut(next)).finally(() => setTogglingCommunity(false));
          }}
        />
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
                <Toggle
                  checked={pushCategories[item.value]}
                  disabled={togglingPush === item.value}
                  stateLabel={pushCategories[item.value] ? "On" : "Off"}
                  onChange={(next) => {
                    setTogglingPush(item.value);
                    Promise.resolve(onTogglePushCategory(item.value, next)).finally(() => setTogglingPush(null));
                  }}
                />
              </div>
            ))}
          </div>
          <NotificationControls />
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
      <ButtonLink href="/features" variant="secondary">
        See everything FantasyDesk can do
      </ButtonLink>
      <button
        type="button"
        onClick={() => {
          trackOnboarding("replayed");
          setReplaying(true);
        }}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{ minHeight: "var(--touch-target-min)", border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
      >
        Replay the tour
      </button>
      <HelpLink context={{ topic: "account" }} className="self-start" />
      {replaying ? <OnboardingCarousel replay onDone={() => setReplaying(false)} /> : null}
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <Button
        variant="secondary"
        loading={busy}
        onClick={() => {
          setBusy(true);
          setError(null);
          onExportData()
            .catch((err) => setError(err instanceof Error ? err.message : "Could not export your data."))
            .finally(() => setBusy(false));
        }}
      >
        {busy ? "Preparing export…" : "Export my data"}
      </Button>
      <Button variant="secondary" onClick={onSignOut}>
        Sign out
      </Button>
    </section>
  );
}

// TEMPORARY: self-service deletion is disabled (delete-account edge function
// reverted); point users at support instead of a button that cannot work.
function DeleteAccountSection() {
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
        Self-service account deletion is temporarily unavailable. Contact support and we will permanently delete
        your account and all data, and cancel any subscription.
      </p>
      <ButtonLink variant="danger" href={supportMailto({ topic: "delete_account" })}>
        Contact support to delete your account
      </ButtonLink>
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
  onSignOut: () => void;
}) {
  return (
    <main className="flex-1 flex flex-col gap-3 px-4 py-3 max-w-2xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <PageTitle page="Account" />
      </header>

      <IdentitySection user={user} />
      <BillingSection entitlement={user.entitlement} trialEndsAt={user.trial_ends_at} onOpenBillingPortal={onOpenBillingPortal} />
      <SavedLeaguesSection />
      <ReferralCard referral={referral} error={referralError} onRetry={onRetryReferral} />
      <PreferencesSection
        communityOptedOut={communityOptedOut}
        onToggleCommunityOptOut={onToggleCommunityOptOut}
        pushCategories={pushCategories}
        onTogglePushCategory={onTogglePushCategory}
      />
      <AccountActionsSection onExportData={onExportData} onSignOut={onSignOut} />
      <DeleteAccountSection />
    </main>
  );
}
