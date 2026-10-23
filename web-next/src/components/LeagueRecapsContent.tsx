"use client";

import { EmptyState } from "@/components/EmptyState";
import { SectionHeading } from "@/components/SectionHeading";
import { useEffect, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import type {
  HistoryAsset,
  HistoryResponse,
  HistorySide,
  HistoryTransaction,
  RecapResponse,
  RecapStory,
  StorylineLeader,
  StorylineTeam,
  StorylinesResponse,
} from "@/lib/api";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { TeamAvatar } from "@/components/TeamAvatar";
import {
  FILTER_ALL,
  FILTER_TRADES,
  FILTER_WIRE,
  HISTORY_FILTERS,
  type RecapStoryGroup,
  buildRecapArchive,
  emptyFilterNote,
  formatHistoryWhen,
  gradeToneColorVar,
  groupRecapStories,
  historyDeepLinkLabel,
  historyFilterToPill,
  matchesHistoryFilter,
  pickLabel,
  recapCategoryColorVar,
  recapStoryCategory,
} from "@/lib/leagueRecapsPresentation";

/**
 * Ports modules/league_recaps_ui.py + modules/league_history_ui.py for
 * Revision 13 — the "League Recaps / History" nav destination (NOT the
 * League Rankings page; the two were disambiguated in app.py's own nav
 * rename). Fixes the exact "this page looks terrible" gap PR #1065 fixed
 * on Streamlit (coridian_, 2026-10-14): every story's own title and
 * headline metric now carries its category's color (modules/
 * league_recaps_styles.py's .dg-recap-story-- and .dg-recap-metric rules),
 * not just a thin left border on the lead story.
 *
 * Recaps reads the exact same GET .../recap endpoint mobile's RecapScreen
 * already calls. History is a thin wrapper (GET .../history) over the same
 * modules.league_history / modules.transaction_grades the Streamlit History
 * tab already used — no grading or recap logic duplicated here.
 *
 * Storylines (the page's third "Memory view" — season-long award cards:
 * Most Active, Trade Market Leader, Biggest Trade, Biggest FAAB, Most Picks
 * Acquired, Roster Turnover, Quietest Desk, Busiest Week, Most Moved Player;
 * modules/league_storylines_ui.py + modules/league_storylines.py) was
 * deferred in Revision 13 for having no mobile reference and no backing
 * endpoint. Re-investigated for Revision 15: mobile still has no Storylines
 * screen (its StorylineSummaryCard is an unrelated weekly-recap teaser, not
 * this season-long awards panel), so this is a direct, faithful port of the
 * Streamlit rendering straight off a new GET .../storylines endpoint (thin
 * wrapper over modules.league_storylines.build_league_storylines — no
 * award-selection logic duplicated here). Unlike Recaps' story cards,
 * Streamlit's Storylines cards have no category/color taxonomy at all
 * (modules/league_storylines_styles.py's .dg-ls-card is a single neutral
 * style) — this port does not force-fit Recaps' category color system onto
 * cards that were never categorized that way.
 */

type MemoryView = "Recaps" | "History" | "Storylines";

const MEMORY_VIEWS: MemoryView[] = ["Recaps", "History", "Storylines"];

function RecapStoryCard({
  story,
  lead,
  isFirstInGroup,
  onOpenHistory,
}: {
  story: RecapStory;
  lead: boolean;
  isFirstInGroup: boolean;
  onOpenHistory: (filter: string) => void;
}) {
  const accent = recapCategoryColorVar(recapStoryCategory(story.story_type));
  const deepLinkLabel = historyDeepLinkLabel(story);
  const identity = story.secondary_team
    ? story.primary_team
      ? `${story.primary_team} vs ${story.secondary_team}`
      : story.secondary_team
    : story.primary_team;

  const containerStyle = lead
    ? {
        background: "var(--color-surface-raised)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `var(--border-width-semantic) solid ${accent}`,
        boxShadow: "var(--shadow-card)",
        padding: "var(--space-md)",
      }
    : {
        borderTop: isFirstInGroup ? "none" : "var(--border-width-default) solid var(--color-border)",
        padding: isFirstInGroup ? "0" : "var(--space-sm) 0 0",
      };

  const body = (
    <>
      <h3
        className={`uppercase font-extrabold ${lead ? "text-lg" : "text-sm"}`}
        style={{ color: accent, letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {story.title}
      </h3>
      {identity ? (
        <p className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {identity}
        </p>
      ) : null}
      <p
        className="text-sm"
        style={{ color: lead ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}
      >
        {story.summary}
      </p>
      {story.metric_value ? (
        <div className="grid gap-0.5 mt-1">
          <span
            className="text-xs uppercase"
            style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
          >
            {story.metric_label || "Recorded"}
          </span>
          <strong className="text-lg font-extrabold" style={{ color: accent }}>
            {story.metric_value}
          </strong>
        </div>
      ) : null}
      {story.players?.length ? (
        <div className="flex flex-wrap gap-2 mt-1">
          {story.players.map((name) => (
            <span
              key={name}
              className="text-xs pl-2"
              style={{ borderLeft: "var(--border-width-semantic) solid var(--color-border-strong)", color: "var(--color-text-primary)" }}
            >
              {name}
            </span>
          ))}
        </div>
      ) : null}
      {story.editorial_label ? (
        <p className="text-sm font-extrabold mt-1" style={{ color: "var(--color-text-primary)" }}>
          {story.editorial_label}
        </p>
      ) : null}
      {deepLinkLabel ? (
        <p className="text-xs uppercase mt-1" style={{ color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {deepLinkLabel} &rsaquo;
        </p>
      ) : null}
    </>
  );

  if (deepLinkLabel) {
    return (
      <div
        role="button"
        tabIndex={0}
        onClick={() => onOpenHistory(story.history_filter || FILTER_ALL)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") onOpenHistory(story.history_filter || FILTER_ALL);
        }}
        className="grid gap-1 cursor-pointer"
        style={containerStyle}
      >
        {body}
      </div>
    );
  }

  return (
    <article className="grid gap-1" style={containerStyle}>
      {body}
    </article>
  );
}

function RecapGroupSection({ group, onOpenHistory }: { group: RecapStoryGroup; onOpenHistory: (filter: string) => void }) {
  const accent = recapCategoryColorVar(group.category);
  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <span className="inline-block" style={{ width: "3px", height: "0.8rem", background: accent }} />
        <span className="uppercase text-xs font-extrabold" style={{ color: accent, letterSpacing: "var(--letter-spacing-badge)" }}>
          {group.label}
        </span>
      </div>
      <div className="flex flex-col">
        {group.stories.map((story, index) => (
          <RecapStoryCard
            key={`${story.story_type}-${story.title}-${index}`}
            story={story}
            lead={false}
            isFirstInGroup={index === 0}
            onOpenHistory={onOpenHistory}
          />
        ))}
      </div>
    </section>
  );
}

function RecapsTab({ leagueId, initial, onOpenHistory }: { leagueId: string; initial: RecapResponse; onOpenHistory: (filter: string) => void }) {
  const [data, setData] = useState<RecapResponse>(initial);
  const [selectedWeek, setSelectedWeek] = useState<number>(initial.recap?.week ?? initial.max_completed_week);
  const [loading, setLoading] = useState(false);

  const loadWeek = (week: number) => {
    setSelectedWeek(week);
    setLoading(true);
    api
      .getLeagueRecap(leagueId, week)
      .then((response) => setData(response))
      .finally(() => setLoading(false));
  };

  if (data.reason === "no_completed_week" || !data.recap) {
    return (
      <EmptyState
        title="No recap yet"
        subtitle="No completed week is ready for a recap yet. Open History for the recorded transaction timeline."
        actionLabel="Open History"
        onAction={() => onOpenHistory("")}
      />
    );
  }

  const archive = buildRecapArchive(data.max_completed_week);
  const stories = data.recap.stories || [];
  const lead = stories[0];
  const groups = groupRecapStories(stories.slice(1));

  return (
    <div className="flex flex-col gap-5">
      {archive.pills.length > 0 ? (
        <div className="flex flex-col gap-2">
          <PillRow
            options={archive.pills.map((pill) => ({ label: pill.label, value: String(pill.week) }))}
            active={String(selectedWeek)}
            onSelect={(value) => loadWeek(Number(value))}
          />
          {archive.overflow.length > 0 ? (
            <select
              className="text-xs px-2 py-2"
              style={{ background: "var(--color-surface-muted)", color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
              value={archive.overflow.some((o) => o.week === selectedWeek) ? String(selectedWeek) : ""}
              onChange={(event) => {
                if (event.target.value) loadWeek(Number(event.target.value));
              }}
            >
              <option value="">More weeks...</option>
              {archive.overflow.map((o) => (
                <option key={o.week} value={o.week}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : null}
        </div>
      ) : null}

      <header className="flex flex-col gap-1" style={{ opacity: loading ? 0.6 : 1 }}>
        <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          League Memory
        </span>
        <SectionHeading>
          Week {data.recap.week} recap
        </SectionHeading>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {data.recap.headline}
        </p>
      </header>

      {stories.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Not enough historical data for a recap this week.
        </p>
      ) : (
        <div className="flex flex-col gap-5" style={{ opacity: loading ? 0.6 : 1 }}>
          <RecapStoryCard story={lead} lead isFirstInGroup onOpenHistory={onOpenHistory} />
          {groups.map((group, index) => (
            <RecapGroupSection key={`${group.category}-${index}`} group={group} onOpenHistory={onOpenHistory} />
          ))}
        </div>
      )}
    </div>
  );
}

function AssetChip({ asset }: { asset: HistoryTransaction["draft_picks"][number] }) {
  if (asset.kind === "pick") {
    return (
      <span
        className="text-xs px-2 py-1"
        style={{ border: "var(--border-width-default) solid var(--color-border)", color: "var(--color-text-secondary)" }}
      >
        {pickLabel(asset)}
      </span>
    );
  }
  if (!asset.player_id) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs px-2 py-1"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <PositionBadge position={asset.position} />
        <span style={{ color: asset.known ? "var(--color-text-primary)" : "var(--color-text-muted)" }}>{asset.name}</span>
      </span>
    );
  }
  return (
    <PlayerIdentityTrigger identity={{ ...asset, sourceLabel: "League History" }}>
      <span
        className="inline-flex items-center gap-1 text-xs px-2 py-1"
        style={{ border: "var(--border-width-default) solid var(--color-border)" }}
      >
        <PlayerAvatar playerId={asset.player_id} size={20} />
        <PositionBadge position={asset.position} />
        <span style={{ color: asset.known ? "var(--color-text-primary)" : "var(--color-text-muted)" }}>{asset.name}</span>
      </span>
    </PlayerIdentityTrigger>
  );
}

function faabLine(side: HistorySide, txType: string): string {
  const bits: string[] = [];
  if (side.faab_spent !== null && side.faab_spent > 0) bits.push(`FAAB $${side.faab_spent}`);
  else if (txType === "waiver" && side.faab_spent === 0) bits.push("No FAAB");
  if (side.faab_received !== null && side.faab_received > 0) bits.push(`Received FAAB $${side.faab_received}`);
  return bits.join(" · ");
}

function HistorySideBlock({ side, txType }: { side: HistorySide; txType: string }) {
  const faab = faabLine(side, txType);
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-2 min-w-0">
        <TeamAvatar avatarUrl={side.avatar_url} size={28} />
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
            {side.team_name}
          </span>
          {side.owner_handle ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {side.owner_handle}
            </span>
          ) : null}
        </div>
      </div>
      {txType === "trade" ? (
        <>
          <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Received
          </span>
          {side.receives.length ? (
            <div className="flex flex-wrap gap-1">
              {side.receives.map((asset, i) => (
                <AssetChip key={`${asset.player_id || asset.label}-${i}`} asset={asset} />
              ))}
            </div>
          ) : (
            <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
              No assets recorded
            </span>
          )}
        </>
      ) : (
        <>
          {side.receives.length ? (
            <>
              <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                Added
              </span>
              <div className="flex flex-wrap gap-1">
                {side.receives.map((asset, i) => (
                  <AssetChip key={`${asset.player_id || asset.label}-${i}`} asset={asset} />
                ))}
              </div>
            </>
          ) : null}
          {side.drops.length ? (
            <>
              <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                Dropped
              </span>
              <div className="flex flex-wrap gap-1">
                {side.drops.map((asset, i) => (
                  <AssetChip key={`${asset.player_id || asset.label}-${i}`} asset={asset} />
                ))}
              </div>
            </>
          ) : null}
        </>
      )}
      {faab ? (
        <span className="text-xs uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {faab}
        </span>
      ) : null}
    </div>
  );
}

function HistoryGradeBlock({ grade }: { grade: HistoryTransaction["grade"] }) {
  if (!grade) return null;

  if (grade.kind === "trade") {
    const sides = grade.sides || [];
    if (!sides.length) return null;
    const allPending = sides.every((side) => !side.letter || side.letter.toLowerCase() === "pending");
    if (grade.pending || grade.partial_evidence || allPending) {
      const why = sides.map((side) => side.why).find(Boolean) || "Future pick value is unresolved.";
      return (
        <div
          className="mt-2 flex flex-col gap-1 pl-2"
          style={{ borderLeft: "var(--border-width-semantic) solid var(--color-warning)" }}
        >
          <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Grade Pending
          </span>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {why}
          </p>
        </div>
      );
    }
    let primaryWhy = "";
    let provisionalNote = "";
    for (const side of sides) {
      const why = side.why || "";
      if (why && !primaryWhy) {
        primaryWhy = why.replace(" Future pick value is estimated until the selection is known.", "").trim();
      }
      if (why.includes("Future pick value is estimated")) {
        provisionalNote = "Future pick value is estimated until the selection is known.";
      }
    }
    return (
      <div className="mt-2 flex flex-col gap-1.5">
        <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {grade.provisional ? "Provisional trade grade" : "Current trade grade"}
        </span>
        {sides.map((side) => (
          <div key={side.team} className="flex items-baseline justify-between gap-2 flex-wrap">
            <span className="text-xs uppercase" style={{ color: "var(--color-text-primary)", letterSpacing: "var(--letter-spacing-badge)" }}>
              {side.team}
            </span>
            <span className="font-extrabold" style={{ font: "var(--font-card-title)", color: gradeToneColorVar(side.tone) }}>
              {side.letter}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {side.confidence}
            </span>
          </div>
        ))}
        {primaryWhy ? (
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            <span style={{ color: "var(--color-text-muted)" }}>Why </span>
            {primaryWhy}
          </p>
        ) : null}
        {provisionalNote ? (
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {provisionalNote}
          </p>
        ) : null}
      </div>
    );
  }

  // Waiver / free-agent grade — always renders, even when still "Pending"
  // (modules/transaction_grades_ui.py's waiver_grade_html has no skip).
  return (
    <div className="mt-2 flex flex-col gap-1">
      <div className="flex items-baseline justify-between gap-2 flex-wrap">
        <span className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {grade.player}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {grade.grade_model_label || "Current pickup grade"}
        </span>
        <span className="font-extrabold" style={{ font: "var(--font-card-title)", color: gradeToneColorVar(grade.tone) }}>
          {grade.letter}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {grade.confidence}
        </span>
      </div>
      {grade.why ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)" }}>Why </span>
          {grade.why}
        </p>
      ) : null}
      {grade.watch ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <span style={{ color: "var(--color-text-muted)" }}>Watch </span>
          {grade.watch}
        </p>
      ) : null}
    </div>
  );
}

function HistoryItemCard({ transaction }: { transaction: HistoryTransaction }) {
  const kicker = transaction.type === "trade" ? "Trade" : transaction.type === "waiver" ? "Waiver" : "Free agent";
  const when = formatHistoryWhen(transaction.week, transaction.timestamp);
  const sides = transaction.sides || [];
  if (!sides.length) return null;
  return (
    <article
      className="p-3 flex flex-col gap-2"
      style={{ background: "var(--color-surface-primary)", border: "var(--border-width-default) solid var(--color-border-strong)" }}
    >
      <header className="flex items-baseline justify-between gap-2 flex-wrap">
        <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {kicker}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {when}
        </span>
      </header>
      <div className="grid gap-3" style={{ gridTemplateColumns: sides.length > 1 ? "repeat(auto-fit, minmax(10rem, 1fr))" : "1fr" }}>
        {sides.map((side) => (
          <HistorySideBlock key={side.roster_id} side={side} txType={transaction.type} />
        ))}
      </div>
      {transaction.draft_picks?.length ? (
        <div className="flex flex-wrap gap-1">
          {transaction.draft_picks.map((pick, i) => (
            <AssetChip key={`${pick.label}-${i}`} asset={pick} />
          ))}
        </div>
      ) : null}
      <HistoryGradeBlock grade={transaction.grade} />
    </article>
  );
}

function HistoryTab({
  leagueId,
  initialFilter,
  cache,
  setCache,
}: {
  leagueId: string;
  initialFilter: string;
  cache: Record<string, HistoryResponse>;
  setCache: (next: Record<string, HistoryResponse>) => void;
}) {
  const [selectedSeasonLeagueId, setSelectedSeasonLeagueId] = useState<string>(leagueId);
  const [filter, setFilter] = useState<string>(initialFilter);
  const [error, setError] = useState<string | null>(null);

  const data = cache[selectedSeasonLeagueId];

  useEffect(() => {
    if (cache[selectedSeasonLeagueId]) return;
    let cancelled = false;
    api
      .getLeagueHistory(leagueId, selectedSeasonLeagueId === leagueId ? undefined : selectedSeasonLeagueId)
      .then((response) => {
        if (cancelled) return;
        setCache({ ...cache, [response.selected_league_id]: response });
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Could not load League History.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSeasonLeagueId]);

  if (!data && !error) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Loading league history…
      </p>
    );
  }
  if (error) {
    return (
      <p className="text-sm" role="alert" style={{ color: "var(--color-danger)" }}>
        {error}
      </p>
    );
  }
  if (!data) return null;

  if (data.reason === "no_history" || data.seasons.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        This league has no Sleeper history to show yet.
      </p>
    );
  }

  const visible = data.transactions.filter((tx) => matchesHistoryFilter(tx, filter));

  return (
    <div className="flex flex-col gap-4">
      {data.seasons.length > 1 ? (
        <PillRow
          options={data.seasons.map((season) => ({ label: season.season || season.name, value: season.league_id }))}
          active={selectedSeasonLeagueId}
          onSelect={setSelectedSeasonLeagueId}
        />
      ) : null}
      <PillRow options={HISTORY_FILTERS.map((label) => ({ label, value: label }))} active={filter} onSelect={setFilter} />
      {visible.length === 0 ? (
        <p className="text-sm max-w-md" style={{ color: "var(--color-text-secondary)" }}>
          {emptyFilterNote(filter)}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {visible.map((transaction) => (
            <HistoryItemCard key={transaction.transaction_id} transaction={transaction} />
          ))}
        </div>
      )}
    </div>
  );
}

// modules/league_storylines_ui.py's _breakdown_note(), verbatim.
function breakdownNote(breakdown: StorylineLeader["breakdown"]): string {
  if (!breakdown) return "";
  const bits: string[] = [];
  if (breakdown.trade) bits.push(`${breakdown.trade} trade${breakdown.trade !== 1 ? "s" : ""}`);
  if (breakdown.waiver) bits.push(`${breakdown.waiver} waiver${breakdown.waiver !== 1 ? "s" : ""}`);
  if (breakdown.free_agent) bits.push(`${breakdown.free_agent} FA add${breakdown.free_agent !== 1 ? "s" : ""}`);
  return bits.join(" · ");
}

function StorylineTeamLine({ team }: { team: StorylineTeam }) {
  return (
    <div className="flex items-center gap-2 min-w-0">
      <TeamAvatar avatarUrl={team.avatar_url} size={28} />
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-extrabold break-words" style={{ color: "var(--color-text-primary)" }}>
          {team.team_name}
        </span>
        {team.owner_handle ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {team.owner_handle}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function StorylineCard({
  kicker,
  question,
  children,
  wide,
  route,
  onOpenHistory,
}: {
  kicker: string;
  question: string;
  children: ReactNode;
  wide?: boolean;
  route?: string;
  onOpenHistory?: (filter: string) => void;
}) {
  const style = {
    background: "var(--color-surface-raised)",
    border: "var(--border-width-default) solid var(--color-border)",
    padding: "var(--space-sm) var(--space-md)",
    display: "grid",
    gap: "var(--space-2xs)",
    gridColumn: wide ? "1 / -1" : undefined,
  };
  const body = (
    <>
      <span
        className="text-xs uppercase"
        style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {kicker}
      </span>
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {question}
      </span>
      {children}
    </>
  );
  if (route && onOpenHistory) {
    return (
      <div
        role="button"
        tabIndex={0}
        onClick={() => onOpenHistory(route)}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") onOpenHistory(route);
        }}
        className="cursor-pointer"
        style={style}
      >
        {body}
      </div>
    );
  }
  return <article style={style}>{body}</article>;
}

function StorylinesTab({
  leagueId,
  data,
  setData,
  onOpenHistory,
}: {
  leagueId: string;
  data: StorylinesResponse | null;
  setData: (next: StorylinesResponse) => void;
  onOpenHistory: (filter: string) => void;
}) {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data) return;
    let cancelled = false;
    api
      .getLeagueStorylines(leagueId)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load league storylines.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [leagueId, data]);

  if (!data && !error) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Loading league storylines…
      </p>
    );
  }
  if (error) {
    return (
      <p className="text-sm" role="alert" style={{ color: "var(--color-danger)" }}>
        {error}
      </p>
    );
  }
  if (!data) return null;

  const report = data.storylines;
  if (!report) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Storylines need a loaded league.
      </p>
    );
  }

  const cards: ReactNode[] = [];

  if (report.most_active) {
    const leader = report.most_active;
    const note = [
      leader.tied ? "Tied on activity count" : "",
      breakdownNote(leader.breakdown),
    ]
      .filter(Boolean)
      .join(" · ");
    cards.push(
      <StorylineCard key="most-active" kicker="Most Active" question="Who is driving league activity?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} move{leader.metric !== 1 ? "s" : ""}
        </span>
        {note ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {note}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.trade_market_leader) {
    const leader = report.trade_market_leader;
    cards.push(
      <StorylineCard key="trade-market" kicker="Trade Market" question="Who is driving the trade market?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} completed trade{leader.metric !== 1 ? "s" : ""}
        </span>
      </StorylineCard>,
    );
  }

  if (report.largest_trade) {
    const trade = report.largest_trade;
    cards.push(
      <StorylineCard
        key="biggest-trade"
        kicker="Biggest Trade"
        question="Which completed trade moved the most assets?"
        wide
        route={FILTER_TRADES}
        onOpenHistory={onOpenHistory}
      >
        <div className="flex flex-col gap-2">
          {trade.teams.slice(0, 3).map((team) => (
            <StorylineTeamLine key={team.roster_id || team.team_name} team={team} />
          ))}
        </div>
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {trade.players} player{trade.players !== 1 ? "s" : ""} · {trade.picks} pick
          {trade.picks !== 1 ? "s" : ""}
        </span>
        {trade.when ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {trade.when}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.biggest_faab) {
    const faab = report.biggest_faab;
    const player = "name" in faab.player ? (faab.player as HistoryAsset) : null;
    cards.push(
      <StorylineCard
        key="biggest-faab"
        kicker="Biggest FAAB"
        question="Who spent the most on a single claim?"
        route={FILTER_WIRE}
        onOpenHistory={onOpenHistory}
      >
        <StorylineTeamLine team={faab} />
        {player ? (
          <div className="flex flex-wrap gap-1">
            <AssetChip asset={player} />
          </div>
        ) : null}
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          ${faab.amount}
        </span>
        {faab.when ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {faab.when}
          </span>
        ) : null}
      </StorylineCard>,
    );
  }

  if (report.most_picks_acquired) {
    const leader = report.most_picks_acquired;
    cards.push(
      <StorylineCard key="most-picks" kicker="Most Picks Acquired" question="Who collected the most future picks?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} pick{leader.metric !== 1 ? "s" : ""} acquired
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Incoming picks from completed trades, not current ownership.
        </span>
      </StorylineCard>,
    );
  }

  if (report.roster_turnover) {
    const leader = report.roster_turnover;
    cards.push(
      <StorylineCard key="roster-turnover" kicker="Roster Turnover" question="Which roster changed the most player assets?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} player-asset change{leader.metric !== 1 ? "s" : ""}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Unique players added or dropped per move. Same-player add/drop counts once.
        </span>
      </StorylineCard>,
    );
  }

  if (report.quietest) {
    const leader = report.quietest;
    cards.push(
      <StorylineCard key="quietest" kicker="Quietest Desk" question="Who stayed out of the market?">
        <StorylineTeamLine team={leader} />
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {leader.metric} completed move{leader.metric !== 1 ? "s" : ""}
        </span>
      </StorylineCard>,
    );
  }

  if (report.busiest_week) {
    const busy = report.busiest_week;
    cards.push(
      <StorylineCard key="busiest-week" kicker="Busiest Week" question="When was the market loudest?">
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          Week {busy.week}
        </span>
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {busy.count} completed moves
        </span>
      </StorylineCard>,
    );
  }

  if (report.most_traded_player) {
    const traded = report.most_traded_player;
    cards.push(
      <StorylineCard key="most-traded-player" kicker="Most Moved Player" question="Which player changed hands the most?">
        <div className="flex flex-wrap gap-1">
          <AssetChip asset={traded.player} />
        </div>
        <span className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {traded.count} completed trades
        </span>
      </StorylineCard>,
    );
  }

  if (cards.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Not enough completed activity this season to form storylines.
      </p>
    );
  }

  const heading = report.season ? `${report.season} storylines` : "Season storylines";

  return (
    <div className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <span
          className="text-xs uppercase"
          style={{ color: "var(--color-text-secondary)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          {heading}
        </span>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          What this season&apos;s activity says, not a grade of old deals.
        </p>
      </header>
      <div className="grid gap-3" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(16rem, 1fr))" }}>
        {cards}
      </div>
    </div>
  );
}

export function LeagueRecapsContent({
  leagueId,
  leagueName,
  initialRecap,
}: {
  leagueId: string;
  leagueName: string;
  initialRecap: RecapResponse;
}) {
  const [view, setView] = useState<MemoryView>("Recaps");
  const [historyCache, setHistoryCache] = useState<Record<string, HistoryResponse>>({});
  const [historyFilter, setHistoryFilter] = useState<string>(FILTER_ALL);
  const [storylinesData, setStorylinesData] = useState<StorylinesResponse | null>(null);

  const openHistory = (filter: string) => {
    setHistoryFilter(historyFilterToPill(filter));
    setView("History");
  };

  let body: ReactNode;
  if (view === "Recaps") body = <RecapsTab leagueId={leagueId} initial={initialRecap} onOpenHistory={openHistory} />;
  else if (view === "History")
    body = (
      <HistoryTab
        leagueId={leagueId}
        initialFilter={historyFilter}
        cache={historyCache}
        setCache={setHistoryCache}
      />
    );
  else
    body = (
      <StorylinesTab
        leagueId={leagueId}
        data={storylinesData}
        setData={setStorylinesData}
        onOpenHistory={openHistory}
      />
    );

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          League Recaps / History
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          What mattered this week, and what happened. History remains the source record.
        </p>
      </header>
      <PillRow
        fullWidth
        options={MEMORY_VIEWS.map((v) => ({ label: v, value: v }))}
        active={view}
        onSelect={(value) => setView(value as MemoryView)}
      />
      {body}
    </main>
  );
}
