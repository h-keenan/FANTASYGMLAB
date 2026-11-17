import { describe, expect, it } from "vitest";

import { simManagerLabel } from "./simManagerLabel";

describe("simManagerLabel", () => {
  it("AI managers read as AI and a first name, flagged for the bot mark", () => {
    expect(simManagerLabel("Tessa Vance")).toEqual({ text: "AI \u00b7 Tessa", isAi: true, short: "Tessa" });
  });
  it("you are You; humans keep their username with no bot mark; nothing is null", () => {
    expect(simManagerLabel("You", { isYou: true })?.text).toBe("You");
    expect(simManagerLabel("coridian_", { human: true })).toMatchObject({ text: "coridian_", isAi: false });
    expect(simManagerLabel("")).toBeNull();
  });
});
