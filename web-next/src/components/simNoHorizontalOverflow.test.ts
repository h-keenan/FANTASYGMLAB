import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Regression (owner report "I can't scroll", Fantasy Sim Team tab on a phone): a CSS grid whose phone track
// is `auto` sizes to its content's min-content, so one wide row made the whole page wider than the viewport
// (iOS Safari then zooms out and the page cannot scroll sideways or settle). Every sim grid that only becomes
// two columns at a breakpoint must pin its phone track to `minmax(0, 1fr)` (Tailwind: grid-cols-1 or
// grid-cols-[minmax(0,1fr)]), so rows shrink/truncate instead of widening the page.
const dir = __dirname;
const files = readdirSync(dir).filter((f) => /^Sim.*\.tsx$/.test(f) && !f.endsWith(".test.tsx"));

describe("Fantasy Sim grids cannot widen the page on phones", () => {
  it.each(files)("%s: a `grid` that gains columns at a breakpoint pins its phone track", (file) => {
    const src = readFileSync(join(dir, file), "utf8");
    const offenders: string[] = [];
    for (const m of src.matchAll(/className="([^"]*)"/g)) {
      const cls = m[1].split(/\s+/);
      const isGrid = cls.includes("grid");
      const grows = cls.some((c) => /^(sm|md|lg|xl):grid-cols-\d/.test(c));
      const pinned = cls.some((c) => c === "grid-cols-1" || c.startsWith("grid-cols-[minmax(0,1fr)]"));
      if (isGrid && grows && !pinned) offenders.push(m[1]);
    }
    expect(offenders).toEqual([]);
  });

  it("the Team tab's lineup/bench grid and its sections can shrink below their content", () => {
    const src = readFileSync(join(dir, "SimGameTeam.tsx"), "utf8");
    expect(src).toContain('grid grid-cols-[minmax(0,1fr)] gap-2 lg:grid-cols-2');
    expect(src).toContain('id="sim.team.lineup"');
    expect(src).toContain('<div className="flex min-w-0 flex-col gap-1">');
  });
});
