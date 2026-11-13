import { describe, expect, it } from "vitest";

import {
  activeFilterChips,
  activeFilterCount,
  applyButtonLabel,
  isChipSelected,
  removeFilterChip,
  singleValue,
  toggleFilterValue,
  valuesFromSingles,
  type FilterGroup,
} from "./filterSheet";

const pos: FilterGroup = { id: "pos", label: "Position", anyValue: "ALL", options: [{ value: "ALL", label: "Any" }, { value: "QB", label: "QB" }, { value: "RB", label: "RB" }] };
const tags: FilterGroup = { id: "tags", label: "Tags", multi: true, options: [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }] };
const hidden: FilterGroup = { id: "roster", label: "Roster", hidden: true, anyValue: "ALL", options: [{ value: "Rostered", label: "Rostered" }] };

describe("filterSheet", () => {
  it("counts only real filters: never the any value, never hidden groups", () => {
    expect(activeFilterCount([pos, tags, hidden], { pos: ["ALL"], tags: ["a", "b"], roster: ["Rostered"] })).toBe(2);
    expect(activeFilterCount([pos], {})).toBe(0);
  });
  it("single-select replaces, any clears, tapping the selected chip clears", () => {
    let v = toggleFilterValue(pos, {}, "QB");
    expect(v.pos).toEqual(["QB"]);
    v = toggleFilterValue(pos, v, "RB");
    expect(v.pos).toEqual(["RB"]);
    expect(toggleFilterValue(pos, v, "RB").pos).toEqual([]);
    expect(toggleFilterValue(pos, v, "ALL").pos).toEqual([]);
  });
  it("multi-select toggles membership", () => {
    let v = toggleFilterValue(tags, {}, "a");
    v = toggleFilterValue(tags, v, "b");
    expect(v.tags).toEqual(["a", "b"]);
    expect(toggleFilterValue(tags, v, "a").tags).toEqual(["b"]);
  });
  it("selects the any chip when nothing else is chosen", () => {
    expect(isChipSelected(pos, {}, "ALL")).toBe(true);
    expect(isChipSelected(pos, { pos: ["QB"] }, "ALL")).toBe(false);
    expect(isChipSelected(pos, { pos: ["QB"] }, "QB")).toBe(true);
  });
  it("builds removable chips with labels and removes one", () => {
    const values = { pos: ["QB"], tags: ["a", "b"] };
    expect(activeFilterChips([pos, tags], values).map((c) => c.label)).toEqual(["QB", "Alpha", "Beta"]);
    expect(removeFilterChip(values, { groupId: "tags", value: "a" }).tags).toEqual(["b"]);
  });
  it("labels the footer and trigger", () => {
    expect(applyButtonLabel(null)).toBe("Apply");
    expect(applyButtonLabel(0)).toBe("No results");
    expect(applyButtonLabel(1)).toBe("Show 1 result");
    expect(applyButtonLabel(24)).toBe("Show 24 results");
  });
  it("round-trips page-style single values", () => {
    const values = valuesFromSingles([pos], { pos: "QB" });
    expect(singleValue(pos, values)).toBe("QB");
    expect(singleValue(pos, valuesFromSingles([pos], { pos: "ALL" }))).toBe("ALL");
  });
});
