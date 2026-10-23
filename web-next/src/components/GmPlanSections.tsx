import Link from "next/link";

import { BeginnerHelp } from "@/components/BeginnerHelp";
import { InfoTip } from "@/components/InfoTip";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { ValueRing } from "@/components/ValueRing";
import { SnapshotTileGlyph, type SnapshotGlyphName } from "@/components/SnapshotTileGlyph";
import { TEAM_STANCE_OPTIONS, type TeamStance } from "@/lib/api";
import type { DeadlineBanner, PlanSnapshotTile } from "@/lib/gmPlanSnapshot";

export const GM_PLAN_TABS = [
  { label: "Overview", value: "overview" },
  { label: "Trades", value: "trades" },
  { label: "Core", value: "core" },
  { label: "Watching", value: "watching" },
] as const;
export type GmPlanTab = (typeof GM_PLAN_TABS)[number]["value"];

export function isGmPlanTab(value: string | null | undefined): value is GmPlanTab {
  return GM_PLAN_TABS.some((tab) => tab.value === value);
}

/** Team Situation: the declared-stance chips, the info tip, and the real trade-deadline banner. */
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
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-label="Team Situation">
      <div className="flex items-center gap-2">
        <SectionHeading>Team Situation</SectionHeading>
        <InfoTip label="How you see this team">
          Tell us how you see this team right now. We&apos;ll lean trade-idea language toward that stance, and use
          it to shape your trade and lineup value adjustments too.
        </InfoTip>
      </div>
      <PillRow
        fullWidth
        options={TEAM_STANCE_OPTIONS.map((option) => ({ label: option.label, value: option.value }))}
        active={stance}
        onSelect={onPick}
      />
      <div className="flex flex-col gap-0.5">
        <BeginnerHelp term="stanceRebuilding" />
        <BeginnerHelp term="stanceCompeting" />
        <BeginnerHelp term="stanceBalanced" />
      </div>
      {selected ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {selected.description}
        </p>
      ) : null}
      {banner ? (
        <DeadlineLink href={tradeHubHref}>
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            Trade deadline: Week {banner.week}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            Declaring a stance sharpens your recommendations.
          </span>
        </DeadlineLink>
      ) : pastDeadline ? (
        <p className="text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>
          Past the trade deadline
        </p>
      ) : null}
    </section>
  );
}

function DeadlineLink({ href, children }: { href?: string; children: React.ReactNode }) {
  const style = {
    background: "color-mix(in srgb, var(--color-accent) 10%, transparent)",
    border: "1px solid color-mix(in srgb, var(--color-accent) 40%, transparent)",
  };
  const cls = "flex flex-col gap-0.5 px-3 py-2";
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

const TILE_GLYPH: Record<PlanSnapshotTile["key"], SnapshotGlyphName> = {
  power: "power",
  capital: "franchise",
  odds: "power",
  record: "record",
  starter: "starter",
  bench: "bench",
  age: "age",
};

function ringTone(percent: number): "low" | "mid" | "high" {
  return percent < 33 ? "low" : percent < 66 ? "mid" : "high";
}

function SnapshotCell({ tile }: { tile: PlanSnapshotTile }) {
  const percent = tile.fill === null ? null : Math.round(tile.fill * 100);
  return (
    <div className="glass-surface flex items-center gap-2 p-3 min-w-0" data-testid={`plan-tile-${tile.key}`}>
      <div className="flex flex-col gap-1 min-w-0 flex-1">
        <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          <SnapshotTileGlyph name={TILE_GLYPH[tile.key]} />
          <span className="break-words min-w-0">{tile.label}</span>
        </span>
        <span style={{ font: "var(--type-primary-metric)", color: "var(--color-text-primary)", fontSize: "1.25rem" }}>
          {tile.value}
        </span>
        {tile.note ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {tile.note}
          </span>
        ) : null}
        {tile.key !== "odds" && percent !== null ? (
          <div
            role="progressbar"
            aria-label={tile.label}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={percent}
            className="h-1.5 w-full"
            style={{ background: "var(--color-surface-muted)" }}
          >
            <div className="h-full" style={{ width: `${percent}%`, background: "var(--color-accent)" }} />
          </div>
        ) : null}
      </div>
      {tile.key === "odds" && percent !== null ? (
        <ValueRing percent={percent} tone={ringTone(percent)} display={`${percent}`} ariaLabel={`${tile.label} ${tile.value}`} size="sm" />
      ) : null}
    </div>
  );
}

/** Plan Snapshot: Playoff Odds / Roster Power / Draft Capital lead, then the rest. */
export function PlanSnapshotGrid({ tiles, analysisHref }: { tiles: PlanSnapshotTile[]; analysisHref?: string }) {
  if (tiles.length === 0) return null;
  return (
    <section className="flex flex-col gap-2" aria-label="Plan Snapshot">
      <SectionHeading
        action={
          analysisHref ? (
            <Link href={analysisHref} className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
              Full analysis
            </Link>
          ) : undefined
        }
      >
        Plan Snapshot
      </SectionHeading>
      <div className="grid grid-cols-2 gap-2">
        {tiles.map((tile) => (
          <SnapshotCell key={tile.key} tile={tile} />
        ))}
      </div>
    </section>
  );
}

/** Loading skeleton that reserves the final page's block heights. */
export function GmPlanSkeleton({ leagueName }: { leagueName: string }) {
  const block = (height: number, key: string) => (
    <div key={key} className="pqv-skeleton-chart w-full" style={{ height }} aria-hidden="true" />
  );
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto" aria-busy="true">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          GM Plan
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
      </header>
      <span className="sr-only" role="status">
        Loading GM Plan
      </span>
      {[block(44, "tabs"), block(190, "situation"), block(250, "snapshot"), block(330, "trades")]}
    </main>
  );
}
