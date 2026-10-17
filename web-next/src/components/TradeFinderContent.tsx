import { useMemo, useState } from "react";

import { api, type LineupPlayer, type MyTeamResponse, type TradeIdea } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import { TradesTabBar } from "@/components/TradesTabBar";
import { tradeHubReasonMessage } from "@/lib/tradeHubPresentation";

/**
 * Trade Finder (Revision 17) — "select these specific players, find who'd
 * want them," ported from modules/trade_hub_ui.py's
 * render_trade_finder_workspace (built hours earlier tonight, PR #1072's
 * follow-up) and mobile's TradeFinderScreen.tsx, the original reference
 * implementation that Streamlit's own version was itself built from. Reads
 * GET .../my-team for the roster picker and GET .../trade-finder for
 * results — the exact same two endpoints mobile's screen calls, and the
 * exact same TradeIdea card shape Trade Hub renders (modules.trade_hub_engine
 * serializes both through one shared card projection), so results render via
 * the shared TradeIdeaCardView (TradeIdeaCard.tsx) rather than a second copy
 * of that ~180-line card.
 *
 * Premium gating is a deliberate divergence from Streamlit: Streamlit's own
 * render_trade_finder_workspace hard-gates the whole page behind
 * current_user_is_premium()/render_premium_lock, but GET .../trade-finder
 * itself returns no entitlement/premium field at all, and mobile's
 * TradeFinderScreen.tsx has no premium check anywhere either — the exact
 * same "ungated per the shared API contract" situation GmPlanContent.tsx
 * documents for GM Plan (Revision 9). Following the API/mobile contract
 * here rather than inventing a client-side paywall Streamlit's web-only
 * route happens to have but nothing else in the system encodes.
 *
 * Strategy/lens default to "retool"/"Dynasty", matching TradeHubContent's
 * own documented default (web-next has no GmStance/ValuationLens context
 * the way mobile does yet).
 *
 * Deliberately NOT covered: the "Quick view a selected player" button grid
 * Streamlit's workspace renders below the selection — a tap-through to
 * Player Quick View, which no other Trades-tab page on web-next wires up
 * either (see TradeHubContent.tsx's and TradeAnalyzerContent.tsx's own
 * "quick-view/full-detail split" notes); adding it here first would be
 * inventing new cross-page surface, not porting this page.
 */

function RosterPickRow({
  player,
  selected,
  onToggle,
}: {
  player: LineupPlayer;
  selected: boolean;
  onToggle: () => void;
}) {
  // Deliberately NOT wrapped in PlayerIdentityTrigger: this entire row's
  // one job is a selection toggle (clicking the name/badges IS "select this
  // player for the search", an existing, tested contract), so a tap-to-
  // open-quick-view here would silently change what clicking a player's
  // name does on this one page instead of adding a new capability — the
  // same kind of surface-specific judgment call this file's own "quick-
  // view/full-detail split" comments already make elsewhere. The OVR badge
  // is intentionally skipped as a "safe" alternate tap target too: a
  // second, inconsistent meaning for the same badge on one page vs. every
  // other page would be a worse outcome than leaving this one row as a
  // pure selection control, unlike every other page's identity rows.
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      className="w-full flex items-center gap-3 py-2 px-2 text-left"
      style={{
        background: selected ? "var(--surface-selected)" : "transparent",
        borderBottom: "var(--border-width-default) solid var(--color-border)",
      }}
    >
      <span
        aria-hidden="true"
        className="flex items-center justify-center shrink-0"
        style={{
          width: "1.125rem",
          height: "1.125rem",
          border: `1.5px solid ${selected ? "var(--border-accent)" : "var(--color-border-strong)"}`,
          background: selected ? "var(--color-accent)" : "transparent",
          color: "var(--color-bg)",
          fontSize: "0.7rem",
          fontWeight: 900,
        }}
      >
        {selected ? "✓" : ""}
      </span>
      <PositionBadge position={player.position} />
      <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
      <div className="flex-1 flex flex-col gap-0.5 min-w-0">
        <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
          {player.name || "Unknown player"}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {player.team || "FA"}
        </span>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <OvrGauge rating={player.overall_rating} size="sm" />
        <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
          {player.score != null ? Math.round(player.score) : "—"}
        </span>
      </div>
    </button>
  );
}

export function TradeFinderContent({
  leagueId,
  leagueName,
  myTeam,
  lens = "Dynasty",
}: {
  leagueId: string;
  leagueName: string;
  myTeam: MyTeamResponse;
  lens?: string;
}) {
  const reasonMessage = myTeam.reason ? tradeHubReasonMessage(myTeam.reason) : null;

  const roster = useMemo(
    () => [...myTeam.starters, ...myTeam.bench].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
    [myTeam],
  );

  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);

  function toggle(playerId: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(playerId)) next.delete(playerId);
      else next.add(playerId);
      return next;
    });
    setIdeas(null);
    setSearchError(null);
  }

  async function search() {
    if (selectedIds.size === 0) return;
    setSearchError(null);
    setSearching(true);
    try {
      const result = await api.getTradeFinderIdeas(leagueId, Array.from(selectedIds), "retool", lens);
      setIdeas(result.ideas);
      if (result.ideas.length === 0 && result.reason === "no_players_selected") {
        setSearchError("Select at least one player to search with.");
      }
    } catch (err) {
      setSearchError(err instanceof Error ? err.message : "Could not search for trades.");
    } finally {
      setSearching(false);
    }
  }

  if (reasonMessage) {
    return (
      <main className="flex-1 flex flex-col gap-4 items-center justify-center px-4">
        <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_finder" />
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {reasonMessage}
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <TradesTabBar leagueId={leagueId} leagueName={leagueName} active="trade_finder" />
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Trade Finder
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Choose players from your roster and search for realistic packages the league would accept for them.
        </p>
      </header>

      {roster.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No eligible roster players are available for Trade Finder right now.
        </p>
      ) : (
        <>
          <section className="flex flex-col gap-2">
            <span
              className="text-xs uppercase font-bold"
              style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
            >
              Players you&apos;d trade away
            </span>
            <div className="flex flex-col" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
              {roster.map((player) => (
                <RosterPickRow
                  key={player.player_id}
                  player={player}
                  selected={selectedIds.has(player.player_id)}
                  onToggle={() => toggle(player.player_id)}
                />
              ))}
            </div>
          </section>

          <button
            type="button"
            onClick={search}
            disabled={selectedIds.size === 0 || searching}
            className="self-start px-4 py-2 text-sm font-bold"
            style={{
              background: selectedIds.size > 0 ? "var(--color-accent)" : "var(--color-surface-muted)",
              color: selectedIds.size > 0 ? "var(--color-bg)" : "var(--color-text-muted)",
            }}
          >
            {searching ? "Searching…" : `Find Realistic Trades${selectedIds.size > 0 ? ` (${selectedIds.size})` : ""}`}
          </button>

          {selectedIds.size === 0 ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Select one or more of your players, then search for realistic trade packages built around them.
            </p>
          ) : null}

          {searchError ? (
            <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
              {searchError}
            </p>
          ) : null}

          {ideas !== null && !searchError ? (
            ideas.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                No realistic trades found for this selection right now.
              </p>
            ) : (
              <div className="flex flex-col gap-4">
                {ideas.map((idea, index) => (
                  <TradeIdeaCardView key={`${idea.partner_team_name}-${index}`} idea={idea} />
                ))}
              </div>
            )
          ) : null}
        </>
      )}
    </main>
  );
}
