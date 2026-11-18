import { TERMS } from "@/lib/terms";
import Link from "next/link";

import { InfoMark } from "@/components/ui/InfoMark";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { IconRow } from "@/components/IconRow";
import { CompactModule } from "@/components/ui/CompactModule";
import { ToneBadge } from "@/components/ToneBadge";
import { TEAM_STANCE_OPTIONS, type TeamStance } from "@/lib/api";
import type { DeadlineBanner } from "@/lib/gmPlanSnapshot";
import { SkeletonBlock } from "@/components/Skeleton";
import { PageTitle } from "@/components/PageTitle";

export const GM_PLAN_TABS = [
  { label: "Overview", value: "overview", glyph: "overview" },
  { label: "Trades", value: "trades", glyph: "trades" },
  { label: "Core", value: "core", glyph: "core" },
  { label: TERMS.watchlist, value: "watching", glyph: "watching" },
] as const;
export type GmPlanTab = (typeof GM_PLAN_TABS)[number]["value"];

export function isGmPlanTab(value: string | null | undefined): value is GmPlanTab {
  return GM_PLAN_TABS.some((tab) => tab.value === value);
}

const STANCE_LOOK: Record<TeamStance, { color: string; tagline: string; help: "stanceRebuilding" | "stanceCompeting" | "stanceBalanced" }> = {
  rebuilding: { color: "var(--color-information)", tagline: "Youth + picks", help: "stanceRebuilding" },
  competing: { color: "var(--color-success)", tagline: "Win now", help: "stanceCompeting" },
  balanced: { color: "var(--color-accent)", tagline: "Both ways", help: "stanceBalanced" },
};

function StanceIcon({ stance }: { stance: TeamStance }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 16 16",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
  if (stance === "rebuilding") {
    // Sprout: building for the future.
    return (
      <svg {...common}>
        <path d="M8 14V8" />
        <path d="M8 8C8 5.5 6.2 4 3.5 4c0 2.6 1.8 4 4.5 4z" />
        <path d="M8 9.5c0-2.3 1.6-3.8 4.5-3.8 0 2.4-1.7 3.8-4.5 3.8z" />
      </svg>
    );
  }
  if (stance === "competing") {
    // Trophy: going for it now.
    return (
      <svg {...common}>
        <path d="M5 2h6v3.5a3 3 0 01-6 0z" />
        <path d="M5 3H3v1a2.5 2.5 0 002.3 2.5M11 3h2v1a2.5 2.5 0 01-2.3 2.5" />
        <path d="M8 9v2M5.5 13h5l-.6-2h-3.8z" />
      </svg>
    );
  }
  // Scales: balance.
  return (
    <svg {...common}>
      <path d="M8 2.5v11M5 13.5h6M3 5h10" />
      <path d="M3 5l-1.6 3.6a2 2 0 003.2 0zM13 5l-1.6 3.6a2 2 0 003.2 0z" />
    </svg>
  );
}

