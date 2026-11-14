"use client";

import { useMemo, useState, type ReactNode } from "react";

import { InsightLink } from "@/components/ui/InsightLink";
import type { InsightKey } from "@/lib/insightLinks";

import type { PositionNeedGroup, DraftCard, DraftCenterResponse, DraftPickAsset } from "@/lib/api";
import { PickRow, draftPickRowProps } from "@/components/PickRow";
import { PickGroupList } from "@/components/PickGroupList";
import { DraftScoutingTab } from "@/components/DraftScoutingTab";
import { pickProvenance } from "@/lib/pickGroups";
import { PillRow } from "@/components/PillRow";
import { CompactModule } from "@/components/ui/CompactModule";
import { formatRank } from "@/components/SnapshotTile";
import { SnapshotTileGlyph, type SnapshotGlyphName } from "@/components/SnapshotTileGlyph";
import { AccentCard } from "@/components/AccentCard";
import { EmptyState } from "@/components/EmptyState";
import { IconRow } from "@/components/IconRow";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueRing } from "@/components/ValueRing";
import { percentileFromRank } from "@/lib/leagueRankingsPresentation";
import {
  POSTURE_REASON_MESSAGE,
  draftToneColor,
  leagueSizeFromPicks,
  visibleDraftPicks,
  type PickScope,
} from "@/lib/draftCenterPresentation";
import { ValuesCredit } from "@/components/ValuesCredit";
import { StructuredRow, StructuredRowList } from "@/components/ui/StructuredRow";
import { TeamAvatar } from "@/components/TeamAvatar";
import { cardRows, signalPills, signalSpokenLabel, strategyTone, type DraftSignalRow } from "@/lib/draftSignals";
import { PageTitle } from "@/components/PageTitle";

/**
 * Ports mobile's DraftCenterScreen.tsx (the GM_TOOLS "Draft Center" nav
 * destination) for Revision 14 — same two endpoints, same scope: your own
 * draft posture, pick values with a My Picks/League toggle, and the
 * league-wide decision/partner cards. The live draft board lives on the
 * Live Draft page and prospect scouting on College Scouting.
 */
export type DraftCenterTab = "overview" | "picks" | "scouting";

export function parseDraftCenterTab(value: string | null | undefined): DraftCenterTab {
  return value === "picks" || value === "scouting" ? value : "overview";
}

