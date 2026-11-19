import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

// Source-level guard for the Sim trade builder (its render needs a full game context): a failed roster load must show the
// shared ErrorState with a retry, never leave the builder silently empty (docs/audits/2026-11-silent-failures.md #5).
describe("SimGameTrades roster load", () => {
  const source = readFileSync(join(__dirname, "SimGameTrades.tsx"), "utf8");
  it("surfaces a failed roster load with a retry", () => {
    expect(source).toMatch(/setRosterFailed\(true\)/);
    expect(source).toMatch(/<ErrorState[^>]*SIM_LOAD_ERROR\.roster[^>]*onRetry=/);
  });
  it("no longer swallows getSimGameTeam failures", () => {
    expect(source.replace(/\s+/g, " ")).not.toMatch(/getSimGameTeam\([^)]*\)[^;]{0,260}\.catch\(\(\) => \{\}\)/);
  });
});
