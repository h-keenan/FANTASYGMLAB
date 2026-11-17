"use client";

import { useEffect, useState } from "react";

import { ButtonLink } from "@/components/Button";
import { CompactModule } from "@/components/ui/CompactModule";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type TrackRecordResponse } from "@/lib/api";
import { planOf } from "@/lib/plan";
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
export function TrackRecordView({ record, plan }: { record: TrackRecordResponse; plan: ReturnType<typeof planOf> }) {
  const { basic, advanced } = record;
  const parts = basicSummary(basic).map((text, index) => ({
    key: `b${index}`,
    text,
    strong: index === 0,
    tone: index > 0 && text.endsWith("net") ? (basic.net_points_total > 0 ? ("success" as const) : basic.net_points_total < 0 ? ("danger" as const) : undefined) : undefined,
  }));
  const showLock = !advanced && plan === "free";
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

export function TrackRecordModule() {
  const [state, setState] = useState<{ record: TrackRecordResponse; plan: ReturnType<typeof planOf> } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getTrackRecord(), api.getMe().catch(() => null)])
      .then(([record, me]) => {
        if (!cancelled) setState({ record, plan: planOf(me?.user) });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Fail soft: no record (offline, table unreachable) simply hides the module.
  return state ? <TrackRecordView record={state.record} plan={state.plan} /> : null;
}
