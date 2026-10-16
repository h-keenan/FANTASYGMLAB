import { useMemo, useState, type ReactNode } from "react";

import type { WaiverPlayer, WaiverPriorityAdd, WaiversResponse } from "@/lib/api";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { SnapshotTile } from "@/components/SnapshotTile";
import { streamlitPageUrl } from "@/lib/streamlitLink";
import {
  confidenceColor,
  faabRangeText,
  formatWaiverScore,
  freeAgentContextLine,
  priorityNeedNote,
  recommendationToneColor,
  trendingAddLabel,
  waiverInjuryDisplay,
  waiversReasonMessage,
} from "@/lib/waiversPresentation";

/**
 * Ports modules/waivers_ui.py's render_waiver_workspace_sections for
 * Revision 4 — Priority Adds (the top recommendation plus the secondary
 * compact list), the Premium-gated secondary board (Stash Candidates /
 * Watchlist Depth / FAAB Shortlist), Waiver Snapshot (Best Available by
 * position), and a searchable/filterable All Free Agents list. Reads from
 * the exact same GET .../waivers endpoint mobile's WaiversScreen.tsx
 * already calls (extended this revision only to expose
 * injured_starters/injury_positions, both already computed server-side —
 * see that endpoint's docstring) — no duplicated ranking, confidence, or
 * FAAB-math logic here, only presentation.
 *
 * Deliberately NOT covered, matching the quick-view/full-detail split this
 * app already draws elsewhere: the collapsed "Detailed Table View" export
 * (a power-user CSV-style dump of every field, Streamlit-only for now —
 * this page's own All Free Agents list already covers normal browsing),
 * and the FAAB Helper calculator (a standalone what-if tool, not part of
 * reading a recommendation). There is no in-app waiver-claim/add API
 * (deliberately — see mobile's own PR #747 precedent): the disclosure
 * below is preserved verbatim for that reason.
 */

const DISCLOSURE_TEXT =
  "FantasyGM Lab does not submit waiver claims for you — place the claim in your Sleeper league once you've decided.";

function WaiverIdentity({ player }: { player: WaiverPlayer }) {
  const injury = waiverInjuryDisplay(player.injury_status);
  const contextLine = freeAgentContextLine(player);
  const trending = trendingAddLabel(player);
  return (
    <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "Waivers" }} className="flex items-center gap-3 min-w-0">
      <PositionBadge position={player.position} />
      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
            {player.name || "Unknown player"}
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
          {player.team || "FA"}
          {contextLine ? ` · ${contextLine}` : ""}
        </span>
        {trending ? (
          <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            {trending}
          </span>
        ) : null}
      </div>
    </PlayerIdentityTrigger>
  );
}

function RecommendationPill({ label, tone }: { label: string; tone: string }) {
  const color = recommendationToneColor(tone);
  return (
    <span
      className="px-1.5 py-0.5 text-xs font-extrabold uppercase shrink-0"
      style={{ background: `color-mix(in srgb, ${color} 15%, transparent)`, color, border: `1px solid ${color}` }}
    >
      {label}
    </span>
  );
}

function FaabRange({ player, prominent = false }: { player: WaiverPriorityAdd; prominent?: boolean }) {
  const { primary, secondary } = faabRangeText(player.faab);
  return (
    <div className="flex flex-col items-end gap-0.5">
      <span
        className={prominent ? "text-lg font-extrabold" : "text-sm font-bold"}
        style={{ color: "var(--color-success)" }}
      >
        {primary}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {secondary}
      </span>
    </div>
  );
}

