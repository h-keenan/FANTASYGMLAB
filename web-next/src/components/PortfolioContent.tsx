"use client";

import Link from "next/link";
import { useState } from "react";

import {
  api,
  type BriefingItem,
  type PortfolioFailedLeague,
  type PortfolioLeague,
  type PortfolioResponse,
  type PortfolioSavedLeague,
} from "@/lib/api";
import { categoryColorVar, categoryLabel } from "@/lib/portfolioPresentation";
import { BriefingItemPlayers, briefingItemIsSinglePlayer } from "@/components/BriefingItemPlayers";
import { PillRow } from "@/components/PillRow";
import { PortfolioExposureView } from "@/components/PortfolioExposureView";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { formatRank } from "@/components/SnapshotTile";
import { TeamAvatar } from "@/components/TeamAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { SkeletonBlock } from "@/components/Skeleton";

/**
 * Ports modules/portfolio_page.py's render_portfolio_page — the cross-
 * league "Portfolio" view (coridian_-approved: a single surface showing a
 * user's standing/needs/opportunities across ALL their connected leagues at
 * once). Every row's data comes from the exact same GET /v1/portfolio
 * endpoint mobile's PortfolioScreen.tsx already calls, which itself reuses
 * modules.dashboard_engine.build_league_summary (the identical engine the
 * single-league Dashboard uses) — this component adds no new aggregation,
 * ranking, or valuation math of its own.
 *
 * Each league card renders up to PORTFOLIO_MAX_SIGNALS (3) quick-glance
 * signals (`top_items`) — value trending down, an injury, a live news
 * story, actionable waiver info — the same multi-signal expansion PR #1071
 * added to both the Streamlit page and mobile's PortfolioScreen, so all
 * three surfaces agree on what a league's card shows.
 *
 * Unlike every other page ported so far, Portfolio has no `leagueId` in its
 * own route — it spans every saved league at once. "Open Dashboard" on a
 * card is the only place a `leagueId` appears, linking into the already-
 * built Next.js Dashboard page (app/dashboard/[leagueId]).
 */

function recordLabel(league: PortfolioLeague): string {
  if (league.wins == null && league.losses == null) return "";
  const base = `${league.wins ?? 0}-${league.losses ?? 0}`;
  return league.ties ? `${base}-${league.ties}` : base;
}

function rankLabel(league: PortfolioLeague): string {
  if (league.power_rank == null) return "";
  return `Roster Power ${formatRank(league.power_rank, league.power_rank_tied)}`;
}

