import { describe, expect, it } from "vitest";

import { PLAYER_NAME_LAST_STAGE, playerNameStage, playerNameStages } from "./playerNameFit";

describe("playerNameStage", () => {
  it("walks full -> initial + whole surname -> smaller -> smaller -> wrapped", () => {
    const stages = playerNameStages("Jonathan Brisker");
    expect(stages.map((s) => s.text)).toEqual(["Jonathan Brisker", "J. Brisker", "J. Brisker", "J. Brisker", "J. Brisker"]);
    expect(stages.map((s) => s.scale)).toEqual([1, 1, 0.92, 0.85, 0.85]);
    expect(stages.map((s) => s.wrap)).toEqual([false, false, false, false, true]);
  });
  it("never produces an ellipsis or a cut surname for any stage", () => {
    const names = ["Rhamondre Stevenson", "Amon-Ra St. Brown", "Jaxon Smith-Njigba", "Michael Penix Jr.", "Kenneth Walker III", "Jason Van Dyke", "T.J. Hockenson", "Neymar", "Ravens D/ST", "J. Cook", "", "  Wan'Dale   Robinson "];
    for (const n of names) {
      const surname = n.replace(/\s+/g, " ").trim().split(" ").slice(1).join(" ");
      for (const s of playerNameStages(n)) {
        expect(s.text).not.toMatch(/[.]{3}|…/);
        if (surname) expect(s.text).toContain(surname.replace(/ (Jr\.|Sr\.|II|III|IV)$/, ""));
      }
    }
  });
  it("keeps suffixes and multi-word surnames whole", () => {
    expect(playerNameStage("Michael Penix Jr.", 1).text).toBe("M. Penix Jr.");
    expect(playerNameStage("Amon-Ra St. Brown", 1).text).toBe("A. St. Brown");
  });
  it("clamps the index and leaves names that cannot shrink as they are", () => {
    expect(playerNameStage("Neymar", 9).index).toBe(PLAYER_NAME_LAST_STAGE);
    expect(playerNameStage("Neymar", 1).short).toBe(false);
    expect(playerNameStage("Chiefs DEF", 1).text).toBe("Chiefs DEF");
  });
});
