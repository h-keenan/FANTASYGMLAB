import { describe, expect, it } from "vitest";

import { partnerFitLine, pickCompactLabel, pickProjectionLine } from "./tradeIdeaPick";

describe("tradeIdeaPick", () => {
  it("shows the projected slot and whose pick it is", () => {
    expect(pickProjectionLine({ projected_slot_label: "1.04", original_team_name: "Gridiron", owner_team_name: "Me" })).toBe("proj. 1.04 · Gridiron's pick");
  });
  it("drops the owner part for the holder's own pick and falls back to the projected range", () => {
    expect(pickProjectionLine({ projected_slot_label: "1.04", original_team_name: "Me", owner_team_name: "Me" })).toBe("proj. 1.04");
    expect(pickProjectionLine({ projected_range: "Early 1st" })).toBe("proj. Early 1st");
    expect(pickProjectionLine({})).toBeNull();
  });
  it("uses a bare apostrophe for names ending in s", () => {
    expect(pickProjectionLine({ projected_slot_label: "1.04", original_team_name: "Bay Area Bandits", owner_team_name: "Me" })).toBe("proj. 1.04 \u00b7 Bay Area Bandits' pick");
  });
  it("passes the partner-fit line through, empty as null", () => {
    expect(partnerFitLine(" Fills their TE hole · they're contending ")).toBe("Fills their TE hole · they're contending");
    expect(partnerFitLine("")).toBeNull();
    expect(partnerFitLine(undefined)).toBeNull();
  });

  it("pickCompactLabel gives one short label for every spelling", () => {
    expect(pickCompactLabel("2027 Round 2")).toBe("2027 2nd");
    expect(pickCompactLabel("2028 R1")).toBe("2028 1st");
    expect(pickCompactLabel("2027 3rd round")).toBe("2027 3rd");
    expect(pickCompactLabel("2027 Round 11")).toBe("2027 11th");
    expect(pickCompactLabel(null, 2027, 4)).toBe("2027 4th");
    expect(pickCompactLabel("2027 Round 1 (Pick 1.04)")).toBe("2027 1st");
    expect(pickCompactLabel("Mystery pick")).toBe("Mystery pick");
    expect(pickCompactLabel("")).toBe("Draft pick");
  });
});