function SignalRow({ item, showDivider }: { item: BriefingItem; showDivider: boolean }) {
  const color = categoryColorVar(item.category);
  const label = categoryLabel(item.category);
  // coridian_, 2026-10-18, screenshot: "not specific just says watch for no
  // reason" — a signal like "Usage down 13% (high confidence)..." read with
  // no subject at all, because this only ever showed reason OR headline,
  // never both. GamePlanCard/WatchListCard show headline (the subject,
  // e.g. "Ashton Jeanty trending down") AND reason (the detail) as two
  // separate lines; this now does the same instead of picking just one.
  const reasonText = item.reason || "";
  const headlineText = item.headline || "";
  const showReason = Boolean(reasonText) && reasonText !== headlineText;
  if (!headlineText && !reasonText) return null;

  const hasPlayerVisual = Boolean(
    (item.presentation?.trade_package &&
      (item.presentation.trade_package.send.length > 0 || item.presentation.trade_package.receive.length > 0)) ||
      (item.route_player_name && item.route_player_id) ||
      (item.mentioned_players && item.mentioned_players.length > 0),
  );
  // Same dedup as modules/daily_gm_briefing_ui.py's _should_show_reason:
  // a Watch item's reason text is often the same pipe-delimited identity
  // dump the chips below now already show — showing both is redundant.
  const showReasonText =
    showReason && !(item.category === "watch" && hasPlayerVisual && (reasonText.includes(" | ") || reasonText.includes(" - ")));

  const badge = <ToneBadge label={label} color={color} />;
  const text = (
    <div className="flex flex-col flex-1 min-w-0">
      {headlineText ? (
        <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {headlineText}
        </span>
      ) : null}
      {showReasonText ? (
        <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {reasonText}
        </span>
      ) : null}
    </div>
  );
  // coridian_, 2026-10-18, screenshot: "this portfolio looks terrible, with
  // zero player PFPs. These need to have the compact player cards that we
  // were supposed to make" — every signal here was a pipe-separated text
  // dump of player names with no identity at all. Same BriefingItemPlayers
  // chips Today's Game Plan already uses.
  const players = <BriefingItemPlayers item={item} sourceLabel="Portfolio" />;

  // coridian_, 2026-10-19, screenshot: "the player card location looks
  // really awkward with it being under the related text" — for the common
  // single-player case, the card now sits beside the category pill instead
  // of stacked below the article text. A trade package (2-column send/
  // receive grid) or several mentioned players can't realistically sit
  // beside a small pill without looking cramped, so those keep the
  // original stacked layout.
  if (briefingItemIsSinglePlayer(item)) {
    return (
      <div
        className="flex flex-col gap-1.5 mt-2"
        style={
          showDivider
            ? { paddingTop: "var(--space-sm)", borderTop: "var(--border-width-default) solid var(--color-border)" }
            : undefined
        }
      >
        <div className="flex items-center gap-2">
          {badge}
          {players}
        </div>
        {text}
      </div>
    );
  }

  return (
    <div
      className="flex flex-col gap-1.5 mt-2"
      style={
        showDivider
          ? { paddingTop: "var(--space-sm)", borderTop: "var(--border-width-default) solid var(--color-border)" }
          : undefined
      }
    >
      <div className="flex items-start gap-2">
        {badge}
        {text}
      </div>
      {players}
    </div>
  );
}

/**
 * coridian_, 2026-10-19: a league stuck mid-draft (Sleeper doesn't assign
 * roster players until the whole draft completes — same reason Dashboard's
 * quiet state already explains this via notReadyReasonMessage) landed here
 * with the same scary "Couldn't load" warning styling as a genuine failure
 * (no linked account, league gone, Sleeper down). Split the two: an
 * `empty_roster` league gets a calm, non-warning note that links straight
 * into Live Draft — the feature actually built for "my draft isn't done
 * yet" — instead of a dead-end error asking if it's even your league.
 */
function DraftingLeaguesNote({ leagues }: { leagues: PortfolioFailedLeague[] }) {
  return (
    <div
      className="flex flex-col gap-1.5 px-3 py-2 text-sm"
      style={{ background: "var(--color-surface-muted)", border: "var(--border-width-default) solid var(--color-border)" }}
    >
      <span style={{ color: "var(--color-text-secondary)" }}>
        {leagues.length === 1 ? "Draft still in progress:" : "Drafts still in progress:"} rosters will show up here
        once each draft finishes.
      </span>
      {leagues.map((league) => (
        <div key={league.league_id} className="flex items-center justify-between gap-2">
          <span style={{ color: "var(--color-text-secondary)" }}>{league.league_name}</span>
          <Link
            href={`/live-draft/${league.league_id}?name=${encodeURIComponent(league.league_name)}`}
            className="text-xs font-bold whitespace-nowrap"
            style={{ color: "var(--color-accent)" }}
          >
            Watch live draft →
          </Link>
        </div>
      ))}
    </div>
  );
}

/** ESPN leagues (reason "espn_not_supported", modules/espn_leagues.py) have no
 * Portfolio summary yet. Not a failure, so not in FailedLeaguesNote's
 * "Couldn't load / Not your league? Remove" list. */
function EspnLeaguesNote({ leagues }: { leagues: PortfolioFailedLeague[] }) {
  return (
    <div
      className="flex flex-col gap-1.5 px-3 py-2 text-sm"
      style={{ background: "var(--color-surface-muted)", border: "var(--border-width-default) solid var(--color-border)" }}
    >
      <span style={{ color: "var(--color-text-secondary)" }}>
        Portfolio isn&apos;t available for ESPN leagues yet. Open them from My Team instead.
      </span>
      {leagues.map((league) => (
        <div key={league.league_id} className="flex items-center justify-between gap-2">
          <span style={{ color: "var(--color-text-secondary)" }}>{league.league_name}</span>
          <Link
            href={`/my-team/${encodeURIComponent(league.league_id)}?name=${encodeURIComponent(league.league_name)}`}
            className="text-xs font-bold whitespace-nowrap"
            style={{ color: "var(--color-accent)" }}
          >
            Open My Team →
          </Link>
        </div>
      ))}
    </div>
  );
}

