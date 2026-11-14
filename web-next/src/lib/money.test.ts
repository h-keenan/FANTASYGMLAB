import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { formatMoney, formatMoneyRange, hasMoney, splitMoney } from "./money";

describe("money helpers", () => {
  it("formats whole and fractional dollars", () => {
    expect(formatMoney(81)).toBe("$81");
    expect(formatMoney(3.99)).toBe("$3.99");
    expect(formatMoney(19.9)).toBe("$19.90");
    expect(formatMoneyRange(8, 12)).toBe("$8–$12");
  });

  it("splits only dollar amounts, leaving points and percents plain", () => {
    expect(splitMoney("of $81 remaining")).toEqual([
      { text: "of ", money: false },
      { text: "$81", money: true },
      { text: " remaining", money: false },
    ]);
    expect(splitMoney("$8–$12")).toEqual([{ text: "$8–$12", money: true }]);
    expect(hasMoney("24.5 pts, 40% of FAAB, 12 wins")).toBe(false);
  });
});

/**
 * Source scan: money is built with lib/money.ts and painted by <Money>. A raw
 * "$" amount (template `$${x}` or a "$12" literal) anywhere else means a
 * dollar figure that skips the money color. Add a file to ALLOWED only with a reason.
 */
const ALLOWED: Record<string, string> = {
  "lib/money.ts": "the formatter itself",
  "lib/privacy.ts": "regex escape, not money",
  "lib/playerBadges.ts": "trade-block badge glyph, not an amount",
};
const RAW_MONEY = /\$\$\{|[`"']\$\d/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name)) out.push(full);
  }
  return out;
}

describe("money source scan", () => {
  it("has no raw dollar formatting outside the shared helper", () => {
    const root = join(__dirname, "..");
    const offenders: string[] = [];
    for (const file of walk(root)) {
      const rel = file.slice(root.length + 1);
      if (ALLOWED[rel]) continue;
      readFileSync(file, "utf8")
        .split("\n")
        .forEach((line, i) => {
          if (/^\s*(\/\/|\*|\/\*)/.test(line)) return;
          if (RAW_MONEY.test(line)) offenders.push(`${rel}:${i + 1}`);
        });
    }
    expect(offenders).toEqual([]);
  });
});
