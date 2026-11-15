import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Source-scan guard for docs/audits/2026-11-ui-consistency-audit-4.md. Each rule is something the audit found drifting
 * between pages (and between web and app) that a shared component or token already answers:
 *
 *  1. One verb for "run it again": "Try again". "Retry" was the label on a handful of one-off buttons (web and app).
 *  2. One secondary call to action: `Button variant="accentOutline"`. Hand-rolled `border: 1px solid var(--color-accent)`
 *     buttons were square-cornered and 36/44px/chip-sized depending on the page.
 *  3. One corner for text fields and selects: `.filter-input` / `.filter-select` take `--radius-control` like <Input>/<Select>.
 *  4. One caption on the in-row value stat: "Value" (web and app twins), never a second wording per page.
 *  5. A person's name in a JSX text slot goes through <PlayerName> (J. Surname ladder), never a bare `{player.name}`.
 */
const WEB_ROOT = path.resolve(__dirname, "..");
const APP_ROOT = path.resolve(__dirname, "../../../mobile/src");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      walk(full, out);
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) out.push(full);
  }
  return out;
}

function scan(root: string, re: RegExp, skip: RegExp = /$^/): string[] {
  const hits: string[] = [];
  for (const file of walk(root)) {
    if (skip.test(file)) continue;
    readFileSync(file, "utf8").split("\n").forEach((line, i) => {
      if (re.test(line)) hits.push(`${path.relative(root, file)}:${i + 1}: ${line.trim().slice(0, 110)}`);
    });
  }
  return hits;
}

describe("ui consistency guard (audit 4)", () => {
  it("nobody labels a button 'Retry' (the verb is 'Try again')", () => {
    // JSX text `>Retry<`, a Button label prop, or a string literal passed as a label. Accessibility names like `Retry ${league}` are fine.
    const re = />\s*Retry\s*</;
    const labelProp = /\blabel=["']Retry["']|\?\s*["']Retry["']\s*:/;
    const hits = [...scan(WEB_ROOT, re), ...scan(APP_ROOT, re), ...scan(WEB_ROOT, labelProp), ...scan(APP_ROOT, labelProp)];
    expect(hits).toEqual([]);
  });

  it("no hand-rolled accent-outline button: use Button variant=\"accentOutline\"", () => {
    const re = /color:\s*"var\(--color-accent\)"[^}]*border:\s*"1px solid var\(--color-accent\)"/;
    const hits = scan(WEB_ROOT, re, /components\/Button\.tsx$/);
    expect(hits).toEqual([]);
    // The twin variant exists on both platforms.
    expect(readFileSync(path.join(WEB_ROOT, "components/Button.tsx"), "utf8")).toContain('"accentOutline"');
    expect(readFileSync(path.join(APP_ROOT, "components/Button.tsx"), "utf8")).toContain("'accentOutline'");
  });

  it(".filter-input and .filter-select use the control radius", () => {
    const css = readFileSync(path.join(WEB_ROOT, "app/globals.css"), "utf8");
    const rule = /\.filter-input,\s*\.filter-select\s*\{([^}]*)\}/.exec(css);
    expect(rule).not.toBeNull();
    expect(rule![1]).toMatch(/border-radius:\s*var\(--radius-control\)/);
  });

  it("the in-row ValueStat caption is 'Value' on web and app", () => {
    expect(readFileSync(path.join(WEB_ROOT, "components/ValueStat.tsx"), "utf8")).toMatch(/label = "Value",/);
    expect(readFileSync(path.join(APP_ROOT, "components/ValueStat.tsx"), "utf8")).toMatch(/label = 'Value',/);
  });

  it("a bare {player.name} / {p.name} is never a web JSX text child (use <PlayerName>)", () => {
    // SimGameHomeCards lists names inside a wrapping sentence ("Give A, B"), where the full name wraps and is never cut.
    const hits = scan(WEB_ROOT, />\s*\{(?:player|p)\.name\}\s*</, /app\/design\/|SimGameHomeCards\.tsx$/);
    expect(hits).toEqual([]);
  });
});
