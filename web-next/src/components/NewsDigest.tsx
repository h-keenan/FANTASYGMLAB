"use client";

import { useMemo, useState, type ReactNode } from "react";

import { PageControl } from "@/components/ui/PageControls";
import { FilterSheet } from "@/components/ui/FilterSheet";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerName } from "@/components/PlayerName";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { PlayerAccordionRow, usePlayerAccordion } from "@/components/ui/PlayerAccordionRow";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { ROSTER_RELATIONSHIP_LABEL, relativeTime } from "@/lib/alertsPresentation";
import {
  NEWS_FILTERS,
  buildNewsDigest,
  newsHeadlineChip,
  newsLeaguePreview,
  type DigestItem,
  type NewsDigestRow,
  type NewsFilterKey,
  type NewsStripPlayer,
  type NewsVerdictTone,
} from "@/lib/newsDigest";

/**
 * The roster-first News digest (docs/audits/ui-pass-3/news-options.html: V1 digest + the V2 player strip). Your players'
 * items first, each a shared PlayerAccordionRow (avatar, "J. Surname", headline, verdict chip; tap to expand "what it
 * means"), a PFP strip that filters to one player, and the league-wide feed as a collapsed CompactModule whose body is
 * the page's existing grouped feed (`feed`). Logic: lib/newsDigest.ts. Mobile twin: components/NewsDigest.tsx.
 */

const TONE: Record<NewsVerdictTone, string> = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
};

/** The roster PFP strip as a collapsed module (UI audit batch H): one tap to open, so the first player row sits right under the control row. */
function RosterStrip({ players, active, onPick }: { players: NewsStripPlayer[]; active: string | null; onPick: (key: string | null) => void }) {
  const picked = players.find((p) => p.key === active);
  return (
    <CompactModule
      id="news.strip"
      title={`Your roster · ${players.length} with news`}
      label="Your roster"
      parts={[{ key: "who", text: picked ? `Showing ${picked.name}` : players.slice(0, 3).map((p) => p.name).join(", ") + (players.length > 3 ? ` +${players.length - 3}` : ""), tone: "muted" }]}
      summaryWhenCollapsed
      testId="news-strip"
    >
      <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label="Filter news by player">
        {players.map((p) => {
          const on = p.key === active;
          return (
            <button
              key={p.key}
              type="button"
              aria-pressed={on}
              aria-label={`${p.name}, ${p.count} ${p.count === 1 ? "item" : "items"}`}
              onClick={() => onPick(on ? null : p.key)}
              className="flex w-[4.25rem] shrink-0 flex-col items-center gap-1 text-center"
              style={{ minHeight: "var(--touch-target-min)" }}
            >
              <span className="relative inline-flex rounded-full" style={{ boxShadow: on ? "0 0 0 2px var(--color-accent-strong)" : undefined, transition: "box-shadow 160ms ease" }}>
                <PlayerAvatar playerId={p.id} tier={p.tier} size={44} fallbackLabel={p.name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2)} />
                {p.unread ? (
                  <span aria-hidden="true" className="absolute -right-0.5 -top-0.5 rounded-full" style={{ width: 11, height: 11, background: "var(--color-accent-strong)", border: "2px solid var(--color-bg, #000)" }} />
                ) : null}
              </span>
              <PlayerName name={p.name} className="text-[0.6875rem] font-bold leading-tight" style={{ color: on ? "var(--color-accent)" : "var(--color-text-secondary)" }} />
            </button>
          );
        })}
      </div>
    </CompactModule>
  );
}

