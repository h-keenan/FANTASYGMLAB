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
    // Grade tone maps: risk / decline mapped to a red token (the old managerTendencies / sharedTrades maps) fail; amber passes.
    expect(run('  if (tone === "risk") return "var(--color-danger)";')).toHaveLength(1);
    const runAs = (file: string, text: string) =>
      JSON.parse(
        execFileSync(
          "node",
          ["-e", `import(${JSON.stringify(script)}).then((m) => console.log(JSON.stringify(m.scanText(${JSON.stringify(file)}, ${JSON.stringify(text)}))))`],
          { encoding: "utf8" },
        ),
      ) as string[];
    // In a grade-tone file even the "danger" slug is a red verdict (old mobile sharedTrades / managerTendencies maps).
    expect(runAs("mobile/src/lib/sharedTrades.ts", "  if (grade === 'DECLINE') return 'danger';")).toHaveLength(1);
    expect(runAs("mobile/src/lib/managerTendencies.ts", "  if (tone === 'risk') return 'danger';")).toHaveLength(1);
    expect(runAs("mobile/src/lib/sharedTrades.ts", "  return toneToken(grade.toLowerCase());")).toHaveLength(0);
    expect(run("const HEADLINE_COLOR = { decline: colors.danger };")).toHaveLength(1);
    expect(run('  if (tone === "risk") return "var(--color-warning)";')).toHaveLength(0);
    expect(run("const t = toneToken(tone);")).toHaveLength(0);
    // The trade picker header "You send" dot was red: tone "danger" mapped to the red token on a line that never said "You send".
    const scanTrade = (text: string) =>
      JSON.parse(
        execFileSync(
          "node",
          ["-e", `import(${JSON.stringify(script)}).then((m) => console.log(JSON.stringify(m.scanText("TradePickerSheet.tsx", ${JSON.stringify(text)}))))`],
          { encoding: "utf8" },
        ),
      ) as string[];
    expect(scanTrade('const toneColor = tone === "danger" ? "var(--color-danger)" : "var(--color-success)";')).toHaveLength(1);
    expect(scanTrade("backgroundColor: tone === 'danger' ? colors.danger : colors.successBright }")).toHaveLength(1);
    expect(scanTrade("const dot = side === 'send' ? colors.danger : colors.success;")).toHaveLength(1);
    expect(scanTrade('const toneColor = sideDotColor(tone);')).toHaveLength(0);
    // The "You send" dot of the shared TradeScale was pink/red (a quoted var(--color-danger) slipped past the Give rule).
    expect(run('background: side === "give" ? "var(--color-danger)" : "var(--color-success)"')).toHaveLength(1);
    expect(run('background: side === "give" ? "var(--color-text-muted)" : "var(--color-success)"')).toHaveLength(0);
  });
});
