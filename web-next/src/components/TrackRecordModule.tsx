"use client";

import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/Button";
import { CompactModule } from "@/components/ui/CompactModule";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type TrackRecordResponse } from "@/lib/api";
import {
  basicSummary,
  calibrationNote,
  compareLine,
  plural,
  reliabilityLabel,
  type TrackLevel,
} from "@/lib/trackRecordView";

/**
 * "Your track record": how our advice did for you, and how your own calls did. Compact, tap to expand.
 * Basic outcome history (graded trades, net points) is free; the deeper analytics (advice vs your own calls,
 * confidence calibration) are Pro (`planOf`, with the server withholding them too). Every number carries its
 * sample size; below the minimum sample it says "too early" instead of a rate. Mobile twin:
 * mobile/src/components/TrackRecordModule.tsx; wording: lib/trackRecordView.ts.
 */
export function TrackRecordView({ record }: { record: TrackRecordResponse }) {
  const { basic, advanced } = record;
  const parts = basicSummary(basic).map((text, index) => ({
    key: `b${index}`,
    text,
    strong: index === 0,
    tone: index > 0 && text.endsWith("net") ? (basic.net_points_total > 0 ? ("success" as const) : undefined) /* a net loss is muted, never red */ : undefined,
  }));
  // The response says whether the advanced block was withheld (`is_pro`), so the lock never depends on a second /me call.
  const showLock = !advanced && !record.is_pro;
  const levels: TrackLevel[] = ["high", "medium", "low"];

  return (
    <CompactModule id="track-record" title="Your track record" parts={parts} persist testId="track-record">
      <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {basic.trades_graded > 0
          ? `${plural(basic.trades_graded, "confirmed trade")} graded on real points. ${reliabilityLabel(basic.reliability)}: a few weeks of games is a small sample, so luck still plays a part.`
          : "Confirm a trade and, a few weeks later, its real points show up here."}
      </p>

      {advanced ? (
        <div className="flex flex-col gap-2" data-testid="track-record-advanced">
          <p className="m-0 text-sm" style={{ color: "var(--color-text-primary)" }}>{compareLine(advanced)}</p>
          {levels
            .map((level) => ({ level, note: calibrationNote(level, advanced) }))
            .filter((row) => row.note)
            .map((row) => (
              <p key={row.level} className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{row.note}</p>
            ))}
          <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>{advanced.caveat}</p>
        </div>
      ) : null}

      {showLock ? (
        <div className="flex flex-wrap items-center gap-2" data-testid="track-record-lock">
          <ToneBadge label="Pro" color="var(--color-premium)" />
          <span className="min-w-0 flex-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Advice vs your own calls and confidence calibration
          </span>
          <ButtonLink href="/premium" variant="premium" size="sm">
            See Pro
          </ButtonLink>
        </div>
      ) : null}
    </CompactModule>
  );
}

export function TrackRecordError() {
  return (
    <CompactModule id="track-record" title="Your track record" parts={[{ key: "err", text: "Could not load right now", strong: true }]} testId="track-record-error">
      <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Your track record could not load. Pull to refresh or try again in a moment.
      </p>
    </CompactModule>
  );
}

export function TrackRecordModule() {
  const [record, setRecord] = useState<TrackRecordResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getTrackRecord()
      .then((body) => {
        if (!cancelled) setRecord(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The module stays visible when the read fails: a short error line, never a blank where it used to be.
  if (failed) return <TrackRecordError />;
  return record ? <TrackRecordView record={record} /> : null;
}
