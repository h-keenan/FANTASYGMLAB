"use client";

import { InfoTip } from "@/components/InfoTip";
import { PageTitle } from "@/components/PageTitle";
import { EmptyState } from "@/components/EmptyState";
import { useMemo, useState, type ReactNode } from "react";

import { api, type CollegeProspect, type CollegeProspectsResponse, MAX_GRADE, MAX_ROUND_PROJECTION, MIN_GRADE, MIN_ROUND_PROJECTION } from "@/lib/api";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { PillRow } from "@/components/PillRow";
import { Button } from "@/components/Button";
import { ToneBadge } from "@/components/ToneBadge";
import { prospectFit, rankByFit, type ScoutingLens } from "@/lib/scoutingLens";
import { PositionBadge } from "@/components/PositionBadge";
import { confidenceColor } from "@/lib/waiversPresentation";
import { aggregateText, classLabel, scoutingConfidenceLabel } from "@/lib/collegeScoutingPresentation";

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

const GRADE_OPTIONS = Array.from({ length: MAX_GRADE - MIN_GRADE + 1 }, (_, i) => MIN_GRADE + i);
const ROUND_OPTIONS = [0, ...Array.from({ length: MAX_ROUND_PROJECTION - MIN_ROUND_PROJECTION + 1 }, (_, i) => MIN_ROUND_PROJECTION + i)];
const NOTE_MAX_LENGTH = 280;

type FilterKey = "all" | "watchlist";

interface ReportDraft {
  grade: number | null;
  roundProjection: number | null;
  note: string;
}

function draftFromProspect(prospect: CollegeProspect): ReportDraft {
  return {
    grade: prospect.my_report?.grade ?? null,
    roundProjection: prospect.my_report?.round_projection ?? null,
    note: prospect.my_report?.note ?? "",
  };
}

function ProspectCard({
  prospect,
  expanded,
  draft,
  flash,
  busy,
  onToggleExpanded,
  onToggleWatchlist,
  onDraftChange,
  onSubmit,
  onRemove,
  lens,
}: {
  lens?: ScoutingLens | null;
  prospect: CollegeProspect;
  expanded: boolean;
  draft: ReportDraft;
  flash: { tone: "success" | "error" | "warning"; message: string } | null;
  busy: boolean;
  onToggleExpanded: () => void;
  onToggleWatchlist: () => void;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => void;
}) {
  const aggregate = prospect.aggregate;
  const hasReport = prospect.my_report != null;
  const fit = lens ? prospectFit(prospect, lens) : null;

  return (
    <article
      className="glass-surface flex flex-col gap-2 p-3"
    >
      <div className="flex items-center gap-2">
        <PositionBadge position={prospect.position} />
        <div className="flex flex-col min-w-0 flex-1">
          <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
            {prospect.name}
          </span>
          <span className="text-xs break-words" style={{ color: "var(--color-text-muted)" }}>
            {classLabel(prospect.school, prospect.draft_year)}
          </span>
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
          onClick={onToggleExpanded}
          className="px-2 py-1 text-xs font-bold"
          style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          {expanded ? "Close" : hasReport ? `Edit your grade — ${prospect.name}` : `Scout ${prospect.name}`}
        </button>
      </div>

      {expanded ? (
        <div className="flex flex-col gap-3 pt-2" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
          {flash ? (
            <p
              className="text-xs font-bold"
              style={{
                color:
                  flash.tone === "success"
                    ? "var(--color-success)"
                    : flash.tone === "warning"
                      ? "var(--color-action)"
                      : "var(--color-danger)",
              }}
              role="status"
            >
              {flash.message}
            </p>
          ) : null}

          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
              Overall grade (1 = pass, 5 = elite)
            </span>
            <PillRow
              options={GRADE_OPTIONS.map((value) => ({ label: String(value), value: String(value) }))}
              active={draft.grade != null ? String(draft.grade) : ""}
              onSelect={(value) => onDraftChange({ ...draft, grade: Number(value) })}
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
              Round projection (optional)
            </span>
            <PillRow
              options={ROUND_OPTIONS.map((value) => ({
                label: value === 0 ? "No projection" : `Round ${value}`,
                value: String(value),
              }))}
              active={String(draft.roundProjection ?? 0)}
              onSelect={(value) => onDraftChange({ ...draft, roundProjection: Number(value) === 0 ? null : Number(value) })}
            />
          </div>

          <div className="flex flex-col gap-1">
            <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
              Note (optional)
            </span>
            <textarea
              value={draft.note}
              onChange={(event) => onDraftChange({ ...draft, note: event.target.value.slice(0, NOTE_MAX_LENGTH) })}
              placeholder="What stands out on tape?"
              maxLength={NOTE_MAX_LENGTH}
              rows={3}
              className="text-sm px-2 py-1.5"
              style={{
                background: "var(--color-surface-raised)",
                color: "var(--color-text-primary)",
                border: "var(--border-width-default) solid var(--color-border)",
              }}
            />
            <span className="text-xs self-end" style={{ color: "var(--color-text-muted)" }}>
              {draft.note.length}/{NOTE_MAX_LENGTH}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onSubmit}
              disabled={busy || draft.grade == null}
              className="px-3 py-1.5 text-xs font-bold"
              style={{
                background: "var(--color-accent)",
                color: "var(--color-on-accent)",
                opacity: busy || draft.grade == null ? 0.6 : 1,
              }}
            >
              {hasReport ? "Update grade" : "Submit grade"}
            </button>
            {hasReport ? (
              <Button variant="dangerOutline" size="sm" onClick={onRemove} disabled={busy}>
                Remove my report
              </Button>
            ) : null}
          </div>
        </div>
      ) : null}
    </article>
  );
}

