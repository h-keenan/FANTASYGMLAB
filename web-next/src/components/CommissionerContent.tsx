"use client";

import { PageTitle } from "@/components/PageTitle";
import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { PillRow } from "@/components/PillRow";
import { IconRow, type IconRowIcon } from "@/components/IconRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SnapshotTile } from "@/components/SnapshotTile";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueRing } from "@/components/ValueRing";
import { VetoCalculator } from "@/components/VetoCalculator";
import { api } from "@/lib/api";
import {
  BAND_LABEL,
  bandTone,
  CONFIDENCE_LABEL,
  DRAFT_ORDER_OPTIONS,
  INTERPRETATION_LABEL,
  integrityReasonMessage,
  calendarLines,
  integritySummaryLine,
  restSummary,
  splitTeams,
  type CommissionerIntegrityResponse,
  type IntegrityCalendar,
  type DraftOrderRule,
  type IntegrityBand,
  type IntegrityCollusionPair,
  type IntegrityInactiveManager,
  type IntegrityTeam,
} from "@/lib/commissionerIntegrity";

/**
 * Commissioner: league integrity for any Pro user who can open the league
 * (no commissioner check; access and the Pro gate are enforced server-side).
 * Every number comes from modules/league_integrity.py; nothing is computed here. Signals are prompts
 * to look, never verdicts, so each card lists the innocent explanations next
 * to the evidence. Mirrors mobile's CommissionerScreen.
 */

const TONE_COLOR: Record<ReturnType<typeof bandTone>, string> = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  muted: "var(--color-text-muted)",
};

function bandColor(band: IntegrityBand): string {
  return TONE_COLOR[bandTone(band)];
}

function EfficiencyBars({ team }: { team: IntegrityTeam }) {
  if (!team.series.length) return null;
  return (
    <div className="flex flex-col gap-1">
      <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
        Lineup efficiency by week
      </span>
      <div
        aria-label="Lineup efficiency by week"
        className="flex items-end gap-1 px-2 pt-2"
        style={{ height: 68, background: "var(--color-surface-muted)", borderRadius: "var(--radius-md, 6px)" }}
      >
        {team.series.map((point) => {
          const pct = Math.max(0.05, Math.min(1, point.efficiency ?? 0));
          return (
            <div key={point.week} className="flex flex-col items-center gap-0.5 flex-1" title={`Week ${point.week}: ${Math.round(pct * 100)}% of best possible`}>
              <div
                style={{
                  width: "100%",
                  height: `${Math.round(pct * 40)}px`,
                  background: point.flagged ? "var(--color-warning)" : "var(--color-success)",
                  opacity: point.flagged ? 1 : 0.55,
                  borderRadius: 2,
                }}
              />
              <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>
                {point.week}
              </span>
            </div>
          );
        })}
      </div>
      <span className="flex items-center gap-3 text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>
        <span className="flex items-center gap-1">
          <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-success)", opacity: 0.55 }} />
          Normal week
        </span>
        <span className="flex items-center gap-1">
          <span aria-hidden="true" style={{ width: 8, height: 8, borderRadius: 2, background: "var(--color-warning)" }} />
          Flagged week
        </span>
      </span>
    </div>
  );
}

/** A titled group of icon rows (evidence / innocent explanations). */
function Bullets({ title, items, icon, color }: { title: string; items: string[]; icon: IconRowIcon; color: string }) {
  if (!items.length) return null;
  return (
    <div className="flex flex-col gap-2">
      <span className="text-xs font-bold uppercase" style={{ color, letterSpacing: "var(--letter-spacing-badge)" }}>
        {title}
      </span>
      <div className="flex flex-col gap-1.5">
        {items.map((text) => (
          <IconRow key={text} icon={icon} color={color}>
            {text}
          </IconRow>
        ))}
      </div>
    </div>
  );
}

const INNOCENT_COLOR = "var(--color-information)";

export function IntegrityTeamCard({ team }: { team: IntegrityTeam }) {
  const [open, setOpen] = useState(team.band === "strong");
  const expandable = team.band === "strong" || team.band === "worth_a_look";
  return (
    <AccentCard accent={bandColor(team.band)} as="article">
      <div className="flex items-center gap-3">
        {team.weeks.evaluated ? (
          <ValueRing
            percent={Math.round((team.weeks.flagged / team.weeks.evaluated) * 100)}
            tint={bandColor(team.band)}
            display={`${team.weeks.flagged}/${team.weeks.evaluated}`}
            ariaLabel={`${team.weeks.flagged} of ${team.weeks.evaluated} weeks flagged`}
            size="md"
          />
        ) : null}
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-base font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
            {team.team_name}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {team.owner_name}
            {team.weeks.evaluated ? ` · ${team.weeks.flagged} of ${team.weeks.evaluated} weeks flagged` : ""}
          </span>
        </div>
        <ToneBadge label={BAND_LABEL[team.band]} color={bandColor(team.band)} />
      </div>
      {expandable ? (
        <>
          {INTERPRETATION_LABEL[team.interpretation] ? (
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {INTERPRETATION_LABEL[team.interpretation]} · {CONFIDENCE_LABEL[team.confidence]}
            </p>
          ) : null}
          <button
            type="button"
            className="text-xs font-bold self-start"
            style={{ color: "var(--color-accent)" }}
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "Hide the evidence" : "Show the evidence"}
          </button>
          {open ? (
            <>
              <Bullets title="Evidence" items={team.evidence.map((e) => e.text)} icon="alert" color={bandColor(team.band)} />
              <EfficiencyBars team={team} />
              <Bullets title="Could be innocent" items={team.innocent_explanations} icon="info" color={INNOCENT_COLOR} />
            </>
          ) : null}
        </>
      ) : null}
    </AccentCard>
  );
}

