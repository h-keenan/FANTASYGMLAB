"use client";

import { TERMS } from "@/lib/terms";
import { ModuleMore } from "@/components/ui/ModuleMore";
import { FreeLimitNote } from "@/components/FreeLimitNote";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { AccentCard } from "@/components/AccentCard";
import { CompactModule } from "@/components/ui/CompactModule";
import { LinkModule } from "@/components/ui/ModuleTemplates";
import { listSummaryParts } from "@/lib/moduleTemplates";
import { abbreviatePlayerName } from "@/lib/formatPlayerName";
import { tradeIdeaSummaryParts } from "@/lib/tradeIdeaSummary";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import { SectionHeading } from "@/components/SectionHeading";
import { InfoMark } from "@/components/ui/InfoMark";
import { useRouter } from "next/navigation";
import { useUndoableRemoval } from "@/components/ui/UndoToast";
import { useMemo, useState } from "react";
import { GM_PLAN_TABS, type GmPlanTab, isGmPlanTab, TeamSituationCard } from "@/components/GmPlanSections";
import { deadlineBanner, type PlanSnapshotTile } from "@/lib/gmPlanSnapshot";
import type { ReactNode } from "react";
import {
  api,
  type GmPlanFocusArea,
  type GmPlanFocusItem,
  type GmPlanInjuryItem,
  type GmPlanOutlookItem,
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
import { ViewTabs } from "@/components/ui/ViewTabs";
import { StatStrip } from "@/components/StatStrip";
import { OutlookRow, PlanSteps } from "@/components/GmPlanSteps";
import { countPlanNeeds, planHeaderChips } from "@/lib/gmPlanHeader";
import { buildPlanSteps, buildPlanWhy, planFacts, planStatTiles, type PlanStance } from "@/lib/gmPlanPlan";
import { PlayerCard } from "@/components/PlayerCardKit";
import { playerCardFromStarter } from "@/lib/playerCard";
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
import { PageTitle } from "@/components/PageTitle";
import { Collapse, PresenceList } from "@/components/ui/Presence";

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
 * Players" checklist) and Watchlist (the Untouchable/Watching
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

const HEADER_GLYPH = { posture: "franchise", window: "age", needs: "injury" } as const;

function focusItemKey(item: GmPlanFocusItem, index: number): string {
  if ("outlook_topic" in item) return `outlook-${item.outlook_topic}-${index}`;
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
        <div className="flex flex-col gap-2 mt-1">
          {item.injured_players.map((player) => (
            <PlayerCard
              key={player.player_id}
              variant="compact"
              model={playerCardFromStarter({
                player_id: player.player_id,
                name: player.name,
                position: player.position,
                team: player.team,
                tier: player.player_tier,
                injury_label: player.injury_status,
              })}
              identity={{ ...player, sourceLabel: "GM Plan" }}
            />
          ))}
        </div>
      ) : null}
    </FactCard>
  );
}

function TradeOpportunityCard({ item, detailsHref }: { item: GmPlanTradeItem; detailsHref?: string }) {
  const hasAssets = item.send_assets.length > 0 || item.receive_assets.length > 0;
  const injuryDisplay = item.their_player_injury_display || "";
  // One calm stripe: an injured target is named in the text, it does not turn the whole idea red.
  const accent = "var(--color-accent)";
  const gain = item.trade_gain;
  const hasGain = gain !== null && gain !== undefined;
  const theirLabel = injuryDisplay ? `${item.their_player} (${injuryDisplay})` : item.their_player;

  // Collapsed: partner + the same summary the Trade Hub idea cards use; the package and rationale open on tap.
  const summary = tradeIdeaSummaryParts({
    gain: hasGain ? gain! : 0,
    sendNames: item.send_assets.length > 0 ? item.send_assets.map((asset) => abbreviatePlayerName(asset.name)) : [abbreviatePlayerName(item.my_player)],
    receiveNames: item.receive_assets.length > 0 ? item.receive_assets.map((asset) => abbreviatePlayerName(asset.name)) : [abbreviatePlayerName(item.their_player)],
    confidenceLabel: item.trade_confidence_label,
  }).filter((part) => hasGain || part.key !== "gain");

  return (
    <CompactModule
      id={`gmplan.trade.${item.my_player_id}.${item.their_player_id}`}
      title={item.partner_team_name || "Trade idea"}
      parts={summary}
      accent={accent}
      persist={false}
    >
      {hasAssets ? (
        <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
          <ExchangeSide label="You send" dotColor="var(--color-text-muted)" assets={item.send_assets} />
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
          <ButtonLink href={detailsHref} variant="accentOutline" size="sm" className="shrink-0">
            View details
          </ButtonLink>
        ) : null}
      </div>
    </CompactModule>
  );
}

