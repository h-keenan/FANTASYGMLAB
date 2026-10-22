import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { api, type WaiverPlayer, type WaiverPriorityAdd, type WaiversResponse } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { HighlightTarget } from "@/components/HighlightTarget";
import { InfoTip } from "@/components/InfoTip";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PlayerMetaLine } from "@/components/PlayerInjuryBadge";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { useExperienceCopy } from "@/context/ExperienceLevelContext";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import {
  confidenceColor,
  faabIsBid,
  faabRangeText,
  filterByRecommendation,
  formatWaiverScore,
  freeAgentContextLine,
  priorityNeedNote,
  trendingAddLabel,
  waiverInjuryDisplay,
  waiverReasonChips,
  waiversReasonMessage,
  type WaiverRecFilter,
} from "@/lib/waiversPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/**
 * Waivers page, laid out as: compact header + 3-stat strip, a
 * Recommended | Explore | Watchlist tab row, and (Recommended) the Top
 * Waiver Target card, "More recommended adds" with All/Add/Stash/Watch
 * filter pills, a Position Snapshot and the Stash / depth / FAAB tile rows.
 * Reads the same GET .../waivers endpoint mobile's WaiversScreen.tsx calls —
 * no ranking, confidence or FAAB logic here, only presentation. Reason
 * chips come only from already-computed signals (waiverReasonChips).
 *
 * The Watchlist tab is the user's GM Targets (getGmTargets) filtered to
 * players who are currently free agents in this league. There is no in-app
 * claim/add API, so the disclosure below is kept (short line + ⓘ).
 */

const DISCLOSURE_TEXT =
  "FantasyDesk does not submit waiver claims for you — place the claim in your Sleeper league once you've decided.";

type WaiverTab = "recommended" | "explore" | "watchlist";

const TAB_OPTIONS: { label: string; value: WaiverTab }[] = [
  { label: "Recommended", value: "recommended" },
  { label: "Explore", value: "explore" },
  { label: "Watchlist", value: "watchlist" },
];

const REC_FILTER_OPTIONS: { label: string; value: WaiverRecFilter }[] = [
  { label: "All", value: "all" },
  { label: "Add", value: "Add" },
  { label: "Stash", value: "Stash" },
  { label: "Watch", value: "Watch" },
];

function WaiverIdentity({ player, avatarSize = 40 }: { player: WaiverPlayer; avatarSize?: number }) {
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = freeAgentContextLine(player);
  const trending = trendingAddLabel(player);
  return (
    <PlayerIdentity
      identity={{ ...player, sourceLabel: "Waivers" }}
      playerId={player.player_id}
      name={player.name || "Unknown player"}
      position={player.position}
      tier={player.tier}
      injuryStatus={injury.label}
      avatarSize={avatarSize}
      after={
        trending ? (
          <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            {trending}
          </span>
        ) : null
      }
    >
      {player.team || "FA"}
      {contextLine ? ` · ${contextLine}` : ""}
    </PlayerIdentity>
  );
}

