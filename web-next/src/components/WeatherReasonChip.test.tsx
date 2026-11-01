import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectionWeatherChip, WeatherReasonChip } from "@/components/WeatherReasonChip";

describe("WeatherReasonChip", () => {
  it("renders nothing without notes", () => {
    const { container } = render(<WeatherReasonChip notes={[]} />);
    expect(container).toBeEmptyDOMElement();
    const empty = render(<ProjectionWeatherChip weather={null} />);
    expect(empty.container).toBeEmptyDOMElement();
  });

  it("states the weather status for each player", () => {
    render(
      <WeatherReasonChip
        notes={[
          { role: "start", player: "Dome QB", status: "dome", applied: false, label: "Dome: no weather effect", reason: null },
          {
            role: "over",
            player: "Rain QB",
            status: "outdoor",
            applied: true,
            label: "Weather: Heavy rain (outdoor) → passing outlook −8%",
            reason: "Heavy rain forecast: passing outlook lowered",
          },
        ]}
      />,
    );
    expect(screen.getByText(/Dome QB: Dome: no weather effect/)).toBeTruthy();
    expect(screen.getByText(/Rain QB: Weather: Heavy rain/)).toBeTruthy();
  });
});
