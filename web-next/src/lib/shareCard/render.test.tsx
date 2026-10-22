// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RankedPlayer, TradeIdea } from "@/lib/api";

import { clearShareCachesForTests, isAllowedImageUrl, renderPlayerCardPng, renderTradeCardPng, sniffImageType } from "./server";
import { fixtureIdea as idea, fixturePlayer as player, pngSize } from "./testFixtures";
import { maxRowsPerSide, rowSizeFor } from "./tradeCard";

describe("share card rendering", () => {
  beforeEach(() => {
    clearShareCachesForTests();
    // Hermetic: every remote image "has no photo", exercising the fallback.
    vi.stubGlobal("fetch", vi.fn(async () => new Response("", { status: 404 })));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the trade card as a 1080x1350 PNG", async () => {
    expect(pngSize(await renderTradeCardPng(idea, "Dynasty"))).toEqual({ width: 1080, height: 1350, isPng: true });
  }, 60_000);

  it("renders a trade with many assets without throwing", async () => {
    const many = { ...idea, package: { ...idea.package, send: Array(6).fill(idea.package.send[0]) } };
    expect(pngSize(await renderTradeCardPng(many, "Non-Dynasty")).height).toBe(1350);
  }, 60_000);

  it("renders the player card as a 1080x1350 PNG, with or without a rating", async () => {
    expect(pngSize(await renderPlayerCardPng(player, "Dynasty"))).toEqual({ width: 1080, height: 1350, isPng: true });
    const bare = { ...player, overall_rating: null, overall_rank: null, position_rank: null, score: null, tier: null };
    expect(pngSize(await renderPlayerCardPng(bare, "Dynasty")).isPng).toBe(true);
  }, 60_000);
});

describe("share card helpers", () => {
  it("only fetches images from Sleeper's CDN", () => {
    expect(isAllowedImageUrl("https://sleepercdn.com/content/nfl/players/thumb/1.jpg")).toBe(true);
    expect(isAllowedImageUrl("https://evil.example.com/a.png")).toBe(false);
    expect(isAllowedImageUrl("http://sleepercdn.com/a.png")).toBe(false);
    expect(isAllowedImageUrl("https://sleepercdn.com.evil.com/a.png")).toBe(false);
  });

  it("types images by their bytes, not Sleeper's Content-Type header", () => {
    expect(sniffImageType(new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 0]))).toBe("image/jpeg");
    expect(sniffImageType(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0]))).toBe("image/png");
    expect(sniffImageType(new Uint8Array([0x52, 0x49, 0x46, 0x46, 0]))).toBeNull();
  });

  it("caps rows so big trades stay legible", () => {
    expect(maxRowsPerSide(1, 2)).toBe(4);
    expect(maxRowsPerSide(4, 4)).toBe(3);
    expect(rowSizeFor(2)).toBeGreaterThan(rowSizeFor(6));
    expect(rowSizeFor(6)).toBeGreaterThanOrEqual(60);
  });
});

/** Opt-in preview: SHARE_CARD_PREVIEW_DIR + SHARE_CARD_PREVIEW_IDEAS (a
 * real GET .../trade-hub response) and/or SHARE_CARD_PREVIEW_PLAYERS (real
 * RankedPlayer rows) write real PNGs, fetching real Sleeper photos. */
const previewDir = process.env.SHARE_CARD_PREVIEW_DIR;
describe.skipIf(!previewDir)("share card preview output", () => {
  it("writes preview PNGs", async () => {
    mkdirSync(previewDir as string, { recursive: true });
    const ideasPath = process.env.SHARE_CARD_PREVIEW_IDEAS;
    if (ideasPath) {
      const { ideas } = JSON.parse(readFileSync(ideasPath, "utf8")) as { ideas: TradeIdea[] };
      const wanted = process.env.SHARE_CARD_PREVIEW_REC_IDS?.split(",") ?? [];
      for (const real of ideas) {
        if (!wanted.includes(real.recommendation_id ?? "")) continue;
        writeFileSync(join(previewDir as string, `after-trade-${real.recommendation_id}.png`), Buffer.from(await renderTradeCardPng(real, "Dynasty")));
      }
    }
    const playersPath = process.env.SHARE_CARD_PREVIEW_PLAYERS;
    if (playersPath) {
      const players = JSON.parse(readFileSync(playersPath, "utf8")) as RankedPlayer[];
      for (const real of players) {
        writeFileSync(join(previewDir as string, `after-player-${real.player_id}.png`), Buffer.from(await renderPlayerCardPng(real, "Dynasty")));
      }
    }
  }, 180_000);
});
