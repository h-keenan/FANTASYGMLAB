import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Motion guard: no layout-property transitions (width/left/margin/...) and no new JS-driven app animation outside the
// reasoned allowlist in scripts/check_motion_usage.mjs (scans web-next/ and mobile/).
describe("motion scan", () => {
  it("finds no new layout-property transitions or non-native-driver animations", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_motion_usage.mjs");
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
