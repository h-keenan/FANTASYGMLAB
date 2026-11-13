import { describe, expect, it } from "vitest";

import { simScrollKey, simShouldScrollTop, simTabAfterStageAction } from "./simScroll";

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

describe("stage-advancing actions", () => {
  it("land on the page that hosts the new stage, and a new offseason step scrolls to the top", () => {
    for (const action of ["start_rookie_draft", "auto_draft", "start_season", "start_playoffs"] as const) expect(simTabAfterStageAction(action)).toBe("home");
    const review = simScrollKey({ view: "game", stage: "offseason", tab: "home", status: "offseason", step: "review" });
    const draft = simScrollKey({ view: "game", stage: "offseason", tab: "home", status: "offseason", step: "rookie_draft" });
    expect(simShouldScrollTop(review, draft)).toBe(true);
  });
});