function FocusItem({ item, detailsHref }: { item: GmPlanFocusItem; detailsHref?: (item: GmPlanTradeItem) => string }) {
  if ("outlook_topic" in item) return <OutlookRow item={item as GmPlanOutlookItem} />;
  if ("partner_team_name" in item) return <TradeOpportunityCard item={item} detailsHref={detailsHref?.(item)} />;
  if ("injury_need_positions" in item) return <InjuryExposureFact item={item} />;
  if ("rank" in item) return <RankFact item={item} />;
  if ("wins" in item) return <RecordFact item={item} />;
  if ("playoff_probability" in item) return <PlayoffOddsFact item={item} />;
  return null;
}

function tradeIdeasParts(items: GmPlanTradeItem[], gated: boolean, watchFor?: string) {
  if (gated) return [{ key: "gate", text: "Locked until GM Plan is available for this league", tone: "muted" as const }];
  return listSummaryParts({
    count: items.length,
    noun: "trade idea",
    none: "No trade ideas right now",
    highlights: items.length > 0
      ? items.slice(0, 2).map((item) => `${item.partner_team_name || "Trade idea"}${item.trade_gain != null ? ` ${formatTradeGain(item.trade_gain)}` : ""}`)
      : [watchFor],
  });
}

function coreParts(protectedRows: ProtectRow[], otherRows: ProtectRow[]) {
  return listSummaryParts({
    count: protectedRows.length,
    noun: "protected player",
    none: "No protected players yet",
    highlights: [
      protectedRows.length > 0 ? protectedRows.slice(0, 3).map((row) => abbreviatePlayerName(row.player.name)).join(", ") : null,
      otherRows.length > 0 ? `${otherRows.length} more on your roster` : null,
    ],
  });
}

function focusAreaParts(area: GmPlanFocusArea) {
  if (area.status === "no_signal") return [{ key: "none", text: area.watch_for || "Nothing to flag right now.", tone: "muted" as const }];
  const tradeNames = area.items
    .filter((item): item is GmPlanTradeItem => "partner_team_name" in item)
    .map((item) => item.partner_team_name)
    .filter(Boolean);
  return [
    ...listSummaryParts({ count: area.items.length, noun: "signal", highlights: tradeNames.length > 0 ? [tradeNames.join(", ")] : [area.framing] }),
  ];
}

