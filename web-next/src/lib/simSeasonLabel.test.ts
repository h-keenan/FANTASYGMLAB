import { describe, expect, it } from "vitest";
import { simSeasonLabel, simSeasonLabelForYear, simSeasonText } from "./simGame";

describe("simSeasonLabel", () => {
  it("is season number then year", () => {
    expect(simSeasonLabel(3, 2028)).toBe("S3 2028");
    expect(simSeasonLabel(1)).toBe("S1");
    expect(simSeasonLabel(null, 2028)).toBe("2028");
    expect(simSeasonLabel(null, null)).toBe("");
  });
  it("derives the season from the start year", () => {
    expect(simSeasonLabelForYear(2028, 2026)).toBe("S3 2028");
    expect(simSeasonLabelForYear(2028, 0)).toBe("2028");
    expect(simSeasonLabelForYear(null, 2026)).toBe("");
  });
  it("prefers the server label", () => {
    expect(simSeasonText({ season_label: "S2 2027", season_no: 9, year: 1 })).toBe("S2 2027");
    expect(simSeasonText({ season: 2, year: 2027 })).toBe("S2 2027");
  });
});

import { simOffseasonHeading, simPickLabelText, simProjNote, simProjText } from "./simGame";

describe("season labels in shared presentation", () => {
  it("heads the offseason with the finished season's label", () => {
    expect(simOffseasonHeading({ season_no: 2, seasons: 5, last_season: { year: 2027 } } as never)).toBe("Offseason after S2 2027");
    expect(simOffseasonHeading({ season_no: 2, seasons: 5, last_season: null, last_season_label: "S2 2027" } as never)).toBe("Offseason after S2 2027");
  });
  it("labels picks with the season they play in", () => {
    expect(simPickLabelText({ id: "pick:2028:2:3", season: 2028, round: 2, season_label: "S3 2028" })).toBe("S3 2028 Round 2");
    expect(simPickLabelText({ id: "pick:2029:2:9" })).toBe("2029 Round 2");
  });
});

describe("bye and out are never projected", () => {
  it("shows Bye / Out instead of a number", () => {
    expect(simProjText({ projection: 0, projection_note: "bye" })).toBe("Bye");
    expect(simProjText({ projection: 0, projection_note: "out" })).toBe("Out");
    expect(simProjText({ projection: 12.34, projection_note: null })).toBe("12.3");
    expect(simProjText({ projection: 12.34 })).toBe("12.3");
    expect(simProjNote({ projection_note: "bye" })).toBe("Bye");
  });
});
