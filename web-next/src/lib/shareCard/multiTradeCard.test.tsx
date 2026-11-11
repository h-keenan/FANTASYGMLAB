// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { buildShareModel, type MultiAsset, type MultiTeamResult } from "@/lib/multiTeamTrade";

import { renderMultiTradeCardSvg, type ShareStaticAssets } from "./clientRender";

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
  for (const n of [3, 4, 6]) {
    it(`draws a ${n}-team card as a persuasion pitch with no scoreboard words`, async () => {
      const model = buildShareModel({ teams: teams(n) });
      const svg = await renderMultiTradeCardSvg(model, "Dynasty Overlords", assets);
      expect(svg.startsWith("<svg")).toBe(true);
      expect(svg).toContain('width="1080"');
      expect(svg).toContain('height="1350"');
      const out = process.env.MULTI_CARD_SAMPLE_DIR;
      if (out) {
        mkdirSync(out, { recursive: true });
        writeFileSync(join(out, `multi-${n}.svg`), svg);
      }
    }, 60_000);
  }

  it("flows for 3 and lists for 4+, with every team's real value change and a get-back line", () => {
    expect(buildShareModel({ teams: teams(3) }).layout).toBe("flow");
    expect(buildShareModel({ teams: teams(4) }).layout).toBe("list");
    const model = buildShareModel({ teams: teams(3) });
    expect(model.teams.map((t) => t.valueChangeText)).toEqual(["+260", "-420", "+260"]);
    expect(model.teams[1].getsBack).toContain("Gets back Receiver 1");
  });
});
