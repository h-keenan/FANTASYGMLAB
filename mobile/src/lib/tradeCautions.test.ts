import assert from "node:assert/strict";
import test from "node:test";
import { cautionDetail, cautionShareLine, verdictCautions } from "./tradeCautions.ts";

const glut = {
  code: "pick_glut",
  tag: "Trading proven value for picks you may not need",
  explanation: "You already hold 5 first- and second-round picks in the next two drafts.",
  softened: true,
  softened_from: "SMASH ACCEPT",
};

test("ignores missing or malformed cautions", () => {
  assert.deepEqual(verdictCautions(undefined), []);
  assert.deepEqual(verdictCautions({ cautions: [{ code: "x", tag: " ", explanation: "" }] }), []);
});

test("explains the softened label and builds the share line", () => {
  assert.match(cautionDetail(glut, "ACCEPT"), /from Smash Accept to Accept/);
  assert.equal(cautionShareLine({ cautions: [glut] }), "Trading proven value for picks you may not need.");
  assert.equal(cautionShareLine({}), "");
});
