import { describe, expect, it } from "vitest";

import { teamPickerLabel } from "./teamLabel";

describe("teamPickerLabel", () => {
  it("keeps both names when they differ", () => {
    expect(teamPickerLabel("Revivalry", "coridian_")).toBe("Revivalry · coridian_");
  });
  it("dedupes the same name, ignoring case and spaces", () => {
    expect(teamPickerLabel("patrickshea", "patrickshea")).toBe("patrickshea");
    expect(teamPickerLabel(" PatrickShea ", "patrickshea")).toBe("PatrickShea");
  });
  it("falls back when empty and uses whichever name exists", () => {
    expect(teamPickerLabel(null, undefined, "Team 4")).toBe("Team 4");
    expect(teamPickerLabel("Solo", "")).toBe("Solo");
    expect(teamPickerLabel("", "owner")).toBe("owner");
  });
});
