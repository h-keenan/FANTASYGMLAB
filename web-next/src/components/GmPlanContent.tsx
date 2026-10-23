"use client";

import Link from "next/link";
import { EmptyState } from "@/components/EmptyState";
import { AccentCard } from "@/components/AccentCard";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import { SectionHeading } from "@/components/SectionHeading";
import { InfoTip } from "@/components/InfoTip";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { GM_PLAN_TABS, type GmPlanTab, isGmPlanTab, PlanSnapshotGrid, TeamSituationCard } from "@/components/GmPlanSections";
import { deadlineBanner, type PlanSnapshotTile } from "@/lib/gmPlanSnapshot";
import type { ReactNode } from "react";
import {
  api,
  type GmPlanFocusArea,
  type GmPlanFocusItem,
  type GmPlanInjuryItem,
  type GmPlanPlayoffOddsItem,
  type GmPlanRankItem,
  type GmPlanRecordItem,
  type GmPlanResponse,
  type GmPlanTradeItem,
  type GmTarget,
  type LeagueRankingsResponse,
  type MyTeamResponse,
  type TeamStance,
  type TeamStanceResponse,
} from "@/lib/api";
import { trackFeatureUse } from "@/lib/analytics";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { PLAIN_COPY } from "@/lib/experienceCopy";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { formatTradeGain } from "@/lib/tradeHubPresentation";
import { gmPlanReasonMessage } from "@/lib/gmPlanPresentation";
import { buildProtectRows, splitProtectRows, type ProtectRow } from "@/lib/teamStancePresentation";
import { groupTargetRows, targetContextLine, type GmTargetRow } from "@/lib/gmTargetsPresentation";
import { formatWaiverScore, waiverInjuryDisplay } from "@/lib/waiversPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Ports modules/gm_plan_ui.py's render_gm_plan_workspace / mobile's
 * GmPlanScreen.tsx for Revision 9 — GM Plan's season-arc roadmap: a
 * phase/stance hero, then three focus-area sections (Where You Stand,
 * Trade Opportunities, Roster Construction). Reads the exact same
 * GET .../gm-plan endpoint both of those already call — no duplicated
 * aggregation or valuation logic here, only presentation.
 *
 * Revision 20 (2026-10-18, coridian_: "What do you think about merging
 * the team situation, GM targets and GM plan into one page?" / agreed
 * "yes I like it... same reasoning as killing the Explore grid today"):
 * Team Situation (stance declaration + the roster-wide "Protected
 * Players" checklist) and GM Targets (the Untouchable/Watching
 * watchlist) are folded in here as always-visible sections — neither was
 * ever Premium-gated, so they stay reachable for Free users even though
 * the roadmap itself (season phase/stance hero + focus areas) still is.
 * The two standalone pages (/team-situation, /gm-targets) now just
 * redirect here; GM orb/sidebar nav lost those two entries, down to one
 * "GM Plan" destination. Protected Players and the Watching group can
 * both legitimately list the same untouchable roster player (one is a
 * roster-wide checklist, the other a tracked-watchlist view over the
 * same underlying flag) — a known, minor, forgivable overlap, not a bug.
 */

function focusItemKey(item: GmPlanFocusItem, index: number): string {
  if ("partner_team_name" in item) return `trade-${item.my_player_id || item.their_player_id || index}`;
  if ("injury_need_positions" in item) return `injury-${index}`;
  if ("rank" in item) return `rank-${item.label}`;
  if ("wins" in item) return "record";
  return "playoff-odds";
}

function FactCard({ accent, children }: { accent: string; children: ReactNode }) {
  return (
    <AccentCard accent={accent} compact>
      {children}
    </AccentCard>
  );
}

function RankFact({ item }: { item: GmPlanRankItem }) {
  const weakSpot = Boolean(item.relative_weak_spot);
  const tieNote = item.tied ? " (tied)" : "";
  return (
    <FactCard accent={weakSpot ? "var(--color-danger)" : "var(--color-accent)"}>
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {item.label}: {item.rank}
        {item.total_teams ? ` of ${item.total_teams}` : ""}
        {tieNote}
      </p>
      {weakSpot ? (
        <p className="text-xs" style={{ color: "var(--color-danger)" }}>
          Relative weak spot in this league.
        </p>
      ) : null}
    </FactCard>
  );
}

