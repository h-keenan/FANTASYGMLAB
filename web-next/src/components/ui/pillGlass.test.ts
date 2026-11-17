import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Guard: the footer pills share ONE glass token and it stays opaque, so list text behind (Players, Roster ...) never reads through
// the pill labels (owner screenshot, 2026-11-17: "...RAFT PICKS . Top 2026 Round 1" showing through).
const css = readFileSync(path.resolve(__dirname, "ui.css"), "utf8");

describe("footer pill glass", () => {
  it("defines --pill-glass-bg with at least 85% opaque stops and a strong blur", () => {
    const token = /--pill-glass-bg:([^;]+);/.exec(css)?.[1] ?? "";
    const alphas = [...token.matchAll(/(\d+)%, transparent/g)].map((m) => Number(m[1]));
    expect(alphas.length).toBeGreaterThanOrEqual(2);
    for (const a of alphas) expect(a).toBeGreaterThanOrEqual(85);
    const blur = /--pill-glass-blur:\s*blur\((\d+)px\)/.exec(css)?.[1];
    expect(Number(blur)).toBeGreaterThanOrEqual(24);
  });
  it("both footer pills use the shared token, never their own translucent fill", () => {
    for (const selector of [".bottom-tab-bar {", ".action-pill {"]) {
      const start = css.indexOf(selector);
      const block = css.slice(start, css.indexOf("}", start));
      expect(block, selector).toContain("var(--pill-glass-bg)");
      expect(block, selector).toContain("var(--pill-glass-blur)");
    }
  });
});
