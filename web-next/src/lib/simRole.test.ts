import { describe, expect, it } from "vitest";

import { simIfStartsHint, simRoleBadge, type SimPlayerRole } from "@/lib/simGame";

const role = (over: Partial<SimPlayerRole>): SimPlayerRole => ({ kind: "starter", label: null, if_starts: 13.5, ...over });

describe("sim team roles", () => {
  it("shows a chip only for a fill-in or a backup", () => {
    expect(simRoleBadge({ role: role({ kind: "fill_in", label: "Starting while Hurts is out" }) })).toEqual({ label: "Starting while Hurts is out", tone: "accent" });
    expect(simRoleBadge({ role: role({ kind: "backup", label: "Backup" }) })).toEqual({ label: "Backup", tone: "muted" });
    expect(simRoleBadge({ role: role({ kind: "starter" }) })).toBeNull();
    expect(simRoleBadge({})).toBeNull();
  });

  it("keeps the 'if he starts' hint separate and only for non-starters", () => {
    expect(simIfStartsHint({ role: role({ kind: "backup", label: "Backup" }) })).toBe("If he starts: 13.5 pts");
    expect(simIfStartsHint({ role: role({ kind: "starter" }) })).toBeNull();
    expect(simIfStartsHint({ role: null })).toBeNull();
  });
});
