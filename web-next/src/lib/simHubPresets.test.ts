import { describe, expect, it } from "vitest";

import { simSetupBody, type SimGameOptionsResponse } from "@/lib/simGame";
import { simHubEmptyHint, simHubGameName, simHubMode, simHubPresetChips, simHubPresets } from "@/lib/simHubPresets";

const withDynasty = {
  ok: true,
  reason: "",
  options: {
    mode: { values: ["redraft", "dynasty"], default: "redraft" },
    teams: { values: [12], default: 12 },
    scoring: { values: ["half"], default: "half" },
    difficulty: { values: ["easy", "normal", "hard"], default: "normal" },
    user_slot: { min: 1, max: 12, default: null },
    auto_lineup: { default: false },
    seasons: { values: [1, 2, 3, 4, 5], default: 5 },
  },
} as unknown as SimGameOptionsResponse;

describe("simHubPresets", () => {
  it("offers only Quick when dynasty is not playable", () => {
    const presets = simHubPresets(null);
    expect(presets.map((p) => p.id)).toEqual(["quick"]);
    expect(presets[0].state.mode).toBe("redraft");
  });

  it("offers Quick, Standard and Deep dynasty when dynasty is available, each a valid create body", () => {
    const presets = simHubPresets(withDynasty);
    expect(presets.map((p) => p.id)).toEqual(["quick", "standard", "deep"]);
    expect(simSetupBody(presets[0].state).mode).toBe("redraft");
    expect(simSetupBody(presets[1].state)).toMatchObject({ mode: "dynasty", seasons: 2 });
    expect(simSetupBody(presets[2].state)).toMatchObject({ mode: "dynasty", seasons: 5 });
    expect(presets[1].action).toBe("Start Standard game");
  });

  it("summarises a preset as chips and picks the first-timer or returning layout", () => {
    const chips = simHubPresetChips(simHubPresets(withDynasty)[1]);
    expect(chips).toContain("Dynasty, 2 seasons");
    expect(chips).toContain("Normal AI");
    expect(simHubMode(0)).toBe("first");
    expect(simHubMode(2)).toBe("returning");
  });

  it("names a saved game by its shape", () => {
    expect(simHubGameName({ settings: { teams: 10, mode: "dynasty" } })).toBe("Dynasty · 10 teams");
    expect(simHubGameName({ settings: {} })).toBe("Redraft · 12 teams");
  });
});

describe("simHubEmptyHint", () => {
  it("names every preset the sheet will show", () => {
    expect(simHubEmptyHint(simHubPresets(withDynasty))).toContain("Quick, Standard or Deep dynasty");
    expect(simHubEmptyHint(simHubPresets(null))).toContain("choose Quick.");
  });
});
