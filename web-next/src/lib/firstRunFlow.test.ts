import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import {
  FIRST_RUN_FUNNEL_STEPS,
  armTrialOffer,
  dismissTrialOffer,
  firstRunStage,
  funnelStepIndex,
  shouldShowTrialOffer,
} from "./firstRunFlow";

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

describe("firstRunFlow twin", () => {
  it("stays byte-identical to the mobile twin", () => {
    const mobile = readFileSync(path.join(__dirname, "../../../mobile/src/lib/firstRunFlow.ts"), "utf8");
    expect(mobile).toBe(readFileSync(path.join(__dirname, "firstRunFlow.ts"), "utf8"));
  });
});
