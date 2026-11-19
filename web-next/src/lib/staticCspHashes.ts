import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Inline-script hashes for PRERENDERED (static / SSG / ISR) routes, so those routes stay static and still get a strict
 * script policy.
 *
 * Why this exists: a nonce needs a per-request render, which would make every route dynamic (a perf regression for the
 * marketing/SEO pages). Prerendered HTML cannot carry a per-request nonce, and its inline scripts (Next's flight data
 * `self.__next_f.push(...)`, page-specific) cannot be hashed ahead of the build. But the HTML Next serves for such a route is
 * a file under `.next/server/app/`, so the hashes of exactly what is served can be read from it. Keyed by the file's mtime so
 * an ISR regeneration (changed flight data) gets fresh hashes.
 *
 * A route with no prerendered file (dynamic route, dev server, or an ISR route not generated yet) returns null; the caller
 * then uses the per-request nonce policy.
 */

const SAFE_PATH = /^\/[A-Za-z0-9/_.\-[\]]*$/;
const JS_TYPES = new Set(["", "text/javascript", "application/javascript", "module"]);

interface Entry {
  mtimeMs: number;
  hashes: string[];
}
const cache = new Map<string, Entry>();

/**
 * Candidate HTML files for a request pathname: the build-time prerender (`.next/server/app/<route>.html`) and the on-demand
 * ISR cache (`.next/server/route-cache/APP_PAGE/<id>/$/<route>.html`, for routes with an empty generateStaticParams such as
 * /dynasty-rankings/qb). Empty for a path that cannot map to a file.
 */
export function prerenderedHtmlPaths(pathname: string, distDir = ".next"): string[] {
  if (!SAFE_PATH.test(pathname) || pathname.includes("..")) return [];
  const route = pathname.replace(/\/+$/, "") || "/index";
  const server = join(process.cwd(), distDir, "server");
  const out = [join(server, "app", `${route}.html`)];
  try {
    const base = join(server, "route-cache", "APP_PAGE");
    for (const id of readdirSync(base)) out.push(join(base, id, "$", `${route}.html`));
  } catch {
    // No ISR cache directory (dev server, or nothing generated yet).
  }
  return out;
}

/** First existing candidate file for a request pathname, or null. */
export function prerenderedHtmlPath(pathname: string, distDir = ".next"): string | null {
  return prerenderedHtmlPaths(pathname, distDir).find((f) => existsSync(f)) ?? null;
}

/** sha256 CSP sources for every executable inline <script> in an HTML document. */
export function inlineScriptHashSources(html: string): string[] {
  const out = new Set<string>();
  const re = /<script\b([^>]*)>([\s\S]*?)<\/script>/gi;
  for (let m = re.exec(html); m; m = re.exec(html)) {
    const attrs = m[1];
    if (/\bsrc\s*=/i.test(attrs)) continue;
    const type = /\btype\s*=\s*["']?([^"'\s>]*)/i.exec(attrs)?.[1]?.toLowerCase() ?? "";
    if (!JS_TYPES.has(type) || m[2] === "") continue; // data blocks (ld+json) never execute
    out.add(`'sha256-${createHash("sha256").update(m[2], "utf8").digest("base64")}'`);
  }
  return [...out];
}

/** Hashes for a prerendered route, or null when the route is not prerendered (use the nonce policy). */
export function prerenderedScriptHashes(pathname: string): string[] | null {
  const file = prerenderedHtmlPath(pathname);
  if (!file) return null;
  try {
    const mtimeMs = statSync(file).mtimeMs;
    const hit = cache.get(file);
    if (hit && hit.mtimeMs === mtimeMs) return hit.hashes;
    const hashes = inlineScriptHashSources(readFileSync(file, "utf8"));
    cache.set(file, { mtimeMs, hashes });
    return hashes;
  } catch {
    return null;
  }
}
