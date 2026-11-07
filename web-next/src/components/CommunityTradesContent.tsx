"use client";

import { InfoTip } from "@/components/InfoTip";
import { PageTitle } from "@/components/PageTitle";
import { EmptyState } from "@/components/EmptyState";
import { LeagueLinkStep } from "@/components/LeagueLinkStep";
import { useState } from "react";

import type { CommunityTradeItem } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { VerdictCallout } from "@/components/VerdictCallout";
import { toCommunityTradeAssets, formatCommunityTradeDate } from "@/lib/communityTradesPresentation";
import { verdictDetailText, verdictToneColorVar } from "@/lib/tradeHistoryPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { SharedTradesFeed } from "@/components/SharedTradesFeed";
import type { SharedCommunityTrade } from "@/lib/api";
import { Toggle } from "@/components/Toggle";
import { AccentCard } from "@/components/AccentCard";
import { AnonymousTeamPair, NetEdgeBar } from "@/components/TradeOutcomeHeader";

/**
 * Social/community layer (docs/roadmap.md), coridian_ 2026-10-19: an
 * anonymized feed of real confirmed trades pulled across ALL users' real
 * leagues — never real team/user identity, always "Team A"/"Team B". See
 * modules/community_trades.py's module docstring for the full
 * anonymization design this renders; this component never receives
 * anything identity-adjacent in the first place (no user_id/league_id/
 * partner_team_name field exists anywhere on CommunityTradeItem).
 *
 * "Interesting" reuses modules.trade_outcome_results' existing verdict/
 * confidence computation (worked_out/didnt_pan_out at "high" confidence) —
 * the exact same badge/detail-text presentation Trade History
 * (TradeHistoryContent.tsx) already uses, imported directly rather than
 * duplicated.
 *
 * Reactions are emoji-only, a fixed small set, no comments/replies —
 * deliberately so this feature needs no moderation layer. No existing
 * emoji-reaction UI precedent exists anywhere else in this app (checked
 * before building this), so this is a fresh, minimal "tap to react, see a
 * count" row.
 */

function ReactionRow({
  item,
  reactionEmoji,
  onReact,
}: {
  item: CommunityTradeItem;
  reactionEmoji: string[];
  onReact: (emoji: string, active: boolean) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5 pt-1">
      {reactionEmoji.map((emoji) => {
        const count = item.reactions[emoji] ?? 0;
        const active = item.my_reactions.includes(emoji);
        return (
          <button
            key={emoji}
            type="button"
            aria-pressed={active}
            onClick={() => onReact(emoji, active)}
            className="flex items-center justify-center gap-1 px-3 min-h-[var(--touch-target-min)] min-w-[var(--touch-target-min)] text-xs font-bold"
            style={{
              borderRadius: "var(--radius-pill)",
              border: `var(--border-width-default) solid ${active ? "var(--color-accent)" : "var(--color-border)"}`,
              background: active ? "color-mix(in srgb, var(--color-accent) 15%, transparent)" : "transparent",
              color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
            }}
          >
            <span>{emoji}</span>
            {count > 0 ? <span>{count}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

function CommunityTradeCard({
  item,
  reactionEmoji,
  onReact,
}: {
  item: CommunityTradeItem;
  reactionEmoji: string[];
  onReact: (outcomeId: string, emoji: string, active: boolean) => void;
}) {
  const date = formatCommunityTradeDate(item.occurred_at);
  const detailText = verdictDetailText({
    status: "ready",
    reason: "",
    verdict: item.verdict,
    verdict_label: item.verdict_label,
    confidence: item.confidence,
    days_since_trade: null,
    production: item.production,
    value: item.value,
  });

  const accent = verdictToneColorVar(item.verdict);
  const netPct = item.value?.net_delta_pct ?? null;

  return (
    <AccentCard accent={accent} className="gap-2">
      <div className="flex items-start gap-3">
        <AnonymousTeamPair color={accent} />
        <div className="flex flex-col min-w-0">
          <h3 style={{ font: "var(--font-card-title)" }}>Team A traded with Team B</h3>
          {date ? (
            <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              {date}
            </span>
          ) : null}
        </div>
      </div>

      <VerdictCallout color={accent} label={item.verdict_label} detail={detailText} />
      {netPct !== null ? (
        <NetEdgeBar
          netPct={netPct}
          label={
            <>
              <span>Team B ahead</span>
              <span>Team A ahead</span>
            </>
          }
        />
      ) : null}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-1">
        <ExchangeSide label="Team A sent" dotColor="var(--color-danger)" assets={toCommunityTradeAssets(item.send)} />
        <ExchangeSide
          label="Team A received"
          dotColor="var(--color-success)"
          assets={toCommunityTradeAssets(item.receive)}
        />
      </div>

      <ReactionRow
        item={item}
        reactionEmoji={reactionEmoji}
        onReact={(emoji, active) => onReact(item.id, emoji, active)}
      />
    </AccentCard>
  );
}

export function CommunityTradesContent({
  trades,
  reactionEmoji,
  optedOut,
  onReact,
  onToggleOptOut,
  shared,
}: {
  trades: CommunityTradeItem[];
  reactionEmoji: string[];
  optedOut: boolean;
  onReact: (outcomeId: string, emoji: string, active: boolean) => void;
  onToggleOptOut: (nextOptedOut: boolean) => void;
  /** Opt-in shared trades; omitted or available=false hides the section. */
  shared?: {
    available: boolean;
    trades: SharedCommunityTrade[];
    onDelete: (id: string) => void | Promise<unknown>;
    onReport: (id: string) => void | Promise<unknown>;
  };
}) {
  const [togglingOptOut, setTogglingOptOut] = useState(false);

  return (
    <main className="flex-1 flex flex-col gap-3 px-4 py-3 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-2">
        <PageTitle page="Community" />
        <InfoTip label="Craziest trades this week: how this works">
          Real confirmed trades from other users&apos; leagues — always shown as &quot;Team A&quot; and &quot;Team
          B&quot;, never a real team or user name. Flagged here because our own trade-grading system found an
          unexpectedly good or bad outcome once the trade had a few weeks to play out, the same system behind your
          own Trade History.
        </InfoTip>
        <AccentCard accent="var(--color-information)" compact className="mt-1">
        <div className="flex items-center justify-between gap-3">
          <span className="flex items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0" style={{ color: "var(--color-information)" }}>
              <rect x="3.5" y="7" width="9" height="6.5" rx="1.5" />
              <path d="M5.5 7V5a2.5 2.5 0 015 0v2" />
            </svg>
            I don&apos;t want MY trades to appear in this feed
          </span>
          <Toggle
            tone="danger"
            checked={optedOut}
            disabled={togglingOptOut}
            stateLabel={optedOut ? "Opted out" : "Opted in"}
            onChange={(next) => {
              setTogglingOptOut(true);
              Promise.resolve(onToggleOptOut(next)).finally(() => setTogglingOptOut(false));
            }}
          />
        </div>
        </AccentCard>
      </header>

      {trades.length === 0 ? (
        <EmptyState title="No standout trades yet." subtitle="Check back once more confirmed trades across the app have had a few weeks to play out.">
          <div className="mt-2">
            <LeagueLinkStep step="trade-analyzer" label="Analyze a trade of your own" pickLabel="Pick a league to analyze a trade" />
          </div>
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-4">
          {trades.map((item) => (
            <CommunityTradeCard key={item.id} item={item} reactionEmoji={reactionEmoji} onReact={onReact} />
          ))}
        </div>
      )}
      {shared ? <SharedTradesFeed {...shared} /> : null}
      <ValuesCredit />
    </main>
  );
}
