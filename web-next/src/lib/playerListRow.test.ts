import { describe, expect, it } from "vitest";

import { limitPlayerListTags, orderPlayerListStats } from "./playerListRow";

describe("playerListRow", () => {
  it("Overall and Trade value share one slot, so a row never carries both", () => {
    const s = (key: string) => ({ key, label: key, value: "1" });
    expect(orderPlayerListStats([s("proj"), s("tval"), s("adp")]).map((x) => x?.key)).toEqual(["proj", "tval", "adp"]);
    expect(orderPlayerListStats([s("proj"), s("ovr"), s("tval")]).map((x) => x?.key)).toEqual(["proj", "ovr"]);
  });
  it("shows at most two tags and collapses the rest into +N", () => {
    expect(limitPlayerListTags(["a", "b"])).toEqual({ shown: ["a", "b"], extra: 0 });
    expect(limitPlayerListTags(["a", "b", "c", "d"])).toEqual({ shown: ["a", "b"], extra: 2 });
  });
  it("orders stats PROJ, OVR, TRADE VALUE, ADP, EDGE and keeps a gap for a missing middle pill", () => {
    const s = (key: string) => ({ key, label: key, value: "1" });
    expect(orderPlayerListStats([s("adp"), s("proj"), s("ovr")]).map((x) => x?.key)).toEqual(["proj", "ovr", "adp"]);
    expect(orderPlayerListStats([s("proj"), s("adp")]).map((x) => x?.key ?? null)).toEqual(["proj", null, "adp"]);
    expect(orderPlayerListStats([s("proj"), s("edge")]).map((x) => x?.key ?? null)).toEqual(["proj", null, null, "edge"]);
  });
});

describe("aligned columns", () => {
  it("an aligned list reserves proj + metric + edge at a fixed width and gives an empty ADP slot no room", async () => {
    const { PLAYER_LIST_ALIGNED_WIDTH, playerListSlotWidth, PLAYER_LIST_SLOT_WIDTH } = await import("./playerListRow");
    expect(PLAYER_LIST_ALIGNED_WIDTH).toBe(PLAYER_LIST_SLOT_WIDTH.proj + PLAYER_LIST_SLOT_WIDTH.metric + PLAYER_LIST_SLOT_WIDTH.edge + 6);
    expect(playerListSlotWidth(2, true)).toBe(0);
    expect(playerListSlotWidth(2, false)).toBe(PLAYER_LIST_SLOT_WIDTH.adp);
    expect(playerListSlotWidth(3, true)).toBe(PLAYER_LIST_SLOT_WIDTH.edge);
    expect(playerListSlotWidth(0, true)).toBe(PLAYER_LIST_SLOT_WIDTH.proj);
  });
});
