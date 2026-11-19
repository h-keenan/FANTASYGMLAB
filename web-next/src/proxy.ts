import { NextResponse, type NextRequest } from "next/server";

import { CSP_HEADER_NAME, NONCE_HEADER, buildCsp, generateNonce } from "@/lib/csp";
import { LANDING_PENDING_SCRIPT } from "@/lib/landingPending";
import { LANDING_SHARE_SCRIPT } from "@/lib/landingShare";

/**
 * Per-request Content-Security-Policy-Report-Only with a fresh nonce (lib/csp.ts). The nonce and the policy are set on the
 * REQUEST headers so Next applies the nonce to its own scripts during server rendering and app/layout.tsx can read it
 * (lib/nonce.ts); the policy is also set on the RESPONSE. Report-only: nothing is blocked.
 */
export function proxy(request: NextRequest) {
  const nonce = generateNonce();
  const policy = buildCsp({
    nonce,
    isDev: process.env.NODE_ENV === "development",
    apiBase: process.env.NEXT_PUBLIC_API_BASE_URL,
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
    sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    hashedScripts: [LANDING_PENDING_SCRIPT, LANDING_SHARE_SCRIPT],
  });
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(NONCE_HEADER, nonce);
  requestHeaders.set(CSP_HEADER_NAME, policy);
  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set(CSP_HEADER_NAME, policy);
  return response;
}

export const config = {
  matcher: [
    // Skip static assets and prefetches: they render no HTML, so there is nothing to nonce.
    {
      source: "/((?!api/csp-report|_next/static|_next/image|favicon.ico|icon.png).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