function Shell({ embedded, children }: { embedded: boolean; children: ReactNode }) {
  if (embedded) return <div className="flex flex-col gap-3">{children}</div>;
  return <main className="flex-1 flex flex-col gap-3 px-4 py-3 max-w-3xl w-full mx-auto">{children}</main>;
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
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, ReportDraft>>({});
  const [flashes, setFlashes] = useState<Record<string, { tone: "success" | "error" | "warning"; message: string }>>({});
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

  const toggleExpanded = (prospect: CollegeProspect) => {
    if (expandedId === prospect.id) {
      setExpandedId(null);
      return;
    }
    setDrafts((prev) => ({ ...prev, [prospect.id]: prev[prospect.id] ?? draftFromProspect(prospect) }));
    setExpandedId(prospect.id);
  };

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
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "success", message: "Saved — thanks for scouting." } }));
        } else {
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not save your grade. Try again in a moment." } }));
        }
      })
      .catch(() => {
        setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not save your grade. Try again in a moment." } }));
      })
      .finally(() => setBusyId(null));
  };

  const removeReport = (prospect: CollegeProspect) => {
    setBusyId(prospect.id);
    api
      .deleteScoutingReport(prospect.id)
      .then((result) => {
        if (result.ok) {
          setProspects((prev) => prev.map((row) => (row.id === prospect.id ? { ...row, my_report: null } : row)));
          setDrafts((prev) => ({ ...prev, [prospect.id]: { grade: null, roundProjection: null, note: "" } }));
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "success", message: "Removed your report." } }));
        } else {
          setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not remove your grade. Try again in a moment." } }));
        }
      })
      .catch(() => {
        setFlashes((prev) => ({ ...prev, [prospect.id]: { tone: "error", message: "Could not remove your grade. Try again in a moment." } }));
      })
      .finally(() => setBusyId(null));
  };

  return (
    <Shell embedded={embedded}>
      <header className="flex flex-col gap-1">
        {embedded ? null : <PageTitle page="College Scouting" />}
        <InfoTip label="How grades are used">
          Every signed-in user&apos;s grade on a prospect pools into one shared signal — that shared aggregate, not
          any single grade, can influence rookie draft-class strength. Your own grade and watchlist stay yours to
          edit any time.
        </InfoTip>
      </header>

      {prospects.length === 0 ? (
        data.catalog_available ? (
          <EmptyState title="No prospects yet" subtitle="Check back soon — the prospect pool is still growing." />
        ) : (
          <EmptyState
            title="College Scouting isn't connected yet"
            subtitle="The prospect catalog isn't reachable right now. Check back soon."
          />
        )
      ) : (
        <div className="flex flex-col gap-4">
          <PillRow
            options={[
              { label: "All Prospects", value: "all" },
              { label: "My Watchlist", value: "watchlist" },
            ]}
            active={filter}
            onSelect={(value) => setFilter(value as FilterKey)}
          />

          {lens ? (
            <div className="flex flex-col gap-1">
              <PillRow
                ariaLabel="Scouting view"
                options={[
                  { label: "Best available", value: "base" },
                  { label: "For my league", value: "league" },
                ]}
                active={view}
                onSelect={(value) => setView(value === "league" ? "league" : "base")}
              />
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {view === "league"
                  ? "Prospects that fit a position you need or a round you hold are listed first and tagged. Same prospects and grades as Best available."
                  : "The shared board, no league applied. Switch to For my league to see fits to your needs and picks."}
              </p>
            </div>
          ) : null}

          {visible.length === 0 ? (
            <EmptyState
              title="No prospects followed yet"
              subtitle="Follow a prospect from All Prospects to track them here."
            />
          ) : (
            <div className="flex flex-col gap-3">
              {visible.map((prospect) => (
                <ProspectCard
                  key={prospect.id}
                  prospect={prospect}
                  expanded={expandedId === prospect.id}
                  draft={drafts[prospect.id] ?? draftFromProspect(prospect)}
                  flash={flashes[prospect.id] ?? null}
                  busy={busyId === prospect.id}
                  onToggleExpanded={() => toggleExpanded(prospect)}
                  onToggleWatchlist={() => toggleWatchlist(prospect)}
                  onDraftChange={(next) => setDrafts((prev) => ({ ...prev, [prospect.id]: next }))}
                  onSubmit={() => submitReport(prospect)}
                  onRemove={() => removeReport(prospect)}
                  lens={lens && view === "league" ? lens : null}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </Shell>
  );
}
