// @vitest-environment node
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { buildReviewShareModel, splitReviewGrade, type ReviewShareModel } from "@/lib/simReview";

import { renderSeasonReviewCardSvg, sniffImageType, type ShareStaticAssets } from "./clientRender";

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

const player = (id: string, name: string, pos: string, team: string, headshot_id: string | null = id) => ({ id, name, pos, team, headshot_id });
const card = (label: string, glyph: "waiver" | "draft" | "boom", tone: "success" | "danger", delta: string, p: ReturnType<typeof player>) => ({
  label, headline: p.name, glyph, tone, delta: { text: delta, tone }, players: [p], chip: null, detail: undefined,
});

const sections = [
  {
    id: "stats", kind: "stats" as const, glyph: "stats" as const, title: "Your season by the numbers",
    items: [
      { label: "Points per game", value: "105.8", tone: "muted" as const },
      { label: "Best week", value: "173.1", tone: "muted" as const },
      { label: "Worst week", value: "80.9", tone: "muted" as const },
      { label: "Longest win streak", value: "4", tone: "muted" as const },
    ],
  },
  {
    id: "moves", kind: "cards" as const, glyph: "waiver" as const, title: "Moves",
    cards: [
      card("Best waiver pickup", "waiver", "success", "+206.4 pts", player("11604", "Germie Bernard", "WR", "PIT")),
      card("Best draft pick", "draft", "success", "+45 vs ADP", player("12527", "Ka'imi Fairbairn", "K", "HOU")),
      card("Worst draft pick", "draft", "danger", "-7 vs ADP", player("p0099", "Tyler Allgeier With A Very Long Name", "RB", "ATL", null)),
      card("Biggest boom", "boom", "success", "+51.5 pts", player("7564", "Ja'Marr Chase", "WR", "CIN")),
    ],
  },
];

// A 1x1 PNG, enough to prove the photo path embeds an image.
const TINY_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

function model(over: Partial<Parameters<typeof buildReviewShareModel>[0]> = {}): ReviewShareModel {
  return buildReviewShareModel({
    letter: "A-",
    gradeTone: "success",
    teamName: "Gridiron Gang",
    playoffResult: "champion",
    isChampion: true,
    record: "7-6-1",
    summary: { record: "7-6-1", finish: 6, points_rank: 2, lineup_efficiency: 0.9, draft_grade: "A" },
    sections: sections as never,
    ...over,
  });
}

async function draw(m: ReviewShareModel, name: string, opts: { size?: "feed" | "story"; photos?: boolean } = {}) {
  const svg = await renderSeasonReviewCardSvg(m, assets, { size: opts.size, fetchImage: process.env.SEASON_CARD_LIVE_IMAGES && opts.photos !== false ? undefined : async () => (opts.photos === false ? null : TINY_PNG) });
  const out = process.env.SEASON_CARD_SAMPLE_DIR;
  if (out) {
    mkdirSync(out, { recursive: true });
    writeFileSync(join(out, `${name}.svg`), svg);
  }
  return svg;
}

describe("season review copy", () => {
  it("titles the outcome and keeps the record out of the headline", () => {
    const champ = model();
    expect(champ.headline).toBe("League Champion");
    expect(champ.subline).toBe("7-6-1 · Finished 6th · 2nd in points");
    expect(champ.tags).toEqual(["90% lineup efficiency", "Draft grade A"]);
    expect(model({ playoffResult: "runner_up", isChampion: false, championName: "Rival" }).headline).toBe("Runner-up");
    expect(model({ playoffResult: "lost_round_1", isChampion: false }).headline).toBe("Made the playoffs");
    expect(model({ playoffResult: "missed", isChampion: false, championName: "Rival" }).tags).toContain("Rival won the title");
    expect(model({ playoffResult: "missed", isChampion: false }).headline).toBe("Missed the playoffs");
  });

  it("splits every grade into a letter and a modifier", () => {
    for (const g of ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]) {
      expect(splitReviewGrade(g)).toEqual({ base: g[0], modifier: g.length > 1 ? g[1] : "" });
    }
    expect(splitReviewGrade("A−")).toEqual({ base: "A", modifier: "-" });
    expect(splitReviewGrade("")).toEqual({ base: "-", modifier: "" });
  });

  it("detects image types by signature", () => {
    expect(sniffImageType(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0, 0, 0, 0, 0]))).toBe("image/png");
  });
});

describe("season review card", () => {
  it("draws the champion feed card with embedded photos, crest, QR and URL", async () => {
    const svg = await draw(model(), "champion");
    expect(svg).toContain('width="1080"');
    expect(svg).toContain('height="1350"');
    expect(svg).toContain("<image");
  }, 60_000);

  it("draws the 1080x1920 story variant", async () => {
    const svg = await draw(model(), "champion-story", { size: "story" });
    expect(svg).toContain('height="1920"');
  }, 60_000);

  it("falls back to initials when photos fail", async () => {
    const svg = await draw(model(), "champion-nophotos", { photos: false });
    expect(svg.startsWith("<svg")).toBe(true);
  }, 60_000);

  it("draws the other outcomes", async () => {
    await draw(model({ letter: "B", gradeTone: "accent", playoffResult: "runner_up", isChampion: false, championName: "Rival Squad" }), "runner-up");
    await draw(model({ letter: "D+", gradeTone: "warning", playoffResult: "missed", isChampion: false, summary: { record: "4-10", finish: 11, points_rank: 9 }, record: "4-10", championName: "Rival Squad" }), "missed");
  }, 60_000);

  for (const letter of ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F"]) {
    it(`draws grade ${letter}`, async () => {
      const svg = await draw(model({ letter }), `grade-${letter.replace("+", "plus").replace("-", "minus")}`);
      expect(svg.startsWith("<svg")).toBe(true);
    }, 60_000);
  }
});
