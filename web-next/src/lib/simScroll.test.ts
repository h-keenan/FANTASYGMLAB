import { describe, expect, it } from "vitest";

import { simScrollKey, simShouldScrollTop } from "./simScroll";

describe("simScrollKey", () => {
  it("a page change scrolls to the top; the same page and the first render never do", () => {
    const week = simScrollKey({ view: "game", stage: "week", tab: "home", week: 4, status: "in_season" });
    const recap = simScrollKey({ view: "game", stage: "week", tab: "home", week: 5, status: "in_season", hasRecap: true, recapIndex: 0 });
    const nextRecap = simScrollKey({ view: "game", stage: "week", tab: "home", week: 5, status: "in_season", hasRecap: true, recapIndex: 1 });
    const tab = simScrollKey({ view: "game", stage: "week", tab: "team", week: 5, status: "in_season" });
    const offseason = simScrollKey({ view: "game", stage: "offseason", tab: "home", week: 14, status: "offseason" });
    expect(simShouldScrollTop(null, week)).toBe(false);
    expect(simShouldScrollTop(week, week)).toBe(false);
    for (const next of [recap, nextRecap, tab, offseason]) expect(simShouldScrollTop(week, next)).toBe(true);
    expect(simShouldScrollTop(recap, nextRecap)).toBe(true);
  });
});
