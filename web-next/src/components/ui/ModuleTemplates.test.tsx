import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

import { CompactModule } from "@/components/ui/CompactModule";
import { Hero, LinkModule, StatStripModule } from "@/components/ui/ModuleTemplates";
import {
  MIN_COLLAPSED_CHARS,
  MODULE_TEMPLATES,
  SIM_TEMPLATE_ADAPTERS,
  catalogIssues,
  collapsedVerdict,
  heroParts,
  listSummaryParts,
  statStripParts,
  trendModel,
} from "@/lib/moduleTemplates";
import { PlayerListRow } from "@/components/PlayerListRow";
import { collapsedModuleProblems, compactModuleOpeningTags, openingTags, rowRightEdgeProblems } from "./assertCompactInformative";

beforeEach(() => window.localStorage.clear());

describe("module template catalog", () => {
  it("documents every template completely and names the sim adapters", () => {
    expect(catalogIssues()).toEqual([]);
    const ids = MODULE_TEMPLATES.map((t) => t.id);
    for (const required of ["hero", "compactModule", "statStrip", "row", "sectionHeader", "actionBar", "listFilter", "tabPage", "state", "trendChart", "insightLink"]) {
      expect(ids).toContain(required);
    }
    for (const adapter of SIM_TEMPLATE_ADAPTERS) expect(ids).toContain(adapter.template);
  });

  it("flags a catalog entry with no collapsed rule or a bad height range", () => {
    const bad = { ...MODULE_TEMPLATES[0], collapsed: "", maxHeight: 10 };
    expect(catalogIssues([bad]).map((i) => i.problem)).toEqual(expect.arrayContaining(["no collapsed-form rule", "max height below min height"]));
  });
});

describe("collapsed-form rule", () => {
  it("rejects empty headers, placeholders and too-short summaries", () => {
    expect(collapsedVerdict([]).ok).toBe(false);
    expect(collapsedVerdict([{ key: "a", text: "—" }, { key: "b", text: "Loading…" }]).ok).toBe(false);
    expect(collapsedVerdict([{ key: "a", text: "3 alerts" }]).reason).toMatch(/shorter than/);
    expect(collapsedVerdict([{ key: "a", text: "3 alerts" }, { key: "b", text: "Gibbs hurt" }]).ok).toBe(true);
  });

  it("builds summaries from real data and drops placeholder values", () => {
    expect(statStripParts([{ label: "Power", value: "#3" }, { label: "Bench", value: "—" }, { label: "Age", value: "26.1" }]).map((p) => p.text)).toEqual(["Power #3", "Age 26.1"]);
    expect(listSummaryParts({ count: 0, noun: "alert" })[0].text).toBe("No alerts");
    expect(listSummaryParts({ count: 3, noun: "alert", highlights: ["Gibbs out"] }).map((p) => p.text)).toEqual(["3 alerts", "Gibbs out"]);
    expect(trendModel([10, 12])).toMatchObject({ direction: "up", label: "+2", tone: "success" });
    expect(trendModel([5, 3], false)).toMatchObject({ direction: "down", tone: "success" });
    expect(trendModel([5])).toBeNull();
    expect(heroParts({ label: "Win odds", value: "62%", context: "vs Rival FC" }).length).toBe(2);
  });
});

