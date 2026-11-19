/**
 * Sanitizer for CSP violation reports (POST /api/csp-report). Keeps only what is needed to fix a policy gap: the violated
 * directive, the blocked resource's ORIGIN (never its path or query), the page's path (never its query or hash), and the
 * disposition. No IP, user agent, cookies, referrer, script sample or full URLs are ever kept or logged.
 */

export const CSP_REPORT_MAX_BYTES = 8 * 1024;
/** Fraction of reports logged. A broken policy produces one report per page view per resource; a sample is plenty. */
export const CSP_REPORT_SAMPLE_RATE = 0.2;

export interface CspViolationSummary {
  directive: string;
  blocked: string;
  page: string;
  disposition: string;
}

function originOnly(raw: unknown): string {
  if (typeof raw !== "string" || !raw) return "unknown";
  if (raw === "inline" || raw === "eval" || raw === "data" || raw === "blob" || raw === "self") return raw;
  try {
    const u = new URL(raw);
    return u.protocol === "data:" || u.protocol === "blob:" ? u.protocol.slice(0, -1) : u.origin;
  } catch {
    return "unknown";
  }
}

function pathOnly(raw: unknown): string {
  if (typeof raw !== "string" || !raw) return "unknown";
  try {
    return new URL(raw).pathname.slice(0, 120);
  } catch {
    return "unknown";
  }
}

const token = (v: unknown) => (typeof v === "string" ? v.replace(/[^a-zA-Z0-9-]/g, "").slice(0, 40) || "unknown" : "unknown");

/** Handles the legacy `report-uri` shape ({"csp-report": {...}}) and the Reporting API shape ([{type, body}]). */
export function summarizeCspReport(payload: unknown): CspViolationSummary | null {
  const first = Array.isArray(payload) ? payload[0] : payload;
  if (!first || typeof first !== "object") return null;
  const record = first as Record<string, unknown>;
  const body = (record["csp-report"] ?? record["body"] ?? null) as Record<string, unknown> | null;
  if (!body || typeof body !== "object") return null;
  return {
    directive: token(body["effective-directive"] ?? body["effectiveDirective"] ?? body["violated-directive"] ?? body["violatedDirective"]),
    blocked: originOnly(body["blocked-uri"] ?? body["blockedURL"] ?? body["blockedUri"]),
    page: pathOnly(body["document-uri"] ?? body["documentURL"] ?? body["documentUri"]),
    disposition: token(body["disposition"]),
  };
}
