import { describe, expect, it } from "vitest";

import { simCrestArt, simCrestHash, simCrestLabel, simCrestLetter, simCrestSpec } from "./simCrest";

describe("simCrestSpec", () => {
  it("is deterministic and ignores case and padding", () => {
    expect(simCrestSpec("Gridiron Ghosts")).toEqual(simCrestSpec("  gridiron ghosts "));
    expect(simCrestHash("a")).toBe(simCrestHash("a"));
  });

  it("gives different teams different crests across the league", () => {
    const names = ["Gridiron Ghosts", "Night Owls", "Blitz Brigade", "The Hail Marys", "Dynasty Dogs", "Red Zone Rebels", "Waiver Wolves", "Sunday Scaries", "Fourth And Long", "Pick Six", "Trade Bait", "Bye Week Bandits"];
    const keys = new Set(names.map((n) => JSON.stringify(simCrestSpec(n))));
    expect(keys.size).toBeGreaterThanOrEqual(11);
  });

  it("picks the letter from the first meaningful word", () => {
    expect(simCrestLetter("The Hail Marys")).toBe("H");
    expect(simCrestLetter("  night owls")).toBe("N");
    expect(simCrestLetter("")).toBe("?");
    expect(simCrestSpec("The Hail Marys").letter).toBe("H");
  });

  it("keeps the letter readable: ink contrasts with the field", () => {
    const lum = (hex: string) => {
      const n = parseInt(hex.slice(1), 16);
      return [(n >> 16) & 255, (n >> 8) & 255, n & 255].reduce((acc, v, i) => {
        const c = v / 255;
        const lin = c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
        return acc + lin * [0.2126, 0.7152, 0.0722][i];
      }, 0);
    };
    for (const name of ["A", "B", "Cobras", "Dragons", "Eagles", "Falcons", "Giants", "Hawks", "Ibex", "Jets", "Kings", "Lions"]) {
      const spec = simCrestSpec(name);
      const [hi, lo] = [Math.max(lum(spec.primary), lum(spec.ink)), Math.min(lum(spec.primary), lum(spec.ink))];
      expect((hi + 0.05) / (lo + 0.05)).toBeGreaterThan(3);
    }
  });

  it("describes drawable art in a 64 box", () => {
    const art = simCrestArt(simCrestSpec("Night Owls"));
    expect(art.viewBox).toBe("0 0 64 64");
    expect(art.outline.startsWith("M")).toBe(true);
    expect(simCrestLabel("Night Owls")).toBe("Night Owls emblem");
  });
});