export function DraftCenterContent({
  leagueId,
  leagueName,
  data,
  picks,
  myRosterId,
  initialTab = "overview",
  onTabChange,
  needGroups = null,
}: {
  /** With it, the posture cells link to the rankings / plan that explain them. */
  leagueId?: string;
  leagueName: string;
  data: DraftCenterResponse;
  picks: DraftPickAsset[];
  myRosterId: string;
  initialTab?: DraftCenterTab;
  onTabChange?: (tab: DraftCenterTab) => void;
  needGroups?: PositionNeedGroup[] | null;
}) {
  const league = leagueId ? { id: leagueId, name: leagueName } : null;
  const [tab, setTab] = useState<DraftCenterTab>(initialTab);
  // The GM orb can pick another Draft Center tab while this page is mounted.
  const [seenInitialTab, setSeenInitialTab] = useState(initialTab);
  if (initialTab !== seenInitialTab) {
    setSeenInitialTab(initialTab);
    setTab(initialTab);
  }
  // Nothing to scope to without a resolved roster — don't strand the user
  // on an empty "My Picks" tab they can't fill, same guard mobile's screen
  // applies to its own initial pickScope.
  const [pickScope, setPickScope] = useState<PickScope>(myRosterId ? "mine" : "league");

  const visiblePicks = useMemo(
    () => visibleDraftPicks(picks, pickScope, myRosterId),
    [picks, pickScope, myRosterId],
  );

  const myPicks = useMemo(
    () => (myRosterId ? picks.filter((pick) => pick.owner_roster_id === myRosterId) : []),
    [picks, myRosterId],
  );
  const leagueSize = useMemo(() => leagueSizeFromPicks(picks), [picks]);

  const { posture, posture_reason: postureReason, decision_cards: decisionCards, partner_cards: partnerCards } = data;

  return (
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page="Draft Center" leagueName={leagueName} />
      </header>

      <PillRow
        sticky
        fullWidth
        ariaLabel="Draft Center section"
        options={[
          { label: "Overview", value: "overview", glyph: "overview" },
          { label: "Picks", value: "picks", glyph: "picks" },
          { label: "Scouting", value: "scouting", glyph: "scouting" },
        ]}
        active={tab}
        onSelect={(value) => {
          const next = parseDraftCenterTab(value);
          setTab(next);
          onTabChange?.(next);
        }}
      />

      {tab === "overview" ? (
      <CompactModule
        id="draft.posture"
        title="Your Draft Posture"
        persist={false}
        defaultOpen
        tone={posture ? "accent" : "muted"}
        accent={posture ? draftToneColor(posture.tone) : undefined}
        parts={
          posture
            ? [
                { key: "label", text: posture.label, strong: true },
                { key: "firsts", text: `${posture.first_rounders ?? 0} firsts` },
                { key: "picks", text: `${posture.pick_count ?? 0} picks` },
                posture.draft_capital_rank ? { key: "cap", text: `Capital ${formatRank(posture.draft_capital_rank, posture.draft_capital_rank_tied)}` } : null,
              ]
            : [{ key: "none", text: POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now.", tone: "muted" }]
        }
      >
        {posture ? (
          <AccentCard accent={draftToneColor(posture.tone)} as="div">
            <div className="flex flex-wrap items-center gap-2">
              <ToneBadge label={posture.label} color={draftToneColor(posture.tone)} wrap />
              <span className="ml-auto flex flex-wrap gap-1.5">
                <ToneBadge label={`${posture.first_rounders ?? 0} firsts`} color="var(--color-premium)" />
                <ToneBadge label={`${posture.pick_count ?? 0} picks`} color="var(--color-information)" />
              </span>
            </div>
            <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              {posture.note}
            </p>
            <div className="grid grid-cols-1 min-[420px]:grid-cols-3 gap-2">
              <CapitalCell
                insight="draft_capital"
                league={league}
                label="Draft Capital"
                rank={posture.draft_capital_rank}
                tied={posture.draft_capital_rank_tied}
                leagueSize={leagueSize}
                note={posture.draft_capital != null ? `${Math.round(posture.draft_capital)} total capital` : undefined}
                glyph="franchise"
              />
              <CapitalCell
                insight="future_capital"
                league={league}
                label="Future Capital"
                rank={posture.future_draft_capital_rank}
                tied={posture.future_draft_capital_rank_tied}
                leagueSize={leagueSize}
                note={
                  posture.future_draft_capital != null
                    ? `${Math.round(posture.future_draft_capital)} beyond this draft`
                    : undefined
                }
                glyph="bench"
              />
              <MaybeInsight insight="strategy" league={league} spoken={["Strategy", posture.strategy_display]}>
              <div className="glass-surface flex flex-col gap-1 p-3 min-w-0">
                <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
                  <SnapshotTileGlyph name="power" />
                  Strategy
                </span>
                <span style={{ font: "var(--type-primary-metric)", color: "var(--color-text-primary)" }}>
                  {posture.strategy_display || "—"}
                </span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {`Roster Power ${formatRank(posture.power_rank, posture.power_rank_tied)} · Franchise ${formatRank(
                    posture.franchise_rank,
                    posture.franchise_rank_tied,
                  )}`}
                </span>
              </div>
              </MaybeInsight>
            </div>
          </AccentCard>
        ) : (
          <EmptyState title={POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now."} />
        )}
      </CompactModule>
      ) : null}

      {tab === "picks" ? (
        <CompactModule
          id="draft.pick-values"
          title="Pick Values"
          persist={false}
          defaultOpen
          parts={[
            { key: "n", text: `${visiblePicks.length} ${pickScope === "league" ? "league " : ""}pick${visiblePicks.length === 1 ? "" : "s"}`, strong: true },
            visiblePicks[0] ? { key: "first", text: [visiblePicks[0].season, visiblePicks[0].round ? `Rd ${visiblePicks[0].round}` : null].filter(Boolean).join(" ") || "Top pick listed first" } : null,
            { key: "scope", text: pickScope === "mine" ? "Your picks" : "Whole league", tone: "muted" },
          ]}
        >
          {myRosterId ? (
            <PillRow
              options={[
                { label: "My Picks", value: "mine" },
                { label: "League", value: "league" },
              ]}
              active={pickScope}
              onSelect={(value) => setPickScope(value as PickScope)}
            />
          ) : null}
          {visiblePicks.length > 0 ? (
            <PickGroupList
              picks={visiblePicks}
              renderPick={(pick) => {
                const row = draftPickRowProps(pick, false);
                const context = [pickProvenance(pick, { showOwner: pickScope === "league" }), pick.pick_tier, pick.projected_pick_range]
                  .filter(Boolean)
                  .join(" · ");
                return <PickRow {...row} pickNo={undefined} context={context} showDivider />;
              }}
            />
          ) : (
            <EmptyState
              title={
                pickScope === "mine"
                  ? "You don't hold any tracked picks in this league right now."
                  : "No draft pick assets available for this league yet."
              }
            />
          )}
        </CompactModule>
      ) : null}

      {tab === "overview" ? (
        <>
          <DraftCardSection id="decision-signals-heading" title="League Draft Decision Signals" cards={decisionCards} myRosterId={myRosterId} />
          <DraftCardSection id="partner-discovery-heading" title="Draft Partner Discovery" cards={partnerCards} myRosterId={myRosterId} />
        </>
      ) : null}

      {tab === "scouting" ? <DraftScoutingTab myPicks={myPicks} needGroups={needGroups} /> : null}

      <ValuesCredit />
    </main>
  );
}

function ringTone(percent: number): "low" | "mid" | "high" {
  return percent < 34 ? "low" : percent < 67 ? "mid" : "high";
}

/** One capital metric: rank as the headline, a percentile ring when the league size is known. */
function MaybeInsight({ insight, league, spoken, children }: { insight: InsightKey; league: { id: string; name: string } | null; spoken: ReadonlyArray<string | null | undefined>; children: ReactNode }) {
  if (!league) return <>{children}</>;
  return (
    <InsightLink insight={insight} league={league} spoken={spoken}>
      {children}
    </InsightLink>
  );
}

function CapitalCell({
  insight,
  league,
  label,
  rank,
  tied,
  leagueSize,
  note,
  glyph,
}: {
  insight: InsightKey;
  league: { id: string; name: string } | null;
  label: string;
  rank: number | null;
  tied: boolean;
  leagueSize: number | null;
  note?: string;
  glyph: SnapshotGlyphName;
}) {
  const percentile = leagueSize ? percentileFromRank(rank, leagueSize) : null;
  const percent = percentile === null ? null : Math.round(percentile);
  return (
    <MaybeInsight insight={insight} league={league} spoken={[label, formatRank(rank, tied), note]}>
    <div className="glass-surface flex items-center gap-2 p-3 min-w-0" style={rank === 1 ? { borderColor: "var(--color-premium)" } : undefined}>
      <div className="flex flex-col gap-1 min-w-0 flex-1">
        <span className="flex items-center gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          <SnapshotTileGlyph name={glyph} />
          {label}
        </span>
        <span style={{ font: "var(--type-primary-metric)", color: rank === 1 ? "var(--color-premium)" : "var(--color-text-primary)" }}>
          {formatRank(rank, tied)}
        </span>
        {note ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {note}
          </span>
        ) : null}
      </div>
      {percent !== null ? (
        <ValueRing
          percent={percent}
          tone={ringTone(percent)}
          display={`${percent}`}
          ariaLabel={`${label} percentile ${percent}`}
          size="sm"
        />
      ) : null}
    </div>
    </MaybeInsight>
  );
}

/**
 * League Draft Decision Signals / Draft Partner Discovery: an AccentCard per
 * card, railed and badged in the tone's semantic color (same vocabulary as the
 * `.tone-*` CSS classes), with the items as icon rows.
 */
function DraftCardSection({ id, title, cards, myRosterId }: { id: string; title: string; cards: DraftCard[]; myRosterId: string }) {
  if (cards.length === 0) return null;
  return (
    <CompactModule
      id={`draft.${id}`}
      title={title}
      persist={false}
      parts={[
        { key: "n", text: `${cards.length} signal${cards.length === 1 ? "" : "s"}`, strong: true },
        { key: "labels", text: cards.slice(0, 2).map((card) => card.label).join(", ") },
      ]}
    >
      <div className="flex flex-col gap-3">
        {cards.map((card) => {
          const color = draftToneColor(card.tone);
          return (
            <AccentCard key={card.label} accent={color} as="div">
              <ToneBadge label={card.label} color={color} wrap />
              <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                {card.title}
              </p>
              {(() => {
                // Schema 2 responses carry structured rows; a response from before that
                // (or a cached one) still renders the legacy strings.
                const rows = cardRows(card);
                if (rows) {
                  return (
                    <StructuredRowList
                      ariaLabel={card.label}
                      items={rows}
                      renderRow={(row) => <DraftSignalRowView row={row} mine={Boolean(myRosterId) && row.team_id === myRosterId} />}
                    />
                  );
                }
                return card.items.length > 0 ? (
                  <div className="flex flex-col gap-2">
                    {card.items.map((item, index) => (
                      <IconRow key={index} icon="arrow" color={color}>
                        {item}
                      </IconRow>
                    ))}
                  </div>
                ) : null;
              })()}
            </AccentCard>
          );
        })}
      </div>
    </CompactModule>
  );
}

const SIGNAL_TONE_COLOR = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  accent: "var(--color-accent)",
  neutral: "var(--color-text-secondary)",
} as const;

/**
 * One Draft Center signal row: crest, team, direction chip, rank pills, one
 * short reason. Tapping it opens the full sentence and the numbers behind it.
 */
function DraftSignalRowView({ row, mine }: { row: DraftSignalRow; mine: boolean }) {
  return (
    <StructuredRow
      lead={<TeamAvatar avatarUrl={row.avatar_url} name={row.team_name} size={36} />}
      title={row.team_name}
      chip={{ label: row.strategy_display, color: SIGNAL_TONE_COLOR[strategyTone(row.strategy)] }}
      pills={signalPills(row)}
      reason={row.reason_short}
      highlight={mine}
      spoken={signalSpokenLabel(row)}
      detailTitle={row.team_name}
      detail={
        <>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {row.reason_long}
          </p>
          {row.evidence.length > 0 ? (
            <dl className="flex flex-col" aria-label="Evidence">
              {row.evidence.map((entry) => (
                <div
                  key={entry.key}
                  className="flex items-center justify-between gap-3 py-2"
                  style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
                >
                  <dt className="text-sm" style={{ color: "var(--color-text-muted)" }}>
                    {entry.label}
                  </dt>
                  <dd className="text-sm font-extrabold">{entry.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
        </>
      }
    />
  );
}