function RecordFact({ item }: { item: GmPlanRecordItem }) {
  return (
    <FactCard accent="var(--color-accent)">
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        Record: {item.wins ?? 0}-{item.losses ?? 0}
        {item.ties ? `-${item.ties}` : ""}
      </p>
    </FactCard>
  );
}

function PlayoffOddsFact({ item }: { item: GmPlanPlayoffOddsItem }) {
  const seedNote = item.median_seed ? `, projected ${item.median_seed}-seed` : "";
  const statusNote = item.clinched ? " · Clinched" : item.eliminated ? " · Eliminated" : "";
  return (
    <FactCard accent="var(--color-accent)">
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {Math.round(item.playoff_probability)}% to make the playoffs{seedNote}
        {statusNote}
      </p>
    </FactCard>
  );
}

function InjuryExposureFact({ item }: { item: GmPlanInjuryItem }) {
  const positions = item.injury_need_positions.join(", ");
  return (
    <FactCard accent="var(--color-danger)">
      <p className="text-sm font-bold" style={{ color: "var(--color-danger)" }}>
        {item.health_flag || item.label}
        {positions ? `: ${positions}` : ""}
      </p>
      <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
        {item.summary || `No healthy bench cover at ${positions}.`}
      </p>
      {item.injured_players.length > 0 ? (
        <div className="flex flex-col divide-y mt-1" style={{ borderColor: "var(--color-border)" }}>
          {item.injured_players.map((player) => (
            <div key={player.player_id} className="flex items-center gap-2 py-1">
              <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "GM Plan" }} className="flex items-center gap-2 flex-1 min-w-0">
                <PositionBadge position={player.position} />
                <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
                  {player.name}
                </span>
                {player.team ? (
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {player.team}
                  </span>
                ) : null}
              </PlayerIdentityTrigger>
              <PlayerInjuryBadge status={player.injury_status} />
            </div>
          ))}
        </div>
      ) : null}
    </FactCard>
  );
}

function TradeOpportunityCard({ item, detailsHref }: { item: GmPlanTradeItem; detailsHref?: string }) {
  const hasAssets = item.send_assets.length > 0 || item.receive_assets.length > 0;
  const injuryDisplay = item.their_player_injury_display || "";
  const accent = injuryDisplay ? "var(--color-danger)" : "var(--color-accent)";
  const gain = item.trade_gain;
  const hasGain = gain !== null && gain !== undefined;
  const gainColor = hasGain && gain! > 0 ? "var(--color-success)" : hasGain && gain! < 0 ? "var(--color-danger)" : "var(--color-text-secondary)";
  const theirLabel = injuryDisplay ? `${item.their_player} (${injuryDisplay})` : item.their_player;

  return (
    <AccentCard accent={accent}>
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-base font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
          {item.partner_team_name || "Trade idea"}
        </h3>
        {hasGain ? (
          <span className="text-sm font-bold shrink-0" style={{ color: gainColor, fontVariantNumeric: "tabular-nums" }}>
            {formatTradeGain(gain!)}
          </span>
        ) : null}
      </div>

      {hasAssets ? (
        <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
          <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={item.send_assets} />
          <div
            className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
            style={{ color: "var(--color-accent)" }}
            aria-hidden="true"
          >
            FOR
          </div>
          <ExchangeSide label="You get" dotColor="var(--color-success)" assets={item.receive_assets} />
        </div>
      ) : (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {item.my_player} → {theirLabel}
        </p>
      )}

      <div className="flex items-end justify-between gap-3">
        <p className="text-xs flex-1 min-w-0" style={{ color: "var(--color-text-secondary)" }}>
          {item.rationale || item.trade_confidence_label}
        </p>
        {detailsHref ? (
          <Link
            href={detailsHref}
            className="inline-flex items-center px-3 text-xs font-bold shrink-0"
            style={{ color: "var(--color-accent)", border: "1px solid var(--color-accent)", minHeight: "2.25rem" }}
          >
            View details
          </Link>
        ) : null}
      </div>
    </AccentCard>
  );
}

function FocusItem({ item, detailsHref }: { item: GmPlanFocusItem; detailsHref?: (item: GmPlanTradeItem) => string }) {
  if ("partner_team_name" in item) return <TradeOpportunityCard item={item} detailsHref={detailsHref?.(item)} />;
  if ("injury_need_positions" in item) return <InjuryExposureFact item={item} />;
  if ("rank" in item) return <RankFact item={item} />;
  if ("wins" in item) return <RecordFact item={item} />;
  if ("playoff_probability" in item) return <PlayoffOddsFact item={item} />;
  return null;
}

