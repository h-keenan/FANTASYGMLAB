import { describe, expect, it } from "vitest";

import type { IdpValueRow, LeagueIdpValuesResponse } from "./api";
import {
  hasIdpValues,
  idpMethodNote,
  idpRowsAsRankedPlayers,
  isIdpPositionFilter,
  playersPositionOptions,
  withIdpPositionOptions,
} from "./idpPresentation";

const BASE = ["ALL", "QB", "RB", "WR", "TE", "K"];

function row(overrides: Partial<IdpValueRow> = {}): IdpValueRow {
  return {
    player_id: "d1",
    name: "Edge Rusher",
    position: "DE",
    family: "DL",
    team: "DET",
    age: 26.1,
    injury_status: null,
    value: 2706,
    ppg: 15.54,
    projected_points: 240,
    points_over_replacement: 53,
    confidence: "high",
    idp_rank: 1,
    ...overrides,
  };
}

const IDP: LeagueIdpValuesResponse = {
  ok: true,
  idp: true,
  players: [row()],
  below_replacement_ids: [],
  unscored_keys: ["bonus_def_int_td_50p"],
};

describe("idpPresentation", () => {
  it("adds DL/LB/DB position chips only for a league with IDP values", () => {
    expect(playersPositionOptions(BASE, IDP)).toEqual([...BASE, "DL", "LB", "DB"]);
    expect(playersPositionOptions(BASE, null)).toEqual(BASE);
    expect(playersPositionOptions(BASE, { ok: true, idp: false, players: [] })).toEqual(BASE);
    expect(playersPositionOptions(BASE, { ok: true, idp: true, players: [], reason: "no_idp_scoring" })).toEqual(BASE);
  });

  it("returns nothing for a non-IDP league", () => {
    expect(idpRowsAsRankedPlayers(null)).toEqual([]);
    expect(idpRowsAsRankedPlayers({ ok: true, idp: false, players: [] })).toEqual([]);
    expect(hasIdpValues(undefined)).toBe(false);
  });

  it("adapts rows to RankedPlayer with the value as score and the lineup family as position", () => {
    const [player] = idpRowsAsRankedPlayers(IDP);
    expect(player).toMatchObject({ player_id: "d1", position: "DL", score: 2706, overall_rank: null, tier: null });
    expect(player.stats?.map((s) => s.key)).toEqual(["idp_ppg", "idp_por"]);
    expect(player.stats?.[0].value).toBe(15.54);
  });

  it("recognises the defense chips and states what is not counted", () => {
    expect(isIdpPositionFilter("LB")).toBe(true);
    expect(isIdpPositionFilter("WR")).toBe(false);
    expect(idpMethodNote(IDP)).toContain("not market prices");
    expect(idpMethodNote(IDP)).toContain("bonus_def_int_td_50p");
    expect(idpMethodNote(null)).toBeNull();
  });
});

describe("withIdpPositionOptions", () => {
  it("adds DL/LB/DB only when defenders are present", () => {
    expect(withIdpPositionOptions(BASE, [])).toEqual(BASE);
    expect(withIdpPositionOptions(BASE, undefined)).toEqual(BASE);
    expect(withIdpPositionOptions(BASE, [{}])).toEqual([...BASE, "DL", "LB", "DB"]);
  });
});

import { idpTradePoolPlayers, tradePositionOptions } from "./idpPresentation";

describe("trade pool", () => {
  const idp = {
    ok: true,
    idp: true,
    players: [row()],
    below_replacement_players: [
      { player_id: "x1", name: "Low Corner", position: "CB", family: "DB", team: "NYJ", age: 23, injury_status: null, value: null },
    ],
  } as unknown as LeagueIdpValuesResponse;

  it("lists valued defenders at their model value and below-replacement ones with a null score", () => {
    const pool = idpTradePoolPlayers(idp);
    expect(pool.map((p) => [p.player_id, p.score])).toEqual([["d1", 2706], ["x1", null]]);
  });

  it("is empty for non-IDP leagues and adds defense chips only when defenders exist", () => {
    expect(idpTradePoolPlayers({ ok: true, idp: false, players: [] })).toEqual([]);
    expect(idpTradePoolPlayers(null)).toEqual([]);
    expect(tradePositionOptions(BASE, [{ position: "QB" }])).toEqual(BASE);
    expect(tradePositionOptions(BASE, idpTradePoolPlayers(idp))).toEqual([...BASE, "DL", "LB", "DB"]);
  });
});
