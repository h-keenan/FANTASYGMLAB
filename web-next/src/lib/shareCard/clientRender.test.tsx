// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import type { TradeVerdict } from "@/lib/api";

import { renderAnalyzerCardSvg, sniffImageType, isAllowedImageUrl, type ShareStaticAssets } from "./clientRender";

const DIR = join(process.cwd(), "public", "share-card");
const buf = (name: string) => {
  const b = readFileSync(join(DIR, name));
  return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer;
};
const dataUri = (name: string) => `data:image/png;base64,${readFileSync(join(DIR, name)).toString("base64")}`;

// The node stand-in for loadBrowserAssets (which fetches these same files).
const assets: ShareStaticAssets = {
  yoga: buf("yoga.wasm"),
  lockup: dataUri("lockup-white.png"),
  qr: dataUri("qr-site.png"),
  fonts: ([500, 700, 800, 900] as const).map((weight) => ({ name: "Inter", data: buf(`inter-latin-${weight}-normal.woff`), weight, style: "normal" as const })),
};

const verdict = {
  band: "Fair",
  ui_verdict: "COUNTER",
  confidence: "Medium",
  rationale: "r",
  value_summary: "",
  roster_summary: "",
  strategy_summary: "",
  risk_summary: "",
  counter_guidance: "",
  fit_total: 0,
  value_delta: 1720,
  tone: "counter",
} as TradeVerdict;

const params = {
  verdict,
  lens: "Dynasty",
  partnerName: "Rival GM",
  myTeamName: "My Squad",
  sendAssets: [
    { asset_type: "player" as const, player_id: "4881", name: "Star Quarterback", position: "QB", team: "BUF", score: 5200, tier: "Elite", overall_rating: 88 },
    { asset_type: "pick" as const, label: "2028 Round 1", season: "2028", round: "1", score: 900 },
  ],
  receiveAssets: [
    { asset_type: "player" as const, player_id: "4034", name: "Backup Quarterback", position: "QB", team: "ARI", score: 3200, tier: "Starter", overall_rating: 71 },
    { asset_type: "player" as const, player_id: "6794", name: "Slot Receiver", position: "WR", team: "LV", score: 1180, tier: "Contributor", overall_rating: 64 },
  ],
};

describe("renderAnalyzerCardSvg (what the browser draws on Share)", () => {
  it("draws the 1080x1350 trade card as SVG from on-screen data, with no network", async () => {
    const out = process.env.ANALYZER_CARD_SAMPLE_DIR;
    // Sample runs use real Sleeper photos (CORS-open, as in the browser).
    const live = async (url: string | null | undefined) => {
      if (!url || !isAllowedImageUrl(url)) return null;
      const bytes = new Uint8Array(await (await fetch(url)).arrayBuffer());
      const type = sniffImageType(bytes);
      return type ? `data:${type};base64,${Buffer.from(bytes).toString("base64")}` : null;
    };
    const svg = await renderAnalyzerCardSvg(params, assets, { fetchImage: out ? live : async () => null });
    expect(svg.startsWith("<svg")).toBe(true);
    expect(svg).toContain('width="1080"');
    expect(svg).toContain('height="1350"');
    // Brand lockup + QR are embedded.
    expect(svg).toContain("data:image/png;base64");

    if (out) {
      mkdirSync(out, { recursive: true });
      writeFileSync(join(out, "analyzer-card-v3.svg"), svg);
    }
  }, 60_000);

  it("keeps remote images out of the card when they cannot be fetched", async () => {
    const calls: Array<string | null | undefined> = [];
    await renderAnalyzerCardSvg({ ...params, partnerAvatarUrl: "https://sleepercdn.com/avatars/x" }, assets, {
      fetchImage: async (url) => {
        calls.push(url);
        return null;
      },
    });
    expect(calls).toContain("https://sleepercdn.com/avatars/x");
    expect(calls).toContain("https://sleepercdn.com/content/nfl/players/thumb/4881.jpg");
  }, 60_000);
});

describe("image helpers", () => {
  it("sniffs the type from bytes, not headers", () => {
    expect(sniffImageType(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0, 0]))).toBe("image/png");
    expect(sniffImageType(new Uint8Array([0xff, 0xd8, 0xff, 0xe0]))).toBe("image/jpeg");
    expect(sniffImageType(new Uint8Array([1, 2, 3, 4]))).toBeNull();
  });

  it("only fetches Sleeper CDN images", () => {
    expect(isAllowedImageUrl("https://sleepercdn.com/avatars/a")).toBe(true);
    expect(isAllowedImageUrl("https://evil.example/a.png")).toBe(false);
    expect(isAllowedImageUrl("http://sleepercdn.com/a")).toBe(false);
  });
});
