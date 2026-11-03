import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LeagueLinkStep } from "./LeagueLinkStep";

const rows: { current: Array<{ league_id: string; league_name: string }> } = { current: [] };
vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: () => ({
      select: () => Promise.resolve({ data: rows.current, error: null }),
    }),
  },
}));

describe("LeagueLinkStep", () => {
  beforeEach(() => {
    rows.current = [];
  });

  it("links straight into the only saved league", async () => {
    rows.current = [{ league_id: "L1", league_name: "My League" }];
    render(<LeagueLinkStep step="trade-analyzer" label="Analyze a trade" />);
    expect(await screen.findByRole("link", { name: /Analyze a trade/ })).toHaveAttribute("href", "/trade-analyzer/L1?name=My%20League");
  });

  it("sends an account with several leagues to the Portfolio to pick one", async () => {
    rows.current = [
      { league_id: "L1", league_name: "A" },
      { league_id: "L2", league_name: "B" },
    ];
    render(<LeagueLinkStep step="alerts" label="See news on your players" pickLabel="Pick a league for your alerts" />);
    expect(await screen.findByRole("link", { name: /Pick a league for your alerts/ })).toHaveAttribute("href", "/portfolio");
  });

  it("renders nothing when there is no saved league", async () => {
    render(<LeagueLinkStep step="alerts" label="x" />);
    await Promise.resolve();
    expect(screen.queryByTestId("league-link-step")).toBeNull();
  });
});
