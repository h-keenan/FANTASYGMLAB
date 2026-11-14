import { describe, expect, it } from "vitest";

import { RECAP_CARD_ROWS, recapCardModel, recapRowsFromItems } from "./recapCard";

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
