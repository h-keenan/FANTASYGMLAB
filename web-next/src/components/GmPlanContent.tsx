"use client";

import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import {
  api,
  TEAM_STANCE_OPTIONS,
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
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { formatTradeGain } from "@/lib/tradeHubPresentation";
import { gmPlanReasonMessage } from "@/lib/gmPlanPresentation";
import { buildProtectRows, splitProtectRows, type ProtectRow } from "@/lib/teamStancePresentation";
import { groupTargetRows, targetContextLine, type GmTargetRow } from "@/lib/gmTargetsPresentation";
import { formatWaiverScore, waiverInjuryDisplay } from "@/lib/waiversPresentation";
import { injuryTone } from "@/lib/myTeamPresentation";

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
    <article
      className="flex flex-col gap-1 p-3"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `3px solid ${accent}`,
      }}
    >
      {children}
    </article>
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
                <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                  {player.name}
                </span>
                {player.team ? (
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {player.team}
                  </span>
                ) : null}
              </PlayerIdentityTrigger>
              {player.injury_status ? (
                <span className="ml-auto text-xs font-bold" style={{ color: "var(--color-danger)" }}>
                  {player.injury_status}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </FactCard>
  );
}

function TradeOpportunityCard({ item }: { item: GmPlanTradeItem }) {
  const hasAssets = item.send_assets.length > 0 || item.receive_assets.length > 0;
  const injuryDisplay = item.their_player_injury_display || "";
  const accent = injuryDisplay ? "var(--color-danger)" : "var(--color-accent)";
  const gain = item.trade_gain;
  const hasGain = gain !== null && gain !== undefined;
  const gainColor = hasGain && gain! > 0 ? "var(--color-success)" : hasGain && gain! < 0 ? "var(--color-danger)" : "var(--color-text-secondary)";
  const theirLabel = injuryDisplay ? `${item.their_player} (${injuryDisplay})` : item.their_player;

  return (
    <article
      className="flex flex-col gap-3 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `3px solid ${accent}`,
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-base font-extrabold truncate" style={{ color: "var(--color-text-primary)" }}>
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

      {item.rationale || item.trade_confidence_label ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {item.rationale || item.trade_confidence_label}
        </p>
      ) : null}
    </article>
  );
}

function FocusItem({ item }: { item: GmPlanFocusItem }) {
  if ("partner_team_name" in item) return <TradeOpportunityCard item={item} />;
  if ("injury_need_positions" in item) return <InjuryExposureFact item={item} />;
  if ("rank" in item) return <RankFact item={item} />;
  if ("wins" in item) return <RecordFact item={item} />;
  if ("playoff_probability" in item) return <PlayoffOddsFact item={item} />;
  return null;
}

