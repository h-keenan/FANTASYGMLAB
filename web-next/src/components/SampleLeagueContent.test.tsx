import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SampleLeagueContent } from "./SampleLeagueContent";

describe("SampleLeagueContent", () => {
  afterEach(() => vi.restoreAllMocks());

  it("labels the page as a sample and links the CTA to the real connect flow", () => {
    render(<SampleLeagueContent />);
    const banner = screen.getByTestId("sample-banner");
    expect(banner.textContent).toContain("Sample league");
    expect(screen.getByRole("link", { name: "Connect your real league" }).getAttribute("href")).toBe("/connect-league");
  });

  it("opens on the sample Dashboard with the real modules, filled from static data and no network", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<SampleLeagueContent />);
    expect(screen.getByTestId("sample-dashboard")).toBeTruthy();
    // Today hero with a top priority, rank strip, watchlist, team snapshot.
    expect(screen.getByRole("heading", { name: /This week/ })).toBeTruthy();
    expect(screen.getAllByText(/Sell Casey Placeholder/).length).toBeGreaterThan(0);
    expect(screen.getByText("Power Rank")).toBeTruthy();
    expect(screen.getByTestId("watchlist-alerts")).toBeTruthy();
    expect(screen.getByText("My Team")).toBeTruthy();
    // League Activity fills from the static promise.
    expect(await screen.findByTestId("league-pulse-card")).toBeTruthy();
    expect(screen.getByTestId("sample-banner")).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("blocks Dashboard links in the sample and explains why", () => {
    render(<SampleLeagueContent />);
    expect(screen.queryByTestId("sample-blocked")).toBeNull();
    fireEvent.click(screen.getByRole("link", { name: "Open the full GM Plan" }));
    expect(screen.getByTestId("sample-blocked").textContent).toContain("Connect your league");
  });

  it("browses roster, game plan and trade with the banner persistent and no network", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<SampleLeagueContent />);
    fireEvent.click(screen.getByRole("tab", { name: "Roster" }));
    expect(screen.getByText("Alex Sampleton")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Top moves" }));
    expect(screen.getByText(/Sell Casey Placeholder/)).toBeTruthy();
    expect(screen.getByTestId("sample-banner")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Open sample trade/ }));
    expect(screen.getByTestId("sample-verdict").textContent).toBe("Fair");
    expect(screen.getByTestId("sample-banner")).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
