// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { clearShareCachesForTests } from "@/lib/shareCard/server";
import { fixtureIdea, fixturePlayer, pngSize } from "@/lib/shareCard/testFixtures";

import { GET as getPlayerCard } from "./player/route";
import { GET as getTradeCard } from "./trade/route";

type FetchArgs = [input: string | URL | Request, init?: RequestInit];

/** Upstream API stub: serves `apiBody` for the API path, 404s for images. */
function stubUpstream(apiStatus: number, apiBody: unknown) {
  const calls: FetchArgs[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (...args: FetchArgs) => {
      calls.push(args);
      const url = String(args[0]);
      if (url.includes("/v1/")) return Response.json(apiBody, { status: apiStatus });
      return new Response("", { status: 404 });
    }),
  );
  return calls;
}

function request(path: string, auth = "Bearer token-123") {
  return new Request(`http://localhost${path}`, { headers: auth ? { authorization: auth } : {} });
}

describe("GET /share-card/trade", () => {
  beforeEach(() => clearShareCachesForTests());
  afterEach(() => vi.unstubAllGlobals());

  it("requires a bearer token", async () => {
    stubUpstream(200, { ideas: [fixtureIdea] });
    expect((await getTradeCard(request("/share-card/trade?leagueId=1&rec=rec-1", ""))).status).toBe(401);
  });

  it("rejects malformed ids and unknown lenses", async () => {
    stubUpstream(200, { ideas: [fixtureIdea] });
    expect((await getTradeCard(request("/share-card/trade?leagueId=../x&rec=rec-1"))).status).toBe(422);
    expect((await getTradeCard(request("/share-card/trade?leagueId=1&rec=rec-1&lens=Bogus"))).status).toBe(422);
  });

  it("draws only an idea the caller's own trade-hub response contains", async () => {
    const calls = stubUpstream(200, { ok: true, ideas: [fixtureIdea] });
    const response = await getTradeCard(request("/share-card/trade?leagueId=L1&rec=rec-1&strategy=retool&lens=Dynasty"));
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/png");
    expect(response.headers.get("cache-control")).toContain("private");
    expect(pngSize(await response.arrayBuffer())).toEqual({ width: 1080, height: 1350, isPng: true });

    const apiCall = calls.find(([url]) => String(url).includes("/v1/"));
    expect(String(apiCall?.[0])).toContain("/v1/leagues/L1/trade-hub?strategy=retool&lens=Dynasty&ad_unlocks=0");
    expect(new Headers(apiCall?.[1]?.headers).get("authorization")).toBe("Bearer token-123");
  }, 60_000);

  it("404s a recommendation the board no longer has, without drawing anything", async () => {
    stubUpstream(200, { ok: true, ideas: [fixtureIdea] });
    const response = await getTradeCard(request("/share-card/trade?leagueId=L1&rec=stale"));
    expect(response.status).toBe(404);
    expect(response.headers.get("content-type")).toContain("application/json");
  });

  it("passes an upstream auth failure through", async () => {
    stubUpstream(401, { detail: "Invalid token" });
    const response = await getTradeCard(request("/share-card/trade?leagueId=L1&rec=rec-1"));
    expect(response.status).toBe(401);
  });

  it("serves a repeat request from the render cache without calling the API again", async () => {
    const calls = stubUpstream(200, { ok: true, ideas: [fixtureIdea] });
    await getTradeCard(request("/share-card/trade?leagueId=L1&rec=rec-1"));
    const apiCallsAfterFirst = calls.filter(([url]) => String(url).includes("/v1/")).length;
    const second = await getTradeCard(request("/share-card/trade?leagueId=L1&rec=rec-1"));
    expect(second.headers.get("x-share-card-cache")).toBe("hit");
    expect(calls.filter(([url]) => String(url).includes("/v1/")).length).toBe(apiCallsAfterFirst);
    // A different user never gets that cached card.
    const other = await getTradeCard(request("/share-card/trade?leagueId=L1&rec=rec-1", "Bearer other-user"));
    expect(other.headers.get("x-share-card-cache")).toBe("miss");
  }, 60_000);
});

describe("GET /share-card/player", () => {
  beforeEach(() => clearShareCachesForTests());
  afterEach(() => vi.unstubAllGlobals());

  it("draws the player from the caller's own rankings", async () => {
    const calls = stubUpstream(200, { ok: true, players: [fixturePlayer] });
    const response = await getPlayerCard(request("/share-card/player?leagueId=L1&playerId=2&lens=Rebuild"));
    expect(response.status).toBe(200);
    expect(pngSize(await response.arrayBuffer()).isPng).toBe(true);
    expect(String(calls.find(([url]) => String(url).includes("/v1/"))?.[0])).toContain("/v1/leagues/L1/rankings?lens=Rebuild&limit=300");
  }, 60_000);

  it("404s a player who isn't on the board", async () => {
    stubUpstream(200, { ok: true, players: [fixturePlayer] });
    expect((await getPlayerCard(request("/share-card/player?leagueId=L1&playerId=999"))).status).toBe(404);
  });
});
