import { describe, expect, it } from "vitest";
import { dropRepeatedSentences, shortSummary } from "./verdictText";

describe("verdictText", () => {
  const lineup = "This costs you about 12.4 pts/week in your starting lineup.";
  it("drops sentences already shown", () => {
    const rationale = `${lineup} Your side gives up more value.`;
    expect(dropRepeatedSentences(rationale, [lineup])).toBe("Your side gives up more value.");
    expect(dropRepeatedSentences(lineup.toUpperCase(), [lineup])).toBe("");
  });
  it("summarises to first sentence", () => {
    expect(shortSummary(`${lineup} More.`)).toBe(lineup);
    expect(shortSummary("", 2)).toBe("");
  });
});
