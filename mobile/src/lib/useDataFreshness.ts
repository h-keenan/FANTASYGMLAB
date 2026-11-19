import { useEffect, useState } from "react";

import { env } from "./env";
import type { FreshnessReport } from "./dataFreshness";

/**
 * The public freshness report (GET /v1/public/data-freshness, no auth), fetched once and shared by every FreshnessLabel on the
 * screen, then reused for 5 minutes. A failed or slow fetch is silent: no report means no label, never an error state.
 * Web twin: web-next/src/lib/useDataFreshness.ts.
 */
const TTL_MS = 5 * 60 * 1000;
let cached: { at: number; report: FreshnessReport | null } | null = null;
let inflight: Promise<FreshnessReport | null> | null = null;

function loadReport(): Promise<FreshnessReport | null> {
  if (cached && Date.now() - cached.at < TTL_MS) return Promise.resolve(cached.report);
  if (!inflight) {
    inflight = fetch(`${env.apiBaseUrl}/v1/public/data-freshness`)
      .then((response) => (response.ok ? (response.json() as Promise<FreshnessReport>) : null))
      .catch(() => null)
      .then((report) => {
        cached = { at: Date.now(), report };
        inflight = null;
        return report;
      });
  }
  return inflight;
}

export function useDataFreshness(enabled = true): FreshnessReport | null {
  const [report, setReport] = useState<FreshnessReport | null>(() => (cached && Date.now() - cached.at < TTL_MS ? cached.report : null));
  useEffect(() => {
    if (!enabled || typeof fetch !== "function") return;
    let live = true;
    void loadReport().then((next) => {
      if (live) setReport(next);
    });
    return () => {
      live = false;
    };
  }, [enabled]);
  return report;
}

/** Test seam: forget the cached report. */
export function resetDataFreshnessCache(): void {
  cached = null;
  inflight = null;
}