function FocusAreaSection({ area, detailsHref }: { area: GmPlanFocusArea; detailsHref?: (item: GmPlanTradeItem) => string }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <SectionHeading>{area.title}</SectionHeading>
        {area.framing ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {area.framing}
          </p>
        ) : null}
      </div>

      {area.status === "no_signal" ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {area.watch_for || "Nothing to flag right now."}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {area.items.map((item, index) => (
            <FocusItem key={focusItemKey(item, index)} item={item} detailsHref={detailsHref} />
          ))}
        </div>
      )}
    </section>
  );
}

function ProtectPlayerRow({
  row,
  busy,
  onToggle,
}: {
  row: ProtectRow;
  busy: boolean;
  onToggle: (playerId: string, next: boolean) => void;
}) {
  const { player, protected: isProtected } = row;

  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentity
        identity={{ ...player, sourceLabel: "Team Situation" }}
        playerId={player.player_id}
        name={player.name || "Unknown player"}
        position={player.position}
        tier={player.tier}
        injuryStatus={player.injury_label}
        className="flex-1 min-w-0"
      >
        {player.team || "FA"}
      </PlayerIdentity>
      <OvrGauge rating={player.overall_rating} size="sm" />
      <button
        type="button"
        disabled={busy}
        onClick={() => onToggle(player.player_id, !isProtected)}
        className="px-2 py-1 text-xs font-bold shrink-0"
        style={
          isProtected
            ? {
                background: "var(--color-premium)",
                color: "var(--color-brand-mark-ink)",
                border: "var(--border-width-default) solid var(--color-premium)",
              }
            : { color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }
        }
      >
        {busy ? "…" : isProtected ? "Protected" : "Protect"}
      </button>
    </div>
  );
}

