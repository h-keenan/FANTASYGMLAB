import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PortfolioFreeStanding } from "@/components/PortfolioFreeStanding";

vi.mock("@/lib/useSavedLeagues", () => ({ useSavedLeagues: () => ({ rows: [], status: "ready", reload: () => {} }) }));
vi.mock("@/lib/api", () => ({ api: { getDashboard: vi.fn() } }));

describe("PortfolioFreeStanding with no saved league", () => {
  it("offers Connect and the sample league instead of leaving only the Pro upsell", () => {
    render(<PortfolioFreeStanding />);
    expect(screen.getByRole("link", { name: "Connect a league" })).toHaveAttribute("href", "/connect-league");
    expect(screen.getByTestId("sample-league-link")).toBeInTheDocument();
  });
});
