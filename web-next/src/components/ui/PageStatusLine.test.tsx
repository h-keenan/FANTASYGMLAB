import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PageStatusLine } from "./PageStatusLine";
import { matchupCardModel } from "@/lib/matchupModules";

describe("PageStatusLine", () => {
  it("is one row: context left, freshness and a refresh icon right", () => {
    const onRefresh = vi.fn();
    render(<PageStatusLine context={<span>Week 10</span>} freshness="Updated 3m ago" onRefresh={onRefresh} />);
    const line = screen.getByTestId("page-status-line");
    expect(line).toHaveTextContent("Week 10");
    expect(line).toHaveTextContent("Updated 3m ago");
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when there is nothing to say", () => {
    const { container } = render(<PageStatusLine />);
    expect(container).toBeEmptyDOMElement();
  });

  it("the Matchup hero kicker does not repeat the week the status line shows", () => {
    const base = { week: 10, live: false, final: false, myName: "You", opponentName: "Mike", myScore: null, opponentScore: null, myProjected: 100, opponentProjected: 90, winPercent: 60, kickedOff: false, playersLeft: null, swing: [] };
    expect(matchupCardModel(base).kicker).toBe("WEEK 10");
    expect(matchupCardModel({ ...base, omitWeek: true }).kicker).toBe("HEAD TO HEAD");
    expect(matchupCardModel({ ...base, live: true, omitWeek: true }).kicker).toBe("LIVE");
  });
});
