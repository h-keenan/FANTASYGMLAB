import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");

describe("prestige avatar glow", () => {
  it("is a blurred box-shadow halo with no border, outline or filled box", () => {
    const rule = css.match(/\.prestige-glow\s*\{[^}]*\}/)?.[0] ?? "";
    const frames = css.match(/@keyframes prestige-glow-pulse\s*\{[\s\S]*?\n\}/)?.[0] ?? "";
    for (const block of [rule, frames]) {
      expect(block).not.toMatch(/border|outline|background/);
    }
    // blur radius is always non-zero so the shadow is a soft halo, never a hard ring
    expect(frames).toMatch(/box-shadow: 0 0 var\(--glow-min/);
    expect(frames).toMatch(/box-shadow: 0 0 var\(--glow-max/);
  });
});