function FocusAreaSection({ area, detailsHref }: { area: GmPlanFocusArea; detailsHref?: (item: GmPlanTradeItem) => string }) {
  return (
    <CompactModule id={`gmplan.area.${area.key}`} title={area.title} parts={focusAreaParts(area)} defaultOpen={area.status !== "no_signal"}>
      {area.framing ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {area.framing}
        </p>
      ) : null}
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
    </CompactModule>
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
        {player.team || "FA"} · {isProtected ? "Held out of trade ideas" : "Open to trade offers"}
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
                background: "var(--color-accent-strong)",
                color: "var(--color-on-accent)",
                border: "var(--border-width-default) solid var(--color-accent-strong)",
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
  const [moreOpen, setMoreOpen] = useState(false);
  const { target, player } = row;
  const injury = waiverInjuryDisplay(player?.injury_status);
  const contextLine = targetContextLine(row);
  const name = player?.name || `Player ${target.player_id}`;

  return (
    <div className="flex flex-col gap-2 py-3" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
      <div className="flex items-center justify-between gap-3">
        <PlayerIdentity
          identity={{ ...player, player_id: target.player_id, name, sourceLabel: TERMS.watchlist, leagueId, leagueName }}
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
            <PositionBadge position={player.position} rank={player.position_rank} title={`Ranked #${player.position_rank} among all ${player.position}s. Overall, not just this league.`} />
          ) : null}
          <OvrGauge rating={player?.overall_rating ?? null} size="sm" />
        </div>
      </div>
      <div className="flex items-center justify-between gap-2">
        <a
          href={`/player-compare/${encodeURIComponent(leagueId)}?a=${encodeURIComponent(target.player_id)}&name=${encodeURIComponent(leagueName)}`}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-accent)" }}
        >
          Compare
        </a>
        <button
          type="button"
          onClick={() => setMoreOpen((v) => !v)}
          aria-expanded={moreOpen}
          aria-label={`More actions for ${name}`}
          className="px-2 py-1 text-xs font-bold"
          style={{ minHeight: "var(--touch-target-min)", color: "var(--color-text-secondary)" }}
        >
          More {moreOpen ? "⌃" : "⌄"}
        </button>
      </div>
      <Collapse open={moreOpen}>
        <div className="flex items-center gap-2 pb-1">
          <button
            type="button"
            onClick={() => onToggleUntouchable(target.player_id, !target.untouchable)}
            className="px-2 py-1 text-xs font-bold"
            style={
              target.untouchable
                ? { background: "var(--color-accent-strong)", color: "var(--color-on-accent)", border: "var(--border-width-default) solid var(--color-accent-strong)" }
                : { color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }
            }
          >
            {target.untouchable ? "Unmark untouchable" : "Mark untouchable"}
          </button>
          <button
            type="button"
            onClick={() => onRemove(target.player_id)}
            className="px-2 py-1 text-xs font-bold"
            style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            Remove
          </button>
        </div>
      </Collapse>
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
  targetsLimit,
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
  /** The server's Watchlist cap for Free and whether this account is
   * Premium (GET .../gm-targets), for the "Free: X of Y" note. */
  targetsLimit?: { freeLimit?: number; isPremium?: boolean };
}) {
  const router = useRouter();
  const [tab, setTab] = useState<GmPlanTab>(initialTab ?? "overview");
  // The GM orb can pick another GM Plan tab while this page is mounted.
  const [seenInitialTab, setSeenInitialTab] = useState(initialTab);
  if (initialTab !== seenInitialTab) {
    setSeenInitialTab(initialTab);
    if (initialTab) setTab(initialTab);
  }
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

  const targetsNote = (
    <FreeLimitNote
      kind="cap"
      noun={TERMS.watchlist}
      limit={targetsLimit?.freeLimit}
      used={trackedRows.length}
      isPremium={targetsLimit?.isPremium}
    />
  );

  const onPickStance = (value: string) => {
    const next = value as TeamStance;
    if (next === stance || !leagueId) return;
    // Genuine optimistic update, result intentionally discarded — same
    // contract mobile's GmStanceContext.setStance uses.
    const previous = stance;
    setStanceState(next);
    // A failed save reverts, unless the user has already picked something newer.
    void api.setTeamStance(leagueId, next).catch(() => {
      setStanceState((current) => (current === next ? previous : current));
    });
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
          // player to the same tracked-targets table Watchlist reads).
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

  // Removing a target is trivial to put back, so it is instant with an Undo
  // toast; the server call only runs once the undo window closes.
  const { schedule: scheduleRemoval, toast: undoToast } = useUndoableRemoval<GmTarget>({
    message: (row) => `Removed ${byId.get(row.player_id)?.name ?? "target"} from your targets.`,
    commit: async (row) => {
      if (!leagueId) return;
      try {
        await api.removeGmTarget(leagueId, row.player_id);
      } catch {
        setTrackedRows((prev) => (prev.some((r) => r.player_id === row.player_id) ? prev : [row, ...prev]));
      }
    },
    restore: (row) => setTrackedRows((prev) => (prev.some((r) => r.player_id === row.player_id) ? prev : [row, ...prev])),
  });
  const removeTarget = (playerId: string) => {
    if (!leagueId) return;
    const row = trackedRows.find((r) => r.player_id === playerId);
    if (!row) return;
    setTrackedRows((prev) => prev.filter((r) => r.player_id !== playerId));
    scheduleRemoval(row);
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

  const facts = planFacts(snapshot ?? []);
  const statTiles = planStatTiles(snapshot ?? []);
  const stanceKey = (stance || "") as PlanStance;
  const planSteps = buildPlanSteps({
    stance: stanceKey,
    tradeCount: tradeItems.length,
    partners: tradeItems.map((t) => t.partner_team_name).filter(Boolean),
    topConfidence: tradeItems.find((t) => t.trade_confidence_label)?.trade_confidence_label ?? null,
    capital: facts.capital,
    areas: otherAreas.map((a) => ({ key: a.key, title: a.title, framing: a.framing ?? "", count: a.items.length, hasSignal: a.status !== "no_signal" && a.items.length > 0 })),
  });
  const headerChips = planHeaderChips({
    stance: stanceKey,
    deadlineWeek: banner ? banner.week : null,
    pastDeadline,
    needs: countPlanNeeds(data.focus_areas ?? []),
  });
  const planWhy = buildPlanWhy(stanceKey, facts, banner ? banner.week : null);

  // Gate order matches the app (GmPlanScreen): the Pro lock decides first (the server answers Free with the upsell before any
  // work), then a reason notice, then the quiet state. `=== false`, like every other gate.
  const planGate = data.is_premium === false ? (
    <>
      <PremiumUpsellCard
        kicker="GM Plan"
        leagueName={leagueName}
        upsell={data.upsell}
        fallbackTitle="Your season-arc roadmap"
        fallbackBody="GM Plan is a Pro feature: where you stand, your best trade paths, and your roster construction. Framed by your declared Team Situation. Upgrade to Pro to unlock it."
        bare
      />
      <section className="glass-surface flex flex-col gap-1 p-4 premium-glow-card" data-testid="gm-plan-pro-preview">
        <p className="text-sm font-bold" style={{ color: "var(--color-premium)" }}>
          {PLAIN_COPY.gmPlanProTitle}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {PLAIN_COPY.gmPlanProBody}
        </p>
      </section>
    </>
  ) : notice ? (
    <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
      {notice}
    </p>
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
      style={{ minHeight: "var(--touch-target-min)", color: "var(--color-text-secondary)" }}
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
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page="GM Plan" leagueName={leagueName} />
      </header>

      <ViewTabs
        label="GM Plan section"
        value={tab}
        options={GM_PLAN_TABS.map((t) => ({ value: t.value, label: t.label }))}
        onChange={(value) => isGmPlanTab(value) && setTab(value)}
      />

      {tab === "overview" ? (
        <>
          {!planGate ? (
            <StatStrip
              columns={3}
              dense
              items={headerChips.map((chip) => ({ glyph: HEADER_GLYPH[chip.key], label: chip.label, value: chip.value, note: chip.note }))}
            />
          ) : null}

          {teamStance ? (
            <TeamSituationCard
              stance={stance}
              onPick={onPickStance}
              banner={banner}
              pastDeadline={pastDeadline}
              tradeHubHref={tradeHubHref}
            />
          ) : null}

          {statTiles.length > 0 ? (
            <StatStrip
              columns={4}
              dense
              items={statTiles.map((t) => ({ glyph: t.glyph, label: t.label, value: t.value, note: t.note }))}
            />
          ) : null}

          {planGate ? (
            <CompactModule id="gmplan.overview.trades" title="Trade ideas" parts={tradeIdeasParts(tradeItems, true)} defaultOpen>
              {planGate}
            </CompactModule>
          ) : (
            <PlanSteps
              steps={planSteps}
              tradeItems={tradeItems}
              detailsHref={detailsHref}
              tradeEmpty={tradesBlock([])}
              renderArea={(key) => {
                const area = otherAreas.find((x) => x.key === key);
                return area ? (
                  <div className="flex flex-col gap-3">
                    {area.items.map((item, index) => (
                      <FocusItem key={focusItemKey(item, index)} item={item} detailsHref={detailsHref} />
                    ))}
                  </div>
                ) : null;
              }}
            />
          )}

          {!planGate && planWhy ? (
            <CompactModule id="gmplan.overview.why" persist={false} title={planWhy.title} parts={[{ key: "w", text: planWhy.headline }]}>
              <ul className="list-disc pl-4 text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {planWhy.bullets.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              {leagueId ? <ModuleMore href={`/my-team/${base}?${q}`}>Full analysis</ModuleMore> : null}
            </CompactModule>
          ) : null}

          {myTeam && leagueId && !noRoster ? (
            <CompactModule
              id="gmplan.overview.core"
              title="Protected Core"
              parts={coreParts(protectedRows, otherRows)}
            >
              {protectedRows.length > 0 ? protectedList(protectedRows.slice(0, 3)) : null}
              {otherRows.length > 0 ? rosterLine : null}
              <ModuleMore onClick={() => setTab("core")}>View protected core</ModuleMore>
            </CompactModule>
          ) : null}

          {leagueId ? (
            <LinkModule
              title="Season outlook"
              href={`/fantasy-sim/${base}?${q}`}
              parts={[
                { key: "a", text: "Season forecast", strong: true },
                { key: "b", text: "playoff odds, record, title odds, what swings them" },
                { key: "c", text: "Pro", tone: "action" },
              ]}
            />
          ) : null}
        </>
      ) : null}

      {tab === "trades" ? (
        <>
          <CompactModule
            id="gmplan.trades.ideas"
            title="Trade ideas"
            parts={tradeIdeasParts(tradeItems, Boolean(planGate), tradeArea?.watch_for)}
            defaultOpen
          >
            {tradesBlock(tradeItems)}
            {tradeHubHref ? <ModuleMore href={tradeHubHref}>View all trade ideas</ModuleMore> : null}
          </CompactModule>
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
          <SectionHeading
            help={
              <InfoMark
                label="Protected Core"
                lines={["Mark players you don't want traded away. This is the same protection the Watchlist uses. Toggling it here or there shows up in both places."]}
              />
            }
          >
            Protected Core
          </SectionHeading>
          {targetsNote}
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
          <SectionHeading note="Considering or monitoring; not trade-protected.">{TERMS.watchlist}</SectionHeading>
          {targetsNote}
          {!rankings || !leagueId ? null : watching.length === 0 ? (
            <EmptyState
              title="Nothing here yet."
              subtitle="Add players you're considering from a player's profile."
              actionLabel="Browse players"
              onAction={() => router.push(`/players/${base}?${q}`)}
            />
          ) : (
            <div className="glass-surface flex flex-col px-3">
              {/* A removed target collapses out in place (and an Undo grows it back) instead of popping. */}
              <PresenceList
                items={watching}
                getKey={(row) => row.target.player_id}
                render={(row) => (
                  <TargetRowView
                    row={row}
                    leagueId={leagueId}
                    leagueName={leagueName}
                    onToggleUntouchable={toggleUntouchable}
                    onRemove={removeTarget}
                  />
                )}
              />
            </div>
          )}
        </section>
      ) : null}
      <ValuesCredit />
      {undoToast}
    </main>
  );
}