function TargetRowView({
  row,
  leagueId,
  leagueName,
  onToggleUntouchable,
  onRemove,
}: {
  row: GmTargetRow;
  leagueId: string;
  leagueName: string;
  onToggleUntouchable: (playerId: string, next: boolean) => void;
  onRemove: (playerId: string) => void;
}) {
  const { target, player } = row;
  const injury = waiverInjuryDisplay(player?.injury_status);
  const contextLine = targetContextLine(row);
  const name = player?.name || `Player ${target.player_id}`;

  return (
    <div className="flex flex-col gap-2 py-3" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <div className="flex items-center justify-between gap-3">
        <PlayerIdentity
          identity={{ ...player, player_id: target.player_id, name, sourceLabel: "GM Targets", leagueId, leagueName }}
          playerId={target.player_id}
          name={name}
          position={player?.position}
          tier={player?.tier}
          injuryStatus={injury.label}
        >
          {player?.team || "—"}
          {contextLine ? ` · ${contextLine}` : ""}
        </PlayerIdentity>
        <div className="flex items-center gap-2 shrink-0">
          {player?.score !== null && player?.score !== undefined ? (
            <ValueStat value={formatWaiverScore(player.score)} />
          ) : null}
          {player?.position_rank ? (
            <span
              className="px-1.5 py-0.5 text-xs font-bold"
              style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
              title={`Ranked #${player.position_rank} among all ${player.position}s — overall, not just this league.`}
            >
              {player.position}
              {player.position_rank}
            </span>
          ) : null}
          <OvrGauge rating={player?.overall_rating ?? null} size="sm" />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <a
          href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(target.player_id)}&name=${encodeURIComponent(leagueName)}`}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          Compare
        </a>
        <button
          type="button"
          onClick={() => onToggleUntouchable(target.player_id, !target.untouchable)}
          className="px-2 py-1 text-xs font-bold"
          style={
            target.untouchable
              ? { background: "var(--color-premium)", color: "var(--color-brand-mark-ink)", border: "var(--border-width-default) solid var(--color-premium)" }
              : { color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }
          }
        >
          {target.untouchable ? "Unmark untouchable" : "Mark untouchable"}
        </button>
        <button
          type="button"
          onClick={() => onRemove(target.player_id)}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-danger)", border: "var(--border-width-default) solid var(--color-danger)" }}
        >
          Remove
        </button>
      </div>
    </div>
  );
}

export function GmPlanContent({
  leagueId,
  leagueName,
  data,
  teamStance,
  myTeam,
  targets,
  rankings,
  snapshot,
  initialTab,
}: {
  /** Optional only so this component's existing unit tests (which predate
   * the Revision 20 merge below) don't all need the full data set —
   * app/gm-plan/[leagueId]/page.tsx always has real ones to pass. */
  leagueId?: string;
  leagueName: string;
  data: GmPlanResponse;
  teamStance?: TeamStanceResponse;
  myTeam?: MyTeamResponse;
  targets?: GmTarget[];
  rankings?: LeagueRankingsResponse;
  /** Plan Snapshot tiles (lib/gmPlanSnapshot); omitted tiles never render. */
  snapshot?: PlanSnapshotTile[];
  initialTab?: GmPlanTab;
}) {
  const router = useRouter();
  const [tab, setTab] = useState<GmPlanTab>(initialTab ?? "overview");
  const [showRoster, setShowRoster] = useState(false);
  const [stance, setStanceState] = useState<TeamStance | "">(teamStance?.stance ?? "");
  const [trackedRows, setTrackedRows] = useState<GmTarget[]>(targets ?? []);
  const [busyPlayerId, setBusyPlayerId] = useState<string | null>(null);

  const protectRows = useMemo(
    () => buildProtectRows(myTeam?.starters ?? [], myTeam?.bench ?? [], trackedRows),
    [myTeam, trackedRows],
  );
  const { protectedRows, otherRows } = useMemo(() => splitProtectRows(protectRows), [protectRows]);

  const byId = useMemo(
    () => new Map((rankings?.players ?? []).map((p) => [p.player_id, p])),
    [rankings],
  );
  const joinedTargets = useMemo<GmTargetRow[]>(
    () => trackedRows.map((target) => ({ target, player: byId.get(target.player_id) ?? null })),
    [trackedRows, byId],
  );
  const { watching } = useMemo(() => groupTargetRows(joinedTargets), [joinedTargets]);

  const onPickStance = (value: string) => {
    const next = value as TeamStance;
    if (next === stance || !leagueId) return;
    // Genuine optimistic update, result intentionally discarded — same
    // contract mobile's GmStanceContext.setStance uses.
    setStanceState(next);
    void api.setTeamStance(leagueId, next).catch(() => {});
  };

  const onToggleProtect = (playerId: string, next: boolean) => {
    if (!leagueId) return;
    setBusyPlayerId(playerId);
    const wasTracked = trackedRows.some((row) => row.player_id === playerId);
    const previous = trackedRows;
    setTrackedRows((prev) => {
      if (!wasTracked) {
        return [...prev, { player_id: playerId, source_surface: "team_stance", created_at: null, untouchable: next }];
      }
      return prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: next } : row));
    });

    (async () => {
      try {
        if (next && !wasTracked) {
          const addResult = await api.addGmTarget(leagueId, playerId, "team_stance");
          if (!addResult.ok) throw new Error(addResult.reason || "not_available");
          // Audit finding, 2026-10-20: gm_target_added (already in
          // TRACKED_EVENTS, already labeled on the Founder Analytics
          // dashboard) had no caller anywhere -- this is the real "save a
          // GM Target" action (the Protected Players checklist adds the
          // player to the same tracked-targets table GM Targets reads).
          // dedupe: false -- every distinct player added is its own real,
          // independently-countable interaction, same reasoning
          // trackFeatureUse's own doc comment gives for pqv_opened/
          // gm_orb_opened (trackFeatureUse's default once_key is scoped by
          // leagueId alone, which would wrongly collapse every other
          // player added in this same league down to a single count).
          trackFeatureUse("gm_target_added", { leagueId, dedupe: false });
        }
        if (next || wasTracked) {
          const result = await api.setGmTargetUntouchable(leagueId, playerId, next);
          if (!result.ok) throw new Error(result.reason || "not_available");
        }
      } catch {
        setTrackedRows(previous);
      } finally {
        setBusyPlayerId(null);
      }
    })();
  };

  const toggleUntouchable = (playerId: string, next: boolean) => {
    if (!leagueId) return;
    setTrackedRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: next } : row)));
    api
      .setGmTargetUntouchable(leagueId, playerId, next)
      .then((result) => {
        if (!result.ok) {
          setTrackedRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: !next } : row)));
        }
      })
      .catch(() => {
        setTrackedRows((prev) => prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: !next } : row)));
      });
  };

  const removeTarget = (playerId: string) => {
    if (!leagueId) return;
    const previous = trackedRows;
    setTrackedRows((prev) => prev.filter((row) => row.player_id !== playerId));
    api.removeGmTarget(leagueId, playerId).catch(() => {
      setTrackedRows(previous);
    });
  };

  const noRoster = protectRows.length === 0;

  const notice = data.reason ? gmPlanReasonMessage(data.reason) : null;
  const quiet = data.quiet || !data.focus_areas || data.focus_areas.length === 0;

  const tradeWindow = data.trade_window ?? myTeam?.trade_window;
  const banner = deadlineBanner(tradeWindow);
  const pastDeadline = Boolean(tradeWindow?.trade_deadline_passed);
  const q = `name=${encodeURIComponent(leagueName)}`;
  const base = leagueId ? encodeURIComponent(leagueId) : "";
  const tradeHubHref = leagueId ? `/trade-hub/${base}?${q}` : undefined;
  const detailsHref = leagueId
    ? (item: GmPlanTradeItem) =>
        `/trade-hub/${base}?${q}${item.their_player_id ? `&playerId=${encodeURIComponent(item.their_player_id)}` : ""}`
    : undefined;

  const tradeArea = data.focus_areas?.find((area) => area.key === "trade_opportunities");
  const tradeItems = (tradeArea?.items ?? []).filter((item): item is GmPlanTradeItem => "partner_team_name" in item);
  const otherAreas = (data.focus_areas ?? []).filter((area) => area.key !== "trade_opportunities");

  const planGate = notice ? (
    <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
      {notice}
    </p>
  ) : !data.is_premium ? (
    <>
      <PremiumUpsellCard
        kicker="GM Plan"
        upsell={data.upsell}
        fallbackTitle="Your season-arc roadmap"
        fallbackBody="GM Plan is a Premium feature: where you stand, your best trade paths, and your roster construction — framed by your declared Team Situation. Upgrade to Premium to unlock it."
        bare
      />
      <section className="glass-surface flex flex-col gap-1 p-4" data-testid="gm-plan-pro-preview">
        <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {PLAIN_COPY.gmPlanProTitle}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {PLAIN_COPY.gmPlanProBody}
        </p>
      </section>
    </>
  ) : quiet ? (
    <EmptyState title="Not enough to build a GM Plan yet." subtitle="We need more of this league's data first." />
  ) : null;

  const rosterLine = (
    <button
      type="button"
      onClick={() => {
        setTab("core");
        setShowRoster(true);
      }}
      className="glass-surface flex items-center justify-between gap-2 px-3 py-2 text-sm"
      style={{ color: "var(--color-text-secondary)" }}
    >
      <span>
        {otherRows.length} more player{otherRows.length === 1 ? "" : "s"} on your roster
      </span>
      <span aria-hidden="true">›</span>
    </button>
  );

  const protectedList = (rows: ProtectRow[]) => (
    <div className="glass-surface flex flex-col px-3">
      {rows.map((row) => (
        <ProtectPlayerRow
          key={row.player.player_id}
          row={row}
          busy={busyPlayerId === row.player.player_id}
          onToggle={onToggleProtect}
        />
      ))}
    </div>
  );

  const linkAction = (label: string, href?: string) =>
    href ? (
      <Link href={href} className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
        {label}
      </Link>
    ) : undefined;

  const tradesBlock = (items: GmPlanTradeItem[], limit?: number) =>
    planGate ? (
      planGate
    ) : items.length === 0 ? (
      <EmptyState
        title="No trade ideas right now."
        subtitle={tradeArea?.watch_for || "Check back as rosters change."}
        actionLabel={tradeHubHref ? "Open Trade Hub" : undefined}
        onAction={tradeHubHref ? () => router.push(tradeHubHref) : undefined}
      />
    ) : (
      <div className="flex flex-col gap-3">
        {(limit ? items.slice(0, limit) : items).map((item, index) => (
          <TradeOpportunityCard key={focusItemKey(item, index)} item={item} detailsHref={detailsHref?.(item)} />
        ))}
      </div>
    );

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          GM Plan
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Roadmap, stance, and watched players.
        </p>
      </header>

      <PillRow
        fullWidth
        options={GM_PLAN_TABS.map((t) => ({ label: t.label, value: t.value }))}
        active={tab}
        onSelect={(value) => isGmPlanTab(value) && setTab(value)}
      />

      {tab === "overview" ? (
        <>
          {teamStance ? (
            <TeamSituationCard
              stance={stance}
              onPick={onPickStance}
              banner={banner}
              pastDeadline={pastDeadline}
              tradeHubHref={tradeHubHref}
            />
          ) : null}

          <PlanSnapshotGrid
            tiles={snapshot ?? []}
            analysisHref={leagueId ? `/my-team/${base}?${q}` : undefined}
          />

          {!planGate && (data.season_phase_label || data.team_stance_label || data.headline) ? (
            <section className="glass-surface flex flex-col gap-2 p-4">
              <div className="flex items-center gap-2 flex-wrap">
                {data.season_phase_label ? (
                  <span
                    className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
                    style={{
                      color: "var(--color-information)",
                      background: "var(--color-information-soft)",
                      letterSpacing: "var(--letter-spacing-badge)",
                    }}
                  >
                    {data.season_phase_label}
                  </span>
                ) : null}
                {data.team_stance_label ? (
                  <span
                    className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
                    style={{
                      color: "var(--color-premium)",
                      background: "var(--color-action-soft)",
                      letterSpacing: "var(--letter-spacing-badge)",
                    }}
                  >
                    {data.team_stance_label}
                  </span>
                ) : null}
              </div>
              {data.headline ? (
                <p className="text-base font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {data.headline}
                </p>
              ) : null}
            </section>
          ) : null}

          <section className="flex flex-col gap-2">
            <SectionHeading action={linkAction("View all", tradeHubHref)}>Trade Opportunities</SectionHeading>
            {tradesBlock(tradeItems, 2)}
          </section>

          {myTeam && leagueId && !noRoster ? (
            <section className="flex flex-col gap-2">
              <SectionHeading
                action={
                  <button type="button" onClick={() => setTab("core")} className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
                    View all
                  </button>
                }
              >
                Protected Core
              </SectionHeading>
              {protectedRows.length > 0 ? protectedList(protectedRows.slice(0, 3)) : null}
              {otherRows.length > 0 ? rosterLine : null}
            </section>
          ) : null}
        </>
      ) : null}

      {tab === "trades" ? (
        <>
          <section className="flex flex-col gap-2">
            <SectionHeading action={linkAction("View all", tradeHubHref)}>Trade Opportunities</SectionHeading>
            {tradesBlock(tradeItems)}
          </section>
          {!planGate ? (
            <div className="flex flex-col gap-6">
              {otherAreas.map((area) => (
                <FocusAreaSection key={area.key} area={area} />
              ))}
            </div>
          ) : null}
        </>
      ) : null}

      {tab === "core" ? (
        <section className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <SectionHeading>Protected Core</SectionHeading>
            <InfoTip label="Players you won't trade">
              Mark players you don&apos;t want traded away. This is the same protection the Watching list uses —
              toggling it here or there shows up in both places.
            </InfoTip>
          </div>
          {!myTeam || !leagueId ? null : noRoster ? (
            <EmptyState title="No roster players found for this league." />
          ) : (
            <>
              {protectedRows.length > 0 ? (
                protectedList(protectedRows)
              ) : (
                <EmptyState
                  title="No protected players yet."
                  subtitle="Protect the players you won't trade."
                  actionLabel={showRoster ? undefined : "Show roster"}
                  onAction={() => setShowRoster(true)}
                />
              )}
              {otherRows.length > 0 ? (
                showRoster ? (
                  <>
                    <h3
                      className="text-xs font-bold uppercase pt-2"
                      style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
                    >
                      Rest of Roster
                    </h3>
                    {protectedList(otherRows)}
                  </>
                ) : (
                  rosterLine
                )
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {tab === "watching" ? (
        <section className="flex flex-col gap-2">
          <SectionHeading note="Considering or monitoring; not trade-protected.">Watching</SectionHeading>
          {!rankings || !leagueId ? null : watching.length === 0 ? (
            <EmptyState
              title="Nothing here yet."
              subtitle="Add players you're considering from a player's profile."
              actionLabel="Browse players"
              onAction={() => router.push(`/players/${base}?${q}`)}
            />
          ) : (
            <div className="glass-surface flex flex-col px-3">
              {watching.map((row) => (
                <TargetRowView
                  key={row.target.player_id}
                  row={row}
                  leagueId={leagueId}
                  leagueName={leagueName}
                  onToggleUntouchable={toggleUntouchable}
                  onRemove={removeTarget}
                />
              ))}
            </div>
          )}
        </section>
      ) : null}
      <ValuesCredit />
    </main>
  );
}
