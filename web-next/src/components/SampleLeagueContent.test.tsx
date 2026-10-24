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

  it("browses roster, game plan and trade with the banner persistent and no network", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<SampleLeagueContent />);
    expect(screen.getByText("Alex Sampleton")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Game Plan" }));
    expect(screen.getByText(/Sell Casey Placeholder/)).toBeTruthy();
    expect(screen.getByTestId("sample-banner")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Open sample trade/ }));
    expect(screen.getByTestId("sample-verdict").textContent).toBe("Fair");
    expect(screen.getByTestId("sample-banner")).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
