import { NextResponse, type NextRequest } from "next/server";

import { BOOT_SCRIPTS } from "@/components/BootScripts";
import { CSP_HEADER_NAME, NONCE_HEADER, buildCsp, generateNonce } from "@/lib/csp";
import { prerenderedScriptHashes } from "@/lib/staticCspHashes";

/**
 * Content-Security-Policy-Report-Only, chosen per request (lib/csp.ts):
 *  - a prerendered route (its HTML exists under .next/server/app) gets a hash policy and stays static;
 *  - every other route gets a fresh nonce on the REQUEST headers (Next applies it to its own scripts while rendering) and
 *    on the response.
 * Report-only: nothing is blocked.
 */
export function proxy(request: NextRequest) {
  const common = {
    isDev: process.env.NODE_ENV === "development",
    apiBase: process.env.NEXT_PUBLIC_API_BASE_URL,
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL,
    sentryDsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
    hashedScripts: BOOT_SCRIPTS(),
  };
  const staticHashes = prerenderedScriptHashes(request.nextUrl.pathname);
  if (staticHashes) {
    const response = NextResponse.next();
    response.headers.set(CSP_HEADER_NAME, buildCsp({ ...common, scriptHashSources: staticHashes }));
    return response;
  }
  const nonce = generateNonce();
  const policy = buildCsp({ ...common, nonce });
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
