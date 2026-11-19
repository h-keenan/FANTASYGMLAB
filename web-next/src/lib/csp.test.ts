// @vitest-environment node
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, utimesSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { readFileSync } from "node:fs";
import { NextRequest } from "next/server";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BOOT_SCRIPTS, BootScripts } from "@/components/BootScripts";
import { CSP_HEADER_NAME, NONCE_HEADER, buildCsp, generateNonce, scriptHashSource, sentryOriginFromDsn } from "@/lib/csp";
import { inlineScriptHashSources, prerenderedHtmlPaths, prerenderedScriptHashes } from "@/lib/staticCspHashes";
import { proxy } from "@/proxy";

const opts = {
  apiBase: "https://api.fantasygmlab.com",
  supabaseUrl: "https://abcdefgh.supabase.co",
  sentryDsn: "https://key@o123.ingest.sentry.io/456",
};

const sha = (body: string) => `'sha256-${createHash("sha256").update(body, "utf8").digest("base64")}'`;

function directive(policy: string, name: string): string {
  return policy.split("; ").find((d) => d.startsWith(`${name} `)) ?? "";
}

describe("buildCsp", () => {
  const policy = buildCsp({ nonce: "NONCE123", ...opts, hashedScripts: ["boot()"] });

  it("allows scripts by nonce and hash and never by unsafe-inline", () => {
    const script = directive(policy, "script-src");
    expect(script).toContain("'nonce-NONCE123'");
    expect(script).toContain("'strict-dynamic'");
    expect(script).toContain(scriptHashSource("boot()"));
    expect(script).not.toContain("unsafe-inline");
    expect(script).not.toContain("unsafe-eval");
  });

  it("a prerendered-route policy has hashes and 'self', no nonce and no strict-dynamic", () => {
    const script = directive(buildCsp({ ...opts, scriptHashSources: ["'sha256-abc'"] }), "script-src");
    expect(script).toBe("script-src 'self' 'sha256-abc'");
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

describe("staticCspHashes", () => {
  it("hashes executable inline scripts only, skipping external and data scripts", () => {
    const html =
      '<script src="/a.js"></script><script>self.__next_f.push([1,"x"])</script><script type="application/ld+json">{"a":1}</script><script type="text/javascript">boot()</script><script></script>';
    expect(inlineScriptHashSources(html).sort()).toEqual([sha('self.__next_f.push([1,"x"])'), sha("boot()")].sort());
  });

  it("maps request paths to prerendered files and refuses traversal", () => {
    expect(prerenderedHtmlPaths("/")[0]).toMatch(/\.next\/server\/app\/index\.html$/);
    expect(prerenderedHtmlPaths("/legal/terms/")[0]).toMatch(/server\/app\/legal\/terms\.html$/);
    expect(prerenderedHtmlPaths("/../../etc/passwd")).toEqual([]);
    expect(prerenderedHtmlPaths("/a b")).toEqual([]);
  });

  it("reads a prerendered file's hashes, refreshes them when it is regenerated, and returns null when there is none", () => {
    const cwd = mkdtempSync(join(tmpdir(), "csp-"));
    mkdirSync(join(cwd, ".next/server/app"), { recursive: true });
    const file = join(cwd, ".next/server/app/news.html");
    writeFileSync(file, "<script>one()</script>");
    vi.spyOn(process, "cwd").mockReturnValue(cwd);
    expect(prerenderedScriptHashes("/news")).toEqual([sha("one()")]);
    writeFileSync(file, "<script>two()</script>");
    utimesSync(file, new Date(), new Date(Date.now() + 5000));
    expect(prerenderedScriptHashes("/news")).toEqual([sha("two()")]);
    expect(prerenderedScriptHashes("/dashboard/123")).toBeNull();
    // On-demand ISR output (empty generateStaticParams) lives in the route cache, not under server/app.
    mkdirSync(join(cwd, ".next/server/route-cache/APP_PAGE/abc/$/dynasty-rankings"), { recursive: true });
    writeFileSync(join(cwd, ".next/server/route-cache/APP_PAGE/abc/$/dynasty-rankings/qb.html"), "<script>isr()</script>");
    expect(prerenderedScriptHashes("/dynasty-rankings/qb")).toEqual([sha("isr()")]);
    vi.restoreAllMocks();
  });
});

describe("proxy", () => {
  afterEach(() => vi.restoreAllMocks());
  const get = (path = "/dashboard/1") => proxy(new NextRequest(`https://app.fantasygmlab.com${path}`));
  const REQ_NONCE = `x-middleware-request-${NONCE_HEADER}`;

  it("a dynamic route gets a report-only CSP with a nonce, and never the enforcing header", () => {
    const res = get();
    const policy = res.headers.get(CSP_HEADER_NAME) ?? "";
    expect(CSP_HEADER_NAME).toBe("Content-Security-Policy-Report-Only");
    expect(policy).toMatch(/script-src[^;]*'nonce-[A-Za-z0-9+/=]+'/);
    expect(res.headers.get("Content-Security-Policy")).toBeNull();
  });

  it("passes the same nonce to Next through the request headers", () => {
    const res = get();
    const nonce = res.headers.get(REQ_NONCE);
    expect(nonce).toBeTruthy();
    expect(res.headers.get(CSP_HEADER_NAME)).toContain(`'nonce-${nonce}'`);
    expect(res.headers.get(`x-middleware-request-${CSP_HEADER_NAME.toLowerCase()}`)).toContain(`'nonce-${nonce}'`);
  });

  it("uses a different nonce on every dynamic request", () => {
    expect(new Set(Array.from({ length: 20 }, () => get().headers.get(REQ_NONCE))).size).toBe(20);
    expect(new Set(Array.from({ length: 20 }, generateNonce)).size).toBe(20);
  });

  it("both policies allow the boot scripts by hash", () => {
    const hashes = BOOT_SCRIPTS().map(scriptHashSource);
    expect(hashes).toHaveLength(2);
    for (const h of hashes) expect(get().headers.get(CSP_HEADER_NAME)).toContain(h);
  });

  it("a prerendered route gets hashes from its HTML, no nonce, and no per-request header (so it can stay static)", async () => {
    vi.resetModules();
    vi.doMock("@/lib/staticCspHashes", () => ({ prerenderedScriptHashes: () => ["'sha256-STATICPAGE'"] }));
    const { proxy: staticProxy } = await import("@/proxy");
    const res = staticProxy(new NextRequest("https://app.fantasygmlab.com/news"));
    const policy = res.headers.get(CSP_HEADER_NAME) ?? "";
    expect(policy).toContain("'sha256-STATICPAGE'");
    expect(directive(policy, "script-src")).not.toMatch(/nonce-|strict-dynamic|unsafe-inline/);
    expect(res.headers.get(REQ_NONCE)).toBeNull();
    for (const h of BOOT_SCRIPTS().map(scriptHashSource)) expect(policy).toContain(h);
    vi.doUnmock("@/lib/staticCspHashes");
  });
});

describe("layout scripts", () => {
  it("renders exactly the two boot scripts whose bodies the policy hashes", () => {
    const html = renderToStaticMarkup(BootScripts());
    const bodies = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
    expect(bodies).toHaveLength(2);
    expect(inlineScriptHashSources(html).sort()).toEqual(BOOT_SCRIPTS().map(scriptHashSource).sort());
    expect(html).toContain("__fdEarly");
  });

  it("app/layout.tsx never reads request headers, so prerendered routes stay static", () => {
    const source = readFileSync(join(__dirname, "../app/layout.tsx"), "utf8");
    expect(source).not.toMatch(/next\/headers|getNonce|await headers\(/);
    expect(source).toMatch(/<BootScripts \/>/);
    expect(source).not.toMatch(/dangerouslySetInnerHTML/);
  });
});
