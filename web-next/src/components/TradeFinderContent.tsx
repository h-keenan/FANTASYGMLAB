import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  api,
  type DraftPickAsset,
  type LineupPlayer,
  type MyTeamResponse,
  type PremiumUpsell,
  type TradeIdea,
} from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { TradeAssetRow } from "@/components/TradeAssetExchange";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import { TradesTabBar } from "@/components/TradesTabBar";
import { pickToTradeAsset } from "@/lib/tradeAnalyzerPresentation";
import { TRADE_DEADLINE_PASSED_MESSAGE, tradeHubReasonMessage } from "@/lib/tradeHubPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";

/** Mirrors modules.trade_ideas.TRADE_FINDER_MAX_SELECTED_PICKS — the server
 * ignores any selected pick past this many, so the picker stops there too. */
export const TRADE_FINDER_MAX_PICKS = 4;

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
 * Premium-gated (2026-10-17, pre-launch audit): matches Streamlit's own
 * render_trade_finder_workspace hard-gate. GET .../trade-finder now
 * returns `is_premium`/`upsell` on its search response; a Free caller's
 * search comes back with an empty idea list and that upsell, which
 * replaces this entire page (builder included) with the same
 * PremiumUpsellCard Portfolio/GM Plan use — matching Streamlit's
 * whole-workspace lock rather than letting a Free user build a selection
 * that can never return results. mobile's TradeFinderScreen.tsx is still
 * ungated and should get the same fix separately.
 *
 * Lens defaults to "Dynasty", matching TradeHubContent's own documented
 * default (web-next has no ValuationLens context the way mobile does for
 * every page yet). Strategy used to default to a hardcoded "retool" too —
 * recommendation-compliance audit finding: that meant a search here never
 * reflected the caller's declared Team Situation (Competing/Rebuilding),
 * only "Balanced", the one stance "retool" happens to match — so this now
 * fetches GET .../team-stance's already-mapped `strategy` field on mount,
 * same as mobile's TradeFinderScreen.tsx (useGmStance) does, falling back
 * to "retool" only while that fetch is in flight or if it fails/no stance
 * is set (unchanged from before for those cases).
 *
 * Deliberately NOT covered: the "Quick view a selected player" button grid
 * Streamlit's workspace renders below the selection — a tap-through to
 * Player Quick View, which no other Trades-tab page on web-next wires up
 * either (see TradeHubContent.tsx's and TradeAnalyzerContent.tsx's own
 * "quick-view/full-detail split" notes); adding it here first would be
 * inventing new cross-page surface, not porting this page.
 *
 * Draft picks: the caller's own picks (GET .../draft-picks filtered to this
 * roster's owner_roster_id — real Sleeper traded-picks ownership, the same
 * list and valuation Trade Analyzer's Picks browser uses) can be offered
 * alongside or instead of players, and "Picks back" asks the engine to keep
 * only packages that return a partner pick. Pick rows reuse Trade Analyzer's
 * shared TradeAssetRow + pickToTradeAsset rather than a local pick layout.
 */

function SelectionCheck({ selected }: { selected: boolean }) {
  return (
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
  );
}

function selectableRowStyle(selected: boolean) {
  return {
    background: selected ? "var(--surface-selected)" : "transparent",
    borderBottom: "var(--border-width-default) solid var(--color-border)",
  };
}

