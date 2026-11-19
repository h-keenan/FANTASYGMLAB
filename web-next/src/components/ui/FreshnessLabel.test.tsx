import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FreshnessLabel } from "./FreshnessLabel";

const NOW = new Date(2026, 10, 19, 12, 0, 0).getTime();
const report = {
  datasets: [
    { name: "values_fantasycalc", as_of: new Date(2026, 10, 19, 10, 0).getTime() / 1000, as_of_source: "fetch_timestamp" },
    { name: "players_db_and_injury_status", as_of: new Date(2026, 10, 19, 9, 40).getTime() / 1000 },
  ],
};

describe("FreshnessLabel", () => {
  it("joins the requested datasets into one muted line", () => {
    render(<FreshnessLabel datasets={["values", "injuries"]} report={report} now={NOW} />);
    expect(screen.getByTestId("freshness-label")).toHaveTextContent("Values as of 2h ago · Injuries updated 9:40am");
  });

  it("labels league data served from last-known provider data, with its age", () => {
    render(<FreshnessLabel datasets={[]} report={null} leagueAsOf={new Date(2026, 10, 19, 11, 48).toISOString()} now={NOW} />);
    expect(screen.getByTestId("freshness-label")).toHaveTextContent("League data as of 12m ago (may be behind)");
  });

  it("renders nothing for live league data (no stamp)", () => {
    render(<FreshnessLabel datasets={[]} report={null} leagueAsOf={undefined} now={NOW} />);
    expect(screen.queryByTestId("freshness-label")).toBeNull();
  });

  it("renders nothing when the report cannot vouch for any dataset", () => {
    render(<FreshnessLabel datasets={["adp"]} report={report} now={NOW} />);
    expect(screen.queryByTestId("freshness-label")).toBeNull();
  });
});
