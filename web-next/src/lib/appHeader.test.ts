import { describe, expect, it } from "vitest";

import { filterLeagues, headerShowsTitle, headerTemplateFor, normalizeHeaderChips, repeatsLabel, ribbonCollapsed } from "./appHeader";
import { leagueCrestColors, leagueCrestHue, leagueInitials } from "./leagueCrest";

describe("appHeader rules", () => {
  it("tab pages are root headers with no title; detail pages keep theirs", () => {
    for (const p of ["/dashboard/L1", "/my-team/L1", "/trade-hub/L1", "/league-rankings/L1", "/waivers/L1", "/news", "/portfolio", "/leagues"]) {
      expect(headerTemplateFor(p)).toBe("root");
      expect(headerShowsTitle(p)).toBe(false);
    }
    expect(headerTemplateFor("/players/L1")).toBe("root");
    expect(headerTemplateFor("/players/L1/12345")).toBe("detail");
    expect(headerTemplateFor("/gm-plan/L1")).toBe("detail");
    expect(headerShowsTitle("/account")).toBe(true);
    expect(headerTemplateFor("/gm-game/abc")).toBe("sim");
    expect(headerTemplateFor("/")).toBe("immersive");
  });

  it("chips: dropped when empty, duplicate, or repeating the page or league label; capped at 4; first is accent", () => {
    const chips = normalizeHeaderChips(
      [{ key: "a", text: "Wk 10" }, { key: "b", text: " " }, { key: "c", text: "wk 10" }, { key: "d", text: "Today" }, { key: "e", text: "7-1" }, { key: "f", text: "Win 57%" }, { key: "g", text: "Dynasty" }, { key: "h", text: "Extra" }],
      ["Today"],
    );
    expect(chips.map((c) => c.text)).toEqual(["Wk 10", "7-1", "Win 57%", "Dynasty"]);
    expect(chips[0].tone).toBe("accent");
  });

  it("repeatsLabel catches a title equal to a pill or tab label", () => {
    expect(repeatsLabel("Today", ["Today", "Team"])).toBe(true);
    expect(repeatsLabel("Trade Hub", ["Trades", "Hub"])).toBe(false);
    expect(repeatsLabel("", ["Today"])).toBe(false);
  });

  it("the ribbon folds after 24px and returns near the top (hysteresis)", () => {
    expect(ribbonCollapsed(10, false)).toBe(false);
    expect(ribbonCollapsed(30, false)).toBe(true);
    expect(ribbonCollapsed(20, true)).toBe(true);
    expect(ribbonCollapsed(2, true)).toBe(false);
  });

  it("league search ranks the current league first", () => {
    const rows = [{ league_id: "1", league_name: "Donk" }, { league_id: "2", league_name: "The Revivalry" }, { league_id: "3", league_name: "Donkey Kong" }];
    expect(filterLeagues(rows, "donk", "3").map((r) => r.league_id)).toEqual(["3", "1"]);
    expect(filterLeagues(rows, "", "2")[0].league_id).toBe("2");
  });
});

describe("leagueCrest", () => {
  it("initials skip filler words", () => {
    expect(leagueInitials("The Revivalry Dynasty Superflex League of Champions 2026")).toBe("RC");
    expect(leagueInitials("Donk")).toBe("DO");
    expect(leagueInitials("")).toBe("FD");
  });
  it("consecutive league ids spread across hues", () => {
    const hues = new Set(["901", "902", "903", "904", "905", "906"].map((id) => Math.floor(leagueCrestHue(id) / 40)));
    expect(hues.size).toBeGreaterThanOrEqual(4);
  });
  it("the colour is a stable hash of the id", () => {
    expect(leagueCrestHue("1221647449446162432")).toBe(leagueCrestHue("1221647449446162432"));
    expect(leagueCrestColors("a").fill).toMatch(/^hsl\(\d+ 62% 62%\)$/);
  });
});
