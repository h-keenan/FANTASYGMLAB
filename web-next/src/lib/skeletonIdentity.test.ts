import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Loading identity guard: no bare "Loading..." text and no spinner-only screens outside the shared Skeleton module
// (rules and allowlist live in scripts/check_skeleton_identity.mjs, which also scans mobile/).
describe("loading identity scan", () => {
  it("finds no bare loading text or spinner-only screens outside the skeleton module", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_skeleton_identity.mjs");
    let output = "";
    try {
      output = execFileSync("node", [script], { encoding: "utf8", stdio: "pipe" });
    } catch (error) {
      const failure = error as { stderr?: string; stdout?: string };
      throw new Error(failure.stderr || failure.stdout || String(error));
    }
    expect(output).toContain("passed");
  });
});