function FailedLeaguesNote({
  leagues,
  busyLeagueId,
  onRemove,
}: {
  leagues: PortfolioFailedLeague[];
  busyLeagueId: string | null;
  onRemove: (leagueId: string) => void;
}) {
  const plural = leagues.length === 1 ? "league" : "leagues";
  return (
    <div
      className="flex flex-col gap-1.5 px-3 py-2 text-sm"
      style={{ background: "var(--color-warning-soft)", border: "var(--border-width-default) solid var(--color-warning)" }}
    >
      <span>{`Couldn't load ${leagues.length} ${plural} right now. Everything else below is up to date.`}</span>
      {leagues.map((league) => (
        <div key={league.league_id} className="flex items-center justify-between gap-2">
          <span style={{ color: "var(--color-text-secondary)" }}>{league.league_name}</span>
          <button
            type="button"
            onClick={() => onRemove(league.league_id)}
            disabled={busyLeagueId === league.league_id}
            className="text-xs font-bold whitespace-nowrap"
            style={{ color: "var(--color-text-muted)" }}
          >
            {busyLeagueId === league.league_id ? "Removing…" : "Not your league? Remove"}
          </button>
        </div>
      ))}
    </div>
  );
}

function PortfolioLeagueCard({ league }: { league: PortfolioLeague }) {
  // Same fallback as modules/portfolio_page.py / mobile's PortfolioScreen:
  // `top_items` is the already-ranked/deduped signal list, falling back to
  // a one-item list built from `top_item` for a cached/mocked response from
  // before PR #1071 added the multi-signal list.
  const signals = league.top_items?.length ? league.top_items : league.top_item ? [league.top_item] : [];
  const record = recordLabel(league);
  // Top-3 gets the gold/silver/bronze pill badge below instead of this
  // "Roster Power #N" text — showing both would say the same rank twice
  // (mirrors modules/portfolio_page.py: `rank_text` is only set when there's
  // no `rank_badge`).
  const showRankBadge = league.power_rank != null && league.power_rank <= 3;
  const metadata = [record, showRankBadge ? "" : rankLabel(league)].filter(Boolean).join(" · ");
  const showHealthFlag = Boolean(league.health_flag) && league.health_flag !== "Stable";

  return (
    <article className="glass-surface flex flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-2 min-w-0">
          {/* coridian_, 2026-10-18 (screenshot): Portfolio's league cards
              had no team logo at all. Same Sleeper CDN avatar the user's
              own roster already has everywhere else in the app (Trade Hub,
              Matchup, League Rankings) — not a new avatar source. */}
          <TeamAvatar avatarUrl={league.team_avatar_url} size={32} />
          <div className="flex flex-col min-w-0">
            <h3 style={{ font: "var(--font-card-title)" }}>
              {league.team_name || "Unclaimed team"} — {league.league_name}
            </h3>
            {metadata ? (
              <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
                {metadata}
              </span>
            ) : null}
          </div>
        </div>
        {showRankBadge ? (
          <span
            className="px-2 py-1 text-xs font-extrabold uppercase whitespace-nowrap"
            style={{
              borderRadius: "var(--radius-pill)",
              background: "var(--color-action-soft)",
              color: "var(--color-premium)",
              letterSpacing: "var(--letter-spacing-badge)",
            }}
          >
            {formatRank(league.power_rank, league.power_rank_tied)}
          </span>
        ) : null}
      </div>

      {showHealthFlag ? (
        <span
          className="self-start mt-2 px-1.5 py-0.5 text-xs font-extrabold uppercase"
          style={{
            borderRadius: "var(--radius-pill)",
            background: "var(--color-warning-soft)",
            color: "var(--color-warning)",
            letterSpacing: "var(--letter-spacing-badge)",
          }}
        >
          {league.health_flag}
        </span>
      ) : null}

      {signals.length > 0 ? (
        <div className="flex flex-col">
          {/* coridian_, 2026-10-19 (screenshot): "this is a trade and a
              usage alert and something else, but they're not clearly
              segregated, and so it all looks one interconnected piece of
              information" — Dashboard's own Today's Game Plan already
              separates TOP PRIORITY/WATCH cards with a real divider
              (GamePlanCard/WatchListCard each render as their own bordered
              card); this compact Portfolio list stacked the same signals
              with nothing but a category chip to tell them apart. */}
          {signals.map((item, index) => (
            <SignalRow key={item.recommendation_id || `${item.category}-${index}`} item={item} showDivider={index > 0} />
          ))}
        </div>
      ) : (
        <p className="text-sm mt-2" style={{ color: "var(--color-text-muted)" }}>
          Open this league to see your Next Move.
        </p>
      )}

      <Link
        href={`/dashboard/${encodeURIComponent(league.league_id)}?name=${encodeURIComponent(league.league_name)}`}
        className="self-start text-sm font-bold mt-3"
        style={{ color: "var(--color-accent)" }}
      >
        Open {league.league_name} Dashboard →
      </Link>
    </article>
  );
}