function OwnedPickRow({
  pick,
  selected,
  disabled,
  onToggle,
}: {
  pick: DraftPickAsset;
  selected: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={selected}
      disabled={disabled}
      className="w-full flex items-center gap-3 py-1 px-2 text-left"
      style={{ ...selectableRowStyle(selected), opacity: disabled ? 0.5 : 1 }}
    >
      <SelectionCheck selected={selected} />
      <div className="flex-1 min-w-0">
        <TradeAssetRow asset={pickToTradeAsset(pick)} disableQuickView />
      </div>
      <span className="text-sm font-extrabold shrink-0" style={{ color: "var(--color-accent)" }}>
        {pick.score != null ? Math.round(pick.score) : "—"}
      </span>
    </button>
  );
}

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
      style={selectableRowStyle(selected)}
    >
      <SelectionCheck selected={selected} />
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
  initialPlayerId,
}: {
  leagueId: string;
  leagueName: string;
  myTeam: MyTeamResponse;
  lens?: string;
  /** ?playerId= from a "Find trades" action (Player Quick View / Player
   * Profile, tap-depth audit 2026-10 proposal 2). When that player is on
   * this roster it starts selected and the search runs once, under the
   * caller's real Team Situation strategy. Anyone else is ignored. Free
   * users get the same Premium upsell a manual search shows. */
  initialPlayerId?: string;
}) {
  // Past the league's trade deadline Trade Finder stops searching for
  // in-season trades (GET .../my-team's additive trade_window).
  const reasonMessage = myTeam.reason
    ? tradeHubReasonMessage(myTeam.reason)
    : myTeam.trade_window?.trade_deadline_passed
      ? myTeam.trade_window.message || TRADE_DEADLINE_PASSED_MESSAGE
      : null;

  const roster = useMemo(
    () => [...myTeam.starters, ...myTeam.bench].sort((a, b) => (b.score ?? 0) - (a.score ?? 0)),
    [myTeam],
  );

  const autoSearchPlayerId =
    initialPlayerId && !reasonMessage && roster.some((player) => player.player_id === initialPlayerId) ? initialPlayerId : null;
  const autoSearchStarted = useRef(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(() =>
    autoSearchPlayerId ? new Set([autoSearchPlayerId]) : new Set(),
  );
  const [ownedPicks, setOwnedPicks] = useState<DraftPickAsset[]>([]);
  const [selectedPickIds, setSelectedPickIds] = useState<Set<string>>(new Set());
  const [returnPicks, setReturnPicks] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);
  // null = not yet known (no search attempted); set from the first search
  // response's `is_premium`/`upsell` — see the premium-gating note above.
  const [premiumUpsell, setPremiumUpsell] = useState<{ locked: boolean; upsell: PremiumUpsell | null } | null>(null);
  // The caller's declared Team Situation, mapped to the real engine
  // strategy key — see this file's docstring. Defaults to "retool" (the
  // same default as before this fetch existed) until GET .../team-stance
  // resolves, matching mobile's useGmStance AUTO_STRATEGY fallback.
  const [strategy, setStrategy] = useState("retool");

  const runSearch = useCallback(
    async (playerIds: Set<string>, pickIds: Set<string>, withReturnPicks: boolean, strategyKey: string) => {
      setSearchError(null);
      setSearching(true);
      try {
        const result = await api.getTradeFinderIdeas(leagueId, Array.from(playerIds), strategyKey, lens, {
          pickIds: Array.from(pickIds),
          returnPicks: withReturnPicks,
        });
        setIdeas(result.ideas);
        setPremiumUpsell({ locked: !result.is_premium, upsell: result.upsell });
        if (result.ideas.length === 0 && result.reason === "no_players_selected") {
          setSearchError("Select at least one player or pick to search with.");
        } else if (result.reason === "trade_deadline_passed") {
          setSearchError(result.message || TRADE_DEADLINE_PASSED_MESSAGE);
        }
      } catch (err) {
        setSearchError(err instanceof Error ? err.message : "Could not search for trades.");
      } finally {
        setSearching(false);
      }
    },
    [leagueId, lens],
  );

  useEffect(() => {
    let cancelled = false;
    // A "Find trades" deep link runs its search once the strategy is known
    // (or failed to load), so it searches the same way a manual tap would.
    const runAutoSearch = (strategyKey: string) => {
      if (cancelled || !autoSearchPlayerId || autoSearchStarted.current) return;
      autoSearchStarted.current = true;
      void runSearch(new Set([autoSearchPlayerId]), new Set(), false, strategyKey);
    };
    api
      .getTeamStance(leagueId)
      .then((result) => {
        if (!cancelled && result.strategy) setStrategy(result.strategy);
        runAutoSearch(result.strategy || "retool");
      })
      .catch(() => {
        // Team Situation fetch failing is never fatal — search still runs
        // under the same "retool" default it always has.
        runAutoSearch("retool");
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, autoSearchPlayerId, runSearch]);

  useEffect(() => {
    const myRosterId = myTeam.roster_id ? String(myTeam.roster_id) : "";
    if (!myRosterId) return;
    let cancelled = false;
    api
      .getLeagueDraftPicks(leagueId, lens)
      .then((result) => {
        if (cancelled) return;
        const mine = (result.picks ?? [])
          .filter((pick) => String(pick.owner_roster_id) === myRosterId)
          .sort((a, b) => (a.season ?? 0) - (b.season ?? 0) || (a.round ?? 0) - (b.round ?? 0));
        setOwnedPicks(mine);
      })
      .catch(() => {
        // No pick list is never fatal — player-only search still works.
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, myTeam.roster_id]);

  const selectionCount = selectedIds.size + selectedPickIds.size;

  function togglePick(pickId: string) {
    setSelectedPickIds((prev) => {
      const next = new Set(prev);
      if (next.has(pickId)) next.delete(pickId);
      else if (next.size < TRADE_FINDER_MAX_PICKS) next.add(pickId);
      return next;
    });
    setIdeas(null);
    setSearchError(null);
  }

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

  function search() {
    if (selectionCount === 0) return;
    void runSearch(selectedIds, selectedPickIds, returnPicks, strategy);
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

  if (premiumUpsell?.locked) {
    return (
      <PremiumUpsellCard
        kicker="Trade Finder"
        upsell={premiumUpsell.upsell}
        fallbackTitle="Build and search for a trade"
        fallbackBody="Trade Finder is a Premium feature — build a custom package and search every roster in your league for a real match. Upgrade to Premium to unlock it."
      />
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
          Pick what you&apos;d move; find realistic packages.
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

          {ownedPicks.length > 0 ? (
            <section className="flex flex-col gap-2">
              <span
                className="text-xs uppercase font-bold"
                style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
              >
                Picks you&apos;d trade away
              </span>
              <div className="flex flex-col" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
                {ownedPicks.map((pick) => {
                  const selected = selectedPickIds.has(pick.pick_id);
                  return (
                    <OwnedPickRow
                      key={pick.pick_id}
                      pick={pick}
                      selected={selected}
                      disabled={!selected && selectedPickIds.size >= TRADE_FINDER_MAX_PICKS}
                      onToggle={() => togglePick(pick.pick_id)}
                    />
                  );
                })}
              </div>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Up to {TRADE_FINDER_MAX_PICKS} picks per search.
              </p>
            </section>
          ) : null}

          <section className="flex flex-col gap-2">
            <span
              className="text-xs uppercase font-bold"
              style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
            >
              What you want back
            </span>
            <PillRow
              options={[
                { label: "Any return", value: "any" },
                { label: "Picks back", value: "picks" },
              ]}
              active={returnPicks ? "picks" : "any"}
              onSelect={(value) => {
                setReturnPicks(value === "picks");
                setIdeas(null);
                setSearchError(null);
              }}
            />
          </section>

          <button
            type="button"
            onClick={search}
            disabled={selectionCount === 0 || searching}
            className="self-start px-4 py-2 text-sm font-bold"
            style={{
              background: selectionCount > 0 ? "var(--color-accent)" : "var(--color-surface-muted)",
              color: selectionCount > 0 ? "var(--color-bg)" : "var(--color-text-muted)",
            }}
          >
            {searching ? "Searching…" : `Find Realistic Trades${selectionCount > 0 ? ` (${selectionCount})` : ""}`}
          </button>

          {selectionCount === 0 ? (
            <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Select players or picks to start.
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
                  <TradeIdeaCardView
                    key={`${idea.partner_team_name}-${index}`}
                    idea={idea}
                    leagueId={leagueId}
                    strategy="retool"
                    lens={lens}
                  />
                ))}
              </div>
            )
          ) : null}
        </>
      )}
      <ValuesCredit />
    </main>
  );
}