function StatStrip({ items }: { items: { label: string; value: string }[] }) {
  return (
    <div
      className="glass-surface flex items-stretch self-start"
      aria-label="Waiver summary"
      style={{ border: "var(--border-width-default) solid var(--color-border)" }}
    >
      {items.map((item, index) => (
        <div
          key={item.label}
          className="flex flex-col items-center justify-center px-3 py-1.5"
          style={index > 0 ? { borderLeft: "var(--border-width-default) solid var(--color-border)" } : undefined}
        >
          <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
            {item.value}
          </span>
          <span className="text-[0.625rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

function ReasonChips({ chips }: { chips: string[] }) {
  if (chips.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {chips.map((chip) => (
        <ToneBadge key={chip} label={chip} color="var(--color-accent)" />
      ))}
    </div>
  );
}

function FaabRange({ player, prominent = false }: { player: WaiverPriorityAdd; prominent?: boolean }) {
  const { primary, secondary } = faabRangeText(player.faab);
  const isBid = faabIsBid(player.faab);
  return (
    <div className="flex flex-col items-end gap-0.5" title={player.faab?.why || undefined}>
      <span
        className={prominent ? "text-lg font-extrabold" : "text-sm font-bold"}
        style={{ color: isBid ? "var(--color-success)" : "var(--color-text-secondary)" }}
      >
        {primary}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {secondary}
      </span>
    </div>
  );
}

function ValueWithRing({ player, big = false }: { player: WaiverPlayer; big?: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex flex-col items-start gap-0.5">
        <span className="text-[0.625rem] uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
          Value
        </span>
        <span
          className={big ? "text-2xl font-black" : "text-base font-extrabold"}
          style={{ color: "var(--color-accent)" }}
        >
          {formatWaiverScore(player.score)}
        </span>
      </div>
      <OvrGauge rating={player.overall_rating} size={big ? "md" : "sm"} />
    </div>
  );
}

function ViewDetailsButton({ player }: { player: WaiverPlayer }) {
  const { openPlayer } = usePlayerQuickView();
  return (
    <button
      type="button"
      onClick={() => openPlayer({ ...player, sourceLabel: "Waivers" })}
      className="inline-flex items-center gap-1 px-3 text-xs font-bold shrink-0"
      style={{
        color: "var(--color-accent)",
        border: "1px solid var(--color-accent)",
        background: "transparent",
        minHeight: "2.25rem",
      }}
    >
      View details <span aria-hidden="true">→</span>
    </button>
  );
}

function TopWaiverTargetCard({ player }: { player: WaiverPriorityAdd }) {
  return (
    <article className="glass-surface flex flex-col gap-3 p-4" style={{ borderColor: "var(--color-premium)" }}>
      <div className="flex items-center justify-between gap-2">
        <span
          className="text-xs font-extrabold uppercase"
          style={{ color: "var(--color-premium)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          ★ Top Waiver Target
        </span>
        <ToneBadge label={`${player.recommendation_label} · #1`} color="var(--color-premium)" />
      </div>
      <WaiverIdentity player={player} avatarSize={56} />
      <ReasonChips chips={waiverReasonChips(player)} />
      <div
        className="flex items-center justify-between gap-3 pt-3"
        style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}
      >
        <ValueWithRing player={player} big />
        <FaabRange player={player} prominent />
      </div>
      {player.faab?.why ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <span className="font-bold">Why: </span>
          {player.faab.why}
        </p>
      ) : null}
      <BeginnerHelp term="waiverValue" />
      <div className="flex items-center justify-between gap-3">
        {player.confidence_label ? (
          <ConfidenceMeter label="Confidence" value={player.confidence_label} color={confidenceColor(player.confidence_label)} />
        ) : (
          <span />
        )}
        <ViewDetailsButton player={player} />
      </div>
      {player.confidence_label ? <BeginnerHelp term="waiverConfidence" /> : null}
    </article>
  );
}

function RecommendedRow({ player, rank, showDivider }: { player: WaiverPriorityAdd; rank: number; showDivider: boolean }) {
  const { openPlayer } = usePlayerQuickView();
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = freeAgentContextLine(player);
  return (
    <button
      type="button"
      onClick={() => openPlayer({ ...player, sourceLabel: "Waivers" })}
      aria-label={`Open ${player.name || "player"}`}
      className="appearance-none bg-transparent border-0 p-0 m-0 text-left cursor-pointer w-full flex flex-col gap-1.5 py-2.5"
      style={showDivider ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      {/* Name line first at full width so names never truncate; value, ring,
          bid and the chevron share the second line. */}
      <span className="flex items-center gap-3 min-w-0 w-full">
        <span className="text-xs font-bold w-5 text-center shrink-0" style={{ color: "var(--color-text-muted)" }}>
          {rank}
        </span>
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <span className="flex flex-col min-w-0 flex-1">
          <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
            {player.name || "Unknown player"}
          </span>
          <PlayerMetaLine injuryStatus={injury.label}>
            {player.team || "FA"}
            {contextLine ? ` · ${contextLine}` : ""}
          </PlayerMetaLine>
        </span>
      </span>
      <ReasonChips chips={waiverReasonChips(player)} />
      <span className="flex items-center gap-3 pl-8 w-full">
        <ValueWithRing player={player} />
        <span className="ml-auto">
          <FaabRange player={player} />
        </span>
        <span aria-hidden="true" style={{ color: "var(--color-text-muted)" }}>
          ›
        </span>
      </span>
    </button>
  );
}

function FreeAgentRow({ player }: { player: WaiverPlayer }) {
  return (
    <div
      className="flex flex-col gap-1 py-2"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        opacity: player.stale_free_agent ? 0.55 : 1,
      }}
    >
      <WaiverIdentity player={player} />
      <div className="flex items-center gap-3 pl-1">
        <ValueStat value={formatWaiverScore(player.score)} align="left" />
        <OvrGauge rating={player.overall_rating} size="sm" />
        {player.position_rank ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
            title={`Ranked #${player.position_rank} among all ${player.position}s — overall, not just free agents.`}
          >
            {player.position}
            {player.position_rank}
          </span>
        ) : null}
      </div>
    </div>
  );
}

/** Small tile used by Position Snapshot and the Stash / depth / FAAB rows. */
function PlayerTile({ position, player, note }: { position: string; player: WaiverPlayer; note?: string }) {
  return (
    <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "Waivers" }} className="min-w-[7.5rem]">
      <div className="glass-surface flex flex-col items-center gap-1 p-3">
        <PositionBadge position={position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <OvrGauge rating={player.overall_rating} size="md" />
        <span className="text-sm font-extrabold truncate max-w-full" style={{ color: "var(--color-text-primary)" }}>
          {player.name || "Unknown"}
        </span>
        <div className="flex flex-col items-center gap-0.5">
          <ValueStat value={formatWaiverScore(player.score)} align="center" />
          {note ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {note}
            </span>
          ) : null}
        </div>
      </div>
    </PlayerIdentityTrigger>
  );
}

function TileRow({ title, players, highlightPlayerId }: { title: string; players: WaiverPlayer[]; highlightPlayerId?: string }) {
  if (players.length === 0) return null;
  return (
    <section className="flex flex-col gap-2">
      <SectionHeading>{title}</SectionHeading>
      <div className="flex gap-3 overflow-x-auto pb-1">
        {players.map((player) => (
          <HighlightTarget key={player.player_id} active={player.player_id === highlightPlayerId}>
            <PlayerTile position={player.position ?? ""} player={player} note={player.team ?? undefined} />
          </HighlightTarget>
        ))}
      </div>
    </section>
  );
}

// Skill positions first; K only as its own tile, last.
const BEST_AVAILABLE_POSITIONS = ["QB", "RB", "WR", "TE", "K"];
const FREE_AGENT_LIST_PREVIEW_ROWS = 60;
const FILTER_POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];

