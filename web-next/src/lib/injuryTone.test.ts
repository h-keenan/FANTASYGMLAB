import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { INJURY_TONE_GOLDEN, injuryTone } from "./injuryTone.generated";
import { injuryTone as presentationTone } from "./myTeamPresentation";
import { waiverInjuryDisplay } from "./waiversPresentation";

describe("shared injury tone (generated from modules/injury_tone.py)", () => {
  it("replays the Python golden rows", () => {
    for (const { status, tone } of INJURY_TONE_GOLDEN) expect(injuryTone(status), status).toBe(tone);
  });

  it("Doubtful is red and Questionable amber on web, matching the app", () => {
    expect(presentationTone("Doubtful")).toBe("danger");
    expect(presentationTone("Questionable")).toBe("warning");
    expect(presentationTone("Hamstring")).toBe("neutral");
    expect(waiverInjuryDisplay("doubtful").tone).toBe("danger");
    expect(waiverInjuryDisplay("questionable").tone).toBe("warning");
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "injuryTone.generated.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/injuryTone.generated.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