function FocusAreaSection({ area }: { area: GmPlanFocusArea }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 style={{ font: "var(--type-section-title)" }}>{area.title}</h2>
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
            <FocusItem key={focusItemKey(item, index)} item={item} />
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
  const tone = injuryTone(player.injury_label);

  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "Team Situation" }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <OvrGauge rating={player.overall_rating} size="sm" />
        <div className="flex-1 flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {player.name || "Unknown player"}
            </span>
            {player.injury_label ? (
              <span
                className="px-1 text-xs font-bold uppercase"
                style={{
                  color:
                    tone === "danger" ? "var(--color-danger)" : tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)",
                }}
              >
                {player.injury_label}
              </span>
            ) : null}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {player.team || "FA"}
          </span>
        </div>
      </PlayerIdentityTrigger>
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
        <PlayerIdentityTrigger
          identity={{ ...player, player_id: target.player_id, name, sourceLabel: "GM Targets", leagueId, leagueName }}
          className="flex items-center gap-3 min-w-0"
        >
          <PositionBadge position={player?.position} />
          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                {name}
              </span>
              {injury.label ? (
                <span
                  className="text-xs font-bold uppercase"
                  style={{
                    color:
                      injury.tone === "danger"
                        ? "var(--color-danger)"
                        : injury.tone === "warning"
                          ? "var(--color-warning)"
                          : "var(--color-text-muted)",
                  }}
                >
                  {injury.label}
                </span>
              ) : null}
            </div>
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {player?.team || "—"}
              {contextLine ? ` · ${contextLine}` : ""}
            </span>
          </div>
        </PlayerIdentityTrigger>
        <div className="flex items-center gap-2 shrink-0">
          {player?.score !== null && player?.score !== undefined ? (
            <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
              {formatWaiverScore(player.score)}
            </span>
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
}) {
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

  const selectedStanceOption = TEAM_STANCE_OPTIONS.find((option) => option.value === stance);
  const noRoster = protectRows.length === 0;

  const notice = data.reason ? gmPlanReasonMessage(data.reason) : null;
  const quiet = data.quiet || !data.focus_areas || data.focus_areas.length === 0;

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          GM Plan
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Your season-arc roadmap, declared stance, and protected/watched players — all in one place.
        </p>
      </header>

      {teamStance ? (
        <section className="flex flex-col gap-2">
          <h2 style={{ font: "var(--type-section-title)" }}>Team Situation</h2>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Tell us how you see this team right now. We&apos;ll lean trade-idea language toward that stance, and use
            it to shape your trade and lineup value adjustments too.
          </p>
          <PillRow
            options={TEAM_STANCE_OPTIONS.map((option) => ({ label: option.label, value: option.value }))}
            active={stance}
            onSelect={onPickStance}
          />
          {selectedStanceOption ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {selectedStanceOption.description}
            </p>
          ) : null}
        </section>
      ) : null}

      {notice ? (
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      ) : !data.is_premium ? (
        <PremiumUpsellCard
          kicker="GM Plan"
          upsell={data.upsell}
          fallbackTitle="Your season-arc roadmap"
          fallbackBody="GM Plan is a Premium feature: where you stand, your best trade paths, and your roster construction — framed by your declared Team Situation. Upgrade to Premium to unlock it."
          bare
        />
      ) : quiet ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          We don&apos;t have enough to build a GM Plan for this league yet.
        </p>
      ) : (
        <>
          <section
            className="flex flex-col gap-2 p-4"
            style={{
              background: "var(--color-surface-secondary)",
              border: "var(--border-width-default) solid var(--color-border)",
              boxShadow: "var(--shadow-card)",
            }}
          >
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

          <div className="flex flex-col gap-6">
            {data.focus_areas.map((area) => (
              <FocusAreaSection key={area.key} area={area} />
            ))}
          </div>
        </>
      )}

      {myTeam && leagueId ? (
        <section className="flex flex-col gap-2">
          <h2 style={{ font: "var(--type-section-title)" }}>Protected Players</h2>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Mark players you don&apos;t want traded away. This is the same protection the Watching list below uses
            — toggling it here or there shows up in both places.
          </p>

          {noRoster ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              No roster players found for this league.
            </p>
          ) : (
            <div
              className="flex flex-col px-3"
              style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
            >
              {protectedRows.map((row) => (
                <ProtectPlayerRow
                  key={row.player.player_id}
                  row={row}
                  busy={busyPlayerId === row.player.player_id}
                  onToggle={onToggleProtect}
                />
              ))}
              {protectedRows.length > 0 && otherRows.length > 0 ? (
                <h3
                  className="text-xs font-bold uppercase pt-3"
                  style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
                >
                  Rest of Roster
                </h3>
              ) : null}
              {otherRows.map((row) => (
                <ProtectPlayerRow
                  key={row.player.player_id}
                  row={row}
                  busy={busyPlayerId === row.player.player_id}
                  onToggle={onToggleProtect}
                />
              ))}
            </div>
          )}
        </section>
      ) : null}

      {rankings && leagueId ? (
        <section className="flex flex-col gap-2">
          <h2 style={{ font: "var(--type-section-title)" }}>Watching</h2>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Players you&apos;re considering buying, selling, adding, or monitoring — not trade-protected.
          </p>
          {watching.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Nothing here yet. Add players you&apos;re considering from a player&apos;s profile to start watching
              them.
            </p>
          ) : (
            <div
              className="flex flex-col px-3"
              style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
            >
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
    </main>
  );
}