describe("template components: collapsed form carries data", () => {
  it("StatStripModule reads as a stat line collapsed and opens into tiles", () => {
    render(
      <StatStripModule
        id="t.stats"
        title="My Team"
        items={[
          { glyph: "power", label: "Power Rank", value: "#3" },
          { glyph: "starter", label: "Starter Strength", value: "#5" },
          { glyph: "age", label: "Avg Age", value: "26.1" },
        ]}
      />,
    );
    expect(collapsedModuleProblems(document.body)).toEqual([]);
    expect(screen.getByTestId("compact-summary")).toHaveTextContent("Power #3 · Starters #5 · Age 26.1");
    expect(screen.queryByText("Power Rank")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /^My Team:/ }));
    expect(screen.getByText("Power Rank")).toBeInTheDocument();
  });

  it("Hero shows the big number, one context line and a signed trend; no trend with one point", () => {
    const { rerender } = render(<Hero label="Team Value" value="8,000" context="71st percentile of 12 teams" trendPoints={[10, 12]} />);
    expect(screen.getByTestId("hero-value")).toHaveTextContent("8,000");
    expect(screen.getByTestId("hero-context")).toHaveTextContent("71st percentile");
    expect(screen.getByTestId("hero-trend")).toHaveTextContent("+2");
    rerender(<Hero label="Team Value" value="8,000" context="71st percentile of 12 teams" trendPoints={[10]} />);
    expect(screen.queryByTestId("hero-trend")).toBeNull();
  });

  it("LinkModule shows its summary and links out", () => {
    render(<LinkModule title="Trade ideas" href="/trade-hub/L" parts={[{ key: "a", text: "2 trade ideas" }, { key: "b", text: "Trade Hub" }]} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/trade-hub/L");
    expect(screen.getByTestId("compact-summary").textContent!.length).toBeGreaterThanOrEqual(MIN_COLLAPSED_CHARS);
  });

  it("the page lint catches a bare header", () => {
    render(
      <CompactModule id="t.bare" title="Bare" persist={false}>
        <p>body</p>
      </CompactModule>,
    );
    expect(collapsedModuleProblems(document.body)).toHaveLength(1);
  });
});

function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) sourceFiles(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

describe("source scan: no CompactModule without a summary (web and app)", () => {
  const roots = [path.resolve(__dirname, "../.."), path.resolve(__dirname, "../../../../mobile/src")];
  for (const root of roots) {
    it(`every <CompactModule> under ${path.basename(path.resolve(root, "..")) === "src" ? "web" : path.basename(path.resolve(root, ".."))} passes parts or summary`, () => {
      const offenders: string[] = [];
      let seen = 0;
      for (const file of sourceFiles(root)) {
        const text = readFileSync(file, "utf8");
        for (const tag of compactModuleOpeningTags(text)) {
          seen += 1;
          if (!/\bparts=/.test(tag) && !/\bsummary=/.test(tag) && !/\{\.\.\./.test(tag)) offenders.push(`${path.relative(root, file)}: ${tag.slice(0, 80).replace(/\s+/g, " ")}`);
        }
      }
      expect(seen).toBeGreaterThan(0);
      expect(offenders).toEqual([]);
    });
  }
});

describe("Row template: the right edge is one action or one number", () => {
  it("passes a row with one trailing action and flags a cluster", () => {
    const { container, rerender } = render(<PlayerListRow name="Jahmyr Gibbs" position="RB" stats={[{ key: "p", label: "Proj", value: "12.1" }]} actions={<button>Draft</button>} />);
    expect(rowRightEdgeProblems(container)).toEqual([]);
    rerender(
      <PlayerListRow
        name="Jahmyr Gibbs"
        position="RB"
        actions={
          <>
            <button>Queue</button>
            <button>Draft</button>
          </>
        }
      />,
    );
    expect(rowRightEdgeProblems(container)).toHaveLength(1);
  });

  for (const root of [path.resolve(__dirname, "../.."), path.resolve(__dirname, "../../../../mobile/src")]) {
    it(`no <PlayerListRow actions={<>...</>}> fragment under ${root.includes("mobile") ? "app" : "web"}`, () => {
      const offenders: string[] = [];
      for (const file of sourceFiles(root)) {
        for (const tag of openingTags(readFileSync(file, "utf8"), "PlayerListRow")) {
          if (/\bactions=\{\s*<>/.test(tag)) offenders.push(path.relative(root, file));
        }
      }
      expect(offenders).toEqual([]);
    });
  }
});
