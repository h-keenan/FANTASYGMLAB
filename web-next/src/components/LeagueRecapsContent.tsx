"use client";

import { useState, type ReactNode } from "react";


import type {
  HistoryResponse,
  RecapResponse,
  StorylinesResponse,
} from "@/lib/api";
import { PillRow, } from "@/components/PillRow";
import { RecapWeekView } from "@/components/RecapWeekView";





import {
  FILTER_ALL,
  historyFilterToPill,
  } from "@/lib/leagueRecapsPresentation";
import { PageTitle } from "@/components/PageTitle";

import type { RecapsTab } from "@/lib/pageTabs";



import dynamic from "next/dynamic";
import { SkeletonCard, } from "@/components/Skeleton";

// Perf pass 2026-11: History, Storylines and Roundup are never the default Recaps view and nothing else imports them, so each ships as its own
// chunk (fetched when its tab opens) instead of in every Recaps visit's first-load JS (the route was over its budget).
const HistoryTab = dynamic(() => import("@/components/LeagueHistoryTab").then((m) => m.HistoryTab), {
  loading: () => <SkeletonCard lines={4} />,
});
const StorylinesTab = dynamic(() => import("@/components/LeagueStorylinesTab").then((m) => m.StorylinesTab), {
  loading: () => <SkeletonCard lines={4} />,
});
const LeagueRoundupTab = dynamic(() => import("@/components/LeagueRoundupTab").then((m) => m.LeagueRoundupTab), {
  loading: () => <SkeletonCard lines={4} />,
});

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

type MemoryView = "Recaps" | "History" | "Storylines" | "Roundup";

const MEMORY_VIEWS: MemoryView[] = ["Recaps", "Roundup", "History", "Storylines"];


const VIEW_BY_TAB: Record<RecapsTab, MemoryView> = { recaps: "Recaps", history: "History", storylines: "Storylines", roundup: "Roundup" };

export function LeagueRecapsContent({
  leagueId,
  leagueName,
  initialRecap,
  initialTab,
  initialWeek,
  embedded = false,
}: {
  /** Hosted inside News > My League: no page shell, title or family tabs of its own (News owns them). */
  embedded?: boolean;
  leagueId: string;
  leagueName: string;
  initialRecap: RecapResponse;
  /** `?tab=` (GM orb search, push deep link). */
  initialTab?: RecapsTab;
  /** `?week=` for the Roundup tab. */
  initialWeek?: number;
}) {
  const [view, setView] = useState<MemoryView>(initialTab ? VIEW_BY_TAB[initialTab] : "Recaps");
  const [seenInitialTab, setSeenInitialTab] = useState(initialTab);
  if (initialTab !== seenInitialTab) {
    setSeenInitialTab(initialTab);
    if (initialTab) setView(VIEW_BY_TAB[initialTab]);
  }
  const [historyCache, setHistoryCache] = useState<Record<string, HistoryResponse>>({});
  const [historyFilter, setHistoryFilter] = useState<string>(FILTER_ALL);
  const [storylinesData, setStorylinesData] = useState<StorylinesResponse | null>(null);

  const openHistory = (filter: string) => {
    setHistoryFilter(historyFilterToPill(filter));
    setView("History");
  };

  let body: ReactNode;
  if (view === "Recaps") body = <RecapWeekView leagueId={leagueId} leagueName={leagueName} initial={initialRecap} onOpenHistory={openHistory} />;
  else if (view === "History")
    body = (
      <HistoryTab
        leagueId={leagueId}
        initialFilter={historyFilter}
        cache={historyCache}
        setCache={setHistoryCache}
      />
    );
  else if (view === "Roundup") body = <LeagueRoundupTab leagueId={leagueId} initialWeek={initialWeek} />;
  else
    body = (
      <StorylinesTab
        leagueId={leagueId}
        data={storylinesData}
        setData={setStorylinesData}
        onOpenHistory={openHistory}
      />
    );

  const Shell: "main" | "div" = embedded ? "div" : "main";
  return (
    <Shell className={embedded ? "flex flex-col gap-4" : "page-shell"}>
      {embedded ? null : (
        <header className="flex flex-col gap-1">
          <PageTitle page="League Recaps" leagueName={leagueName} />
        </header>
      )}
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-2" data-testid="recaps-controls">
          <PillRow ariaLabel="League memory view" variant="scroll" options={MEMORY_VIEWS.map((v) => ({ value: v, label: v }))} active={view} onSelect={(value) => setView(value as MemoryView)} />
        </div>
        {body}
      </div>
    </Shell>
  );
}
