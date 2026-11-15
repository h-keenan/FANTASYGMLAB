import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { canOpenPlayer, isValidNonInteractiveReason, playerOpenLabel } from "@/lib/playerTap";

describe("player tap rule", () => {
  it("a player with an id can open, one without stays plain", () => {
    expect(canOpenPlayer({ id: "7564", name: "Ja" })).toBe(true);
    expect(canOpenPlayer({ id: null, name: "Rookie" })).toBe(false);
    expect(playerOpenLabel("Kayshon Boutte")).toBe("Open Kayshon Boutte");
  });

  it("a nonInteractive opt-out needs a real reason", () => {
    expect(isValidNonInteractiveReason("")).toBe(false);
    expect(isValidNonInteractiveReason("the row button around it already opens the player")).toBe(true);
  });

  // Source scan (scripts/check_player_tap.mjs): fails when a player template is nested inside another tap target without a
  // reasoned nonInteractive opt-out, when a nonInteractive has no reason, or when a new file draws a bare avatar / name.
  it("every player template is tappable or explicitly non-interactive", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_player_tap.mjs");
    let out = "";
    try {
      out = execFileSync("node", [script], { encoding: "utf8", stdio: "pipe" });
    } catch (error) {
      const failure = error as { stderr?: string; stdout?: string };
      throw new Error(failure.stderr || failure.stdout || String(error));
    }
    expect(out).toContain("passed");
  });
});
