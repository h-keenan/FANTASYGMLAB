"use client";

import { useEffect, useMemo, useState } from "react";

import { ButtonLink } from "@/components/Button";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { EmptyState } from "@/components/EmptyState";
import { PlayerQuickView, StatGroup, type SimPqvSections } from "@/components/PlayerQuickView";
import { ProspectReportForm, type ReportDraft, type ReportFlash } from "@/components/ProspectReportForm";
import { SkeletonBlock } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { ViewTabs } from "@/components/ui/ViewTabs";
import { WeeklyPointsPanel } from "@/components/WeeklyPointsChartLazy";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { api, type CollegeProspect } from "@/lib/api";
import { aggregateText, scoutingConfidenceLabel } from "@/lib/collegeScoutingPresentation";
import {
  PROSPECT_NO_STATS,
  PROSPECT_SOURCE_NAME,
  PROSPECT_SOURCE_URL,
  adpHeroTile,
  advancedTiles,
  classYearLabel,
  gameStatLine,
  handOffPlayerId,
  hometownLine,
  lineTiles,
  prospectMetaLine,
  prospectWeeklySeries,
  recruitingTiles,
  roundHeroTile,
  type ProspectProfileResponse,
} from "@/lib/prospectProfile";
import { confidenceColor } from "@/lib/waiversPresentation";

interface LoadState {
  profile: ProspectProfileResponse | null;
  failed: boolean;
  done: boolean;
}

/**
 * The college prospect detail sheet. It IS the shared player quick view (same sheet chrome, hero header, swipeable tabs and
 * weekly chart as an NFL player or a Fantasy Sim player), fed a prospect's own sections through `customSections`:
 * Overview (crowd grade, round, ADP, your report, watchlist), Stats (CFBD season lines + advanced + weekly chart) and
 * Profile (recruiting + hometown). Basics are free; advanced metrics are Pro (the server withholds them and sets advanced_locked).
 * Once he is drafted the normal NFL player card takes over (`sleeper_player_id`). Mobile twin: components/ProspectSheet.tsx.
 */
export function ProspectSheet({
  prospect,
  draft,
  flash,
  busy,
  onDraftChange,
  onSubmit,
  onRemove,
  onToggleWatchlist,
  onClose,
}: {
  prospect: CollegeProspect;
  draft: ReportDraft;
  flash: ReportFlash | null;
  busy: boolean;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => Promise<boolean>;
  onToggleWatchlist: () => void;
  onClose: () => void;
}) {
  const { openPlayer } = usePlayerQuickView();
  const [state, setState] = useState<LoadState>({ profile: null, failed: false, done: false });

  useEffect(() => {
    let cancelled = false;
    api.getProspectProfile(prospect.id)
      .then((profile) => {
        if (!cancelled) setState({ profile: profile.ok ? profile : null, failed: !profile.ok && profile.reason !== "not_found", done: true });
      })
      .catch(() => {
        if (!cancelled) setState({ profile: null, failed: true, done: true });
      });
    return () => {
      cancelled = true;
    };
  }, [prospect.id]);

  // Drafted and mapped: the normal NFL player card takes over.
  const handOffId = handOffPlayerId(prospect) ?? (state.profile?.prospect?.drafted ? handOffPlayerId(state.profile.prospect) : null);
  useEffect(() => {
    if (!handOffId) return;
    openPlayer({ player_id: handOffId, name: prospect.name, position: prospect.position, team: state.profile?.prospect?.nfl_team ?? undefined, sourceLabel: "Drafted prospect" });
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handOffId]);

  const { profile } = state;
  const aggregate = prospect.aggregate;
  const sections: SimPqvSections = useMemo(() => {
    const round = roundHeroTile(aggregate.avg_round_projection, aggregate.scout_count);
    const metaLine = prospectMetaLine(prospect.draft_year, profile?.bio) || `${prospect.draft_year ?? ""} class`;
    return {
      overview: (
        <ProspectOverview
          prospect={prospect}
          adpNote={state.done ? (profile?.adp?.source?.source ?? null) : null}
          draft={draft}
          flash={flash}
          busy={busy}
          onDraftChange={onDraftChange}
          onSubmit={onSubmit}
          onRemove={onRemove}
          onToggleWatchlist={onToggleWatchlist}
        />
      ),
      heroGrade: (
        <div className="pqv-stat-tile" data-testid="prospect-grade-tile">
          <span className={`pqv-stat-tile-value${aggregate.avg_grade == null ? " pqv-stat-tile-value--empty" : ""}`}>{aggregate.avg_grade != null ? aggregate.avg_grade.toFixed(1) : "—"}</span>
          <span className="pqv-stat-tile-caption">Crowd grade</span>
          <span className="pqv-stat-tile-note">{aggregate.scout_count > 0 ? `${aggregate.scout_count} ${aggregate.scout_count === 1 ? "scout" : "scouts"}` : "Not yet scouted"}</span>
        </div>
      ),
      heroTiles: [round, adpHeroTile(state.done ? profile?.adp : null)],
      headerMeta: { line: metaLine, logo: profile?.bio?.school_logo_url ?? null },
      stats: <ProspectStats prospect={prospect} state={state} />,
      profile: <ProspectProfile prospect={prospect} state={state} />,
    };
    // The form props change on every keystroke; the sheet re-renders with them.
  }, [prospect, profile, state, aggregate, draft, flash, busy, onDraftChange, onSubmit, onRemove, onToggleWatchlist]);

  if (handOffId) return null;
  return (
    <PlayerQuickView
      identity={{ player_id: `prospect-${prospect.id}`, name: prospect.name, position: prospect.position, team: prospect.school, sourceLabel: "College prospect" }}
      onClose={onClose}
      remote={false}
      customSections={sections}
    />
  );
}

