// @vitest-environment node
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { buildPartnerPitch, clearRateLimitForTests, parseAnalyzerPayload } from "@/lib/shareCard/analyzerShare";
import { clearShareCachesForTests } from "@/lib/shareCard/server";
import { fixturePlayer, pngSize } from "@/lib/shareCard/testFixtures";

import { POST } from "./route";

type FetchArgs = [input: string | URL | Request, init?: RequestInit];

const verdict = {
  band: "Fair",
  ui_verdict: "COUNTER",
  confidence: "Medium",
  rationale: "Roughly even on value, but you give up the better starter.",
  value_summary: "",
  roster_summary: "",
  strategy_summary: "",
  risk_summary: "",
  counter_guidance: "",
  fit_total: 0,
  value_delta: -274,
  tone: "counter",
};
const sent = { ...fixturePlayer, player_id: "1", name: "Sent Player", position: "QB", team: "ARI", score: 4400 };
const pick2028 = { pick_id: "2028:1:4", label: "2028 Round 1", score: 900, season: 2028, round: 1, original_roster_id: "4", owner_roster_id: "4", original_team_name: null, owner_team_name: null, pick_tier: null, projected_pick_range: null };
const pick = { pick_id: "2027:3:4", label: "2027 Round 3", score: 834, season: 2027, round: 3, original_roster_id: "4", owner_roster_id: "4", original_team_name: null, owner_team_name: null, pick_tier: null, projected_pick_range: null };

function stub(opts: { analyzer?: unknown; players?: unknown[] } = {}) {
  const calls: FetchArgs[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (...args: FetchArgs) => {
      calls.push(args);
      const url = String(args[0]);
      if (url.includes("/trade-analyzer")) return Response.json(opts.analyzer ?? { ok: true, verdict, reason: "" });
      if (url.includes("/rankings")) return Response.json({ ok: true, players: opts.players ?? [sent, fixturePlayer] });
      if (url.includes("/draft-picks")) return Response.json({ ok: true, picks: [pick, pick2028], reason: "" });
      if (url.includes("/team-profiles")) {
        return Response.json({ ok: true, profiles: { "4": { team_name: "Rival GM", owner_name: "r", username: "r", avatar_id: "", avatar_url: "", roster_id: 4, owner_id: "o" } } });
      }
      if (url.includes("/rank?")) return Response.json({ player: null });
      if (url.includes("/portfolio/")) return Response.json({ league: { team_name: "My Squad", team_avatar_url: null } });
      return new Response("", { status: 404 });
    }),
  );
  return calls;
}

const base = { leagueId: "L1", sendPlayerIds: ["1"], receivePlayerIds: ["2"], sendPickIds: ["2028:1:4"], receivePickIds: ["2027:3:4"], partnerRosterId: "4" };

function post(body: unknown, auth = "Bearer tok-1") {
  return POST(
    new Request("http://localhost/share-card/analyzer", {
      method: "POST",
      headers: auth ? { authorization: auth, "content-type": "application/json" } : {},
      body: typeof body === "string" ? body : JSON.stringify(body),
    }),
  );
}