export function WaiversContent({
  leagueName,
  data,
  highlightPlayerId,
  leagueId,
}: {
  leagueName: string;
  data: WaiversResponse;
  /** See components/HighlightTarget.tsx — a GM Plan/Dashboard waiver tile's specific
   * player, threaded through as ?playerId= (gamePlanTileHref). */
  highlightPlayerId?: string;
  /** Needed only for the Watchlist tab (GM Targets lookup). */
  leagueId?: string;
}) {
  // A GM Plan/Dashboard deep link to a player who isn't on the Recommended
  // tab opens Explore so the highlighted free agent is visible.
  const [tab, setTab] = useState<WaiverTab>(() => {
    if (!highlightPlayerId) return "recommended";
    const onRecommended = [
      ...data.priority_adds,
      ...data.stash_candidates,
      ...data.watchlist_candidates,
      ...data.faab_targets,
    ].some((p) => p.player_id === highlightPlayerId);
    return onRecommended ? "recommended" : "explore";
  });
  const [recFilter, setRecFilter] = useState<WaiverRecFilter>("all");
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");
  const [targetIds, setTargetIds] = useState<string[] | null>(null);
  const [targetsFailed, setTargetsFailed] = useState(false);
  const copy = useExperienceCopy();

  const notice = data.reason ? waiversReasonMessage(data.reason) : null;

  // GM Targets are only fetched when the Watchlist tab is first opened.
  useEffect(() => {
    if (tab !== "watchlist" || targetIds !== null || !leagueId) return;
    let cancelled = false;
    api
      .getGmTargets(leagueId)
      .then((result) => {
        if (!cancelled) setTargetIds(result.targets.map((t) => t.player_id));
      })
      .catch(() => {
        if (!cancelled) setTargetsFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, targetIds, leagueId]);

  const priorityAdds = data.priority_adds;
  const topPriority = priorityAdds[0] ?? null;
  const secondaryPriority = priorityAdds.length > 1 ? priorityAdds.slice(1) : [];
  const visibleSecondary = filterByRecommendation(secondaryPriority, recFilter);

  const bestAvailable = useMemo(() => {
    const activeAgents = data.players.filter((p) => !p.stale_free_agent && (p.score ?? 0) > 0);
    const source = activeAgents.length > 0 ? activeAgents : data.players;
    return BEST_AVAILABLE_POSITIONS.map((pos) => {
      const group = source.filter((p) => p.position === pos);
      if (group.length === 0) return null;
      const top = [...group].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
      return { position: pos, player: top, count: group.length };
    }).filter((entry): entry is { position: string; player: WaiverPlayer; count: number } => entry !== null);
  }, [data.players]);

  const filteredFreeAgents = useMemo(() => {
    const query = search.trim().toLowerCase();
    return data.players
      .filter((p) => position === "ALL" || p.position === position)
      .filter((p) => !query || (p.name ?? "").toLowerCase().includes(query));
  }, [data.players, position, search]);

  const visibleFreeAgents = useMemo(() => {
    const base = filteredFreeAgents.slice(0, FREE_AGENT_LIST_PREVIEW_ROWS);
    // A GM Plan tile's named player can be ranked below this list's preview
    // cutoff — guarantee it still surfaces (same fail-open principle).
    if (!highlightPlayerId || base.some((p) => p.player_id === highlightPlayerId)) return base;
    const target = filteredFreeAgents.find((p) => p.player_id === highlightPlayerId);
    return target ? [target, ...base] : base;
  }, [filteredFreeAgents, highlightPlayerId]);

  const watchlistPlayers = useMemo(() => {
    if (!targetIds) return [];
    const ids = new Set(targetIds);
    return data.players.filter((p) => ids.has(p.player_id));
  }, [data.players, targetIds]);

  if (notice) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const faabItem =
    data.faab_enabled === false
      ? { label: "Waivers", value: data.waiver_mode === "reverse_standings" ? "Reverse" : "Rolling" }
      : { label: "FAAB", value: data.faab_remaining != null ? `$${data.faab_remaining}` : "—" };
  const stats = [
    { label: "Available", value: String(data.available_count ?? data.players.length) },
    faabItem,
    { label: "Team need", value: data.needed_positions.length > 0 ? data.needed_positions.join("/") : "None" },
  ];

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {leagueName}
          </span>
          <h1 style={{ font: "var(--font-page-title)" }}>Waivers</h1>
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            Ranked by fit for your team.
          </p>
          <BeginnerHelp term="waiversIntro" />
        </div>
        <StatStrip items={stats} />
      </header>
      {copy.isBeginner ? <BeginnerHelp text={copy.help("averageWireValue")} /> : null}

      <PillRow options={TAB_OPTIONS} active={tab} onSelect={(value) => setTab(value as WaiverTab)} fullWidth />

      {tab === "recommended" ? (
        <>
          <section className="flex flex-col gap-3" aria-labelledby="priority-adds-heading">
            <span id="priority-adds-heading" className="sr-only">
              Priority Adds
            </span>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {priorityNeedNote(data.needed_positions)}
            </p>
            <InfoTip label="How Priority Adds rank">
              Need fits and injury cover rank first, then value. {DISCLOSURE_TEXT}
            </InfoTip>
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Place claims in Sleeper — we don&apos;t submit them.
            </p>
            {data.injury_positions && data.injury_positions.length > 0 ? (
              <p className="text-xs" style={{ color: "var(--color-warning)" }}>
                Injury cover: {data.injury_positions.join(" / ")} ({data.injured_starters ?? 0} injured starter
                {data.injured_starters === 1 ? "" : "s"}).
              </p>
            ) : null}

            {!topPriority ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                No waiver option clearly helps right now. See Position Snapshot below.
              </p>
            ) : (
              <HighlightTarget active={topPriority.player_id === highlightPlayerId}>
                <TopWaiverTargetCard player={topPriority} />
              </HighlightTarget>
            )}
          </section>

          {secondaryPriority.length > 0 ? (
            <section className="flex flex-col gap-3" aria-labelledby="more-adds-heading">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <SectionHeading>
                  <span id="more-adds-heading">More recommended adds</span>
                </SectionHeading>
                <PillRow
                  options={REC_FILTER_OPTIONS}
                  active={recFilter}
                  onSelect={(value) => setRecFilter(value as WaiverRecFilter)}
                />
              </div>
              {visibleSecondary.length === 0 ? (
                <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                  None in this group.
                </p>
              ) : (
                <div className="glass-surface flex flex-col px-3">
                  {visibleSecondary.map((player, index) => (
                    <HighlightTarget key={player.player_id} active={player.player_id === highlightPlayerId}>
                      <RecommendedRow player={player} rank={index + 2} showDivider={index < visibleSecondary.length - 1} />
                    </HighlightTarget>
                  ))}
                </div>
              )}
            </section>
          ) : null}

          {bestAvailable.length > 0 ? (
            <section className="flex flex-col gap-2" aria-labelledby="snapshot-heading">
              <SectionHeading>
                <span id="snapshot-heading">Position Snapshot</span>
              </SectionHeading>
              <div className="flex gap-3 overflow-x-auto pb-1">
                {bestAvailable.map(({ position: pos, player, count }) => (
                  <PlayerTile key={pos} position={pos} player={player} note={`${count} active`} />
                ))}
              </div>
            </section>
          ) : null}

          {!data.entitlement.is_premium ? (
            <div
              className="p-4 flex flex-col gap-2"
              style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
            >
              <p className="text-sm font-bold">Full waiver board and FAAB shortlist</p>
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                Priority Adds stay free. Premium adds stashes, depth and FAAB.
              </p>
              <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
                Upgrade →
              </Link>
            </div>
          ) : (
            <>
              <InfoTip label="Stash, depth and FAAB: ranked by raw value">
                Includes positions you don&apos;t currently need, so a higher number here can still rank below a lower one
                in Priority Adds above. Kickers and defenses are never stash candidates.
              </InfoTip>
              <TileRow title="Top Stash Candidates" players={data.stash_candidates} highlightPlayerId={highlightPlayerId} />
              <TileRow title="Bench Depth" players={data.watchlist_candidates} highlightPlayerId={highlightPlayerId} />
              <TileRow title="FAAB Shortlist" players={data.faab_targets} highlightPlayerId={highlightPlayerId} />
            </>
          )}
        </>
      ) : null}

      {tab === "explore" ? (
        <section className="flex flex-col gap-3" aria-labelledby="all-free-agents-heading">
          <SectionHeading>
            <span id="all-free-agents-heading">All Free Agents</span>
          </SectionHeading>
          <InfoTip label="Unrostered players in this league">
            Showing the best available players not currently on a roster in this league. Stale or retired profiles are
            pushed to the bottom.
          </InfoTip>
          <div className="flex flex-wrap gap-2">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search free agents"
              className="filter-input px-3 py-2 text-sm flex-1 min-w-[10rem]"
            />
            <select
              value={position}
              onChange={(event) => setPosition(event.target.value)}
              className="filter-select px-3 py-2 text-sm"
            >
              {FILTER_POSITIONS.map((pos) => (
                <option key={pos} value={pos}>
                  {pos}
                </option>
              ))}
            </select>
          </div>
          {visibleFreeAgents.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              No free agents match.
            </p>
          ) : (
            <>
              <div className="glass-surface flex flex-col px-3">
                {visibleFreeAgents.map((player) => (
                  <HighlightTarget key={player.player_id} active={player.player_id === highlightPlayerId}>
                    <FreeAgentRow player={player} />
                  </HighlightTarget>
                ))}
              </div>
              {filteredFreeAgents.length > visibleFreeAgents.length ? (
                <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Showing top {visibleFreeAgents.length} of {filteredFreeAgents.length} available players.
                </p>
              ) : null}
            </>
          )}
        </section>
      ) : null}

      {tab === "watchlist" ? (
        <section className="flex flex-col gap-3" aria-labelledby="watchlist-heading">
          <SectionHeading>
            <span id="watchlist-heading">Your GM Targets on the wire</span>
          </SectionHeading>
          {targetsFailed || !leagueId ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Couldn&apos;t load your GM Targets.
            </p>
          ) : targetIds === null ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading…
            </p>
          ) : watchlistPlayers.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              None of your GM Targets are free agents right now.
            </p>
          ) : (
            <div className="glass-surface flex flex-col px-3">
              {watchlistPlayers.map((player) => (
                <FreeAgentRow key={player.player_id} player={player} />
              ))}
            </div>
          )}
          {leagueId ? (
            <Link
              href={`/gm-targets/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
              className="text-sm font-bold self-start"
              style={{ color: "var(--color-accent)" }}
            >
              Manage GM Targets →
            </Link>
          ) : null}
        </section>
      ) : null}
      <ValuesCredit />
    </main>
  );
}
