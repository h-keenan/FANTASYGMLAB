import { describe, expect, it } from "vitest";

import { WHY_REGISTRY, whyEntry, whyTriggerLabel } from "./tapForWhyContent";

describe("tapForWhyContent", () => {
  it("every metric has a title and 1 to 3 plain sentences", () => {
    for (const [key, entry] of Object.entries(WHY_REGISTRY)) {
      expect(entry.id).toBe(key);
      expect(entry.title.length).toBeGreaterThan(0);
      expect(entry.sentences.length).toBeGreaterThanOrEqual(1);
      expect(entry.sentences.length).toBeLessThanOrEqual(3);
    }
  });
  it("reuses the shared beginner copy so captions and popovers never disagree", () => {
    expect(whyEntry("ovr").sentences[0]).toMatch(/Overall \(1-99\)/);
  });
  it("labels the trigger from spoken text or the title", () => {
    expect(whyTriggerLabel("value", "Value 82")).toBe("Why: Value 82");
    expect(whyTriggerLabel("faab")).toBe("Why: FAAB bid");
  });
});
