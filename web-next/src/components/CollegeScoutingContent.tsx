"use client";

import { PageTitle } from "@/components/PageTitle";
import { EmptyState } from "@/components/EmptyState";
import { ModuleErrorBoundary } from "@/components/ModuleErrorBoundary";
import { FreshnessLabel } from "@/components/ui/FreshnessLabel";
import dynamic from "next/dynamic";
import { useMemo, useState, type ReactNode } from "react";

import { api, type CollegeProspect, type CollegeProspectsResponse, MAX_GRADE } from "@/lib/api";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { ViewTabs } from "@/components/ui/ViewTabs";
import { PageControl } from "@/components/ui/PageControls";
import { draftFromProspect, type ReportDraft, type ReportFlash } from "@/components/ProspectReportForm";
import { usePlayerQuickView } from "@/context/PlayerQuickViewContext";
import { handOffPlayerId } from "@/lib/prospectProfile";
import { ToneBadge } from "@/components/ToneBadge";
import { prospectFit, rankByFit, type ScoutingLens } from "@/lib/scoutingLens";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { confidenceColor } from "@/lib/waiversPresentation";
import { aggregateText, classLabel, scoutingConfidenceLabel } from "@/lib/collegeScoutingPresentation";

// The prospect sheet is the shared player quick view: load it on demand, not with the board.
const ProspectSheet = dynamic(() => import("@/components/ProspectSheet").then((m) => m.ProspectSheet), { ssr: false });

/**
 * Ports modules/college_scouting_ui.py's render_college_scouting_workspace /
 * mobile's CollegeProspectsScreen.tsx + ProspectScoutingDetailScreen.tsx for
 * Revision 20 — the shared, crowdsourced college prospect catalog. Reads
 * and writes the exact same GET/POST/DELETE /v1/scouting/* endpoints both
 * existing surfaces already use; no new valuation or aggregation logic
 * lives here (see modules/college_scouting.py's "NO FABRICATED DATA"
 * section — an empty catalog is the honest state, never invented rows).
 *
 * Deliberately NOT premium-gated here, unlike Streamlit's own route
 * (current_user_is_premium() blur+lock before rendering this workspace):
 * GET /v1/scouting/prospects itself returns no entitlement/premium field at
 * all, and mobile's CollegeProspectsScreen.tsx has no such gate either (it's
 * reached through a one-time "follow college football?" interest opt-in in
 * Settings instead). Same posture as GmPlanContent.tsx's own precedent —
 * following the shared, ungated API contract rather than inventing a
 * client-side paywall this page has no basis for.
 *
 * One combined list + inline grading form (collapsible per card), matching
 * the real Streamlit page's st.expander-per-prospect layout rather than
 * mobile's separate list/detail screens — a second route buys nothing here
 * since both the list and the detail form read/write the same single
 * CollegeProspect row.
 */

type FilterKey = "all" | "watchlist";

function ProspectCard({
  prospect,
  onToggleWatchlist,
  onOpen,
  lens,
}: {
  lens?: ScoutingLens | null;
  prospect: CollegeProspect;
  onToggleWatchlist: () => void;
  onOpen: () => void;
}) {
  const aggregate = prospect.aggregate;
  const hasReport = prospect.my_report != null;
  const fit = lens ? prospectFit(prospect, lens) : null;

  return (
    <article
      className="glass-surface flex flex-col gap-2 p-3"
    >
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          {/* Prospects have no NFL headshot yet: id null keeps the avatar on initials. The whole card opens his sheet. */}
          <CompactPlayerCard
            player={{ id: null, name: prospect.name, position: prospect.position }}
            detail={classLabel(prospect.school, prospect.draft_year)}
            testId="prospect-player"
            onOpen={onOpen}
          />
        </div>
        {fit && (fit.needsPosition || fit.pickNote) ? (
          <span className="flex flex-wrap justify-end gap-1">
            {fit.needsPosition ? <ToneBadge label="Fits your need" color="var(--color-success)" /> : null}
            {fit.pickNote ? <ToneBadge label={fit.pickNote} color="var(--color-information)" /> : null}
          </span>
        ) : null}
      </div>

      <div
        className="flex items-center gap-2 pt-2"
        style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}
      >
        {aggregate.scout_count > 0 ? (
          <ConfidenceMeter
            label="Signal"
            value={scoutingConfidenceLabel(aggregate.scout_count)}
            color={confidenceColor(scoutingConfidenceLabel(aggregate.scout_count))}
          />
        ) : null}
        <span className="text-sm font-bold" style={{ color: "var(--color-text-secondary)" }}>
          {aggregateText(aggregate)}
        </span>
      </div>

      {prospect.my_report?.grade != null ? (
        <span className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>
          Your grade: {prospect.my_report.grade}/{MAX_GRADE}
        </span>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onToggleWatchlist}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          {prospect.on_watchlist ? "Unfollow" : "Follow"}
        </button>
        <button
          type="button"
          onClick={onOpen}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          {hasReport ? `Edit your grade: ${prospect.name}` : `Scout ${prospect.name}`}
        </button>
      </div>
    </article>
  );
}

