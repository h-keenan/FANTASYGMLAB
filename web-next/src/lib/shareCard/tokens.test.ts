// @vitest-environment node
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { PLAYER_TIER_LADDER } from "@/lib/playerTier";
import { POSITION_COLOR_VAR } from "@/lib/playerPresentation";

import { SHARE_TOKEN_HEX, overallRatingTintHex, resolveTokenColor, tokenValue } from "./tokens";

/** The first (dark, default) `:root { ... }` block of globals.css. */
function darkRootTokens(): Map<string, string> {
  const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");
  const start = css.indexOf(":root {");
  const end = css.indexOf("\n}", start);
  const block = css.slice(start, end).replace(/\/\*[\s\S]*?\*\//g, "");
  const tokens = new Map<string, string>();
  for (const match of block.matchAll(/(--[a-z0-9-]+):\s*([^;]+);/gi)) {
    tokens.set(match[1], match[2].trim());
  }
  return tokens;
}

describe("share card tokens", () => {
  it("match globals.css's dark :root values exactly (no second palette)", () => {
    const root = darkRootTokens();
    for (const [name, value] of Object.entries(SHARE_TOKEN_HEX)) {
      expect(root.get(name), name).toBe(value);
    }
  });

  it("cover every tier and position color the cards can draw", () => {
    for (const tier of PLAYER_TIER_LADDER) expect(tokenValue(tier.colorVar), tier.colorVar).toBeTruthy();
    for (const colorVar of Object.values(POSITION_COLOR_VAR)) expect(tokenValue(colorVar), colorVar).toBeTruthy();
  });

  it("resolves var(--token) strings from the shared presentation helpers", () => {
    expect(resolveTokenColor("var(--color-success)")).toBe("#22c55e");
    expect(resolveTokenColor("var(--color-premium)")).toBe("#facc15");
    expect(resolveTokenColor("#123456")).toBe("#123456");
  });

  it("mirrors overallRatingTint's red -> gold -> green ramp", () => {
    expect(overallRatingTintHex(0)).toBe("#ef4444");
    expect(overallRatingTintHex(50)).toBe("#facc15");
    expect(overallRatingTintHex(100)).toBe("#22c55e");
  });
});
