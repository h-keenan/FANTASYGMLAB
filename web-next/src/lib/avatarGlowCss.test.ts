import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(process.cwd(), "src/app/globals.css"), "utf8");

describe("prestige avatar glow", () => {
  it("is a blurred box-shadow halo with no border, outline or filled box, animated with opacity only", () => {
    const blocks = [...css.matchAll(/\.prestige-glow(?:::before|::after)?(?:,\s*\.prestige-glow::after)?\s*\{[^}]*\}/g)].map((m) => m[0]);
    const frames = ["prestige-glow-out", "prestige-glow-in"].map((n) => css.match(new RegExp(`@keyframes ${n}\\s*\\{[\\s\\S]*?\\n\\}`))?.[0] ?? "");
    for (const block of [...blocks, ...frames]) {
      expect(block).not.toMatch(/border:|outline|background/);
    }
    for (const f of frames) {
      expect(f).toMatch(/opacity/);
      expect(f).not.toMatch(/box-shadow|filter/); // the shadows are static; only opacity animates (compositor)
    }
    // blur radius is always non-zero so the shadow is a soft halo, never a hard ring
    expect(css).toMatch(/box-shadow: 0 0 var\(--glow-min/);
    expect(css).toMatch(/box-shadow: 0 0 var\(--glow-max/);
  });
  it("PQV hero glow has no zero-blur spread ring", () => {
    const rule = css.match(/\.pqv-avatar-glow\s*\{[^}]*\}/)?.[0] ?? "";
    expect(rule).toMatch(/box-shadow/);
    expect(rule).not.toMatch(/0 0 0 \d+px/);
    expect(rule).not.toMatch(/border:/);
  });
});
