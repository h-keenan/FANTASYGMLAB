import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Nav sheet guard: destination lists are built and rendered only by the shared sheet (scripts/check_nav_sheet.mjs).

describe("nav sheet scan", () => {
  it("finds no destination list outside the shared navigation sheet", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_nav_sheet.mjs");
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
