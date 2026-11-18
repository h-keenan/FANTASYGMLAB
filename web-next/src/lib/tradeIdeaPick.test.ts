import { describe, expect, it } from "vitest";

import { partnerFitLine, pickProjectionLine } from "./tradeIdeaPick";

describe("tradeIdeaPick", () => {
  it("shows the projected slot and whose pick it is", () => {
    expect(pickProjectionLine({ projected_slot_label: "1.04", original_team_name: "Gridiron", owner_team_name: "Me" })).toBe("proj. 1.04 · Gridiron's pick");
  });
  it("drops the owner part for the holder's own pick and falls back to the projected range", () => {
    expect(pickProjectionLine({ projected_slot_label: "1.04", original_team_name: "Me", owner_team_name: "Me" })).toBe("proj. 1.04");
    expect(pickProjectionLine({ projected_range: "Early 1st" })).toBe("proj. Early 1st");
    expect(pickProjectionLine({})).toBeNull();
  });
  it("passes the partner-fit line through, empty as null", () => {
    expect(partnerFitLine(" Fills their TE hole · they're contending ")).toBe("Fills their TE hole · they're contending");
    expect(partnerFitLine("")).toBeNull();
    expect(partnerFitLine(undefined)).toBeNull();
  });
});
