"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PendingTradeOutcome, type TradeOutcomeAnswer } from "@/lib/api";
import {
  isTradeOutcomePromptDismissed,
  setTradeOutcomePromptDismissed,
} from "@/lib/tradeOutcomePromptDismissed";

// "/" is the signed-out landing page and the signup/Sleeper-import/paywall
// flow (same rule GmOrb.tsx uses); "/premium" is the standalone paywall.
const HIDDEN_PATHS = new Set(["/", "/premium"]);

/**
 * "Did this trade happen?": web port of mobile's TradeOutcomePrompt.tsx,
 * the follow-up half of Trade Outcomes. Same endpoints, same copy, same
 * four answers. Answers live on the server (`trade_outcomes` row), so
 * anything answered on the phone is gone from GET /v1/trade-outcomes/pending
 * here, and the other way round. Answered trades then show in Trade History
 * (GET /v1/trade-outcomes/history reads every non-pending row).
 *
 * Mounted once in the root layout, like mobile mounts it once at the root.
 *
 * Frequency, matching mobile where mobile has a rule:
 * - The server decides what is pending: a share at least ~20h old, not
 *   answered, and not snoozed. "Still pending" snoozes it ~20h server-side.
 * - Checked on sign-in/mount and when the tab becomes visible again (web's
 *   version of mobile's "app returned to the foreground"). Never polled.
 * - One at a time, oldest first. Answering shows the next one, as on mobile.
 *
 * Web-only differences, to keep the site uncluttered:
 * - A small corner card instead of mobile's full-screen modal. It never
 *   blocks the page or navigation.
 * - It has a close button. Closing it hides the prompt for the rest of the
 *   browser session (sessionStorage) without answering or snoozing, so the
 *   row is asked about again next session or on the phone.
 * - Hidden when signed out and on "/" and "/premium" (onboarding/paywall).
 */
export function TradeOutcomePrompt() {
  const { session } = useAuth();
  const pathname = usePathname();
  const userId = session?.user?.id ?? null;
  // Keyed by the user it was fetched for, so a sign-out or account switch
  // can never show the previous user's pending trade.
  const [pending, setPending] = useState<{ userId: string; queue: PendingTradeOutcome[] } | null>(null);
  const [answering, setAnswering] = useState(false);
  // Lazy read is hydration-safe: the server and the first client render
  // both have no session yet, so both render nothing either way.
  const [dismissed, setDismissed] = useState(isTradeOutcomePromptDismissed);
  const checking = useRef(false);

  useEffect(() => {
    if (!userId) return;
    let cancelled = false;
    const checkPending = () => {
      if (checking.current || isTradeOutcomePromptDismissed()) return;
      checking.current = true;
      api
        .getPendingTradeOutcomes()
        .then((result) => {
          if (cancelled) return;
          setPending({ userId, queue: Array.isArray(result?.outcomes) ? result.outcomes : [] });
        })
        .catch(() => {
          // Silent: this is a courtesy prompt, not core functionality.
        })
        .finally(() => {
          checking.current = false;
        });
    };
    checkPending();
    const onVisibility = () => {
      if (document.visibilityState === "visible") checkPending();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      cancelled = true;
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [userId]);

  const current = pending && pending.userId === userId ? (pending.queue[0] ?? null) : null;

  const answer = async (outcome: TradeOutcomeAnswer) => {
    if (!current || answering) return;
    setAnswering(true);
    try {
      await api.answerTradeOutcome(current.id, outcome);
      setPending((prev) => (prev ? { ...prev, queue: prev.queue.filter((item) => item.id !== current.id) } : prev));
    } catch {
      // Leave it in the queue; the next visibility check asks again.
    } finally {
      setAnswering(false);
    }
  };

  const dismiss = () => {
    setTradeOutcomePromptDismissed();
    setDismissed(true);
  };

  if (!session || !current || dismissed) return null;
  if (pathname && HIDDEN_PATHS.has(pathname)) return null;

  const summary = current.trade_summary ?? { send: [], receive: [], partner_team_name: "", value_edge_label: "" };
  const sendNames = (summary.send ?? []).map((a) => a.name).join(", ") || "Nothing";
  const receiveNames = (summary.receive ?? []).map((a) => a.name).join(", ") || "Nothing";
  const partner = current.partner_team_name || summary.partner_team_name || "your trade partner";

  const buttonBase = "flex-1 text-sm font-bold py-2 px-3 disabled:opacity-60";

  return (
    <section
      role="region"
      aria-label="Did this trade happen?"
      data-testid="trade-outcome-prompt"
      // Bottom-right on desktop; on phone-width it sits above the GM orb
      // (bottom-3, 3.25rem tall) so the two never overlap. z-30 keeps it
      // under the orb (40) and every sheet/modal (50).
      className="glass-surface fixed right-4 left-4 bottom-20 md:left-auto md:bottom-6 md:right-6 md:w-96 flex flex-col gap-3 p-4"
      style={{ zIndex: 30, maxWidth: "24rem", marginLeft: "auto" }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex flex-col gap-0.5">
          <h2 style={{ font: "var(--font-card-title)", color: "var(--color-text-primary)" }}>Did this trade happen?</h2>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            You shared a trade with {partner}
          </p>
        </div>
        <button
          type="button"
          aria-label="Dismiss trade follow-up"
          onClick={dismiss}
          className="shrink-0 text-sm"
          style={{ color: "var(--color-text-muted)" }}
        >
          ✕
        </button>
      </div>

      <div
        className="flex flex-col gap-0.5 p-3"
        style={{
          background: "var(--surface-1)",
          border: "var(--border-width-default) solid var(--border-subtle)",
          borderRadius: "var(--radius-md)",
        }}
      >
        <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
          You sent
        </span>
        <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
          {sendNames}
        </span>
        <span className="text-xs font-bold uppercase mt-1" style={{ color: "var(--color-text-muted)" }}>
          You received
        </span>
        <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
          {receiveNames}
        </span>
      </div>

      <div className="flex flex-col gap-2" aria-busy={answering}>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={answering}
            onClick={() => void answer("yes")}
            className={buttonBase}
            style={{ background: "var(--color-success)", color: "#fff", borderRadius: "var(--radius-control)" }}
          >
            Yes, it happened
          </button>
          <button
            type="button"
            disabled={answering}
            onClick={() => void answer("no")}
            className={buttonBase}
            style={{ background: "var(--color-danger)", color: "#fff", borderRadius: "var(--radius-control)" }}
          >
            No
          </button>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={answering}
            onClick={() => void answer("still_pending")}
            className={buttonBase}
            style={{
              background: "var(--surface-raised)",
              color: "var(--color-text-secondary)",
              border: "var(--border-width-default) solid var(--border-standard)",
              borderRadius: "var(--radius-control)",
            }}
          >
            Still pending
          </button>
          <button
            type="button"
            disabled={answering}
            onClick={() => void answer("didnt_send")}
            className={buttonBase}
            style={{
              background: "var(--surface-raised)",
              color: "var(--color-text-secondary)",
              border: "var(--border-width-default) solid var(--border-standard)",
              borderRadius: "var(--radius-control)",
            }}
          >
            Didn&apos;t send
          </button>
        </div>
      </div>
    </section>
  );
}
