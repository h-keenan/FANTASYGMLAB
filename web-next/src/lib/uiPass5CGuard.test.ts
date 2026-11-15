import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** UI pass 5 D4 + D7 (coridian_, 2026-11-14). */
const APP = path.resolve(__dirname, "../../../mobile/src");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(full, out);
    else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) out.push(full);
  }
  return out;
}

describe("ui pass 5 (C)", () => {
  it("D7: the app reports failures with the in-app notice, never a system 'Could not ...' alert", () => {
    const hits: string[] = [];
    for (const file of walk(APP)) {
      readFileSync(file, "utf8").split("\n").forEach((line, i) => {
        if (/Alert\.alert\(\s*['"`](Could not|Select a league first|Name required|GM Targets is full)/.test(line)) hits.push(`${path.relative(APP, file)}:${i + 1}`);
      });
    }
    expect(hits).toEqual([]);
  });

  it("D7: NoticeProvider wraps the navigator in App.tsx", () => {
    const app = readFileSync(path.join(APP, "../App.tsx"), "utf8");
    expect(app).toMatch(/<NoticeProvider>\s*<RootNavigator \/>/);
  });

  it("D4: the phone shell is on by default for every signed-in user; the kill switch stays", () => {
    const src = readFileSync(path.resolve(__dirname, "shellNav.ts"), "utf8");
    expect(src).toContain('opts.env ?? "on"');
    expect(src).toContain('env === "off"');
  });
});
