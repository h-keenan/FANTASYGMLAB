import { describe, expect, it } from "vitest";

import type { RankedPlayer } from "./api";
import { filterPlayers, matchesPlayersAge, matchesPlayersAvailability, matchesPlayersStatus } from "./playersPresentation";

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Test Player",
    position: "WR",
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 10,
    position_rank: 3,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 80,
    ...overrides,
  };
}

describe("matchesPlayersAge", () => {
  it("passes everything for ALL", () => {
    expect(matchesPlayersAge(null, "ALL")).toBe(true);
    expect(matchesPlayersAge(40, "ALL")).toBe(true);
  });

  it("excludes unknown age for any real bucket", () => {
    expect(matchesPlayersAge(null, "Under 25")).toBe(false);
  });

  it("buckets correctly at the edges", () => {
    expect(matchesPlayersAge(24, "Under 25")).toBe(true);
    expect(matchesPlayersAge(25, "Under 25")).toBe(false);
    expect(matchesPlayersAge(25, "25-28")).toBe(true);
    expect(matchesPlayersAge(28, "25-28")).toBe(true);
    expect(matchesPlayersAge(29, "25-28")).toBe(false);
    expect(matchesPlayersAge(29, "29+")).toBe(true);
  });
});

describe("matchesPlayersStatus", () => {
  it("treats empty/missing status as neither Active nor Inactive explicitly, matching mobile", () => {
    expect(matchesPlayersStatus("", "Active")).toBe(false);
    expect(matchesPlayersStatus("", "Inactive")).toBe(false);
  });

  it("is case-insensitive", () => {
    expect(matchesPlayersStatus("ACTIVE", "Active")).toBe(true);
    expect(matchesPlayersStatus("Retired", "Inactive")).toBe(true);
  });
});

describe("matchesPlayersAvailability", () => {
  it("treats any non-empty injury_status as Injured", () => {
    expect(matchesPlayersAvailability("Questionable", "Injured")).toBe(true);
    expect(matchesPlayersAvailability(null, "Injured")).toBe(false);
    expect(matchesPlayersAvailability(null, "Healthy")).toBe(true);
    expect(matchesPlayersAvailability("Out", "Healthy")).toBe(false);
  });
});

describe("filterPlayers", () => {
  const pool = [
    player({ player_id: "a", name: "Alpha Receiver", position: "WR", age: 22, status: "Active", injury_status: null }),
    player({ player_id: "b", name: "Beta Back", position: "RB", age: 30, status: "Active", injury_status: "Questionable" }),
    player({ player_id: "c", name: "Gamma Kicker", position: "K", age: 26, status: "Inactive", injury_status: null }),
  ];

  it("combines search, position, age, status, and availability without re-sorting", () => {
    const result = filterPlayers(pool, {
      search: "",
      position: "ALL",
      ageFilter: "ALL",
      statusFilter: "ALL",
      availabilityFilter: "ALL",
    });
    expect(result.map((p) => p.player_id)).toEqual(["a", "b", "c"]);
  });

  it("search matches name only, case-insensitively", () => {
    const result = filterPlayers(pool, {
      search: "beta",
      position: "ALL",
      ageFilter: "ALL",
      statusFilter: "ALL",
      availabilityFilter: "ALL",
    });
    expect(result.map((p) => p.player_id)).toEqual(["b"]);
  });

  it("position filter includes K, unlike mobile's own list", () => {
    const result = filterPlayers(pool, {
      search: "",
      position: "K",
      ageFilter: "ALL",
      statusFilter: "ALL",
      availabilityFilter: "ALL",
    });
    expect(result.map((p) => p.player_id)).toEqual(["c"]);
  });

  it("stacks every filter at once", () => {
    const result = filterPlayers(pool, {
      search: "",
      position: "ALL",
      ageFilter: "29+",
      statusFilter: "Active",
      availabilityFilter: "Injured",
    });
    expect(result.map((p) => p.player_id)).toEqual(["b"]);
  });
});
