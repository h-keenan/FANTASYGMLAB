import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerInjuryBadge } from "./PlayerInjuryBadge";
import { TradeAssetRow } from "./TradeAssetExchange";
import { injuryAbbreviation } from "@/lib/myTeamPresentation";

describe("injuryAbbreviation", () => {
  it("maps common statuses to short codes", () => {
    expect(injuryAbbreviation("Questionable")).toBe("Q");
    expect(injuryAbbreviation("QUESTIONABLE")).toBe("Q");
    expect(injuryAbbreviation("Doubtful")).toBe("D");
    expect(injuryAbbreviation("Out")).toBe("O");
    expect(injuryAbbreviation("IR")).toBe("IR");
    expect(injuryAbbreviation("Injured Reserve")).toBe("IR");
    expect(injuryAbbreviation("Suspended")).toBe("SUS");
    expect(injuryAbbreviation("Sus")).toBe("SUS");
    expect(injuryAbbreviation("PUP")).toBe("PUP");
  });

  it("never drops an unknown status", () => {
    expect(injuryAbbreviation("NFI-R")).toBe("NFI");
    expect(injuryAbbreviation("Personal")).toBe("PER");
    expect(injuryAbbreviation("Note")).toBe("NOTE");
    expect(injuryAbbreviation("")).toBe("");
    expect(injuryAbbreviation(null)).toBe("");
  });
});

describe("PlayerInjuryBadge", () => {
  it("renders nothing for a healthy or unknown player", () => {
    const { container } = render(<PlayerInjuryBadge status="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the short code and keeps the full status for hover and screen readers", () => {
    render(<PlayerInjuryBadge status="Questionable" />);
    const badge = screen.getByTestId("player-injury-badge");
    expect(badge).toHaveAttribute("title", "Questionable");
    expect(within(badge).getByText("Q")).toHaveAttribute("aria-hidden", "true");
    expect(within(badge).getByText("Questionable")).toHaveClass("sr-only");
    expect(badge).toHaveClass("shrink-0");
    expect(badge.style.color).toBe("var(--color-warning)");
  });

  it("uses the danger color for Out-caliber statuses", () => {
    render(<PlayerInjuryBadge status="Out" />);
    expect(screen.getByTestId("player-injury-badge").style.color).toBe("var(--color-danger)");
  });
});

describe("TradeAssetRow injury placement", () => {
  // Owner screenshot, 2026-10-21: "Ja... QUESTIONABLE" — the injury label
  // sat on the name line and took the name's width.
  it("keeps the name line to the name alone and puts the injury pill on the team/age line", () => {
    render(
      <TradeAssetRow
        asset={{
          asset_type: "player",
          player_id: "1",
          name: "Jaylen Wright",
          position: "RB",
          team: "MIA",
          age: 23,
          injury_status: "Questionable",
          score: 2960,
          overall_rating: 75,
        }}
      />,
    );
    const name = screen.getByText("Jaylen Wright");
    // The name is a direct child of the identity column, with no sibling
    // pill sharing its line.
    expect(name.nextElementSibling).not.toHaveAttribute("data-testid", "player-injury-badge");
    const metaText = screen.getByText("MIA · Age 23");
    expect(metaText.parentElement).toContainElement(screen.getByTestId("player-injury-badge"));
    expect(metaText.parentElement).not.toContainElement(name);
  });
});
