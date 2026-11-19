/**
 * Content-Security-Policy (REPORT-ONLY for now; enforcement is a later step once the reports are clean).
 *
 * Built per request in src/proxy.ts with a fresh nonce. The nonce is passed to the layout through the `x-nonce` request
 * header (see lib/nonce.ts) so the two inline <head> scripts (THEME_BOOT_SCRIPT, the early-fetch script) and the landing
 * page's inline scripts carry it. Next reads the nonce from the request CSP header and applies it to its own scripts.
 *
 * Origins below come from a grep of web-next/src for every external host (not guessed):
 *  - API origin (NEXT_PUBLIC_API_BASE_URL, api.fantasygmlab.com in production): fetch/XHR in connect-src, share images in img-src.
 *  - Supabase (NEXT_PUBLIC_SUPABASE_URL): auth/REST in connect-src, avatars/storage in img-src.
 *  - sleepercdn.com: player headshots, team logos and manager avatars in img-src (lib/avatarFallback.ts, TeamAvatar).
 *  - Sentry ingest host, derived from NEXT_PUBLIC_SENTRY_DSN, in connect-src (lib/errorReporter.ts); absent without a DSN.
 *  - Google Fonts: fonts.googleapis.com (stylesheet) and fonts.gstatic.com (files). Nothing loads them today; allowed so a
 *    font add does not become a violation.
 *  - There is no third-party analytics script: analytics events post to the API origin (lib/analytics.ts).
 *
 * Scripts: nonce + 'strict-dynamic' only, never 'unsafe-inline'. The landing page's two inline scripts are constant strings
 * rendered by a synchronous server component (app/page.tsx), so they are allowed by sha256 hash instead of a nonce. Styles: React `style={{}}` props render as inline style
 * ATTRIBUTES in server HTML, which only 'unsafe-inline' can allow, so style-src-attr carries it (an inline style attribute
 * cannot run script); style ELEMENTS stay on nonce/self, which is where the injection risk is.
 */

import { createHash } from "node:crypto";

export const CSP_HEADER_NAME = "Content-Security-Policy-Report-Only";
export const NONCE_HEADER = "x-nonce";
export const CSP_REPORT_PATH = "/api/csp-report";

const SLEEPER_CDN = "https://sleepercdn.com";
const API_ORIGIN_PROD = "https://api.fantasygmlab.com";
const GOOGLE_FONTS_STYLES = "https://fonts.googleapis.com";
const GOOGLE_FONTS_FILES = "https://fonts.gstatic.com";

/** Cryptographically random, base64, unique per call. Works in the proxy (Edge-style) runtime. */
export function generateNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let binary = "";
  for (const b of bytes) binary += String.fromCharCode(b);
  return btoa(binary);
}

/** The origin of a URL, or null when it is missing or malformed. */
export function originOf(raw: string | undefined | null): string | null {
  if (!raw) return null;
  try {
    const u = new URL(raw.trim());
    return u.protocol === "https:" || u.protocol === "http:" ? u.origin : null;
  } catch {
    return null;
  }
}

/** Sentry ingest origin from a DSN (https://<key>@<host>/<project>); null for a missing or malformed DSN. */
export function sentryOriginFromDsn(dsn: string | undefined | null): string | null {
  if (!dsn) return null;
  try {
    const u = new URL(dsn.trim());
    return u.protocol === "https:" ? u.origin : null;
  } catch {
    return null;
  }
}

export interface CspOptions {
  nonce: string;
  isDev?: boolean;
  apiBase?: string;
  supabaseUrl?: string;
  sentryDsn?: string;
  /** Constant inline script bodies to allow by sha256 hash (the exact text between the <script> tags). */
  hashedScripts?: string[];
}

/** 'sha256-<base64>' CSP source for an inline script body. */
export function scriptHashSource(body: string): string {
  return `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;
}

function unique(values: Array<string | null | undefined>): string[] {
  return [...new Set(values.filter((v): v is string => Boolean(v)))];
}

export function buildCsp({ nonce, isDev = false, apiBase, supabaseUrl, sentryDsn, hashedScripts = [] }: CspOptions): string {
  const api = originOf(apiBase);
  const supabase = originOf(supabaseUrl);
  const sentry = sentryOriginFromDsn(sentryDsn);
  const connect = unique(["'self'", api, API_ORIGIN_PROD, supabase, sentry]);
  const img = unique(["'self'", "data:", "blob:", SLEEPER_CDN, api, API_ORIGIN_PROD, supabase]);
  const directives: Array<[string, string[]]> = [
    ["default-src", ["'self'"]],
    // React uses eval for dev-only stack reconstruction; production never needs it.
    ["script-src", ["'self'", `'nonce-${nonce}'`, "'strict-dynamic'", ...hashedScripts.map(scriptHashSource), ...(isDev ? ["'unsafe-eval'"] : [])]],
    ["style-src-elem", ["'self'", `'nonce-${nonce}'`, GOOGLE_FONTS_STYLES]],
    ["style-src-attr", ["'unsafe-inline'"]],
    ["img-src", img],
    ["font-src", ["'self'", "data:", GOOGLE_FONTS_FILES]],
    ["connect-src", connect],
    ["worker-src", ["'self'", "blob:"]],
    ["manifest-src", ["'self'"]],
    ["object-src", ["'none'"]],
    ["base-uri", ["'self'"]],
    ["frame-ancestors", ["'none'"]],
    ["report-uri", [CSP_REPORT_PATH]],
  ];
  return directives.map(([name, values]) => `${name} ${values.join(" ")}`).join("; ");
}