function ProspectOverview({
  prospect,
  adpNote,
  draft,
  flash,
  busy,
  onDraftChange,
  onSubmit,
  onRemove,
  onToggleWatchlist,
}: {
  prospect: CollegeProspect;
  adpNote: string | null;
  draft: ReportDraft;
  flash: ReportFlash | null;
  busy: boolean;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => Promise<boolean>;
  onToggleWatchlist: () => void;
}) {
  const aggregate = prospect.aggregate;
  const hasReport = prospect.my_report != null;
  return (
    <div className="flex flex-col gap-3 pt-2" data-testid="prospect-overview">
      <section className="pqv-stat-season">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3>Crowd scouting</h3>
          {aggregate.scout_count > 0 ? (
            <ConfidenceMeter label="Signal" value={scoutingConfidenceLabel(aggregate.scout_count)} color={confidenceColor(scoutingConfidenceLabel(aggregate.scout_count))} />
          ) : null}
        </div>
        <p className="m-0 text-sm font-bold" style={{ color: "var(--color-text-secondary)" }}>
          {aggregateText(aggregate)}
          {aggregate.avg_round_projection != null && aggregate.scout_count > 0 ? ` · projected round ${aggregate.avg_round_projection.toFixed(1)}` : ""}
        </p>
        {prospect.my_report?.grade != null ? (
          <p className="m-0 text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            Your grade: {prospect.my_report.grade}/5
          </p>
        ) : null}
        {adpNote ? (
          <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="prospect-adp-source">
            Rookie ADP from {adpNote}.
          </p>
        ) : null}
        <div className="pt-1">
          <button
            type="button"
            onClick={onToggleWatchlist}
            className="px-2 py-1 text-xs font-bold"
            style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            {prospect.on_watchlist ? "Unfollow" : "Follow"}
          </button>
        </div>
      </section>
      <section className="pqv-stat-season">
        <h3>{hasReport ? "Your report" : `Scout ${prospect.name}`}</h3>
        <ProspectReportForm hasReport={hasReport} draft={draft} flash={flash} busy={busy} onDraftChange={onDraftChange} onSubmit={onSubmit} onRemove={onRemove} />
      </section>
    </div>
  );
}

function SourceLine({ profile }: { profile: ProspectProfileResponse | null }) {
  const source = profile?.source;
  return (
    <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="prospect-source">
      Source:{" "}
      <a href={source?.url ?? PROSPECT_SOURCE_URL} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-accent)" }}>
        {source?.name ?? PROSPECT_SOURCE_NAME}
      </a>
      {source?.as_of ? ` · updated ${source.as_of}` : ""}
    </p>
  );
}

