import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { SimPlayerStory } from "./SimPlayerStory";
import type { SimStoryEntry } from "@/lib/simGame";

const base = { year: 2027, season_label: "S2 2027", tone: "neutral" as const };
const story: SimStoryEntry[] = [
  { ...base, kind: "depth", season: 2, week: 0, text: "Lost the BAL QB1 starting job to R. Cole (rookie won the job)", tone: "bad" },
  { ...base, kind: "season", season: 2, week: 99, text: "QB3 · did not play: behind R. Cole", tone: "bad" },
];

describe("SimPlayerStory", () => {
  beforeEach(() => window.localStorage.clear());

  it("shows the season line first and the depth chart move with its reason", () => {
    render(<SimPlayerStory story={story} />);
    const lines = screen.getAllByTestId("sim-story-line");
    expect(lines.map((l) => l.getAttribute("data-kind"))).toEqual(["season", "depth"]);
    expect(screen.getAllByText(/rookie won the job/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/did not play/).length).toBeGreaterThan(0);
  });

  it("renders nothing without a story", () => {
    const { container } = render(<SimPlayerStory story={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
