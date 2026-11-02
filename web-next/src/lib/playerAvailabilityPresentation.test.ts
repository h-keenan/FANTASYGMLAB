import { describe, expect, it } from "vitest";

import {
  availabilityDetailParts,
  byePillText,
  cleanInjuryLabel,
  newsAgeLabel,
  newsPageHref,
} from "./playerAvailabilityPresentation";

describe("playerAvailabilityPresentation", () => {
  it("never renders IR as 'Ir'", () => {
    expect(cleanInjuryLabel("IR")).toBe("Injured Reserve");
    expect(cleanInjuryLabel("Questionable")).toBe("Questionable");
    expect(cleanInjuryLabel("  ")).toBeNull();
    expect(cleanInjuryLabel(null)).toBeNull();
  });
  it("lists only the detail fields that exist", () => {
    const base = { status: "IR", label: "Injured Reserve", severity: "out" as const, unavailable: true, report: null };
    expect(availabilityDetailParts({ ...base, body_part: "Knee", return_note: "No return date reported" })).toEqual([
      "Knee",
      "No return date reported",
    ]);
    expect(availabilityDetailParts({ ...base, body_part: null, return_note: "No return date reported" })).toEqual([
      "No return date reported",
    ]);
  });
  it("only appends '(this week)' to the bye pill for an unavailable player", () => {
    expect(byePillText(8, true, true)).toBe("Bye: Wk 8 (this week)");
    expect(byePillText(8, true, false)).toBe("Bye: Wk 8");
    expect(byePillText(8, false, true)).toBe("Bye: Wk 8");
  });
  it("formats news age and the filtered news link", () => {
    const now = 1_000_000 * 1000;
    expect(newsAgeLabel(1_000_000 - 7200, now)).toBe("2h ago");
    expect(newsAgeLabel(null, now)).toBe("");
    expect(newsPageHref("12", "A B")).toBe("/news?player=12&name=A%20B");
  });
});
