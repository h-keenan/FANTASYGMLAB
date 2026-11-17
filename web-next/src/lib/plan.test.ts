import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { normalizeMe } from "@/lib/apiDefaults";
import { freeLimitNote } from "@/lib/freeLimits";
import { isProOrNull, planOf } from "@/lib/plan";
import { simNewGameBlock } from "@/lib/simGame";

// Entitlement matrix: for each paid feature gate, Pro unlocks it and Free sees
// the paywall. Server gates (is_premium) are covered by tests/test_entitlement_matrix.py.
const FREE = { entitlement: "free", profile_status: "ok" };
const PRO = { entitlement: "premium", profile_status: "ok" };
const FRONT_OFFICE = { entitlement: "front_office", profile_status: "ok" };
const UNREADABLE = { entitlement: "free", profile_status: "error" };

describe("planOf: one Pro answer for every web surface", () => {
  it("maps what /v1/me can say", () => {
    expect(planOf(PRO)).toBe("pro");
    expect(planOf(FRONT_OFFICE)).toBe("pro");
    expect(planOf(FREE)).toBe("free");
    expect(planOf({ entitlement: "banana", profile_status: "ok" })).toBe("free");
    expect(planOf(UNREADABLE)).toBe("unknown");
    expect(planOf(null)).toBe("unknown");
    expect(isProOrNull(PRO)).toBe(true);
    expect(isProOrNull(FREE)).toBe(false);
    expect(isProOrNull(UNREADABLE)).toBeNull();
  });

  it("survives the /v1/me normalizer for Pro, Free and unreadable", () => {
    const me = (user: Record<string, unknown>) => normalizeMe({ ok: true, user }).user;
    expect(planOf(me({ entitlement: "premium", profile_status: "ok" }))).toBe("pro");
    expect(planOf(me({ entitlement: "free", profile_status: "ok" }))).toBe("free");
    expect(planOf(me({ entitlement: "free", profile_status: "error" }))).toBe("unknown");
    expect(planOf(me({ entitlement: "premium" }))).toBe("unknown"); // missing status is not trusted
  });
});

describe("paid-feature gates", () => {
  it("Sim: Free gets 1 free season in 1 saved game, then the paywall; Pro is never paywalled for seasons", () => {
    expect(simNewGameBlock(0, 1, false, false)).toBeNull();
    expect(simNewGameBlock(0, 1, false, true)).toMatch(/Go Pro/);
    expect(simNewGameBlock(1, 1, false, false)).toMatch(/Go Pro/);
    expect(simNewGameBlock(1, 3, true, false)).toBeNull();
    expect(simNewGameBlock(0, 3, true, false)).toBeNull();
    expect(simNewGameBlock(3, 3, true, false)).not.toMatch(/Go Pro/);
  });

  it("Sim: an unverified plan never shows the Free paywall", () => {
    expect(simNewGameBlock(0, 1, undefined, true)).toBeNull();
  });

  it("limit notes: Free sees the upgrade note, Pro and unreadable do not", () => {
    const base = { noun: "trade ideas", limit: 4, kind: "window", total: 10 } as const;
    expect(freeLimitNote({ ...base, isPremium: isProOrNull(FREE) })?.cta).toBe("upgrade");
    expect(freeLimitNote({ ...base, isPremium: isProOrNull(PRO) })).toBeNull();
    expect(freeLimitNote({ ...base, isPremium: isProOrNull(UNREADABLE) })).toBeNull();
  });
});

describe("no divergent Pro check", () => {
  it("entitlement is only compared to a plan literal inside plan.ts and the /v1/me normalizer", () => {
    const root = join(__dirname, "..");
    const offenders: string[] = [];
    const walk = (dir: string) => {
      for (const name of readdirSync(dir)) {
        const path = join(dir, name);
        if (statSync(path).isDirectory()) walk(path);
        else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name) && !/(\/|^)(plan|apiDefaults)\.ts$/.test(path)) {
          if (/entitlement\s*[!=]==?\s*["'](premium|pro|free)["']/.test(readFileSync(path, "utf8"))) offenders.push(path);
        }
      }
    };
    walk(root);
    expect(offenders).toEqual([]);
  });
});
