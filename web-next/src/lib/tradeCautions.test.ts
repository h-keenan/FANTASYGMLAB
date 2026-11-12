import { describe, expect, it } from "vitest";
import { cautionDetail, cautionShareLine, verdictCautions } from "./tradeCautions";

const glut = {
  code: "pick_glut",
  tag: "Trading proven value for picks you may not need",
  explanation: "You already hold 5 first- and second-round picks in the next two drafts.",
  softened: true,
  softened_from: "SMASH ACCEPT",
};

describe("tradeCautions", () => {
  it("ignores missing or malformed cautions", () => {
    expect(verdictCautions(undefined)).toEqual([]);
    expect(verdictCautions({ cautions: null })).toEqual([]);
    expect(verdictCautions({ cautions: [{ code: "x", tag: " ", explanation: "" }] })).toEqual([]);
  });
  it("explains the softened label so copy agrees with it", () => {
    expect(cautionDetail(glut, "ACCEPT")).toContain("from Smash Accept to Accept");
    expect(cautionDetail({ ...glut, softened: false }, "ACCEPT")).toBe(glut.explanation);
  });
  it("builds the share line from the tag", () => {
    expect(cautionShareLine({ cautions: [glut] })).toBe("Trading proven value for picks you may not need.");
    expect(cautionShareLine({})).toBe("");
  });
});
