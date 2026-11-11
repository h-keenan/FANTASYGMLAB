import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Guard: a load failure renders the shared ErrorState (one "Try again", plain
 * language, HelpLink), not a hand-rolled <p role="alert"> with "Could not
 * load ...". Add a file to ALLOWED only with a reason.
 */
const ALLOWED: Record<string, string> = {
  "ErrorState.tsx": "the shared component itself",
};

const HAND_ROLLED = /<p[^>]*role="alert"[^>]*>[^<]*(Could not load|Couldn't load|Failed to load)/;

describe("ErrorState guard", () => {
  it("has no hand-rolled load-failure paragraphs", () => {
    const dir = __dirname;
    const offenders: string[] = [];
    for (const name of readdirSync(dir)) {
      if (!name.endsWith(".tsx") || ALLOWED[name]) continue;
      const source = readFileSync(join(dir, name), "utf8").replace(/\s+/g, " ");
      if (HAND_ROLLED.test(source)) offenders.push(name);
    }
    expect(offenders).toEqual([]);
  });

  it("has no bare Retry buttons", () => {
    const offenders: string[] = [];
    for (const name of readdirSync(__dirname)) {
      if (!name.endsWith(".tsx")) continue;
      if (/>\s*Retry\s*</.test(readFileSync(join(__dirname, name), "utf8"))) offenders.push(name);
    }
    expect(offenders).toEqual([]);
  });
});
