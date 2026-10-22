"use client";

import { useState } from "react";

import type { CommunityTradeItem } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { VerdictCallout } from "@/components/VerdictCallout";
import { toCommunityTradeAssets, formatCommunityTradeDate } from "@/lib/communityTradesPresentation";
import { verdictDetailText, verdictToneColorVar } from "@/lib/tradeHistoryPresentation";

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
            className="flex items-center gap-1 px-2 py-1 text-xs font-bold"
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

  return (
    <article className="glass-surface flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col min-w-0">
          <h3 style={{ font: "var(--font-card-title)" }}>Team A traded with Team B</h3>
          {date ? (
            <span className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
              {date}
            </span>
          ) : null}
        </div>
      </div>

      <VerdictCallout color={verdictToneColorVar(item.verdict)} label={item.verdict_label} detail={detailText} />

      <div className="grid grid-cols-2 gap-4 mt-1">
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
    </article>
  );
}

export function CommunityTradesContent({
  trades,
  reactionEmoji,
  optedOut,
  onReact,
  onToggleOptOut,
}: {
  trades: CommunityTradeItem[];
  reactionEmoji: string[];
  optedOut: boolean;
  onReact: (outcomeId: string, emoji: string, active: boolean) => void;
  onToggleOptOut: (nextOptedOut: boolean) => void;
}) {
  const [togglingOptOut, setTogglingOptOut] = useState(false);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-2">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Community
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Craziest trades this week</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Real confirmed trades from other users&apos; leagues — always shown as &quot;Team A&quot; and &quot;Team
          B&quot;, never a real team or user name. Flagged here because our own trade-grading system found an
          unexpectedly good or bad outcome once the trade had a few weeks to play out, the same system behind your
          own Trade History.
        </p>
        <div className="flex items-center justify-between gap-3 mt-2 p-3" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            I don&apos;t want MY trades to appear in this feed
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={optedOut}
            disabled={togglingOptOut}
            onClick={() => {
              setTogglingOptOut(true);
              Promise.resolve(onToggleOptOut(!optedOut)).finally(() => setTogglingOptOut(false));
            }}
            className="px-2.5 py-1 text-xs font-bold"
            style={{
              border: "var(--border-width-default) solid var(--color-border)",
              color: optedOut ? "var(--color-danger)" : "var(--color-success)",
            }}
          >
            {optedOut ? "Opted out" : "Opted in"}
          </button>
        </div>
      </header>

      {trades.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No standout trades yet. Check back once more confirmed trades across the app have had a few weeks to play
          out.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {trades.map((item) => (
            <CommunityTradeCard key={item.id} item={item} reactionEmoji={reactionEmoji} onReact={onReact} />
          ))}
        </div>
      )}
    </main>
  );
}
