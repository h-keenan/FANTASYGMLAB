import { describe, expect, it } from "vitest";

import type { SimGame, SimRealismFlag, SimRealismInfo } from "./simGame";
import {
  SIM_REALISM_NOT_RETROACTIVE,
  simRealismBanner,
  simRealismBannerKey,
  simRealismEligible,
  simRealismGroups,
  simRealismParts,
  simRealismPending,
  simRealismToast,
  simRealismWhen,
} from "./simRealism";
import { simTransactionGlyph } from "./simGame";

const flag = (name: string, boundary: SimRealismFlag["boundary"], when = ""): SimRealismFlag => ({ flag: name, value: 1, label: name, body: `${name} body`, boundary, when });

const info = (over: Partial<SimRealismInfo> = {}): SimRealismInfo => ({
  rules_version: 0,
  eligible: true,
  pending: [flag("hint_v", "now", "Right away"), flag("world_v", "week", "From the next simulated week"), flag("aging_v", "season", "From the next offseason")],
  scheduled: [],
  in_force: {},
  history: [],
  note: SIM_REALISM_NOT_RETROACTIVE,
  ...over,
});

const game = (rules: SimRealismInfo | null | undefined, status = "in_season"): Pick<SimGame, "id" | "rules" | "status"> => ({ id: "g1", rules, status } as Pick<SimGame, "id" | "rules" | "status">);

describe("Realism update view logic", () => {
  it("is eligible only while a rule is off and the server says so", () => {
    expect(simRealismEligible(game(info()))).toBe(true);
    expect(simRealismEligible(game(info({ eligible: false })))).toBe(false);
    expect(simRealismEligible(game(info({ pending: [] })))).toBe(false);
    expect(simRealismEligible(game(null))).toBe(false);
    expect(simRealismEligible(game(undefined))).toBe(false); // an older server sends no rules block
    expect(simRealismPending(game(info({ eligible: false })))).toEqual([]);
  });

  it("groups the preview by when each rule starts, in a fixed order", () => {
    const groups = simRealismGroups([flag("aging_v", "season"), flag("hint_v", "now"), flag("kd_v", "now")]);
    expect(groups.map((g) => g.boundary)).toEqual(["now", "season"]);
    expect(groups[0].flags.map((f) => f.flag)).toEqual(["hint_v", "kd_v"]);
    expect(groups[0].when).toBe("Right away");
    expect(simRealismWhen(flag("x", "week"))).toBe("From the next simulated week");
  });

  it("shows the Home banner only for an eligible, undismissed, unfinished save", () => {
    const b = simRealismBanner(game(info()), false);
    expect(b?.count).toBe(3);
    expect(b?.body).toContain(SIM_REALISM_NOT_RETROACTIVE);
    expect(simRealismBanner(game(info()), true)).toBeNull();
    expect(simRealismBanner(game(info({ eligible: false })), false)).toBeNull();
    expect(simRealismBanner(game(info(), "complete"), false)).toBeNull();
    expect(simRealismBanner(game(null), false)).toBeNull();
  });

  it("keys the dismissal by game, version and rule set", () => {
    expect(simRealismBannerKey("g1", info())).not.toBe(simRealismBannerKey("g2", info()));
    expect(simRealismBannerKey("g1", info())).not.toBe(simRealismBannerKey("g1", info({ rules_version: 1 })));
    expect(simRealismBannerKey("g1", info())).toBe(simRealismBannerKey("g1", info({ pending: [...info().pending].reverse() })));
  });

  it("words the menu header and the toast", () => {
    expect(simRealismParts(info())[0].text).toBe("3 newer rules available");
    expect(simRealismParts(info({ eligible: false, pending: [], scheduled: [flag("aging_v", "season")] }))[1].text).toBe("1 rule start next offseason");
    expect(simRealismParts(info({ eligible: false, pending: [] }))[0].text).toBe("Up to date");
    expect(simRealismParts(null)[0].text).toBe("Not available");
    expect(simRealismToast({ upgraded: true, flags: ["a", "b"] })).toBe(`Rules updated: 2 new rules on. ${SIM_REALISM_NOT_RETROACTIVE}`);
    expect(simRealismToast({ upgraded: false, flags: [] })).toBe("This game already plays by the newest rules.");
  });

  it("gives the activity feed's Rules updated row an accent glyph", () => {
    expect(simTransactionGlyph({ type: "rules" })).toEqual({ glyph: "stats", tone: "accent" });
  });
});
