import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("PillRow scroll variant", () => {
  it("segments size to their label (flex-basis auto), never a bare flex-1 with shrink-0 (labels overlapped at the 44px minimum)", () => {
    const src = readFileSync(path.resolve(__dirname, "../components/PillRow.tsx"), "utf8");
    expect(src).toContain('"flex-[1_0_auto] min-w-[var(--touch-target-min)]"');
    expect(src).not.toContain('"flex-1 shrink-0');
  });
});
