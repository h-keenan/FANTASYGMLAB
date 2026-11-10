import { describe, expect, it } from "vitest";

import { ACCENT_BY_DESTINATION, accentFor, destinationId } from "./destinationAccents.generated";
import { accentVar } from "./destinationAccent";
import { FEATURE_ITEMS } from "./featureCatalog";
import { FOUNDER_DESTINATION, useNavDestinations } from "./navDestinations";

describe("shared destination accents (nav / orb / catalog / app)", () => {
  it("gives every catalog item the shared accent, and every accent a catalog item", () => {
    for (const item of FEATURE_ITEMS) {
      expect(ACCENT_BY_DESTINATION[item.id], item.id).toBeDefined();
      expect(item.color, item.id).toBe(accentVar(item.id));
    }
    for (const id of Object.keys(ACCENT_BY_DESTINATION)) {
      expect(FEATURE_ITEMS.some((i) => i.id === id), id).toBe(true);
    }
  });

  it("colors every nav row that has an accent from the shared map, by label", () => {
    const nav = useNavDestinations("L1", "X");
    const rows = [...nav.coreLeagueDestinations, ...nav.gmToolsDestinations, ...nav.generalDestinations];
    let checked = 0;
    for (const row of rows) {
      if (!ACCENT_BY_DESTINATION[destinationId(row.label)]) continue;
      checked += 1;
      expect(row.color, row.label).toBe(accentVar(row.label));
    }
    expect(checked).toBeGreaterThan(15);
    expect(FOUNDER_DESTINATION.color).toBe("var(--color-diagnostic)");
  });

  it("falls back to accent for destinations with no entry", () => {
    expect(accentFor("Home")).toBe("accent");
  });
});
