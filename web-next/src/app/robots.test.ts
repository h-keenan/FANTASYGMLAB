import { describe, expect, it } from "vitest";

import robots from "./robots";

describe("robots", () => {
  it("points crawlers at the sitemap that lists /trade-analyzer", () => {
    expect(robots().sitemap).toBe("https://app.fantasygmlab.com/sitemap.xml");
  });
});