function PriorityAddPrimaryCard({ player }: { player: WaiverPriorityAdd }) {
  return (
    <article
      className="flex flex-col gap-3 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-premium)",
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-xs font-extrabold uppercase"
          style={{ color: "var(--color-premium)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          {player.recommendation_label} · Top Waiver Target
        </span>
      </div>
      <WaiverIdentity player={player} />
      <div
        className="flex items-center justify-between gap-3 pt-3"
        style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span className="text-2xl font-black" style={{ color: "var(--color-accent)" }}>
            {formatWaiverScore(player.score)}
          </span>
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
            Value
          </span>
        </div>
        <FaabRange player={player} prominent />
      </div>
      {player.confidence_label ? (
        <ConfidenceMeter label="Confidence" value={player.confidence_label} color={confidenceColor(player.confidence_label)} />
      ) : null}
    </article>
  );
}

function PriorityAddCompactRow({ player, showDivider }: { player: WaiverPriorityAdd; showDivider: boolean }) {
  return (
    <div
      className="flex items-center justify-between gap-3 py-2.5"
      style={showDivider ? { borderBottom: "var(--border-width-default) solid var(--color-border)" } : undefined}
    >
      <div className="flex flex-col gap-1 min-w-0 flex-1">
        <WaiverIdentity player={player} />
        {player.confidence_label ? (
          <ConfidenceMeter label="Confidence" value={player.confidence_label} color={confidenceColor(player.confidence_label)} />
        ) : null}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-base font-extrabold" style={{ color: "var(--color-accent)" }}>
          {formatWaiverScore(player.score)}
        </span>
        <RecommendationPill label={player.recommendation_label} tone={player.recommendation_tone} />
      </div>
      <FaabRange player={player} />
    </div>
  );
}

function FreeAgentRow({ player }: { player: WaiverPlayer }) {
  return (
    <div
      className="flex items-center justify-between gap-3 py-2"
      style={{
        borderBottom: "var(--border-width-default) solid var(--color-border)",
        opacity: player.stale_free_agent ? 0.55 : 1,
      }}
    >
      <WaiverIdentity player={player} />
      <div className="flex items-center gap-2 shrink-0">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
          {formatWaiverScore(player.score)}
        </span>
        {player.position_rank ? (
          <span
            className="px-1.5 py-0.5 text-xs font-bold"
            style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)" }}
          >
            {player.position}
            {player.position_rank}
          </span>
        ) : null}
        <OvrGauge rating={player.overall_rating} size="sm" />
      </div>
    </div>
  );
}

function BestAvailableTile({ position, player, count }: { position: string; player: WaiverPlayer; count: number }) {
  return (
    <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "Waivers" }} className="min-w-[7.5rem]">
      <div
        className="flex flex-col items-center gap-1 p-3"
        style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <OvrGauge rating={player.overall_rating} size="md" />
        <PositionBadge position={position} />
        <span className="text-sm font-extrabold truncate max-w-full" style={{ color: "var(--color-text-primary)" }}>
          {player.name || "Unknown"}
        </span>
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
            {formatWaiverScore(player.score)}
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {count} active
          </span>
        </div>
      </div>
    </PlayerIdentityTrigger>
  );
}

const BEST_AVAILABLE_POSITIONS = ["QB", "RB", "WR", "TE", "K"];
const FREE_AGENT_LIST_PREVIEW_ROWS = 60;
const FILTER_POSITIONS = ["ALL", "QB", "RB", "WR", "TE", "K"];

function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="uppercase" style={{ font: "var(--type-section-title)", letterSpacing: "0.02em" }}>
      {children}
    </h2>
  );
}

