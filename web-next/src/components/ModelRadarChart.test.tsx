import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelRadarChart } from "./ModelRadarChart";

describe("ModelRadarChart", () => {
  it("renders a labeled accessible summary of all 5 factors when every rating is present", () => {
    render(
      <ModelRadarChart
        model={{
          market_rating: 91,
          opportunity_rating: 84,
          scarcity_rating: 62,
          role_rating: 73,
          durability_rating: 58,
        }}
      />,
    );

    expect(screen.getByText("Model attributes: MKT 91, OPP 84, SCR 62, ROLE 73, DUR 58")).toBeInTheDocument();
  });

  // Same "no fabricated rating" principle as OvrGauge — a radar polygon
  // needs a real point on every axis to be an honest shape.
  it("renders nothing when any one of the 5 ratings is missing", () => {
    const { container } = render(
      <ModelRadarChart
        model={{
          market_rating: 91,
          opportunity_rating: 84,
          scarcity_rating: null,
          role_rating: 73,
          durability_rating: 58,
        }}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });
});
