// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { buildShareModel, type MultiAsset, type MultiTeamResult } from "@/lib/multiTeamTrade";

import { embedMultiTradeAvatars, renderMultiTradeCardSvg, type ShareStaticAssets } from "./clientRender";

const DIR = join(process.cwd(), "public", "share-card");
const buf = (name: string) => {
  const b = readFileSync(join(DIR, name));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
};
const dataUri = (name: string) => `data:image/png;base64,${readFileSync(join(DIR, name)).toString("base64")}`;
const assets: ShareStaticAssets = {
  yoga: buf("yoga.wasm"),
  lockup: dataUri("lockup-white.png"),
  qr: dataUri("qr-site.png"),
  fonts: ([500, 700, 800, 900] as const).map((weight) => ({ name: "Inter", data: buf(`inter-latin-${weight}-normal.woff`), weight, style: "normal" as const })),
};

const player = (id: string, label: string, position: string, extra: Partial<MultiAsset> = {}): MultiAsset => ({ type: "player", id, label, position, team: "BUF", score: 1000, ...extra });

function teams(n: number): MultiTeamResult[] {
  return Array.from({ length: n }, (_, i) => {
    const next = (i + 1) % n;
    const prev = (i + n - 1) % n;
    return {
      roster_id: String(i + 1),
      team_name: `Team Number ${i + 1}`,
      is_perspective: i === 0,
      sends: [player(`s${i}`, `Sender ${i}`, "WR", { to_roster_id: String(next + 1), to_team_name: `Team Number ${next + 1}` })],
      receives: [player(`r${i}`, `Receiver ${i}`, "RB", { from_roster_id: String(prev + 1), from_team_name: `Team Number ${prev + 1}` })],
      verdict: {},
      trade_score: 0,
      market_delta: i === 1 ? -420 : 260,
      lineup_delta: { per_week: 1.4 },
      tone: i === 1 ? "decline" : "accept",
      outcome: i === 1 ? "loses" : "wins",
      why: [],
      veto_risk: null,
    };
  });
}

describe("multi-team share card", () => {
  for (const n of [3, 4, 5, 6]) {
    it(`draws a ${n}-team card at 1080x1350 with gain/loss colors and sends lines`, async () => {
      const model = buildShareModel({ teams: teams(n) });
      const svg = await renderMultiTradeCardSvg(model, "Dynasty Overlords", assets);
      expect(svg.startsWith("<svg")).toBe(true);
      expect(svg).toContain('width="1080"');
      expect(svg).toContain('height="1350"');
      expect(svg).toContain("#25cc61");
      expect(svg).not.toContain("#ff9090");
      const out = process.env.MULTI_CARD_SAMPLE_DIR;
      if (out) {
        mkdirSync(out, { recursive: true });
        writeFileSync(join(out, `multi-${n}.svg`), svg);
      }
    }, 60_000);
  }

  it("keeps long names and many assets inside the canvas for 3 and 4 teams", async () => {
    for (const n of [3, 4]) {
      const long = teams(n).map((t, i) => ({
        ...t,
        team_name: ["Not Your Dad's Dih", "KING TITUS", "Cowboys Run Table Supreme Edition", "The Extremely Long Named Squad"][i],
        sends: [1, 2, 3, 4].map((k) => ({ ...t.sends[0], id: `x${i}${k}`, label: `Long Player Name ${i}${k}` })),
        receives: [1, 2, 3, 4].map((k) => ({ ...t.receives[0], id: `y${i}${k}`, label: `Another Long Player ${i}${k}`, from_team_name: "The Extremely Long Named Squad" })),
      }));
      const svg = await renderMultiTradeCardSvg(buildShareModel({ teams: long }), "Dynasty Overlords", assets);
      expect(svg).toContain('height="1350"');
      const out = process.env.MULTI_CARD_SAMPLE_DIR;
      if (out) writeFileSync(join(out, `multi-long-${n}.svg`), svg);
    }
  }, 60_000);

  it("flows for 3 and lists for 4+, with every team's real value change and a get-back line", () => {
    expect(buildShareModel({ teams: teams(3) }).layout).toBe("flow");
    expect(buildShareModel({ teams: teams(4) }).layout).toBe("list");
    const model = buildShareModel({ teams: teams(3) });
    expect(model.teams.map((t) => t.valueChangeText)).toEqual(["+260", "-420", "+260"]);
    expect(model.teams.map((t) => t.valueTone)).toEqual(["gain", "loss", "gain"]);
    expect(model.verdict.text).toContain("Biggest gain");
    expect(model.teams[1]).not.toHaveProperty("getsBack");
    expect(model.teams[1].sends.map((a) => a.label)).toEqual(["Sender 1"]);
  });

  it("embeds fetched avatars, falls back to initials when a fetch fails", async () => {
    const withAvatars = teams(3).map((t, i) => ({ ...t, avatar_url: `https://sleepercdn.com/avatars/thumbs/a${i}` }));
    const model = buildShareModel({ teams: withAvatars });
    const png = dataUri("lockup-white.png");
    const fetchImage = async (url: string | null | undefined) => (url?.endsWith("a1") ? null : png);
    const embedded = await embedMultiTradeAvatars(model, fetchImage);
    expect(embedded.teams.map((t) => t.avatarUrl)).toEqual([png, null, png]);
    expect(embedded.edges.every((e) => e.fromAvatarUrl === null || e.fromAvatarUrl === png)).toBe(true);
    const svg = await renderMultiTradeCardSvg(model, "Dynasty Overlords", assets, { fetchImage });
    expect(svg).toContain("data:image/png;base64");
    const out = process.env.MULTI_CARD_SAMPLE_DIR;
    if (out) writeFileSync(join(out, "multi-3-avatars.svg"), svg);
  }, 60_000);
});
