import { describe, expect, it } from "vitest";

import {
  DIGEST_CATEGORIES,
  activeCapPreset,
  digestEnabled,
  digestPatch,
  hourLabel,
  leagueMode,
  quietSummary,
} from "./notificationControls";

const PRESETS = [
  { key: "light", label: "Light", cap: 2 },
  { key: "standard", label: "Standard", cap: 4 },
  { key: "frequent", label: "Frequent", cap: 7 },
];

describe("notificationControls", () => {
  it("formats hours on a 12-hour clock", () => {
    expect([0, 7, 12, 13, 22].map(hourLabel)).toEqual(["12 AM", "7 AM", "12 PM", "1 PM", "10 PM"]);
  });

  it("matches the effective cap to a preset, null cap means the server default", () => {
    expect(activeCapPreset({ weekly_cap: null }, PRESETS, 4)).toBe("standard");
    expect(activeCapPreset({ weekly_cap: 2 }, PRESETS, 4)).toBe("light");
    expect(activeCapPreset({ weekly_cap: 5 }, PRESETS, 4)).toBeNull();
  });

  it("digest switch round-trips and never touches critical categories", () => {
    expect(digestEnabled({ category_modes: {} })).toBe(false);
    const on = digestPatch(true).category_modes ?? {};
    expect(Object.keys(on).sort()).toEqual([...DIGEST_CATEGORIES].sort());
    expect(digestEnabled({ category_modes: on })).toBe(true);
    expect(Object.keys(on)).not.toContain("injury");
    expect(Object.keys(on)).not.toContain("lineup_lock");
    expect(Object.values(digestPatch(false).category_modes ?? {}).every((mode) => mode === "instant")).toBe(true);
  });

  it("defaults a league to All and summarizes quiet hours", () => {
    expect(leagueMode({ league_overrides: { L1: "mute" } }, "L1")).toBe("mute");
    expect(leagueMode({ league_overrides: {} }, "L2")).toBe("all");
    expect(quietSummary({ quiet_hours_enabled: true, quiet_start: 22, quiet_end: 8 })).toBe("10 PM to 8 AM");
    expect(quietSummary({ quiet_hours_enabled: false, quiet_start: 22, quiet_end: 8 })).toBe("Off");
  });
});
