import assert from 'node:assert/strict';
import { describe, it } from 'node:test';


import { RECAP_CARD_ROWS, recapCardModel, recapRowsFromItems } from "./recapCard.ts";

// Tiny jest-style matcher set so this file stays line-for-line comparable with web-next/src/lib/statusHeader.test.ts.
const subset = (actual: any, expected: any): void => {
  for (const key of Object.keys(expected)) {
    if (expected[key] && typeof expected[key] === 'object') subset(actual[key], expected[key]);
    else assert.equal(actual[key], expected[key]);
  }
};
const expect = (actual: any) => ({
  toBe: (e: unknown) => assert.equal(actual, e),
  toEqual: (e: unknown) => assert.deepEqual(actual, e),
  toBeNull: () => assert.equal(actual, null),
  toHaveLength: (n: number) => assert.equal(actual.length, n),
  toBeLessThanOrEqual: (n: number) => assert.ok(actual <= n),
  toMatchObject: (e: object) => subset(actual, e),
  toMatch: (re: RegExp) => assert.ok(re.test(actual)),
  not: { toMatch: (re: RegExp) => assert.ok(!re.test(actual)) },
});



describe("recap card model", () => {
  it("shows three rows and keeps the rest behind More, dropping only empty values", () => {
    const rows = recapRowsFromItems([1, 2, 3, 4, 5].map((n) => ({ label: `L${n}`, detail: n === 2 ? "" : `v${n}` })));
    const model = recapCardModel({ kicker: "SEASON", badge: "A-", rows });
    expect(model.rows.map((r) => r.value)).toEqual(["v1", "v3", "v4"]);
    expect(model.more.map((r) => r.value)).toEqual(["v5"]);
    expect(model.rows).toHaveLength(RECAP_CARD_ROWS);
    expect(model.badge).toBe("A-");
  });
  it("accepts text items and falsy entries", () => {
    const model = recapCardModel({ kicker: "NEXT", rows: [...recapRowsFromItems([{ label: "Lineup", text: "2 issues", tone: "warning" }]), false, null] });
    expect(model.rows).toEqual([{ key: "0-Lineup", label: "Lineup", value: "2 issues", tone: "warning" }]);
    expect(model.badge).toBeNull();
  });
});
