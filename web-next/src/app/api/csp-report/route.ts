import { CSP_REPORT_MAX_BYTES, CSP_REPORT_SAMPLE_RATE, summarizeCspReport } from "@/lib/cspReport";

/**
 * POST /api/csp-report: receives Content-Security-Policy-Report-Only violation reports (see lib/csp.ts). A sample is logged
 * as one sanitized line (directive, blocked origin, page path; no PII, see lib/cspReport.ts). Always answers 204 so a bad or
 * oversized report can never surface anywhere. Not a secret-bearing endpoint: it only logs.
 */
export async function POST(request: Request): Promise<Response> {
  try {
    if (Math.random() >= CSP_REPORT_SAMPLE_RATE) return new Response(null, { status: 204 });
    const raw = await request.text();
    if (raw.length > CSP_REPORT_MAX_BYTES) return new Response(null, { status: 204 });
    const summary = summarizeCspReport(JSON.parse(raw));
    if (summary) {
      console.warn(`csp_violation directive=${summary.directive} blocked=${summary.blocked} page=${summary.page} disposition=${summary.disposition}`);
    }
  } catch {
    // Malformed report: nothing to learn, nothing to surface.
  }
  return new Response(null, { status: 204 });
}
