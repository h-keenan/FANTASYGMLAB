import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Runs the repo-level drift guard (scripts/check_lib_twins.mjs) so a local
// `npm test` catches a web/mobile lib twin edited on one side only. CI also
// runs the script directly in the lib-twins job, which fires on mobile-only
// changes too (this web-next job would not).
describe("web/mobile lib twins", () => {
  it("has no unclassified or drifted twin files", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_lib_twins.mjs");
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
