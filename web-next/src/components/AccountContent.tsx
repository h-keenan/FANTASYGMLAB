"use client";

import { HelpLink } from "@/components/HelpLink";
import { planOf, type Plan } from "@/lib/plan";
import {
  APP_STORE_SUBSCRIPTIONS_URL,
  DELETE_ACCOUNT_APP_STORE_NOTE,
  DELETE_ACCOUNT_FAILED,
  DELETE_ACCOUNT_STRIPE_NOTE,
  DELETE_ACCOUNT_SUMMARY,
} from "@/lib/accountDeletionCopy";
import { PageTitle } from "@/components/PageTitle";
import { useState } from "react";

import type { MeResponse, PushCategory, ReferralStatusResponse } from "@/lib/api";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ReferralCard } from "@/components/ReferralCard";
import { OptionRadioGroup } from "@/components/OptionRadioGroup";
import { useDisplayPreferences } from "@/context/DisplayPreferencesContext";
import { useExperienceLevel } from "@/context/ExperienceLevelContext";
import { DENSITY_OPTIONS, THEME_OPTIONS } from "@/lib/displayPreferences";
import {
  EXPERIENCE_LEVEL_OPTIONS,
  PLAIN_COPY,
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
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { ACCOUNT_SECTION_TITLE } from "@/lib/accountSections";

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
  { value: "sim_week_ready", label: "Fantasy Sim week ready", description: "Off by default: when your Fantasy Sim week has been waiting for you" },
];

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
              <span className="flex flex-col gap-0.5 min-w-0">
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
        <div className="flex flex-col gap-0.5 min-w-0">
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

type RowGlyph = "mail" | "user" | "card" | "compass" | "sliders" | "bell" | "shield" | "download" | "trash" | "help" | "tour" | "grid" | "doc" | "people" | "gift" | "logout";

const GLYPH_PATHS: Record<RowGlyph, string> = {
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 20c0-4 4-6 8-6s8 2 8 6",
  card: "M3 6h18v12H3zM3 10h18",
  compass: "M12 21a9 9 0 100-18 9 9 0 000 18zM15.5 8.5l-2 5-5 2 2-5z",
  sliders: "M4 8h10M18 8h2M4 16h2M10 16h10M14 6v4M6 14v4",
  bell: "M6 16V11a6 6 0 0112 0v5l2 2H4zM10 21h4",
  shield: "M12 3l8 3v6c0 5-4 8-8 9-4-1-8-4-8-9V6z",
  download: "M12 4v11M7 11l5 5 5-5M5 20h14",
  trash: "M5 7h14M9 7V4h6v3M7 7l1 13h8l1-13",
  help: "M12 21a9 9 0 100-18 9 9 0 000 18zM9.5 9.5a2.5 2.5 0 114 2c-1 .7-1.5 1.2-1.5 2.5M12 17v.1",
  tour: "M12 21a9 9 0 100-18 9 9 0 000 18zM10 8.5v7l6-3.5z",
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  doc: "M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5",
  people: "M9 11a3 3 0 100-6 3 3 0 000 6zM3 20c0-3 3-5 6-5s6 2 6 5M17 11a2.5 2.5 0 100-5M18 15c2 .5 3 2 3 5",
  gift: "M4 10h16v10H4zM3 7h18v3H3zM12 7v13M12 7c-2-4-5-3-4 0M12 7c2-4 5-3 4 0",
  logout: "M10 4H5v16h5M15 8l4 4-4 4M19 12H9",
};

