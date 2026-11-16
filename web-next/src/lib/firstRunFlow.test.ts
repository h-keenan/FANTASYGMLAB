import { readFileSync } from "node:fs";
import path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";

import {
  FIRST_RUN_FUNNEL_STEPS,
  armTrialOffer,
  dismissTrialOffer,
  firstRunStage,
  funnelStepIndex,
  shouldShowTrialOffer,
  firstRunPromptSlot,
} from "./firstRunFlow";
import { claimFirstRunPrompt, currentFirstRunPrompt, resetFirstRunPrompts } from "./useFirstRunPrompt";

describe("firstRunStage (navigation guard)", () => {
  it("signed out always sees sign-in", () => {
    expect(firstRunStage({ signedIn: false, introSeen: true, leagueCount: 3 })).toBe("sign_in");
  });

  it("new account: intro first, then connect, never a paywall stage", () => {
    expect(firstRunStage({ signedIn: true, introSeen: false, leagueCount: 0 })).toBe("intro");
    expect(firstRunStage({ signedIn: true, introSeen: true, leagueCount: 0 })).toBe("connect");
    expect(firstRunStage({ signedIn: true, introSeen: true, leagueCount: null })).toBe("connect");
  });

  it("a connected league goes straight to its home, even if the intro was never seen", () => {
    expect(firstRunStage({ signedIn: true, introSeen: false, leagueCount: 1 })).toBe("league_home");
    expect(firstRunStage({ signedIn: true, introSeen: true, leagueCount: 2 })).toBe("portfolio");
  });

  it("has no billing input: entitlement or trial status cannot gate any stage", () => {
    const stages = new Set<string>();
    for (const signedIn of [false, true]) {
      for (const introSeen of [false, true]) {
        for (const leagueCount of [null, 0, 1, 5]) stages.add(firstRunStage({ signedIn, introSeen, leagueCount }));
      }
    }
    expect([...stages].sort()).toEqual(["connect", "intro", "league_home", "portfolio", "sign_in"]);
    expect(stages.has("paywall")).toBe(false);
  });
});

describe("trial offer state machine", () => {
  it("arms once on first connect and a dismissed offer never re-arms", () => {
    expect(armTrialOffer("idle")).toBe("armed");
    expect(armTrialOffer("armed")).toBe("armed");
    expect(armTrialOffer("dismissed")).toBe("dismissed");
  });

  it("dismiss always resolves, so a user can always continue free", () => {
    const state = dismissTrialOffer();
    expect(state).toBe("dismissed");
    expect(shouldShowTrialOffer({ state, isPremium: false, onLeagueHome: true })).toBe(false);
  });

  it("shows only when armed, on the league home, and not already Pro", () => {
    const base = { state: "armed" as const, isPremium: false, onLeagueHome: true };
    expect(shouldShowTrialOffer(base)).toBe(true);
    expect(shouldShowTrialOffer({ ...base, onLeagueHome: false })).toBe(false);
    expect(shouldShowTrialOffer({ ...base, isPremium: true })).toBe(false);
    expect(shouldShowTrialOffer({ ...base, state: "idle" })).toBe(false);
  });
});

describe("funnel ids", () => {
  it("orders connect before the first league view", () => {
    expect([...FIRST_RUN_FUNNEL_STEPS]).toEqual(["level", "value", "connect", "first_league_view"]);
    expect(funnelStepIndex("connect")).toBeLessThan(funnelStepIndex("first_league_view"));
  });
});

describe("first-run prompt slot (audit F3)", () => {
  it("ranks Start here over the direction check-in over the trial offer", () => {
    expect(firstRunPromptSlot({ start_here: true, direction_checkin: true, trial_offer: true })).toBe("start_here");
    expect(firstRunPromptSlot({ direction_checkin: true, trial_offer: true })).toBe("direction_checkin");
    expect(firstRunPromptSlot({ trial_offer: true })).toBe("trial_offer");
    expect(firstRunPromptSlot({ start_here: false, direction_checkin: false })).toBeNull();
    expect(firstRunPromptSlot({})).toBeNull();
  });

  it("never lets more than one prompt through, whatever wants it", () => {
    const kinds = ["start_here", "direction_checkin", "trial_offer"] as const;
    for (let mask = 0; mask < 8; mask += 1) {
      const wants = Object.fromEntries(kinds.map((k, i) => [k, Boolean(mask & (1 << i))]));
      const winners = kinds.filter((k) => firstRunPromptSlot(wants) === k);
      expect(winners.length).toBe(mask === 0 ? 0 : 1);
    }
  });
});

describe("first-run prompt store", () => {
  beforeEach(() => resetFirstRunPrompts());

  it("hands the slot down as higher priorities release it", () => {
    claimFirstRunPrompt("trial_offer", true);
    claimFirstRunPrompt("direction_checkin", true);
    expect(currentFirstRunPrompt()).toBe("direction_checkin");
    claimFirstRunPrompt("start_here", true);
    expect(currentFirstRunPrompt()).toBe("start_here");
    claimFirstRunPrompt("start_here", false);
    expect(currentFirstRunPrompt()).toBe("direction_checkin");
    claimFirstRunPrompt("direction_checkin", false);
    expect(currentFirstRunPrompt()).toBe("trial_offer");
    claimFirstRunPrompt("trial_offer", false);
    expect(currentFirstRunPrompt()).toBeNull();
  });
});

describe("firstRunFlow twin", () => {
  it("stays byte-identical to the mobile twin", () => {
    const mobile = readFileSync(path.join(__dirname, "../../../mobile/src/lib/firstRunFlow.ts"), "utf8");
    expect(mobile).toBe(readFileSync(path.join(__dirname, "firstRunFlow.ts"), "utf8"));
  });
});
