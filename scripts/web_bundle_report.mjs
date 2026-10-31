// Per-route client JS (gzip KB) from a finished `next build` (Turbopack).
// Union of the chunks the route's client-reference manifest lists (layout +
// page client modules), so lazily imported chunks (next/dynamic) are not counted.
//   node scripts/web_bundle_report.mjs [web-next-dir]
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const root = path.resolve(process.argv[2] || "web-next");
const next = path.join(root, ".next");
const appDir = path.join(next, "server", "app");
const gz = new Map();
const size = (c) => {
  const f = path.join(next, c.replace(/^\/_next\//, ""));
  if (!gz.has(f)) gz.set(f, fs.existsSync(f) && f.endsWith(".js") ? zlib.gzipSync(fs.readFileSync(f)).length : 0);
  return gz.get(f);
};
const rows = [];
(function walk(dir) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) walk(p);
    else if (e.name === "page_client-reference-manifest.js") {
      const src = fs.readFileSync(p, "utf8");
      const m = src.match(/__RSC_MANIFEST\["([^"]+)"\]\s*=\s*(\{.*\})\s*;?\s*$/s);
      if (!m) continue;
      const chunks = new Set();
      for (const mod of Object.values(JSON.parse(m[2]).clientModules)) for (const c of mod.chunks || []) chunks.add(c);
      rows.push([m[1].replace(/\/page$/, "") || "/", chunks.size, [...chunks].reduce((a, c) => a + size(c), 0)]);
    }
  }
})(appDir);
rows.sort((a, b) => b[2] - a[2]);
let total = 0;
for (const [r, n, b] of rows) console.log(`${(b / 1024).toFixed(0).padStart(5)} KB gz  ${String(n).padStart(3)} chunks  ${r}`);
for (const f of gz.keys()) total += gz.get(f);
console.log(`all chunks reachable: ${(total / 1024).toFixed(0)} KB gz`);