function Glyph({ name, color = "var(--color-text-secondary)" }: { name: RowGlyph; color?: string }) {
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center"
      style={{ width: "1.75rem", height: "1.75rem", borderRadius: "var(--radius-pill)", background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d={GLYPH_PATHS[name]} />
      </svg>
    </span>
  );
}

function SectionHeading({ id, children, color }: { id: string; children: React.ReactNode; color?: string }) {
  return (
    <h2 id={id} className="text-xs font-bold uppercase px-1" style={{ color: color ?? "var(--color-text-muted)", letterSpacing: "0.03em" }}>
      {children}
    </h2>
  );
}

/** One grouped glass surface of icon rows with hairline dividers (never a card per row). */
function SettingsGroup({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-2" aria-labelledby={id}>
      <SectionHeading id={id}>{title}</SectionHeading>
      <div className="glass-surface flex flex-col">{children}</div>
    </section>
  );
}

const ROW_DIVIDER = { borderTop: "var(--border-width-default) solid var(--color-border)" } as const;

/** Icon + label + (value | action) row. One line of supporting copy at most. */
function SettingsRow({
  icon,
  iconColor,
  label,
  value,
  copy,
  children,
}: {
  icon: RowGlyph;
  iconColor?: string;
  label: string;
  value?: React.ReactNode;
  copy?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 settings-row" style={{ minHeight: "var(--touch-target-min)" }}>
      <Glyph name={icon} color={iconColor} />
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-sm font-semibold">{label}</span>
        {copy ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {copy}
          </span>
        ) : null}
      </div>
      {value ? (
        <span className="text-sm text-right min-w-0 break-words" style={{ color: "var(--color-text-secondary)" }}>
          {value}
        </span>
      ) : null}
      {children}
    </div>
  );
}

/** A row that opens its controls on tap (native details: content stays in the DOM, keyboard accessible). */
function ExpandSetting({
  icon,
  label,
  value,
  children,
}: {
  icon: RowGlyph;
  label: string;
  value?: string;
  children: React.ReactNode;
}) {
  return (
    <details className="settings-row group">
      <summary
        className="flex items-center gap-3 px-4 py-3 cursor-pointer list-none"
        style={{ minHeight: "var(--touch-target-min)" }}
      >
        <Glyph name={icon} />
        <span className="text-sm font-semibold flex-1 min-w-0">{label}</span>
        {value ? (
          <span className="text-sm text-right" style={{ color: "var(--color-text-secondary)" }}>
            {value}
          </span>
        ) : null}
        <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>
          ›
        </span>
      </summary>
      <div className="flex flex-col gap-3 px-4 pb-4">{children}</div>
    </details>
  );
}

function RowList({ children }: { children: React.ReactNode[] }) {
  return (
    <>
      {children
        .filter(Boolean)
        .map((child, index) => (
          <div key={index} style={index === 0 ? undefined : ROW_DIVIDER}>
            {child}
          </div>
        ))}
    </>
  );
}

function ProfileHeader({ user, sleeperUsername }: { user: MeResponse["user"]; sleeperUsername: string }) {
  const plan = planOf(user);
  const name = sleeperUsername || user.email || "Your account";
  return (
    <section className="glass-surface p-4 flex items-center gap-3" aria-label="Profile">
      <TeamAvatar name={name} size={56} ringColor={plan === "pro" ? "var(--color-premium)" : "var(--color-border)"} />
      <div className="flex flex-col min-w-0 flex-1 gap-1">
        <span className="text-lg font-extrabold break-words">{name}</span>
        {sleeperUsername && user.email ? (
          <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
            {user.email}
          </span>
        ) : null}
      </div>
      <span
        className="text-xs font-extrabold px-2 py-1 shrink-0"
        style={{
          color: plan === "pro" ? "var(--color-premium)" : "var(--color-text-secondary)",
          border: `var(--border-width-default) solid ${plan === "pro" ? "var(--color-premium)" : "var(--color-border)"}`,
          borderRadius: "var(--radius-pill)",
        }}
      >
        {plan === "pro" ? "Pro" : plan === "free" ? "Free" : "Unavailable"}
      </span>
    </section>
  );
}

