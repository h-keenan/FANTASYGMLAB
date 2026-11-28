import { describe, expect, it } from "vitest";

import { countPlanNeeds, planHeaderChips } from "./gmPlanHeader";

describe("planHeaderChips", () => {
  it("states posture, window and needs from real fields", () => {
    const chips = planHeaderChips({ stance: "rebuilding", deadlineWeek: 11, pastDeadline: false, needs: 3 });
    expect(chips.map((c) => [c.key, c.value])).toEqual([
      ["posture", "Rebuild"],
      ["window", "Wk 11"],
      ["needs", "3"],
    ]);
  });

  it("is honest when nothing is set or the window has closed", () => {
    expect(planHeaderChips({ stance: "", deadlineWeek: null, pastDeadline: true, needs: 0 }).map((c) => c.value)).toEqual(["Not set", "Closed", "0"]);
    expect(planHeaderChips({ stance: "competing", deadlineWeek: null, pastDeadline: false, needs: 0 })[1].value).toBe("Open");
  });
});

describe("countPlanNeeds", () => {
  it("counts injured-starter positions and relative weak spots, nothing else", () => {
    expect(
      countPlanNeeds([
        { items: [{ injury_need_positions: ["TE", "RB"] }, { relative_weak_spot: true }, { relative_weak_spot: false }, {}] },
        { items: [{ relative_weak_spot: true }] },
      ]),
    ).toBe(4);
  });
});
