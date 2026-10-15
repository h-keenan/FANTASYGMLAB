"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";

import { api } from "@/lib/api";
import type { HistoryResponse, HistorySide, HistoryTransaction, RecapResponse, RecapStory } from "@/lib/api";
import { PositionBadge } from "@/components/PositionBadge";
import { streamlitPageUrl } from "@/lib/streamlitLink";
import {
  FILTER_ALL,
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
 * already calls. History is a new thin wrapper (GET .../history) over the
 * same modules.league_history / modules.transaction_grades the Streamlit
 * History tab already used — no grading or recap logic duplicated here.
 *
 * Storylines (the page's third "Memory view" in Streamlit — biggest
 * trade/FAAB/activity narratives, modules/league_storylines_ui.py) is NOT
 * ported this revision: it has no mobile reference implementation and no
 * backing endpoint, and inventing one here would be guessed scope rather
 * than a thin wrapper over something that already exists. It deep-links to
 * the classic Streamlit page instead, same "not yet ported" contract every
 * other deferred surface uses (see streamlitLink.ts).
 */

type MemoryView = "Recaps" | "History" | "Storylines";

function TabBar({ active, onChange }: { active: MemoryView; onChange: (view: MemoryView) => void }) {
  const views: MemoryView[] = ["Recaps", "History", "Storylines"];
  return (
    <div className="flex w-full" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
      {views.map((view) => {
        const isActive = view === active;
        return (
          <button
            key={view}
            type="button"
            onClick={() => onChange(view)}
            aria-pressed={isActive}
            className="flex-1 py-2.5 text-xs font-bold uppercase"
            style={{
              letterSpacing: "var(--letter-spacing-badge)",
              background: isActive ? "var(--color-information-soft)" : "var(--color-surface-muted)",
              color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
              borderLeft: view === "Recaps" ? "none" : "var(--border-width-default) solid var(--color-border)",
            }}
          >
            {view}
          </button>
        );
      })}
    </div>
  );
}

function PillRow({
  options,
  active,
  onSelect,
}: {
  options: { label: string; value: string }[];
  active: string;
  onSelect: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-0" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
      {options.map((option) => {
        const isActive = option.value === active;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onSelect(option.value)}
            aria-pressed={isActive}
            className="px-3 py-2 text-xs font-bold uppercase"
            style={{
              letterSpacing: "0.03em",
              background: isActive ? "var(--color-information-soft)" : "var(--color-surface-muted)",
              color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
              border: "var(--border-width-default) solid var(--color-border)",
              marginLeft: "-1px",
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

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
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        No completed week is ready for a recap yet. Open History for the recorded transaction timeline.
      </p>
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
        <h2 className="uppercase font-extrabold" style={{ font: "var(--type-section-title)" }}>
          Week {data.recap.week} recap
        </h2>
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
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-extrabold truncate" style={{ color: "var(--color-text-primary)" }}>
          {side.team_name}
        </span>
        {side.owner_handle ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {side.owner_handle}
          </span>
        ) : null}
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

function StorylinesTab() {
  return (
    <div
      className="p-4 flex flex-col gap-2"
      style={{ border: "var(--border-width-semantic) solid var(--color-accent)", background: "var(--color-surface-secondary)" }}
    >
      <p className="text-sm font-extrabold" style={{ color: "var(--color-text-primary)" }}>
        Storylines isn&apos;t in the new design yet
      </p>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Biggest trade, biggest FAAB pickup, and season activity narratives still live on the classic page. Open it there,
        then use the League Memory pills to switch to Storylines.
      </p>
      <Link
        href={streamlitPageUrl("league_recaps")}
        target="_blank"
        rel="noopener noreferrer"
        className="self-start text-xs font-bold uppercase px-3 py-2"
        style={{ background: "var(--color-accent)", color: "var(--color-bg)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        Open classic League Memory
      </Link>
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
  else body = <StorylinesTab />;

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
      <TabBar active={view} onChange={setView} />
      {body}
    </main>
  );
}