function DigestRow({ row, acc }: { row: NewsDigestRow; acc: ReturnType<typeof usePlayerAccordion> }) {
  const { openPlayer } = usePlayerQuickView();
  const { item, verdict } = row;
  const slot = item.roster_relationship;
  const time = relativeTime(item.published_ts);
  const meta = [
    slot ? { key: "slot", text: ROSTER_RELATIONSHIP_LABEL[slot], tone: slot === "starter" ? ("success" as const) : undefined } : null,
    item.source ? { key: "src", text: item.source } : null,
    time ? { key: "time", text: time } : null,
  ].filter((p): p is { key: string; text: string; tone: "success" | undefined } => Boolean(p));
  const name = item.matched_player ?? "Player";
  return (
    <PlayerAccordionRow
      mode="desk"
      player={{ id: item.matched_player_id ?? null, name, position: item.matched_player_position ?? null, team: item.matched_player_team ?? null, tier: item.matched_player_tier ?? null }}
      open={acc.isOpen(row.key)}
      onToggle={() => acc.toggle(row.key)}
      ariaLabel={`${name}: ${item.title ?? "news"}`}
      metaParts={meta}
      headline={item.title}
      trailingAction={<ToneBadge label={verdict.label} color={TONE[verdict.tone]} size="xs" testId="news-verdict" />}
      onOpenProfile={
        item.matched_player_id
          ? () => openPlayer({ player_id: item.matched_player_id as string, name, position: item.matched_player_position, team: item.matched_player_team, tier: item.matched_player_tier, sourceLabel: "News" })
          : undefined
      }
      testId="news-row"
    >
      <div className="flex flex-col gap-1">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>What it means</span>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{row.impact}</p>
        {item.summary ? <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{item.summary}</p> : null}
        {item.link ? (
          <a href={item.link} target="_blank" rel="noopener noreferrer" className="text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)", display: "inline-flex", alignItems: "center" }}>
            Read the article
          </a>
        ) : null}
      </div>
    </PlayerAccordionRow>
  );
}

export function NewsDigest({
  alerts,
  general,
  reasonNote,
  feed,
}: {
  /** Roster-matched alerts of the account's league; empty when there is none. */
  alerts: readonly DigestItem[];
  general: readonly DigestItem[];
  /** Why there is no roster news (no league linked, empty roster), shown instead of an empty list. */
  reasonNote?: string | null;
  /** The league-wide feed body for the given (filtered) items. */
  feed: (items: DigestItem[]) => ReactNode;
}) {
  const [filter, setFilter] = useState<NewsFilterKey>("all");
  const [playerKey, setPlayerKey] = useState<string | null>(null);
  const acc = usePlayerAccordion();
  const digest = useMemo(() => buildNewsDigest({ alerts, general, filter, playerKey }), [alerts, general, filter, playerKey]);
  const chip = newsHeadlineChip(digest);
  const hasRoster = alerts.length > 0;
  const preview = newsLeaguePreview(digest.league);
  const picked = digest.strip.find((p) => p.key === playerKey);
  return (
    <div className="flex flex-col gap-3" data-testid="news-digest">
      <PageControl>
        <FilterSheet
          title="Show"
          groups={[{ id: "filter", label: "News type", anyValue: "all", options: NEWS_FILTERS.map((f) => ({ value: f.key, label: f.label })) }]}
          values={{ filter: filter === "all" ? [] : [filter] }}
          onApply={(next) => setFilter((next.filter?.[0] ?? "all") as NewsFilterKey)}
          showChips={false}
          testId="news-filter"
        />
      </PageControl>
      {digest.strip.length > 0 ? <RosterStrip players={digest.strip} active={playerKey} onPick={setPlayerKey} /> : null}
      {digest.rows.length > 0 ? (
        <>
          <div className="flex items-center justify-between gap-2">
            <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
              {picked ? `${picked.name} · ${digest.rows.length} ${digest.rows.length === 1 ? "item" : "items"}` : `Your players · ${digest.rows.length}`}
            </span>
            {chip ? <ToneBadge label={chip} color="var(--color-accent)" size="xs" testId="news-headline-chip" /> : null}
          </div>
          <div className="flex flex-col">
            {digest.rows.map((row) => <DigestRow key={row.key} row={row} acc={acc} />)}
          </div>
        </>
      ) : (
        // One muted line, not a heading + paragraph (UI audit batch H): the league feed below is the first module.
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }} data-testid="news-roster-empty">
          {reasonNote ?? (hasRoster ? "No news on your players for this filter." : "No news on your players right now.")}
        </p>
      )}
      {digest.league.length > 0 ? (
        <CompactModule
          id="news.league"
          title={`Around the NFL · ${digest.league.length}`}
          label="Around the NFL"
          parts={[preview ? { key: "preview", text: preview, tone: "muted" } : null]}
          defaultOpen={digest.rows.length === 0}
          summaryWhenCollapsed
          testId="news-league-module"
        >
          {feed(digest.league)}
        </CompactModule>
      ) : null}
    </div>
  );
}