export function WaiversContent({ leagueName, data }: { leagueName: string; data: WaiversResponse }) {
  const [search, setSearch] = useState("");
  const [position, setPosition] = useState("ALL");

  const notice = data.reason ? waiversReasonMessage(data.reason) : null;

  const priorityAdds = data.priority_adds;
  const topPriority = priorityAdds[0] ?? null;
  const secondaryPriority = priorityAdds.length > 1 ? priorityAdds.slice(1) : [];

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

  const visibleFreeAgents = filteredFreeAgents.slice(0, FREE_AGENT_LIST_PREVIEW_ROWS);

  if (notice) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const hasSecondaryCandidates =
    data.stash_candidates.length > 0 || data.watchlist_candidates.length > 0 || data.faab_targets.length > 0;

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Waivers
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Free agents ranked for your roster — ordered by fit for your team, not just raw value.
        </p>
      </header>

      <div className="flex flex-wrap gap-3">
        <SnapshotTile label="Available players" value={String(data.available_count ?? data.players.length)} />
        <SnapshotTile label="Avg Wire Score" value={String(data.avg_wire_score ?? 0)} />
        <SnapshotTile label="Current need" value={data.needed_positions.length > 0 ? data.needed_positions.join(" / ") : "None"} />
      </div>

      <section className="flex flex-col gap-3" aria-labelledby="priority-adds-heading">
        <span id="priority-adds-heading" className="sr-only">
          Priority Adds
        </span>
        <SectionHeading>Priority Adds</SectionHeading>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {priorityNeedNote(data.needed_positions)} Need fits and injury cover rank first, then value.
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {DISCLOSURE_TEXT}
        </p>
        {data.injury_positions && data.injury_positions.length > 0 ? (
          <p className="text-xs" style={{ color: "var(--color-warning)" }}>
            Injury replacement watch is active for {data.injury_positions.join(" / ")}. Your current lineup is carrying{" "}
            {data.injured_starters ?? 0} injured starter{data.injured_starters === 1 ? "" : "s"}.
          </p>
        ) : null}

        {!topPriority ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No waiver option materially improves your current roster right now. Use Waiver Snapshot below for best available by
            position.
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            <PriorityAddPrimaryCard player={topPriority} />
            {secondaryPriority.length > 0 ? (
              <div
                className="flex flex-col px-3"
                style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
              >
                {secondaryPriority.map((player, index) => (
                  <PriorityAddCompactRow key={player.player_id} player={player} showDivider={index < secondaryPriority.length - 1} />
                ))}
              </div>
            ) : null}
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="secondary-board-heading">
        <span id="secondary-board-heading" className="sr-only">
          Beyond Priority Adds
        </span>
        <SectionHeading>Beyond Priority Adds</SectionHeading>
        {!data.entitlement.is_premium ? (
          <div
            className="p-4 flex flex-col gap-2"
            style={{ background: "var(--color-action-soft)", border: "var(--border-width-default) solid var(--color-action)" }}
          >
            <p className="text-sm font-bold">Full waiver board and FAAB shortlist</p>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Priority Adds stay free — Premium adds stash candidates, watchlist depth, and a FAAB shortlist so you don&apos;t miss
              the next claim.
            </p>
            <a href={streamlitPageUrl("premium")} className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
              Upgrade →
            </a>
          </div>
        ) : !hasSecondaryCandidates ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No additional stash, watchlist, or FAAB shortlist candidates right now.
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {data.stash_candidates.length > 0 ? (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  Stash Candidates
                </span>
                <div
                  className="flex flex-col px-3"
                  style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
                >
                  {data.stash_candidates.map((player) => (
                    <FreeAgentRow key={player.player_id} player={player} />
                  ))}
                </div>
              </div>
            ) : null}
            {data.watchlist_candidates.length > 0 ? (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  Watchlist Depth
                </span>
                <div
                  className="flex flex-col px-3"
                  style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
                >
                  {data.watchlist_candidates.map((player) => (
                    <FreeAgentRow key={player.player_id} player={player} />
                  ))}
                </div>
              </div>
            ) : null}
            {data.faab_targets.length > 0 ? (
              <div className="flex flex-col gap-2">
                <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
                  FAAB Shortlist
                </span>
                <div
                  className="flex flex-col px-3"
                  style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
                >
                  {data.faab_targets.map((player) => (
                    <FreeAgentRow key={player.player_id} player={player} />
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </section>

      {bestAvailable.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="snapshot-heading">
          <SectionHeading>
            <span id="snapshot-heading">Waiver Snapshot</span>
          </SectionHeading>
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Best available options by position — broad wire scan, not roster priorities.
          </p>
          <div className="flex gap-3 overflow-x-auto pb-1">
            {bestAvailable.map(({ position: pos, player, count }) => (
              <BestAvailableTile key={pos} position={pos} player={player} count={count} />
            ))}
          </div>
        </section>
      ) : null}

      <section className="flex flex-col gap-3" aria-labelledby="all-free-agents-heading">
        <SectionHeading>
          <span id="all-free-agents-heading">All Free Agents</span>
        </SectionHeading>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Showing the best available players not currently on a roster in this league. Stale or retired profiles are pushed to the
          bottom.
        </p>
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
            <div
              className="flex flex-col px-3"
              style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
            >
              {visibleFreeAgents.map((player) => (
                <FreeAgentRow key={player.player_id} player={player} />
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
    </main>
  );
}
