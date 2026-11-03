import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NextSteps, nextStepHref } from "./NextSteps";

describe("NextSteps", () => {
  it("links each step to its league page with the league name carried along", () => {
    render(<NextSteps steps={["matchup", "waivers", "trade-hub"]} leagueId="123" leagueName="My League" />);
    expect(screen.getByRole("link", { name: /Check your lineup/ })).toHaveAttribute("href", "/matchup/123?name=My%20League");
    expect(screen.getByRole("link", { name: /Find a waiver add/ })).toHaveAttribute("href", "/waivers/123?name=My%20League");
    expect(screen.getByRole("link", { name: /See trade ideas/ })).toHaveAttribute("href", "/trade-hub/123?name=My%20League");
  });

  it("renders nothing without a league", () => {
    const { container } = render(<NextSteps steps={["matchup"]} leagueId="" leagueName="" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("builds the roster link", () => {
    expect(nextStepHref("my-team", "9", "A B")).toBe("/my-team/9?name=A%20B");
  });
});