function ProspectStats({ prospect, state }: { prospect: CollegeProspect; state: LoadState }) {
  const { profile } = state;
  const seasons = profile?.seasons ?? [];
  const [picked, setPicked] = useState<string | null>(null);
  if (!state.done) return <SkeletonBlock height="10rem" />;
  if (state.failed) return <EmptyState title="Could not load stats" subtitle="Close the sheet and open him again." />;
  const series = prospectWeeklySeries(profile?.weekly ?? null);
  if (seasons.length === 0 && !series) {
    return (
      <div className="flex flex-col gap-2">
        <EmptyState title="No college stats yet" subtitle={PROSPECT_NO_STATS} />
        <SourceLine profile={profile} />
      </div>
    );
  }
  const active = seasons.find((s) => String(s.season) === picked) ?? seasons[0];
  const advanced = advancedTiles(profile?.advanced, prospect.position);
  const games = (profile?.weekly?.games ?? []).filter((g) => g.fantasy_points != null).slice(-5).reverse();
  return (
    <div className="flex flex-col gap-3 pt-2" data-testid="prospect-stats">
      {active ? (
        <section className="pqv-stat-season" data-testid="prospect-season-stats">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h3>{active.season} season{active.team ? ` · ${active.team}` : ""}</h3>
            {seasons.length > 1 ? (
              <ViewTabs
                label="Season"
                value={String(active.season)}
                options={seasons.map((s) => ({ value: String(s.season), label: String(s.season) }))}
                onChange={setPicked}
              />
            ) : null}
          </div>
          <StatGroup title="Season stats" items={lineTiles(active, prospect.position)} hideTitle />
          {active.fantasy_points != null ? (
            <p className="m-0 pt-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
              College fantasy points (derived): <strong>{active.fantasy_points.toFixed(1)}</strong>
            </p>
          ) : null}
        </section>
      ) : null}

      {advanced.length > 0 ? (
        <section className="pqv-stat-season" data-testid="prospect-advanced">
          <h3>Advanced</h3>
          <StatGroup title="Advanced" items={advanced} hideTitle />
          <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
            PPA is predicted points added per play. Usage is his share of his team&apos;s plays.
          </p>
        </section>
      ) : profile?.advanced_locked ? (
        <section className="pqv-stat-season" data-testid="prospect-advanced-lock">
          <div className="flex flex-wrap items-center gap-2">
            <ToneBadge label="Pro" color="var(--color-premium)" />
            <span className="min-w-0 flex-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Advanced metrics: PPA and usage
            </span>
            <ButtonLink href="/premium" variant="premium" size="sm">
              See Pro
            </ButtonLink>
          </div>
        </section>
      ) : null}

      {series ? (
        <section className="pqv-stat-season" data-testid="prospect-weekly">
          <h3>Points by week · {series.season}</h3>
          <WeeklyPointsPanel name={prospect.name} weeks={series.weeks} season={series.season} pointsLabel="college pts" />
          <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
            Derived from {PROSPECT_SOURCE_NAME} stat lines (PPR, no fumbles).
          </p>
          {games.length > 0 ? (
            <ul className="m-0 flex list-none flex-col gap-1 p-0 pt-1" data-testid="prospect-game-log">
              {games.map((g) => (
                <li key={g.week} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  <span className="font-bold" style={{ color: "var(--color-text-primary)" }}>
                    Wk {g.week}{g.opponent ? ` vs ${g.opponent}` : ""}
                  </span>{" "}
                  · {gameStatLine(g, prospect.position)}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}
      <SourceLine profile={profile} />
    </div>
  );
}

function ProspectProfile({ prospect, state }: { prospect: CollegeProspect; state: LoadState }) {
  if (!state.done) return <SkeletonBlock height="6rem" />;
  const { profile } = state;
  const recruiting = recruitingTiles(profile?.recruiting);
  const hometown = hometownLine(profile?.recruiting, profile?.bio?.hometown);
  const classYear = classYearLabel(profile?.bio?.class_year);
  const bits = [classYear, prospect.school, hometown ? `From ${hometown}` : null].filter((b): b is string => Boolean(b));
  if (recruiting.length === 0 && bits.length <= 1) {
    return (
      <div className="flex flex-col gap-2">
        <EmptyState title="No profile yet" subtitle="Recruiting and hometown fill in weekly." />
        <SourceLine profile={profile} />
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3 pt-2" data-testid="prospect-profile">
      <section className="pqv-stat-season">
        <h3>Recruiting</h3>
        {recruiting.length > 0 ? <StatGroup title="Recruiting" items={recruiting} hideTitle /> : <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>No recruiting rank on file.</p>}
        {bits.length > 0 ? (
          <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {bits.join(" · ")}
          </p>
        ) : null}
      </section>
      <SourceLine profile={profile} />
    </div>
  );
}
