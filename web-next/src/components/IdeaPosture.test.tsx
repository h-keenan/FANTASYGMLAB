import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { IdeaPosture } from "./IdeaPosture";
import type { TradePosture } from "@/lib/api";

const posture: TradePosture = {
  key: "contender",
  group: "contender",
  label: "Contender",
  source: "auto",
  confidence: 0.8,
  confidence_label: "high",
  rank: 2,
  league_size: 12,
  record: "4-2",
  standing: "#2 of 12, 4-2",
  why: "From your roster strength, record and age curve (#2 of 12, 4-2)",
};

describe("IdeaPosture", () => {
  it("shows the shared chip, the honest label and the trade-off note on a costly idea", () => {
    render(
      <IdeaPosture
        leagueId="L1"
        idea={{
          posture,
          posture_label: "GOOD VALUE, COSTS YOUR LINEUP",
          posture_note: "You're a contender: this costs ~60 lineup points.",
          posture_alignment: "costly",
        }}
      />,
    );
    expect(screen.getByTestId("posture-chip")).toBeInTheDocument();
    expect(screen.getByText("GOOD VALUE, COSTS YOUR LINEUP")).toBeInTheDocument();
    expect(screen.getByText(/this costs ~60 lineup points/)).toBeInTheDocument();
  });

  it("tags an aligned idea and renders nothing without a posture", () => {
    const { rerender } = render(<IdeaPosture idea={{ posture, posture_alignment: "aligned" }} />);
    expect(screen.getByText("Fits your plan")).toBeInTheDocument();
    rerender(<IdeaPosture idea={{}} />);
    expect(screen.queryByTestId("idea-posture")).toBeNull();
  });
});
