// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { NextRequest } from "next/server";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { BootScripts } from "@/components/BootScripts";
import { CSP_HEADER_NAME, NONCE_HEADER, buildCsp, generateNonce, scriptHashSource, sentryOriginFromDsn } from "@/lib/csp";
import { LANDING_PENDING_SCRIPT } from "@/lib/landingPending";
import { proxy } from "@/proxy";

const opts = {
  apiBase: "https://api.fantasygmlab.com",
  supabaseUrl: "https://abcdefgh.supabase.co",
  sentryDsn: "https://key@o123.ingest.sentry.io/456",
};

function directive(policy: string, name: string): string {
  return policy.split("; ").find((d) => d.startsWith(`${name} `)) ?? "";
}

describe("buildCsp", () => {
  const policy = buildCsp({ nonce: "NONCE123", ...opts, hashedScripts: [LANDING_PENDING_SCRIPT] });

  it("allows scripts by nonce and never by unsafe-inline", () => {
    const script = directive(policy, "script-src");
    expect(script).toContain("'nonce-NONCE123'");
    expect(script).toContain("'strict-dynamic'");
    expect(script).toContain(scriptHashSource(LANDING_PENDING_SCRIPT));
    expect(script).not.toContain("unsafe-inline");
    expect(script).not.toContain("unsafe-eval");
    expect(policy).not.toMatch(/script-src[^;]*unsafe-inline/);
  });

  it("allows unsafe-eval for scripts only in development", () => {
    expect(directive(buildCsp({ nonce: "n", isDev: true }), "script-src")).toContain("'unsafe-eval'");
  });

  it("keeps unsafe-inline to inline style attributes only", () => {
    expect(directive(policy, "style-src-attr")).toBe("style-src-attr 'unsafe-inline'");
    expect(directive(policy, "style-src-elem")).not.toContain("unsafe-inline");
    expect(directive(policy, "style-src-elem")).toContain("https://fonts.googleapis.com");
  });

  it("allows the API, Supabase and Sentry origins to connect and Sleeper CDN images", () => {
    const connect = directive(policy, "connect-src");
    expect(connect).toContain("https://api.fantasygmlab.com");
    expect(connect).toContain("https://abcdefgh.supabase.co");
    expect(connect).toContain("https://o123.ingest.sentry.io");
    expect(directive(policy, "img-src")).toContain("https://sleepercdn.com");
    expect(directive(policy, "font-src")).toContain("https://fonts.gstatic.com");
  });

  it("locks down objects, base uri and framing, and reports to the first-party route", () => {
    expect(policy).toContain("object-src 'none'");
    expect(policy).toContain("base-uri 'self'");
    expect(policy).toContain("frame-ancestors 'none'");
    expect(policy).toContain("report-uri /api/csp-report");
  });

  it("derives the Sentry origin only from a valid https DSN", () => {
    expect(sentryOriginFromDsn("not a url")).toBeNull();
    expect(sentryOriginFromDsn("")).toBeNull();
    expect(directive(buildCsp({ nonce: "n" }), "connect-src")).not.toContain("sentry");
  });
});

describe("proxy", () => {
  const get = () => proxy(new NextRequest("https://app.fantasygmlab.com/dashboard/1"));

  it("sets a report-only CSP header with a nonce, and never the enforcing header", () => {
    const res = get();
    const policy = res.headers.get(CSP_HEADER_NAME) ?? "";
    expect(CSP_HEADER_NAME).toBe("Content-Security-Policy-Report-Only");
    expect(policy).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9+/=]+'/);
    expect(res.headers.get("Content-Security-Policy")).toBeNull();
  });

  it("passes the same nonce to the layout through the request headers", () => {
    const res = get();
    const nonce = res.headers.get(`x-middleware-request-${NONCE_HEADER}`);
    expect(nonce).toBeTruthy();
    expect(res.headers.get(CSP_HEADER_NAME)).toContain(`'nonce-${nonce}'`);
    expect(res.headers.get(`x-middleware-request-${CSP_HEADER_NAME.toLowerCase()}`)).toContain(`'nonce-${nonce}'`);
  });

  it("uses a different nonce on every request", () => {
    const nonces = new Set(Array.from({ length: 20 }, () => get().headers.get(`x-middleware-request-${NONCE_HEADER}`)));
    expect(nonces.size).toBe(20);
    expect(new Set(Array.from({ length: 20 }, generateNonce)).size).toBe(20);
  });
});

describe("layout scripts", () => {
  it("renders the theme boot script and the early-fetch script with the request nonce", () => {
    const html = renderToStaticMarkup(BootScripts({ nonce: "abc123==", apiBase: "https://api.fantasygmlab.com", storageKey: "sb-x-auth-token" }));
    const tags = html.match(/<script[^>]*>/g) ?? [];
    expect(tags).toHaveLength(2);
    for (const tag of tags) expect(tag).toContain('nonce="abc123=="');
    expect(html).toContain("__fdEarly");
  });

  it("app/layout.tsx reads the nonce and hands it to BootScripts", () => {
    const source = readFileSync(join(__dirname, "../app/layout.tsx"), "utf8");
    expect(source).toMatch(/await getNonce\(\)/);
    expect(source).toMatch(/<BootScripts nonce=\{nonce\}/);
    expect(source).not.toMatch(/dangerouslySetInnerHTML/);
  });

  it("getNonce reads the x-nonce request header", async () => {
    vi.resetModules();
    vi.doMock("next/headers", () => ({ headers: async () => new Headers({ [NONCE_HEADER]: "from-proxy" }) }));
    const { getNonce } = await import("@/lib/nonce");
    expect(await getNonce()).toBe("from-proxy");
    vi.doUnmock("next/headers");
  });
});
