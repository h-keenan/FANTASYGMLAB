/**
 * Browser-side Trade Analyzer share card. The analysis is already on the
 * page, so the card is a template filled with it: the same TradeShareCard
 * component the server cards use is drawn to SVG by Satori (lazy-imported on
 * Share only), then rasterized to a PNG on a canvas. No API call, no quota.
 *
 * renderAnalyzerCardSvg is environment-neutral (the sample-PNG script and
 * tests run it in node); only svgToPngBlob needs a DOM.
 */

import type { TradeAsset, TradeVerdict } from "@/lib/api";
import { isPrivacyMode } from "@/lib/privacy";
import { valuationLensLabel } from "@/lib/valuationLens";

import { buildAnalyzerIdea, buildPartnerPitch } from "./analyzerShare";
import { STORY_SIZE, SHARE_FONT_FAMILY, ShareBackdrop, type ShareBrandAssets } from "./frame";
import { TradeShareCard } from "./tradeCard";

export interface AnalyzerCardParams {
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
  verdict: TradeVerdict;
  lens: string;
  partnerName: string;
  partnerAvatarUrl?: string | null;
  myTeamName?: string | null;
  myAvatarUrl?: string | null;
}

/** Bytes for the static brand assets, loaded by the caller (fetch in the
 * browser, readFile in node). */
export interface ShareStaticAssets {
  yoga: ArrayBuffer;
  lockup: string;
  qr: string;
  fonts: Array<{ name: string; data: ArrayBuffer; weight: 500 | 700 | 800 | 900; style: "normal" }>;
}

const FONT_WEIGHTS = [500, 700, 800, 900] as const;
const ASSET_BASE = "/share-card";
const IMAGE_TIMEOUT_MS = 2500;

function toDataUri(bytes: Uint8Array, mime: string): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return `data:${mime};base64,${btoa(binary)}`;
}

/** Satori rejects a mislabelled image, and Sleeper's Content-Type does not
 * match its bytes, so the type comes from the file signature. */
export function sniffImageType(bytes: Uint8Array): "image/png" | "image/jpeg" | null {
  if (bytes.length > 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return "image/png";
  if (bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "image/jpeg";
  return null;
}

export function isAllowedImageUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && (parsed.hostname === "sleepercdn.com" || parsed.hostname.endsWith(".sleepercdn.com"));
  } catch {
    return false;
  }
}

/** Remote image -> data URI, or null (blocked / offline / timeout). Never
 * throws: a missing photo falls back to the ringed disc. */
async function fetchImageDataUri(url: string | null | undefined): Promise<string | null> {
  if (!url || !isAllowedImageUrl(url)) return null;
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(IMAGE_TIMEOUT_MS) });
    if (!response.ok) return null;
    const bytes = new Uint8Array(await response.arrayBuffer());
    const type = sniffImageType(bytes);
    return type ? toDataUri(bytes, type) : null;
  } catch {
    return null;
  }
}

let staticAssets: Promise<ShareStaticAssets> | null = null;

/** Brand lockup, QR, fonts and the layout engine's wasm, fetched once. */
export function loadBrowserAssets(): Promise<ShareStaticAssets> {
  if (!staticAssets) {
    const get = async (name: string) => {
      const response = await fetch(`${ASSET_BASE}/${name}`);
      if (!response.ok) throw new Error(`Missing share asset ${name}`);
      return response.arrayBuffer();
    };
    staticAssets = Promise.all([
      get("yoga.wasm"),
      get("lockup-white.png"),
      get("qr-site.png"),
      ...FONT_WEIGHTS.map((w) => get(`inter-latin-${w}-normal.woff`)),
    ])
      .then(([yoga, lockup, qr, ...fonts]) => ({
        yoga,
        lockup: toDataUri(new Uint8Array(lockup), "image/png"),
        qr: toDataUri(new Uint8Array(qr), "image/png"),
        fonts: fonts.map((data, index) => ({ name: SHARE_FONT_FAMILY, data, weight: FONT_WEIGHTS[index], style: "normal" as const })),
      }))
      .catch((error) => {
        staticAssets = null;
        throw error;
      });
  }
  return staticAssets;
}

let satoriReady: Promise<typeof import("satori/standalone")["default"]> | null = null;

function loadSatori(yoga: ArrayBuffer) {
  if (!satoriReady) {
    satoriReady = import("satori/standalone")
      .then(async (mod) => {
        await mod.init(yoga);
        return mod.default;
      })
      .catch((error) => {
        satoriReady = null;
        throw error;
      });
  }
  return satoriReady;
}

function svgDataUri(svg: string): string {
  return toDataUri(new TextEncoder().encode(svg), "image/svg+xml");
}

/** The story-size (1080x1350) card as SVG text, from the on-screen data. */
export async function renderAnalyzerCardSvg(
  params: AnalyzerCardParams,
  assets: ShareStaticAssets,
  options: { fetchImage?: (url: string | null | undefined) => Promise<string | null> } = {},
): Promise<string> {
  const satori = await loadSatori(assets.yoga);
  const { width, height } = STORY_SIZE;
  const idea = buildAnalyzerIdea({
    sendAssets: params.sendAssets,
    receiveAssets: params.receiveAssets,
    verdict: params.verdict,
    partnerName: params.partnerName,
    partnerAvatarUrl: params.partnerAvatarUrl,
  });
  // Privacy mode masks names on screen, so real photos/avatars stay off the card too.
  const fetchImage = options.fetchImage ?? (isPrivacyMode() ? async () => null : fetchImageDataUri);
  const playerIds = [...params.sendAssets, ...params.receiveAssets]
    .filter((asset) => asset.asset_type !== "pick" && asset.player_id)
    .map((asset) => asset.player_id as string);
  const [partnerAvatar, myAvatar, ...shots] = await Promise.all([
    fetchImage(idea.partner_team_avatar_url),
    fetchImage(params.myAvatarUrl),
    ...playerIds.map((id) => fetchImage(`https://sleepercdn.com/content/nfl/players/thumb/${encodeURIComponent(id)}.jpg`)),
  ]);
  const headshots = Object.fromEntries(playerIds.map((id, index) => [id, shots[index]]));

  const backdrop = svgDataUri(await satori(<ShareBackdrop width={width} height={height} />, { width, height, fonts: assets.fonts }));
  const brand: ShareBrandAssets = { lockup: assets.lockup, qr: assets.qr, backdrop };
  return satori(
    <TradeShareCard
      idea={idea}
      brand={brand}
      images={{ headshots, partnerAvatar, myAvatar }}
      lens={valuationLensLabel(params.lens)}
      myTeamName={params.myTeamName}
      pitch={buildPartnerPitch(idea.package.send, idea.package.receive, params.partnerName)}
      width={width}
      height={height}
    />,
    { width, height, fonts: assets.fonts },
  );
}

/** Rasterize the SVG on a canvas (browser only). */
export async function svgToPngBlob(svg: string, width: number, height: number): Promise<Blob> {
  const image = new Image();
  image.decoding = "async";
  const loaded = new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("Could not draw the share card."));
  });
  image.src = svgDataUri(svg);
  await loaded;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Could not draw the share card.");
  context.drawImage(image, 0, 0, width, height);
  return new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("Could not draw the share card."))), "image/png");
  });
}

/** The whole browser flow: assets -> Satori SVG -> PNG Blob. */
export async function renderAnalyzerCardBlob(params: AnalyzerCardParams): Promise<Blob> {
  const assets = await loadBrowserAssets();
  const svg = await renderAnalyzerCardSvg(params, assets);
  return svgToPngBlob(svg, STORY_SIZE.width, STORY_SIZE.height);
}
