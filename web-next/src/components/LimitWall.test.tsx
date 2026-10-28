import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { limitWallForReason } from "@/lib/limitWall";
import { LimitWall } from "./LimitWall";

vi.mock("@/lib/analytics", () => ({ trackUse: vi.fn() }));

describe("LimitWall", () => {
  it("shows the limit, reset, Pro line and an upgrade link to /premium", () => {
    const wall = limitWallForReason("weekly_limit_reached", {
      info: { limit: 3, window: "week", resets_at: "2026-11-02T00:00:00+00:00" },
      timeZone: "UTC",
    })!;
    render(<LimitWall wall={wall} feature="trade_analyzer_weekly_limit" />);
    expect(screen.getByRole("alert")).toHaveTextContent("3 free trade checks");
    expect(screen.getByText(/resets Monday, Nov 2/)).toBeInTheDocument();
    expect(screen.getByText(/Pro removes the weekly cap/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upgrade to Pro/ })).toHaveAttribute("href", "/premium");
  });

  it("guests are asked to create an account", () => {
    const wall = limitWallForReason("weekly_limit_reached", { isGuest: true })!;
    render(<LimitWall wall={wall} feature="x" />);
    expect(screen.getByRole("link", { name: /Create an account/ })).toHaveAttribute("href", "/premium");
  });
});
