import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Runs scripts/check_verdict_colors.mjs so a local `npm test` catches a hard-coded verdict or probability colour.
describe("verdict colour guard", () => {
  const script = path.resolve(__dirname, "../../../scripts/check_verdict_colors.mjs");
  it("passes on the tree", () => {
    expect(execFileSync("node", [script], { encoding: "utf8", stdio: "pipe" })).toContain("passed");
  });
  it("flags a hard-coded red on a win-probability line", () => {
    const run = (text: string) =>
      JSON.parse(
        execFileSync(
          "node",
          ["-e", `import(${JSON.stringify(script)}).then((m) => console.log(JSON.stringify(m.scanText("x.tsx", ${JSON.stringify(text)}))))`],
          { encoding: "utf8" },
        ),
      ) as string[];
    expect(run('style={{ color: winPercent < 30 ? "var(--color-danger)" : "x" }}')).toHaveLength(1);
    expect(run('const tone = winPercent >= 55 ? "success" : "accent";')).toHaveLength(1);
    expect(run("color={probabilityColorVar(p)}")).toHaveLength(0);
  });
});