function CollusionCard({ pair }: { pair: IntegrityCollusionPair }) {
  return (
    <AccentCard accent={bandColor(pair.band)} as="article">
      <div className="flex items-start justify-between gap-2">
        <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {pair.headline}
        </span>
        <ToneBadge label={BAND_LABEL[pair.band]} color={bandColor(pair.band)} />
      </div>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {pair.summary} · {CONFIDENCE_LABEL[pair.confidence]}
      </p>
      <Bullets title="Evidence" items={pair.evidence} icon="alert" color={bandColor(pair.band)} />
      <Bullets title="Could be innocent" items={pair.innocent_explanations} icon="info" color={INNOCENT_COLOR} />
    </AccentCard>
  );
}

function InactiveCard({ manager }: { manager: IntegrityInactiveManager }) {
  return (
    <AccentCard accent="var(--color-warning)" as="article">
      <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
        {manager.team_name}
      </span>
      <Bullets title="Evidence" items={manager.evidence} icon="clock" color="var(--color-warning)" />
      <Bullets title="Could be innocent" items={manager.innocent_explanations} icon="info" color={INNOCENT_COLOR} />
    </AccentCard>
  );
}

function CalendarCard({ calendar }: { calendar: IntegrityCalendar | null | undefined }) {
  if (!calendarLines(calendar).length || !calendar) return null;
  const d = calendar.trade_deadline_week;
  const deadlineNote =
    d == null
      ? "No deadline set"
      : calendar.deadline_phase === "passed"
        ? "Passed; reopens after the season"
        : calendar.deadline_phase === "final_week"
          ? "This week: last call"
          : calendar.weeks_to_deadline != null
            ? `${calendar.weeks_to_deadline} week${calendar.weeks_to_deadline === 1 ? "" : "s"} left`
            : undefined;
  const season = calendar.regular_season_weeks;
  const progress =
    calendar.in_season && calendar.current_week && season
      ? Math.max(0, Math.min(100, Math.round((calendar.current_week / season) * 100)))
      : null;
  return (
    <section className="flex flex-col gap-2" aria-label="League calendar" data-testid="integrity-calendar">
      <SectionHeading>League calendar</SectionHeading>
      <div className="grid grid-cols-3 gap-2">
        {calendar.current_week && calendar.in_season ? (
          <SnapshotTile compact glyph="age" label="Now" value={`Wk ${calendar.current_week}`} note={season ? `of ${season}` : undefined} />
        ) : null}
        <SnapshotTile
          compact
          glyph="record"
          label="Trade deadline"
          value={d == null ? "None" : `Wk ${d}`}
          note={deadlineNote}
          tone={calendar.deadline_phase === "final_week" ? "risk" : "neutral"}
        />
        {calendar.playoff_week_start ? (
          <SnapshotTile compact glyph="power" label="Playoffs" value={`Wk ${calendar.playoff_week_start}`} note="Start" />
        ) : null}
      </div>
      {progress !== null ? (
        <div
          role="progressbar"
          aria-label="Regular season progress"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={progress}
          className="h-1.5 w-full"
          style={{ background: "var(--color-surface-muted)" }}
        >
          <div className="h-full" style={{ width: `${progress}%`, background: "var(--color-accent)" }} />
        </div>
      ) : null}
    </section>
  );
}

