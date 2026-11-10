import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import type { RankedPlayer } from "@/lib/api";
import { mergeSearchMatches, useLeaguePlayerSearchState } from "@/lib/leaguePlayerSearch";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, searchLeaguePlayers: vi.fn() } };
});

const p = (id: string) => ({ player_id: id, name: id }) as unknown as RankedPlayer;

describe("mergeSearchMatches", () => {
  it("appends server matches missing from the window, keeping window order", () => {
    const merged = mergeSearchMatches([p("1"), p("2")], [p("2"), p("650")]);
    expect(merged.map((x) => x.player_id)).toEqual(["1", "2", "650"]);
  });
  it("returns the same array when nothing is new", () => {
    const pool = [p("1")];
    expect(mergeSearchMatches(pool, [p("1")])).toBe(pool);
    expect(mergeSearchMatches(pool, [])).toBe(pool);
  });
});

describe("useLeaguePlayerSearchState", () => {
  beforeEach(() => vi.mocked(api.searchLeaguePlayers).mockReset());

  it("does not call the server for short queries or a missing league", () => {
    const short = renderHook(() => useLeaguePlayerSearchState("L1", "Dynasty", "a"));
    const noLeague = renderHook(() => useLeaguePlayerSearchState("", "Dynasty", "beck"));
    expect(short.result.current).toEqual({ players: [], pending: false });
    expect(noLeague.result.current).toEqual({ players: [], pending: false });
    expect(api.searchLeaguePlayers).not.toHaveBeenCalled();
  });

  it("is pending until the server answers, then returns the matches", async () => {
    vi.mocked(api.searchLeaguePlayers).mockResolvedValue({ ok: true, players: [p("650")] } as never);
    const { result } = renderHook(() => useLeaguePlayerSearchState("L1", "Dynasty", "beck"));
    expect(result.current.pending).toBe(true);
    await waitFor(() => expect(result.current.players.map((x) => x.player_id)).toEqual(["650"]));
    expect(result.current.pending).toBe(false);
    expect(api.searchLeaguePlayers).toHaveBeenCalledWith("L1", "beck", "Dynasty");
  });
});
