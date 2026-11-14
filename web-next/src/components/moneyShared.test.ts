import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { formatMoney, formatMoneyRange, splitMoney } from "@/lib/money";

/**
 * Guard: dollar amounts are built by lib/money.ts and painted by <Money>
 * (--color-money). No raw "$${x}" / "$12" formatting elsewhere in src.
 */
const ALLOWED = new Set(["lib/money.ts", "lib/money.test.ts", "components/Money.tsx", "lib/privacy.ts"]);
const SRC = join(__dirname, "..");
const RAW_MONEY = /\$\$\{|["'`]\$\d/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

describe("money guard", () => {
  it("has no raw money formatting outside the shared module", () => {
    const offenders = walk(SRC)
      .filter((f) => !ALLOWED.has(f.slice(SRC.length + 1)))
      .filter((f) => readFileSync(f, "utf8").split("\n").some((l) => !/^\s*(\/\/|\*|\/\*)/.test(l) && RAW_MONEY.test(l)))
      .map((f) => f.slice(SRC.length + 1));
    expect(offenders).toEqual([]);
  });

  it("formats and splits amounts", () => {
    expect(formatMoney(81)).toBe("$81");
    expect(formatMoney(3.99)).toBe("$3.99");
    expect(formatMoneyRange(8, 12)).toBe("$8–$12");
    expect(splitMoney("of $81 remaining")).toEqual([
      { text: "of ", money: false },
      { text: "$81", money: true },
      { text: " remaining", money: false },
    ]);
    expect(splitMoney("42.5 pts").some((s) => s.money)).toBe(false);
  });
});
