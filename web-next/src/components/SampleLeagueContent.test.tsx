import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SampleLeagueContent } from "./SampleLeagueContent";

describe("SampleLeagueContent", () => {
  afterEach(() => vi.restoreAllMocks());

  it("labels the page as a sample and links the CTA to the real connect flow", () => {
    render(<SampleLeagueContent />);
    const banner = screen.getByTestId("sample-banner");
    expect(banner.textContent).toContain("Sample league");
    expect(screen.getAllByRole("link", { name: "Connect your league" })[0].getAttribute("href")).toBe("/connect-league");
  });

  it("opens on the sample Dashboard with the real modules, filled from static data and no network", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<SampleLeagueContent />);
    expect(screen.getByTestId("sample-dashboard")).toBeTruthy();
    // Today hero with a top priority, rank strip, watchlist, team snapshot.
    expect(screen.getByRole("heading", { name: /This week/ })).toBeTruthy();
    expect(screen.getAllByText(/Sell Casey Placeholder/).length).toBeGreaterThan(0);
    // My Team and Watchlist are compact modules: informative collapsed, tiles/cards on tap.
    fireEvent.click(screen.getByTestId("stat-strip-toggle"));
    expect(screen.getByText("Power Rank")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /^Watchlist/ }));
    expect(screen.getByTestId("watchlist-alerts")).toBeTruthy();
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

  it("wears the shared chrome: sticky tab strip, in-flow bottom stack and an inert (no arrows) dashboard", () => {
    render(<SampleLeagueContent />);
    expect(screen.getByTestId("sample-tab-strip").className).toContain("sticky");
    const stack = screen.getByTestId("sample-bottom-stack");
    expect(stack.className).toContain("bottom-stack");
    expect(stack.querySelector('[data-testid="sample-tab-bar"]')).toBeTruthy();
    // Taps are off, so the dashboard opts into the inert-links scope (hides arrows/chevrons in CSS).
    expect(screen.getByTestId("sample-dashboard").hasAttribute("data-inert-links")).toBe(true);
    // The banner is one slim row: badge + CTA, no stacked layout.
    expect(screen.getByTestId("sample-banner").className).toContain("items-center");
  });

  it("shows initials, not blank discs, for League Activity teams", async () => {
    render(<SampleLeagueContent />);
    const card = await screen.findByTestId("league-pulse-card");
    expect(card.textContent).toMatch(/TP|MM|EE/);
    expect(card.textContent).not.toContain("›");
  });

  it("ends the Trade tab with a connect-your-league CTA module", () => {
    render(<SampleLeagueContent />);
    fireEvent.click(screen.getByRole("tab", { name: "Trade" }));
    // One in the desktop rail (lg+) and one at the end of the tab (hidden from lg).
    const cta = screen.getAllByTestId("sample-connect-module")[0];
    expect(cta.textContent).toContain("Connect your league to see yours");
    expect(cta.querySelector("a")?.getAttribute("href")).toBe("/connect-league");
  });
});
