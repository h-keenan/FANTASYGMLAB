import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DecisionFitCard, PlayerHeroHeader } from "./PlayerHeroHeader";
import type { UsageTrend } from "@/lib/api";
import { usageConfidenceBars, usageTrendTone } from "@/lib/playerQuickViewPresentation";

const RISING: UsageTrend = {
  direction: "up",
  trend_pct: 13,
  confidence_label: "high confidence",
  arrow: "▲",
  tone: "positive",
  detail: "Weighted last 4 games vs earlier-season baseline (6 usable games).",
};
const FALLING: UsageTrend = { ...RISING, direction: "down", trend_pct: -37, arrow: "▼", tone: "negative" };

function renderHero(overrides: Partial<Parameters<typeof PlayerHeroHeader>[0]> = {}) {
  return render(
    <PlayerHeroHeader
      playerId="9493"
      name="Michael Mayer"
      nameId="pqv-name"
      contextLabel="Trade Board"
      position="TE"
      team="LV"
      age={25}
      tier="Contributor"
      score={2133}
      overallRating={78}
      usageTrend={RISING}
      {...overrides}
    />,
  );
}

describe("usageTrendTone", () => {
  it("is positive for rising usage", () => {
    expect(usageTrendTone(RISING)).toBe("positive");
  });
  it("is danger for a confirmed decline (high confidence or a 20%+ drop)", () => {
    expect(usageTrendTone(FALLING)).toBe("danger");
    expect(usageTrendTone({ ...FALLING, confidence_label: "moderate confidence", trend_pct: -24 })).toBe("danger");
  });
  it("is neutral, never green, for a mild moderate-confidence decline", () => {
    expect(usageTrendTone({ ...FALLING, confidence_label: "moderate confidence", trend_pct: -8 })).toBe("neutral");
  });
  it("maps confidence to signal bars", () => {
    expect(usageConfidenceBars("high confidence")).toBe(3);
    expect(usageConfidenceBars("moderate confidence")).toBe(2);
    expect(usageConfidenceBars("")).toBe(1);
  });
});

describe("PlayerHeroHeader", () => {
  it("renders the concept's header: context label, name, team/age pill, three tiles, archetype pill", () => {
    renderHero();
    expect(screen.getByText("Trade Board")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 2, name: "Michael Mayer" })).toHaveAttribute("id", "pqv-name");
    expect(screen.getByText("LV").closest(".pqv-meta-pill")).toHaveTextContent("LV•Age 25");
    expect(screen.getByLabelText("78 overall rating")).toBeInTheDocument();
    expect(screen.getByText("Player score")).toBeInTheDocument();
    expect(screen.getByText("2,133")).toBeInTheDocument();
    const usage = screen.getByTestId("pqv-usage-tile");
    expect(usage).toHaveAttribute("data-tone", "positive");
    expect(usage).toHaveTextContent("▲ 13%");
    expect(usage).toHaveTextContent("High confidence");
    expect(usage).toHaveAccessibleName("Usage up 13%, high confidence");
    expect(screen.getByText("Contributor").closest(".pqv-archetype-pill")).not.toBeNull();
  });

  it("colors a declining usage trend red, with a down arrow and the magnitude", () => {
    renderHero({ usageTrend: FALLING });
    const usage = screen.getByTestId("pqv-usage-tile");
    expect(usage).toHaveAttribute("data-tone", "danger");
    expect(usage.className).toContain("pqv-stat-tile--danger");
    expect(usage).toHaveTextContent("▼ 37%");
  });

  it("keeps all three tiles with dashes when score, value and trend are missing", () => {
    const { container } = renderHero({ overallRating: null, score: null, usageTrend: null, tier: null });
    expect(container.querySelectorAll(".pqv-stat-tile")).toHaveLength(3);
    expect(screen.getAllByText("—")).toHaveLength(3);
    expect(screen.getByText("No clear trend")).toBeInTheDocument();
    expect(container.querySelector(".pqv-archetype-pill")).toBeNull();
  });

  it("shows a placeholder, not 'no trend', while the usage read is loading", () => {
    renderHero({ usageTrend: null, usageLoading: true });
    expect(screen.queryByText("No clear trend")).toBeNull();
  });

  it("keeps a very long name intact for CSS wrapping instead of truncating it", () => {
    const longName = "Amon-Ra St. Brown-Featherstonehaugh Jr.";
    renderHero({ name: longName });
    expect(screen.getByRole("heading", { name: longName })).toHaveClass("pqv-name");
  });

  it("falls back to FA and N/A when team and age are missing", () => {
    renderHero({ team: null, age: null });
    expect(screen.getByText("FA")).toBeInTheDocument();
    expect(screen.getByText("Age N/A")).toBeInTheDocument();
  });

  it("does not claim FA while identity is still loading, and explains a missing value", () => {
    renderHero({ team: null, age: null, score: null, loadingIdentity: true });
    expect(screen.queryByText("FA")).not.toBeInTheDocument();
    expect(screen.queryByText("No market value yet")).not.toBeInTheDocument();
  });

  it("explains an empty Value tile instead of a bare dash", () => {
    renderHero({ score: null, valueNote: null });
    expect(screen.getByText("No market value yet")).toBeInTheDocument();
  });

  it("renders resolved team and age for a Loveland-like player", () => {
    renderHero({ position: "TE", team: "CHI", age: 22, score: null, valueNote: "No market value yet" });
    expect(screen.getByText("CHI")).toBeInTheDocument();
    expect(screen.queryByText("FA")).not.toBeInTheDocument();
  });
});

describe("DecisionFitCard", () => {
  it("renders the accent label and the narrative", () => {
    render(<DecisionFitCard narrative="Market value is the biggest driver." />);
    expect(screen.getByRole("heading", { name: "Decision Fit" })).toBeInTheDocument();
    expect(screen.getByText("Market value is the biggest driver.")).toBeInTheDocument();
  });
});