describe("POST /share-card/analyzer", () => {
  beforeEach(() => {
    clearShareCachesForTests();
    clearRateLimitForTests();
    vi.stubEnv("SHARE_CARD_INTERNAL_SECRET", "sekret");
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("requires a bearer token", async () => {
    stub();
    expect((await post(base, "")).status).toBe(401);
  });

  it("rejects malformed, oversized and empty payloads", async () => {
    stub();
    expect((await post("{nope")).status).toBe(400);
    expect((await post({ ...base, sendPlayerIds: ["../x"] })).status).toBe(422);
    expect((await post({ ...base, lens: "Bogus" })).status).toBe(422);
    expect((await post({ ...base, sendPlayerIds: Array.from({ length: 11 }, (_, i) => `p${i}`) })).status).toBe(422);
    expect((await post({ leagueId: "L1" })).status).toBe(422);
    expect((await post({ ...base, pad: "x".repeat(5000) })).status).toBe(413);
  });

  it("rate limits per caller", async () => {
    stub();
    let last = 0;
    for (let i = 0; i < 12; i++) last = (await post({ ...base, sendPlayerIds: [`p${i}`] })).status;
    expect(last).toBe(429);
  }, 60_000);

  it("re-derives the verdict upstream and ignores client-sent values", async () => {
    const calls = stub();
    const response = await post({ ...base, grade: "A+", score: 9999, verdict: { ui_verdict: "ACCEPT" } });
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toBe("image/png");
    const png = await response.arrayBuffer();
    expect(pngSize(png)).toEqual({ width: 1080, height: 1350, isPng: true });

    const analyzer = calls.find(([url]) => String(url).includes("/trade-analyzer"));
    expect(analyzer?.[1]?.method).toBe("POST");
    expect(new Headers(analyzer?.[1]?.headers).get("authorization")).toBe("Bearer tok-1");
    const sentBody = JSON.parse(String(analyzer?.[1]?.body));
    expect(sentBody).toMatchObject({ send_player_ids: ["1"], receive_pick_ids: ["2027:3:4"], partner_roster_id: "4" });
    expect(JSON.stringify(sentBody)).not.toContain("9999");
    // Quota-exempt token is sent server-to-server only when the secret is configured.
    expect(new Headers(analyzer?.[1]?.headers).get("x-share-card-token")).toBe("sekret");

    const out = process.env.SHARE_CARD_SAMPLE_DIR;
    if (out) {
      mkdirSync(out, { recursive: true });
      writeFileSync(join(out, "analyzer-card-v2.png"), Buffer.from(png));
    }
  }, 60_000);

  it("404s when a posted id can't be resolved, instead of a partial card", async () => {
    stub({ players: [fixturePlayer] });
    const response = await post(base);
    expect(response.status).toBe(404);
  });

  it("explains a missing verdict", async () => {
    stub({ analyzer: { ok: true, verdict: null, reason: "empty_roster" } });
    const response = await post(base);
    expect(response.status).toBe(422);
  });
});

describe("parseAnalyzerPayload", () => {
  it("dedupes ids and defaults strategy/lens", () => {
    const parsed = parseAnalyzerPayload({ ...base, sendPlayerIds: ["1", "1"] });
    expect(parsed.ok && parsed.payload).toMatchObject({ sendPlayerIds: ["1"], strategy: "retool", lens: "Dynasty" });
  });
});

describe("buildPartnerPitch", () => {
  const player = (name: string, position: string, score: number) => ({ asset_type: "player" as const, name, position, score });
  const pk = { asset_type: "pick" as const, season: "2027", round: "3", score: 100 };

  it("pitches value gain, position upgrade and incoming picks when supported", () => {
    const pitch = buildPartnerPitch([player("Star WR", "WR", 5000), pk], [player("Meh WR", "WR", 3000)], "Rival GM");
    expect(pitch.headline).toBe("A trade that works for Rival GM");
    expect(pitch.lines).toEqual(["You gain 2,100 in value", "Upgrade at WR: Star WR", "Adds a 2027 Round 3 pick"]);
  });

  it("says fair value when within 5% and never claims a partner edge it doesn't have", () => {
    expect(buildPartnerPitch([player("A", "QB", 1000)], [player("B", "RB", 1030)], "X").lines).toEqual(["Fair value both ways"]);
    const sender = buildPartnerPitch([player("A", "QB", 1000)], [player("B", "RB", 3000)], "X");
    expect(sender.headline).toBe("Trade proposal for X");
    expect(sender.lines.join(" ")).not.toMatch(/gain|works for/i);
  });

  it("is a neutral proposal with no partner picked", () => {
    expect(buildPartnerPitch([player("A", "QB", 1)], [player("B", "RB", 1)], "").headline).toBe("Trade proposal");
  });
});