export function CommissionerView({
  data,
  draftOrder,
  onDraftOrder,
}: {
  data: CommissionerIntegrityResponse;
  draftOrder: DraftOrderRule;
  onDraftOrder: (value: DraftOrderRule) => void;
}) {
  const { flagged, rest } = splitTeams(data.teams);
  const [showRest, setShowRest] = useState(false);
  return (
    <>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="integrity-summary">
        {integritySummaryLine(data)}
      </p>
      <CalendarCard calendar={data.calendar} />
      <div className="flex flex-col gap-1">
        <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          How is your draft order set?
        </span>
        <PillRow
          options={DRAFT_ORDER_OPTIONS.map((o) => ({ label: o.label, value: o.value }))}
          active={draftOrder}
          onSelect={(value) => onDraftOrder(value as DraftOrderRule)}
          variant="fill"
          ariaLabel="Draft order rule"
        />
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Worst record means the worst team picks first; Lottery covers any other order. Sleeper does not publish this, so it changes how a flagged team is described, not the lineup math.
        </span>
      </div>

      {flagged.length ? (
        <section className="flex flex-col gap-3">
          <SectionHeading>Worth a look</SectionHeading>
          {flagged.map((team) => (
            <IntegrityTeamCard key={team.roster_id} team={team} />
          ))}
        </section>
      ) : null}

      {data.collusion.length ? (
        <section className="flex flex-col gap-3">
          <SectionHeading note="Same two managers, repeated trades: one-sided on value (picks priced like the Trade Analyzer), assets going back and forth, or several trades in one week. A prompt to look, not a verdict.">
            Repeated trades worth a look
          </SectionHeading>
          {data.collusion.map((pair) => (
            <CollusionCard key={pair.roster_ids.join("-")} pair={pair} />
          ))}
        </section>
      ) : null}

      {data.inactive.length ? (
        <section className="flex flex-col gap-3">
          <SectionHeading>Possibly inactive</SectionHeading>
          {data.inactive.map((m) => (
            <InactiveCard key={m.roster_id} manager={m} />
          ))}
        </section>
      ) : null}

      {rest.length ? (
        <section className="flex flex-col gap-3">
          <SectionHeading>{flagged.length ? "Everyone else" : "Team lineups"}</SectionHeading>
          <div className="glass-surface p-4 flex items-center justify-between gap-3" data-testid="integrity-rest-summary">
            <IconRow icon="check" color="var(--color-success)" textClassName="text-sm font-bold">
              <span style={{ color: "var(--color-success)" }}>{restSummary(data.teams, flagged.length)}</span>
            </IconRow>
            <button
              type="button"
              className="text-xs font-bold shrink-0"
              style={{ color: "var(--color-accent)" }}
              aria-expanded={showRest}
              onClick={() => setShowRest((v) => !v)}
            >
              {showRest ? "Hide teams" : `Show ${rest.length} team${rest.length === 1 ? "" : "s"}`}
            </button>
          </div>
          {showRest ? rest.map((team) => <IntegrityTeamCard key={team.roster_id} team={team} />) : null}
        </section>
      ) : null}

      {data.limits?.length ? (
        <details className="glass-surface p-4">
          <summary className="text-sm font-bold cursor-pointer" style={{ color: "var(--color-text-primary)" }}>
            What this can and can&rsquo;t tell you
          </summary>
          <div className="flex flex-col gap-2 mt-3">
            {data.limits.map((limit) => (
              <IconRow key={limit} icon="info" color="var(--color-text-muted)" textClassName="text-xs">
                {limit}
              </IconRow>
            ))}
          </div>
        </details>
      ) : null}
    </>
  );
}

export function CommissionerContent({ leagueId, leagueName, lens }: { leagueId: string; leagueName: string; lens?: string }) {
  const [draftOrder, setDraftOrder] = useState<DraftOrderRule>("unknown");
  const [state, setState] = useState<{ key: string; data: CommissionerIntegrityResponse | null; error: string | null }>({
    key: "",
    data: null,
    error: null,
  });
  const key = `${leagueId}|${draftOrder}`;
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getCommissionerIntegrity(leagueId, draftOrder)
      .then((data) => {
        if (!cancelled) setState({ key, data, error: null });
      })
      .catch((err) => {
        if (!cancelled) setState({ key, data: null, error: err instanceof Error ? err.message : "Could not load League integrity." });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, draftOrder, key, attempt]);

  const ready = state.key === key;
  const data = ready ? state.data : null;

  return (
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page="Commissioner" leagueName={leagueName} />
      </header>
      {!ready ? (
        <LoadingScreen status="Reading the league’s weekly lineups…" />
      ) : state.error || !data ? (
        <ErrorState message={state.error || "Could not load League integrity."} onRetry={() => { setState({ key: "", data: null, error: null }); setAttempt((n) => n + 1); }} />
      ) : data.is_premium === false ? (
        <PremiumUpsellCard
          kicker="League integrity"
          leagueName={leagueName}
          upsell={data.upsell ?? null}
          fallbackTitle="Spot tanking and lineup problems early"
          fallbackBody="League integrity is a Pro feature: lineup efficiency, tanking signals with the evidence behind them, repeated lopsided trades and inactive managers."
          bare
        />
      ) : data.reason ? (
        <>
          <EmptyState title="Nothing to show yet" subtitle={integrityReasonMessage(data.reason)} />
          <CalendarCard calendar={data.calendar} />
        </>
      ) : (
        <CommissionerView data={data} draftOrder={draftOrder} onDraftOrder={setDraftOrder} />
      )}
      {ready && data && data.is_premium !== false ? <VetoCalculator leagueId={leagueId} lens={lens} /> : null}
    </main>
  );
}
