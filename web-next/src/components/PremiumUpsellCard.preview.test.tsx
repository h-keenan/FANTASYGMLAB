import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PremiumUpsellCard } from "./PremiumUpsellCard";
import { paidPreview } from "@/lib/paidPreviews";

vi.mock("@/lib/analytics", () => ({ trackUse: vi.fn() }));

describe("paid-page preview on the Pro wall", () => {
  it("lists what the page contains, with the person's own league name, before Upgrade", () => {
    render(
      <PremiumUpsellCard kicker="Draft Center" leagueName="No quitters league" upsell={null} fallbackTitle="Draft" fallbackBody="Draft Center is a Pro feature." />,
    );
    const preview = screen.getByTestId("paid-preview");
    expect(preview).toHaveTextContent("What you get with Pro");
    expect(preview).toHaveTextContent("Pick decision signals across every team in No quitters league");
    expect(screen.getByRole("link", { name: /Upgrade/ })).toHaveAttribute("href", "/premium");
  });

  it("shows a real example only when the page supplies one", () => {
    const { rerender } = render(
      <PremiumUpsellCard kicker="Playoff Odds" bare upsell={null} fallbackTitle="t" fallbackBody="b" />,
    );
    expect(screen.queryByTestId("paid-preview-example")).toBeNull();
    rerender(
      <PremiumUpsellCard kicker="Playoff Odds" bare example="Right now you're 4th in L at 4-3." upsell={null} fallbackTitle="t" fallbackBody="b" />,
    );
    expect(screen.getByTestId("paid-preview-example")).toHaveTextContent("4th in L at 4-3");
  });

  it("renders no preview block for a surface without one (saved-league cap)", () => {
    render(<PremiumUpsellCard kicker="Saved leagues" bare upsell={null} fallbackTitle="t" fallbackBody="b" />);
    expect(screen.queryByTestId("paid-preview")).toBeNull();
    expect(paidPreview("saved_leagues")).toBeNull();
  });

  it("has a preview for every gated surface", () => {
    for (const key of ["draft_center", "live_draft", "commissioner", "college_scouting", "portfolio", "exposure", "gm_plan", "playoff_odds", "what_if", "trade_finder"]) {
      expect(paidPreview(key)?.bullets.length, key).toBeGreaterThan(0);
    }
  });
});