/**
 * Placeholder for a saved league whose row is still loading (progressive
 * Portfolio — see lib/portfolioProgress.ts). Shaped like
 * PortfolioLeagueCard (avatar + title/metadata, a few signal lines, the
 * Dashboard link) so swapping the real card in doesn't visibly jump the
 * page. Reuses the shared .pqv-skeleton-line shimmer rather than a new
 * loading treatment. The league name is real (it comes from the index), so
 * it's shown instead of a bar.
 */
function PortfolioLeagueSkeleton({ league }: { league: PortfolioSavedLeague }) {
  return (
    <article className="glass-surface flex flex-col p-4" aria-busy="true">
      <span className="sr-only">Loading {league.league_name}…</span>
      <div className="flex items-start gap-2" aria-hidden="true">
        <SkeletonBlock width={32} height={32} radius="var(--radius-pill)" />
        <div className="flex flex-col gap-2 min-w-0 flex-1">
          <h3 style={{ font: "var(--font-card-title)", color: "var(--color-text-muted)" }}>{league.league_name}</h3>
          <SkeletonBlock width="35%" height={12} />
        </div>
      </div>
      <div className="flex flex-col gap-3 mt-4" aria-hidden="true">
        <SkeletonBlock width="85%" height={14} />
        <SkeletonBlock width="70%" height={12} />
        <SkeletonBlock width="80%" height={14} />
        <SkeletonBlock width="60%" height={12} />
      </div>
      <SkeletonBlock width="45%" height={14} className="mt-4" />
    </article>
  );
}

/** "Add a league" (tap-depth audit #4): Portfolio is the multi-league
 * landing page and has no header league switcher, so this is the same
 * /connect-league route the switcher's "+ Add another league" row uses.
 * Only on the Premium views. A free account sees the upsell card instead,
 * which is already its upgrade path past the one-league cap. */
function AddLeagueLink() {
  return (
    <Link href="/connect-league" className="self-start text-sm font-bold mt-1" style={{ color: "var(--color-accent)" }}>
      + Add a league
    </Link>
  );
}

