import { describe, expect, it } from "vitest";

import type { GuillotineResponse } from "@/lib/api";
import { guillotineView } from "@/lib/guillotine";

const base: GuillotineResponse = {
  ok: true,
  is_guillotine: true,
  reason: "",
  alive: true,
  weeks_survived: 4,
  teams_alive: 9,
  teams_total: 12,
  chop_line: null,
};

describe("guillotineView", () => {
  it("renders nothing for normal leagues or missing data", () => {
    expect(guillotineView(null)).toBeNull();
    expect(guillotineView({ ...base, is_guillotine: false })).toBeNull();
  });

  it("says nothing about the chop line without projections", () => {
    const view = guillotineView(base)!;
    expect(view.badge).toEqual({ label: "Alive", tone: "success" });
    expect(view.items.map((i) => i.label)).toEqual(["Survived", "Alive"]);
  });

  it("flags at-risk with the margin", () => {
    const view = guillotineView({ ...base, chop_line: { line: 88.4, my_projected: 85.1, margin: -3.3, at_risk: true } })!;
    expect(view.badge).toEqual({ label: "At risk", tone: "danger" });
    expect(view.items.at(-1)).toEqual({ label: "Margin", value: "-3.3", tone: "risk" });
  });

  it("marks eliminated teams and hides the chop line", () => {
    const view = guillotineView({
      ...base,
      alive: false,
      chop_line: { line: 90, my_projected: null, margin: null, at_risk: false },
    })!;
    expect(view.badge.label).toBe("Chopped");
    expect(view.items).toHaveLength(2);
  });
});
