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
    // The GM Plan "-747": a negative trade gain toned "danger" and an injury-driven red stripe, neither using a verdict word.
    expect(run('tone: input.gain > 0 ? "success" : input.gain < 0 ? "danger" : "muted",')).toHaveLength(1);
    expect(run('const gainColor = gain > 0 ? colors.success : gain < 0 ? colors.danger : colors.textSecondary;')).toHaveLength(1);
    expect(run('const accent = injuryDisplay ? "var(--color-danger)" : "var(--color-accent)";')).toHaveLength(1);
    expect(run("tone: bandCompactTone(deltaBand(input.gain)),")).toHaveLength(0);
    // Trade History "-12 pts" in red and its red verdict stripe (2026-11-17).
    expect(run('{ key: "pts", tone: netPts > 0 ? "success" : netPts < 0 ? "danger" : undefined }')).toHaveLength(1);
    expect(run("const accent = verdict ? verdictToneColorVar(verdict) : outcomeToneColorVar(o);")).toHaveLength(1);
  });
});