/** Team Situation: the declared-stance cards, the info tip, and the real trade-deadline banner. */
export function TeamSituationCard({
  stance,
  onPick,
  banner,
  pastDeadline,
  tradeHubHref,
}: {
  stance: TeamStance | "";
  onPick: (value: string) => void;
  banner: DeadlineBanner;
  pastDeadline: boolean;
  tradeHubHref?: string;
}) {
  const selected = TEAM_STANCE_OPTIONS.find((option) => option.value === stance);
  const selectedLook = selected ? STANCE_LOOK[selected.value] : null;
  const copy = useExperienceCopy();
  return (
    <CompactModule
      id="gmplan.situation"
      title="Team Situation"
      tone="action"
      defaultOpen={!selected}
      parts={[
        selected
          ? { key: "stance", text: selected.label, strong: true, tone: "action" }
          : { key: "stance", text: "Not set yet", tone: "warning" },
        banner ? { key: "deadline", text: `Trade deadline Wk ${banner.week}` } : pastDeadline ? { key: "deadline", text: "Past the trade deadline", tone: "muted" } : null,
      ]}
    >
      <div className="flex items-center">
        <span className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          How you see this team
        </span>
        <InfoMark
          label="how you see this team"
          lines={[
            "Tell us how you see this team right now. We'll lean trade-idea language toward that stance, and use it to shape your trade and lineup value adjustments too.",
            selectedLook ? copy.help(selectedLook.help) : null,
          ]}
        />
      </div>
      <div role="tablist" aria-label="Team stance" className="grid grid-cols-3 gap-2">
        {TEAM_STANCE_OPTIONS.map((option) => {
          const look = STANCE_LOOK[option.value];
          const active = option.value === stance;
          return (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => onPick(option.value)}
              className="flex flex-col items-center gap-1 px-2 py-3 text-center min-w-0"
              style={{
                minHeight: "var(--touch-target-min)",
                cursor: "pointer",
                background: active
                  ? `color-mix(in srgb, ${look.color} 16%, transparent)`
                  : "var(--color-surface-muted)",
                border: `var(--border-width-default) solid ${active ? look.color : "var(--color-border)"}`,
                boxShadow: active ? `inset 0 -3px 0 ${look.color}` : "none",
                color: active ? look.color : "var(--color-text-secondary)",
              }}
            >
              <StanceIcon stance={option.value} />
              <span className="text-xs font-extrabold uppercase" style={{ letterSpacing: "var(--letter-spacing-tight)" }}>
                {option.label}
              </span>
              <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>
                {look.tagline}
              </span>
            </button>
          );
        })}
      </div>
      {selected && selectedLook ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {selected.description}
        </p>
      ) : (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Pick the stance that fits your team right now.
        </p>
      )}
      {banner ? (
        <DeadlineLink href={tradeHubHref}>
          <ToneBadge label={`Week ${banner.week}`} color="var(--color-accent)" />
          <span className="flex flex-col gap-0.5 min-w-0 flex-1">
            <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
              Trade deadline: Week {banner.week}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              {selected ? "Your stance shapes the trade ideas below." : "Declaring a stance sharpens your recommendations."}
            </span>
          </span>
          {tradeHubHref ? (
            <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
              →
            </span>
          ) : null}
        </DeadlineLink>
      ) : pastDeadline ? (
        <IconRow icon="clock" color="var(--color-text-muted)" textClassName="text-xs font-bold">
          Past the trade deadline
        </IconRow>
      ) : null}
    </CompactModule>
  );
}

function DeadlineLink({ href, children }: { href?: string; children: React.ReactNode }) {
  const style = {
    background: "color-mix(in srgb, var(--color-accent) 10%, transparent)",
    borderTop: "1px solid color-mix(in srgb, var(--color-accent) 40%, transparent)",
    borderRight: "1px solid color-mix(in srgb, var(--color-accent) 40%, transparent)",
    borderBottom: "1px solid color-mix(in srgb, var(--color-accent) 40%, transparent)",
    borderLeft: "var(--border-width-semantic) solid var(--color-accent)",
  };
  const cls = "flex items-center gap-3 px-3 py-2";
  return href ? (
    <Link href={href} className={cls} style={style} data-testid="deadline-banner">
      {children}
    </Link>
  ) : (
    <div className={cls} style={style} data-testid="deadline-banner">
      {children}
    </div>
  );
}

/** Loading skeleton that reserves the final page's block heights. */
export function GmPlanSkeleton({ leagueName }: { leagueName: string }) {
  const block = (height: number, key: string) => (
    <SkeletonBlock key={key} height={height} />
  );
  return (
    <main className="page-shell" aria-busy="true">
      <header className="flex flex-col gap-1">
        <PageTitle page="GM Plan" leagueName={leagueName} />
      </header>
      <span className="sr-only" role="status">
        Loading GM Plan
      </span>
      {[block(44, "tabs"), block(190, "situation"), block(250, "snapshot"), block(330, "trades")]}
    </main>
  );
}
