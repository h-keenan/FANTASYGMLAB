import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatStrip } from "@/components/StatStrip";

import { InsightLink } from "./InsightLink";

const league = { id: "42", name: "Dynasty Dudes" };

describe("InsightLink", () => {
  it("renders a real link with the destination in its accessible name and no chevron (the whole tile is the affordance)", () => {
    render(
      <InsightLink insight="age" league={league} spoken={["Avg Age", "24.1"]}>
        <div className="glass-surface">24.1</div>
      </InsightLink>,
    );
    const link = screen.getByRole("link", { name: "Avg Age, 24.1, open the Roster Age rankings" });
    expect(link).toHaveAttribute("href", "/league-rankings/42?name=Dynasty%20Dudes#board-age");
    expect(link.querySelector(".ui-insight-chevron")).toBeNull();
    expect(link.textContent).toBe("24.1");
  });
});

describe("StatStrip", () => {
  const items = [
    { glyph: "age" as const, insight: "age" as const, label: "Avg Age", value: "24.1", note: "League avg 25.2" },
    { glyph: "injury" as const, insight: "injury" as const, label: "Injured starters", value: "None" },
    { glyph: "record" as const, label: "Odds", value: "5%" },
  ];

  it("links every tile that declares an insight when the league is known", () => {
    render(<StatStrip columns={3} items={items} league={league} />);
    expect(screen.getByRole("link", { name: /Avg Age, 24.1, League avg 25.2, open the Roster Age rankings/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Injured starters, None, open Alerts/ })).toHaveAttribute("href", "/alerts/42?name=Dynasty%20Dudes");
    expect(screen.getAllByRole("link")).toHaveLength(2);
  });

  it("stays plain tiles without a league (previews, sample data)", () => {
    render(<StatStrip columns={3} items={items} />);
    expect(screen.queryAllByRole("link")).toHaveLength(0);
  });
});
