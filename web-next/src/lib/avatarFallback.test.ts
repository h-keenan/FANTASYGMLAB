import { describe, expect, it } from "vitest";

import { avatarChain, avatarMonogram, pickAvatarSource, teamLogoUrl } from "./avatarFallback";

describe("avatar fallback chain", () => {
  it("real player: headshot, then monogram", () => {
    const input = { playerId: "4046", name: "Patrick Mahomes", position: "QB" };
    expect(avatarChain(input).map((s) => s.kind)).toEqual(["headshot", "monogram"]);
    expect(pickAvatarSource(input, []).kind).toBe("headshot");
    expect(pickAvatarSource(input, ["headshot:4046"])).toMatchObject({ kind: "monogram", label: "PM", position: "QB" });
  });

  it("team defense: logo, never a headshot, then monogram", () => {
    const input = { playerId: "SF", name: "49ers D/ST", position: "DEF", team: "SF" };
    const first = pickAvatarSource(input, []);
    expect(first).toMatchObject({ kind: "teamLogo", url: "https://sleepercdn.com/images/team_logos/nfl/sf.png" });
    expect(pickAvatarSource(input, [first.key]).kind).toBe("monogram");
  });

  it("made-up sim player (no id): monogram straight away", () => {
    expect(pickAvatarSource({ playerId: null, name: "Ranked Player 0", position: "WR" }, [])).toMatchObject({ kind: "monogram", label: "R0", position: "WR" });
  });

  it("monogram is never empty", () => {
    expect(avatarMonogram({})).toBe("?");
    expect(avatarMonogram({ team: "buf" })).toBe("BUF");
    expect(avatarMonogram({ name: "Odell Beckham Jr." })).toBe("OB");
    expect(avatarMonogram({ name: "Ignored", label: "XY" })).toBe("XY");
    expect(pickAvatarSource({}, ["anything"]).kind).toBe("monogram");
  });

  it("rejects non-team codes for logos", () => {
    expect(teamLogoUrl("")).toBeNull();
    expect(teamLogoUrl("12")).toBeNull();
  });
});
