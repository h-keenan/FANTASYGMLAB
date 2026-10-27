"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { api } from "@/lib/api";
import {
  VERDICT_FEEDBACK_REASONS,
  VERDICT_TRUST_COPY,
  type VerdictAssumptions,
  type VerdictFeedbackReason,
  type VerdictReportContext,
} from "@/lib/verdictTrust";

type Status = "idle" | "choosing" | "sending" | "sent" | "failed";

/**
 * Under a trade verdict: one line saying what it assumed (details one tap
 * away) and a "Report a bad verdict" action. A report is one fixed reason, no
 * free text, stored anonymously with a one-way account hash (server:
 * modules.verdict_feedback), and ends in a thank-you.
 */
export function VerdictTrust({
  assumptions,
  context,
}: {
  assumptions: VerdictAssumptions | null | undefined;
  context: VerdictReportContext;
}) {
  const [status, setStatus] = useState<Status>("idle");

  const send = async (reason: VerdictFeedbackReason) => {
    setStatus("sending");
    try {
      const result = await api.postVerdictFeedback(reason, context);
      setStatus(result.ok ? "sent" : "failed");
    } catch {
      setStatus("failed");
    }
  };

  return (
    <section className="flex flex-col gap-2" aria-label="Verdict assumptions and feedback" data-testid="verdict-trust">
      {assumptions ? (
        <details className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          <summary className="cursor-pointer" data-testid="verdict-assumptions-line">
            {assumptions.line}
          </summary>
          <ul className="mt-1 flex flex-col gap-0.5 pl-4 list-disc" aria-label={VERDICT_TRUST_COPY.assumptionsTitle}>
            {assumptions.items.map((item) => (
              <li key={item.key}>
                <strong>{item.label}:</strong> {item.value}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {status === "sent" ? (
        <p role="status" className="m-0 text-sm" style={{ color: "var(--color-success)" }}>
          {VERDICT_TRUST_COPY.thanks}
        </p>
      ) : status === "idle" ? (
        <button
          type="button"
          onClick={() => setStatus("choosing")}
          className="self-start text-xs font-bold underline"
          style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)" }}
        >
          {VERDICT_TRUST_COPY.report}
        </button>
      ) : (
        <div className="flex flex-col gap-2" role="group" aria-label={VERDICT_TRUST_COPY.reportPrompt}>
          <p className="m-0 text-sm font-bold">{VERDICT_TRUST_COPY.reportPrompt}</p>
          <div className="flex flex-wrap gap-2">
            {VERDICT_FEEDBACK_REASONS.map((reason) => (
              <Button
                key={reason.key}
                variant="secondary"
                size="sm"
                disabled={status === "sending"}
                onClick={() => void send(reason.key)}
              >
                {reason.label}
              </Button>
            ))}
          </div>
          {status === "sending" ? (
            <p role="status" className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
              {VERDICT_TRUST_COPY.sending}
            </p>
          ) : null}
          {status === "failed" ? (
            <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-danger)" }}>
              {VERDICT_TRUST_COPY.failed}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => setStatus("idle")}
            className="self-start text-xs underline"
            style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)" }}
          >
            {VERDICT_TRUST_COPY.cancel}
          </button>
        </div>
      )}
    </section>
  );
}