export function PortfolioContent({
  data,
  order,
  pending = [],
}: {
  data: PortfolioResponse;
  /** Saved-league order (progressive loading); defaults to data.leagues' own order. */
  order?: string[];
  /** Saved leagues whose row hasn't arrived yet — rendered as skeleton cards in place. */
  pending?: PortfolioSavedLeague[];
}) {
  const [removedIds, setRemovedIds] = useState<string[]>([]);
  const [busyLeagueId, setBusyLeagueId] = useState<string | null>(null);
  const [view, setView] = useState<"leagues" | "exposure">("leagues");
  const allFailedLeagues = data.failed_leagues.filter((league) => !removedIds.includes(league.league_id));
  const draftingLeagues = allFailedLeagues.filter((league) => league.reason === "empty_roster");
  const espnLeagues = allFailedLeagues.filter((league) => league.reason === "espn_not_supported");
  const failedLeagues = allFailedLeagues.filter(
    (league) => league.reason !== "empty_roster" && league.reason !== "espn_not_supported",
  );

  const removeFailedLeague = (leagueId: string) => {
    setBusyLeagueId(leagueId);
    api
      .removeSavedLeague(leagueId)
      .then((result) => {
        if (result.ok) setRemovedIds((prev) => [...prev, leagueId]);
      })
      .finally(() => setBusyLeagueId(null));
  };

  if (!data.is_premium) {
    return (
      <PremiumUpsellCard
        kicker="Portfolio"
        upsell={data.upsell}
        fallbackTitle="See every league at a glance"
        fallbackBody="Portfolio is a Premium feature — free accounts keep one saved league, so there's nothing to aggregate yet. Upgrade to Premium to save every league you're in and see your record, rank, and top need or opportunity across all of them in one place."
      />
    );
  }

  if (data.leagues.length === 0 && allFailedLeagues.length === 0 && pending.length === 0) {
    return (
      <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
        <header className="flex flex-col gap-1">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Portfolio
          </span>
          <h1 style={{ font: "var(--font-page-title)" }}>No saved leagues yet</h1>
          <AddLeagueLink />
        </header>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Save a league to see it here.
        </p>
      </main>
    );
  }

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Portfolio
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Your leagues</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Standing, record, and top need per league.
        </p>
        <AddLeagueLink />
      </header>

      <PillRow
        options={[
          { label: "Leagues", value: "leagues" },
          { label: "Exposure", value: "exposure" },
        ]}
        active={view}
        onSelect={(value) => setView(value as "leagues" | "exposure")}
      />

      {view === "exposure" ? (
        <PortfolioExposureView lens={data.lens} />
      ) : (
        <>
      {draftingLeagues.length > 0 ? <DraftingLeaguesNote leagues={draftingLeagues} /> : null}

      {espnLeagues.length > 0 ? <EspnLeaguesNote leagues={espnLeagues} /> : null}

      {failedLeagues.length > 0 ? (
        <FailedLeaguesNote leagues={failedLeagues} busyLeagueId={busyLeagueId} onRemove={removeFailedLeague} />
      ) : null}

      {data.leagues.length === 0 && pending.length === 0 && failedLeagues.length > 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          None of your saved leagues could be loaded right now. Try again in a moment.
        </p>
      ) : data.leagues.length > 0 || pending.length > 0 ? (
        <div className="flex flex-col gap-4">
          {cardSlots(data.leagues, pending, order).map((slot) =>
            slot.kind === "league" ? (
              <PortfolioLeagueCard key={slot.league.league_id} league={slot.league} />
            ) : (
              <PortfolioLeagueSkeleton key={slot.league.league_id} league={slot.league} />
            ),
          )}
        </div>
      ) : null}
        </>
      )}
    </main>
  );
}

type CardSlot = { kind: "league"; league: PortfolioLeague } | { kind: "pending"; league: PortfolioSavedLeague };

/** Loaded cards and still-loading skeletons, in saved-league order (so a
 * card never jumps position when an earlier league finishes later). */
function cardSlots(leagues: PortfolioLeague[], pending: PortfolioSavedLeague[], order?: string[]): CardSlot[] {
  if (!order) {
    return [
      ...leagues.map((league): CardSlot => ({ kind: "league", league })),
      ...pending.map((league): CardSlot => ({ kind: "pending", league })),
    ];
  }
  const loaded = new Map(leagues.map((league) => [league.league_id, league]));
  const waiting = new Map(pending.map((league) => [league.league_id, league]));
  const slots: CardSlot[] = [];
  for (const leagueId of order) {
    const league = loaded.get(leagueId);
    if (league) {
      slots.push({ kind: "league", league });
      loaded.delete(leagueId);
      continue;
    }
    const placeholder = waiting.get(leagueId);
    if (placeholder) slots.push({ kind: "pending", league: placeholder });
  }
  // Anything not named in `order` still renders rather than vanishing.
  for (const league of loaded.values()) slots.push({ kind: "league", league });
  return slots;
}