function Shell({ embedded, children }: { embedded: boolean; children: ReactNode }) {
  if (embedded) return <div className="flex flex-col gap-3">{children}</div>;
  return <main className="page-shell">{children}</main>;
}

export function CollegeScoutingContent({
  data,
  embedded = false,
  lens = null,
}: {
  /** League overlay (needs + your pick slots). Null with no league: the base list only. */
  lens?: ScoutingLens | null;
  data: CollegeProspectsResponse;
  /** Inside the Draft Center Scouting tab: no page shell or title (the host page owns both). */
  embedded?: boolean;
}) {
  const [prospects, setProspects] = useState<CollegeProspect[]>(data.prospects);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [openId, setOpenId] = useState<string | null>(null);
  const { openPlayer } = usePlayerQuickView();
  const [drafts, setDrafts] = useState<Record<string, ReportDraft>>({});
  const [flashes, setFlashes] = useState<Record<string, ReportFlash>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const [view, setView] = useState<"base" | "league">("base");
  const visible = useMemo(() => {
    const scoped = filter === "watchlist" ? prospects.filter((row) => row.on_watchlist) : prospects;
    return lens && view === "league" ? rankByFit(scoped, lens) : scoped;
  }, [prospects, filter, lens, view]);

  const toggleWatchlist = (prospect: CollegeProspect) => {
    const next = !prospect.on_watchlist;
    setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: next } : row)));
    const mutation = next ? api.addProspectToWatchlist(prospect.id) : api.removeProspectFromWatchlist(prospect.id);
    mutation
      .then((result) => {
        if (!result.ok) {
          setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: !next } : row)));
        }
      })
      .catch(() => {
        setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, on_watchlist: !next } : row)));
      });
  };

  const openSheet = (prospect: CollegeProspect) => {
    // Drafted and mapped: the normal NFL player card, not a college sheet.
    const nflId = handOffPlayerId(prospect);
    if (nflId) {
      openPlayer({ player_id: nflId, name: prospect.name, position: prospect.position, sourceLabel: "Drafted prospect" });
      return;
    }
    setDrafts((prev) => ({ ...prev, [prospect.id]: prev[prospect.id] ?? draftFromProspect(prospect) }));
    setOpenId(prospect.id);
  };
  const openProspect = openId ? prospects.find((row) => row.id === openId) ?? null : null;

  const submitReport = (prospect: CollegeProspect) => {
    const draft = drafts[prospect.id] ?? draftFromProspect(prospect);
    if (draft.grade == null) {
      setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "warning", message: "Choose a grade before saving." } }));
      return;
    }
    setBusyId(prospect.id);
    api
      .submitScoutingReport(prospect.id, { grade: draft.grade, round_projection: draft.roundProjection, note: draft.note.trim() })
      .then((result) => {
        if (result.ok) {
          setProspects((prev) =>
            prev.map((row) =>
              row.id === prospect.id
                ? { ...row, my_report: { grade: draft.grade, round_projection: draft.roundProjection, note: draft.note.trim() } }
                : row,
            ),
          );
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "success", message: "Saved: thanks for scouting." } }));
        } else {
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not save your grade. Try again in a moment." } }));
        }
      })
      .catch(() => {
        setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not save your grade. Try again in a moment." } }));
      })
      .finally(() => setBusyId(null));
  };

  const removeReport = async (prospect: CollegeProspect): Promise<boolean> => {
    setBusyId(prospect.id);
    try {
      const result = await api.deleteScoutingReport(prospect.id);
      if (!result.ok) return false;
      setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, my_report: null } : row)));
      setDrafts((prev) => ({ ...prev, [prospect.id]: { grade: null, roundProjection: null, note: "" } }));
      setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "success", message: "Removed your report." } }));
      return true;
    } catch {
      return false;
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Shell embedded={embedded}>
      <header className="flex flex-col gap-1">
        {embedded ? null : (
          <PageTitle
            page="College Scouting"
            info={
              <p>
                How grades are used: every signed-in user&apos;s grade on a prospect pools into one shared signal. That shared aggregate, not any single grade,
                can influence rookie draft-class strength. Your own grade and watchlist stay yours to edit any time.
              </p>
            }
          />
        )}
        {prospects.length > 0 ? <FreshnessLabel datasets={["prospects"]} className="text-xs" /> : null}
      </header>

      {prospects.length === 0 ? (
        data.catalog_available ? (
          <EmptyState title="No prospects yet" subtitle="Check back soon: the prospect pool is still growing." />
        ) : (
          <EmptyState
            title="College Scouting isn't connected yet"
            subtitle="The prospect catalog isn't reachable right now. Check back soon."
          />
        )
      ) : (
        <div className="flex flex-col gap-4">
          {/* One control row (UI audit batch H): both views are compact selects side by side, not two stacked pill rows plus a paragraph. */}
          <>
            <PageControl>
              <ViewTabs
                label="Show"
                className="min-w-0 flex-1"
                value={filter}
                options={[
                  { value: "all", label: "All" },
                  { value: "watchlist", label: "Watchlist" },
                ]}
                onChange={(value) => setFilter(value as FilterKey)}
              />
              {lens ? (
                <ViewTabs
                  label="Scouting view"
                  className="min-w-0 flex-1"
                  value={view}
                  options={[
                    { value: "base", label: "Best" },
                    { value: "league", label: "My league" },
                  ]}
                  onChange={(value) => setView(value === "league" ? "league" : "base")}
                />
              ) : null}
            </PageControl>
            {lens && view === "league" ? (
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                Prospects that fit a position you need or a round you hold are listed first and tagged. Same prospects and grades as Best available.
              </p>
            ) : null}
          </>

          {visible.length === 0 ? (
            <EmptyState
              title="No prospects followed yet"
              subtitle="Follow a prospect from All Prospects to track them here."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {visible.map((prospect) => (
                <ModuleErrorBoundary key={prospect.id} name="prospect_card">
                <ProspectCard
                  prospect={prospect}
                  onToggleWatchlist={() => toggleWatchlist(prospect)}
                  onOpen={() => openSheet(prospect)}
                  lens={lens && view === "league" ? lens : null}
                />
                </ModuleErrorBoundary>
              ))}
            </div>
          )}
        </div>
      )}
      {openProspect ? (
        <ProspectSheet
          key={openProspect.id}
          prospect={openProspect}
          draft={drafts[openProspect.id] ?? draftFromProspect(openProspect)}
          flash={flashes[openProspect.id] ?? null}
          busy={busyId === openProspect.id}
          onDraftChange={(next) => setDrafts((prev) => ({ ...prev, [openProspect.id]: next }))}
          onSubmit={() => submitReport(openProspect)}
          onRemove={() => removeReport(openProspect)}
          onToggleWatchlist={() => toggleWatchlist(openProspect)}
          onClose={() => setOpenId(null)}
        />
      ) : null}
    </Shell>
  );
}