function PlanRow({
  plan,
  trialEndsAt,
  onOpenBillingPortal,
}: {
  plan: Plan;
  trialEndsAt?: string;
  onOpenBillingPortal: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const trial = trialEndLabel(trialEndsAt);
  return (
    <div>
      <SettingsRow
        icon="card"
        iconColor={plan === "pro" ? "var(--color-premium)" : undefined}
        label="Plan"
        value={plan === "pro" ? "Pro plan" : plan === "free" ? "Free plan" : "Unavailable"}
        copy={plan === "unknown" ? "We could not confirm your plan. Nothing has changed." : undefined}
      >
        {plan === "pro" ? (
          <Button
            variant="premium"
            size="sm"
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
        ) : plan === "free" ? (
          <ButtonLink href="/premium" variant="premium" size="sm">
            Upgrade to Pro
          </ButtonLink>
        ) : null}
      </SettingsRow>
      {trial && plan === "pro" ? (
        <p className="text-xs font-bold px-4 pb-3" style={{ color: "var(--color-premium)" }}>
          {trial}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs px-4 pb-3" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

function PushSettings({
  pushCategories,
  onTogglePushCategory,
}: {
  pushCategories: Record<PushCategory, boolean>;
  onTogglePushCategory: (category: PushCategory, enabled: boolean) => void;
}) {
  const [togglingPush, setTogglingPush] = useState<PushCategory | null>(null);
  const onCount = PUSH_CATEGORY_LABELS.filter((item) => pushCategories[item.value]).length;
  return (
    <ExpandSetting icon="bell" label="Push notifications" value={`${onCount} of ${PUSH_CATEGORY_LABELS.length} on`}>
      <div className="flex flex-col" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
        {PUSH_CATEGORY_LABELS.map((item, index) => (
          <div
            key={item.value}
            className="flex items-center justify-between gap-3 p-3"
            style={{ borderTop: index === 0 ? "none" : "var(--border-width-default) solid var(--color-border)" }}
          >
            <div className="flex flex-col gap-0.5 min-w-0">
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
    </ExpandSetting>
  );
}

function ActionRow({
  icon,
  label,
  busyLabel,
  onRun,
  fallbackError,
}: {
  icon: RowGlyph;
  label: string;
  busyLabel: string;
  onRun: () => Promise<void>;
  fallbackError: string;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <div>
      <SettingsRow icon={icon} label={label}>
        <Button
          variant="secondary"
          size="sm"
          loading={busy}
          onClick={() => {
            setBusy(true);
            setError(null);
            onRun()
              .catch((err) => setError(err instanceof Error ? err.message : fallbackError))
              .finally(() => setBusy(false));
          }}
        >
          {busy ? busyLabel : label}
        </Button>
      </SettingsRow>
      {error ? (
        <p role="alert" className="text-xs px-4 pb-3" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}

function DeleteAccountRow({ onDeleteAccount }: { onDeleteAccount: () => Promise<void> }) {
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <div style={{ background: "color-mix(in srgb, var(--color-danger) 6%, transparent)" }}>
      <SettingsRow icon="trash" iconColor="var(--color-danger)" label={ACCOUNT_SECTION_TITLE.danger} copy="Permanently removes your account and data.">
        {!confirming ? (
          <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
            Delete account
          </Button>
        ) : null}
      </SettingsRow>
      {confirming ? (
        <div className="flex flex-col gap-2 px-4 pb-4">
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {DELETE_ACCOUNT_SUMMARY}
          </p>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {DELETE_ACCOUNT_STRIPE_NOTE}
          </p>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {DELETE_ACCOUNT_APP_STORE_NOTE}{" "}
            <a href={APP_STORE_SUBSCRIPTIONS_URL} target="_blank" rel="noopener noreferrer" className="underline">
              Open Subscriptions
            </a>
          </p>
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <div className="flex items-center gap-2">
            <Button
              variant="danger"
              loading={busy}
              onClick={() => {
                setBusy(true);
                setError(null);
                onDeleteAccount().catch((err) => {
                  setError(err instanceof Error && err.message ? err.message : DELETE_ACCOUNT_FAILED);
                  setBusy(false);
                });
              }}
            >
              {busy ? "Deleting…" : "Confirm delete"}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => setConfirming(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}

const LEGAL_LINKS: Array<{ pageKey: string; label: string }> = [
  { pageKey: "about_disclaimer", label: "About / Disclaimer" },
  { pageKey: "terms", label: "Terms of Use" },
  { pageKey: "privacy", label: "Privacy Policy" },
  { pageKey: "subscription_terms", label: "Subscription Terms" },
  { pageKey: "no_affiliation", label: "No-Affiliation Disclaimer" },
];

function HelpAndLegalGroup() {
  const [replaying, setReplaying] = useState(false);
  return (
    <SettingsGroup id="account-help-heading" title="Help & legal">
      <RowList>
        {[
          <SettingsRow key="features" icon="grid" label="See everything FantasyDesk can do">
            <ButtonLink href="/features" variant="secondary" size="sm">
              Open
            </ButtonLink>
          </SettingsRow>,
          <SettingsRow key="tour" icon="tour" label="Replay the tour">
            <button
              type="button"
              onClick={() => {
                trackOnboarding("replayed");
                setReplaying(true);
              }}
              className="px-3 py-1 text-sm font-bold"
              style={{ minHeight: "var(--touch-target-min)", border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
            >
              Replay the tour
            </button>
          </SettingsRow>,
          <SettingsRow key="help" icon="help" label="Help & feedback">
            <HelpLink context={{ topic: "account" }} />
          </SettingsRow>,
          <ExpandSetting key="legal" icon="doc" label="Legal">
            <ul className="flex flex-col gap-1">
              {LEGAL_LINKS.map((item) => (
                <li key={item.pageKey}>
                  <a href={`/legal/${item.pageKey}`} className="tap-link text-sm underline" style={{ color: "var(--color-text-secondary)" }}>
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </ExpandSetting>,
        ]}
      </RowList>
      {replaying ? <OnboardingCarousel replay onDone={() => setReplaying(false)} /> : null}
    </SettingsGroup>
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
  const [linkedUsername, setLinkedUsername] = useState<string | null>(null);
  const [togglingCommunity, setTogglingCommunity] = useState(false);
  const sleeperUsername = linkedUsername ?? user.sleeper_username ?? "";
  const { level } = useExperienceLevel();
  const { density, themeMode } = useDisplayPreferences();
  const experienceValue = level === null ? "Not set" : EXPERIENCE_LEVEL_OPTIONS[level].title;
  const displayValue = `${DENSITY_OPTIONS.find((o) => o.value === density)?.label ?? ""} · ${THEME_OPTIONS.find((o) => o.value === themeMode)?.label ?? ""}`;

  return (
    <main className="page-shell page-shell-narrow">
      <header className="flex flex-col gap-1">
        <PageTitle page="Account" />
      </header>

      <ProfileHeader user={user} sleeperUsername={sleeperUsername} />

      <SettingsGroup id="account-identity-heading" title="Account">
        <RowList>
          {[
            sleeperUsername ? null : <SettingsRow key="email" icon="mail" label="Email" value={user.email || "—"} />,
            <SettingsRow key="sleeper" icon="user" label="Sleeper username" value={sleeperUsername ? undefined : "Not linked"}>
              <SleeperUsernameRelink current={sleeperUsername} onLinked={setLinkedUsername} />
            </SettingsRow>,
            <PlanRow key="plan" plan={planOf(user)} trialEndsAt={user.trial_ends_at} onOpenBillingPortal={onOpenBillingPortal} />,
          ]}
        </RowList>
      </SettingsGroup>

      <SavedLeaguesSection />

      <ReferralCard referral={referral} error={referralError} onRetry={onRetryReferral} />

      <SettingsGroup id="account-preferences-heading" title="Preferences">
        <RowList>
          {[
            <ExpandSetting key="exp" icon="compass" label="Experience level" value={experienceValue}>
              <ExplanationsSetting />
            </ExpandSetting>,
            <ExpandSetting key="display" icon="sliders" label="Display" value={displayValue}>
              <DisplaySettings />
            </ExpandSetting>,
          ]}
        </RowList>
      </SettingsGroup>

      {pushCategories ? (
        <SettingsGroup id="account-notifications-heading" title="Notifications">
          <PushSettings pushCategories={pushCategories} onTogglePushCategory={onTogglePushCategory} />
        </SettingsGroup>
      ) : null}

      <SettingsGroup id="account-privacy-heading" title="Privacy & data">
        <RowList>
          {[
            <SettingsRow key="community" icon="people" label="Community Trade Feed" copy="I don't want MY trades to appear in this feed">
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
            </SettingsRow>,
            <ActionRow key="export" icon="download" label="Export my data" busyLabel="Preparing export…" onRun={onExportData} fallbackError="Could not export your data." />,
            <DeleteAccountRow key="delete" onDeleteAccount={onDeleteAccount} />,
          ]}
        </RowList>
      </SettingsGroup>

      <HelpAndLegalGroup />

      <section className="glass-surface px-4 py-2" aria-label="Sign out">
        <SettingsRow icon="logout" label="Session">
          <ConfirmInPlace label="Sign out" buttonVariant="secondary" onConfirm={onSignOut} />
        </SettingsRow>
      </section>
    </main>
  );
}
