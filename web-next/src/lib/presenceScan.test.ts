import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Runs the repo-level guard (scripts/check_presence_usage.mjs): no NEW hand-rolled expander body (`{open ? (<div>) : null}`)
// or stray LayoutAnimation outside the shared Presence module (`Collapse` / `Presence` / `PresenceList`) and its allowlist.
describe("shared presence usage", () => {
  it("has no hand-rolled expand/collapse outside the allowlist", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_presence_usage.mjs");
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
