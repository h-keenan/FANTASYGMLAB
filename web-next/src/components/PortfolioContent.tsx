import Link from "next/link";

import type { BriefingItem, PortfolioFailedLeague, PortfolioLeague, PortfolioResponse } from "@/lib/api";
import { categoryColorVar, categoryLabel } from "@/lib/portfolioPresentation";
import { BriefingItemPlayers } from "@/components/BriefingItemPlayers";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { formatRank } from "@/components/SnapshotTile";
import { TeamAvatar } from "@/components/TeamAvatar";

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

function SignalRow({ item }: { item: BriefingItem }) {
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

  return (
    <div className="flex flex-col gap-1.5 mt-2">
      <div className="flex items-start gap-2">
        <span
          className="px-1.5 py-0.5 text-xs font-extrabold uppercase whitespace-nowrap"
          style={{
            borderRadius: "var(--radius-pill)",
            background: `color-mix(in srgb, ${color} 15%, transparent)`,
            color,
            letterSpacing: "var(--letter-spacing-badge)",
          }}
        >
          {label}
        </span>
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
      </div>
      {/* coridian_, 2026-10-18, screenshot: "this portfolio looks terrible,
          with zero player PFPs. These need to have the compact player cards
          that we were supposed to make" — every signal here was a
          pipe-separated text dump of player names with no identity at all.
          Same BriefingItemPlayers chips Today's Game Plan already uses. */}
      <BriefingItemPlayers item={item} sourceLabel="Portfolio" />
    </div>
  );
}

function FailedLeaguesNote({ leagues }: { leagues: PortfolioFailedLeague[] }) {
  const names = leagues.map((league) => league.league_name).join(", ");
  const plural = leagues.length === 1 ? "league" : "leagues";
  return (
    <div
      className="px-3 py-2 text-sm"
      style={{ background: "var(--color-warning-soft)", border: "var(--border-width-default) solid var(--color-warning)" }}
    >
      {`Couldn't load ${leagues.length} ${plural} right now: ${names}. Everything else below is up to date.`}
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
    <article
      className="flex flex-col p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        boxShadow: "var(--shadow-card)",
      }}
    >
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
          {signals.map((item, index) => (
            <SignalRow key={item.recommendation_id || `${item.category}-${index}`} item={item} />
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

export function PortfolioContent({ data }: { data: PortfolioResponse }) {
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

  if (data.leagues.length === 0 && data.failed_leagues.length === 0) {
    return (
      <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
        <header className="flex flex-col gap-1">
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Portfolio
          </span>
          <h1 style={{ font: "var(--font-page-title)" }}>No saved leagues yet</h1>
        </header>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Save a league to see your standing, record, and top need or opportunity across every league here.
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
          Your standing, record, and top need or opportunity across every saved league.
        </p>
      </header>

      {data.failed_leagues.length > 0 ? <FailedLeaguesNote leagues={data.failed_leagues} /> : null}

      {data.leagues.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          None of your saved leagues could be loaded right now. Try again in a moment.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {data.leagues.map((league) => (
            <PortfolioLeagueCard key={league.league_id} league={league} />
          ))}
        </div>
      )}
    </main>
  );
}
