"use client";

import { MAX_GRADE, MAX_ROUND_PROJECTION, MIN_GRADE, MIN_ROUND_PROJECTION, type CollegeProspect } from "@/lib/api";
import { PillRow } from "@/components/PillRow";
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { Toggle } from "@/components/Toggle";

/**
 * Your own scouting report on a college prospect (grade, round projection, note): the one form, shown in the prospect sheet's
 * Overview. Reads and writes the same POST/DELETE /v1/scouting/prospects/{id}/report the board always used.
 */
const GRADE_OPTIONS = Array.from({ length: MAX_GRADE - MIN_GRADE + 1 }, (_, i) => MIN_GRADE + i);
const ROUND_OPTIONS = [0, ...Array.from({ length: MAX_ROUND_PROJECTION - MIN_ROUND_PROJECTION + 1 }, (_, i) => MIN_ROUND_PROJECTION + i)];
export const NOTE_MAX_LENGTH = 280;

export interface ReportDraft {
  grade: number | null;
  roundProjection: number | null;
  note: string;
  /** Post anonymously (default): other scouts never see your display name. */
  anonymous: boolean;
}

export interface ReportFlash {
  tone: "success" | "error" | "warning";
  message: string;
}

export function draftFromProspect(prospect: CollegeProspect): ReportDraft {
  return {
    grade: prospect.my_report?.grade ?? null,
    roundProjection: prospect.my_report?.round_projection ?? null,
    note: prospect.my_report?.note ?? "",
    anonymous: prospect.my_report?.anonymous !== false,
  };
}

export function ProspectReportForm({
  hasReport,
  draft,
  flash,
  busy,
  onDraftChange,
  onSubmit,
  onRemove,
}: {
  hasReport: boolean;
  draft: ReportDraft;
  flash: ReportFlash | null;
  busy: boolean;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => Promise<boolean>;
}) {
  return (
    <div className="flex flex-col gap-3" data-testid="prospect-report-form">
      {flash ? (
        <p
          className="text-xs font-bold"
          style={{
            color: flash.tone === "success" ? "var(--color-success)" : flash.tone === "warning" ? "var(--color-action)" : "var(--color-danger)",
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
          options={ROUND_OPTIONS.map((value) => ({ label: value === 0 ? "No projection" : `Round ${value}`, value: String(value) }))}
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

      <div className="flex items-center justify-between gap-3 text-xs">
        <span style={{ color: "var(--color-text-secondary)" }}>Post anonymously</span>
        <Toggle
          label="Post anonymously"
          checked={draft.anonymous}
          onChange={(next) => onDraftChange({ ...draft, anonymous: next })}
        />
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
          <ConfirmInPlace
            variant="row"
            mode="ask"
            size="sm"
            label="Remove my report"
            prompt="Remove your report?"
            confirmLabel="Remove"
            errorText="Could not remove your grade. Try again in a moment."
            disabled={busy}
            onConfirm={onRemove}
          />
        ) : null}
      </div>
    </div>
  );
}
