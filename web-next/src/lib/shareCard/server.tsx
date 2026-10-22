/**
 * Server-side plumbing for the share-card routes: brand assets and fonts
 * (read once per process), player/team images (fetched once, cached), the
 * rendered-PNG cache, and the upstream API call that supplies the real data.
 *
 * Kept out of the client bundle: only the app/share-card route handlers
 * import this file.
 */

import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { ImageResponse } from "next/og";
import type { ReactElement } from "react";

import type { RankedPlayer, TradeIdea } from "@/lib/api";
import { valuationLensLabel } from "@/lib/valuationLens";

import { OG_SIZE, SHARE_FONT_FAMILY, STORY_SIZE, ShareBackdrop, type ShareBrandAssets } from "./frame";
import { PlayerShareCard } from "./playerCard";
import { TradeShareCard } from "./tradeCard";

export type ShareFormat = "story" | "og";

export function shareSize(format: ShareFormat) {
  return format === "og" ? OG_SIZE : STORY_SIZE;
}

// ---------------------------------------------------------------- assets

const ASSET_DIR = join(process.cwd(), "public", "share-card");
const FONT_WEIGHTS = [500, 700, 800, 900] as const;

type FontOption = { name: string; data: ArrayBuffer; weight: 500 | 700 | 800 | 900; style: "normal" };

let staticAssets: Promise<{ brand: ShareBrandAssets; fonts: FontOption[] }> | null = null;

function toArrayBuffer(buffer: Buffer): ArrayBuffer {
  return buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength) as ArrayBuffer;
}

export function loadStaticAssets() {
  if (!staticAssets) {
    staticAssets = (async () => {
      const [lockup, qr, ...fonts] = await Promise.all([
        readFile(join(ASSET_DIR, "lockup-white.png")),
        readFile(join(ASSET_DIR, "qr-site.png")),
        ...FONT_WEIGHTS.map((weight) => readFile(join(ASSET_DIR, `inter-latin-${weight}-normal.woff`))),
      ]);
      return {
        brand: {
          lockup: `data:image/png;base64,${lockup.toString("base64")}`,
          qr: `data:image/png;base64,${qr.toString("base64")}`,
        },
        fonts: fonts.map((data, index) => ({
          name: SHARE_FONT_FAMILY,
          data: toArrayBuffer(data),
          weight: FONT_WEIGHTS[index],
          style: "normal" as const,
        })),
      };
    })().catch((error) => {
      staticAssets = null;
      throw error;
    });
  }
  return staticAssets;
}

// ---------------------------------------------------------------- remote images

const SLEEPER_HEADSHOT_BASE = "https://sleepercdn.com/content/nfl/players/thumb";
const IMAGE_TIMEOUT_MS = 2500;
const IMAGE_TTL_MS = 6 * 60 * 60 * 1000;
const IMAGE_CACHE_MAX = 400;
const imageCache = new Map<string, { at: number; value: string | null }>();

/** Only Sleeper's own CDN is fetched — the avatar URL comes from the API
 * response, and this keeps the route from fetching arbitrary hosts. */
export function isAllowedImageUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && (parsed.hostname === "sleepercdn.com" || parsed.hostname.endsWith(".sleepercdn.com"));
  } catch {
    return false;
  }
}

export function sniffImageType(bytes: Uint8Array): "image/png" | "image/jpeg" | null {
  if (bytes.length > 8 && bytes[0] === 0x89 && bytes[1] === 0x50 && bytes[2] === 0x4e && bytes[3] === 0x47) return "image/png";
  if (bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) return "image/jpeg";
  return null;
}

/** Remote image -> data URI, or null (no photo / timeout / not allowed).
 * Never throws: a missing photo falls back to the ringed disc, same as the
 * in-app PlayerAvatar. */
export async function fetchImageDataUri(url: string | null | undefined): Promise<string | null> {
  if (!url || !isAllowedImageUrl(url)) return null;
  const cached = imageCache.get(url);
  if (cached && Date.now() - cached.at < IMAGE_TTL_MS) return cached.value;
  let value: string | null = null;
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(IMAGE_TIMEOUT_MS) });
    if (response.ok) {
      const bytes = Buffer.from(await response.arrayBuffer());
      // Sleeper's Content-Type header doesn't match the bytes (avatars
      // labelled image/png are JPEGs and vice versa), and Satori rejects a
      // mislabelled image, so the type comes from the file signature.
      const type = sniffImageType(bytes);
      if (type) value = `data:${type};base64,${bytes.toString("base64")}`;
    }
  } catch {
    value = null;
  }
  if (imageCache.size >= IMAGE_CACHE_MAX) imageCache.delete(imageCache.keys().next().value as string);
  imageCache.set(url, { at: Date.now(), value });
  return value;
}

export function headshotUrl(playerId: string): string {
  return `${SLEEPER_HEADSHOT_BASE}/${encodeURIComponent(playerId)}.jpg`;
}

// ---------------------------------------------------------------- render cache

const RENDER_TTL_MS = 10 * 60 * 1000;
const RENDER_CACHE_MAX = 64;
const renderCache = new Map<string, { at: number; png: ArrayBuffer }>();

export function cacheKey(parts: unknown[]): string {
  return createHash("sha256").update(JSON.stringify(parts)).digest("hex");
}

export function getCachedPng(key: string): ArrayBuffer | null {
  const hit = renderCache.get(key);
  if (!hit) return null;
  if (Date.now() - hit.at > RENDER_TTL_MS) {
    renderCache.delete(key);
    return null;
  }
  return hit.png;
}

export function putCachedPng(key: string, png: ArrayBuffer) {
  if (renderCache.size >= RENDER_CACHE_MAX) renderCache.delete(renderCache.keys().next().value as string);
  renderCache.set(key, { at: Date.now(), png });
}

export function clearShareCachesForTests() {
  renderCache.clear();
  imageCache.clear();
}

export function pngResponse(png: ArrayBuffer, cacheState: "hit" | "miss"): Response {
  return new Response(png, {
    headers: {
      "Content-Type": "image/png",
      // Per-user data behind auth: never shared caches.
      "Cache-Control": "private, max-age=600",
      "X-Share-Card-Cache": cacheState,
    },
  });
}

export async function renderPng(element: ReactElement, format: ShareFormat): Promise<ArrayBuffer> {
  const { fonts } = await loadStaticAssets();
  const response = new ImageResponse(element, { ...shareSize(format), fonts });
  return response.arrayBuffer();
}

const backdrops = new Map<ShareFormat, Promise<string>>();

/** Brand assets plus this size's backdrop, which is drawn once per process
 * and then reused as a plain image (see ShareBackdrop). */
export async function brandFor(format: ShareFormat): Promise<ShareBrandAssets> {
  const { brand } = await loadStaticAssets();
  let backdrop = backdrops.get(format);
  if (!backdrop) {
    backdrop = renderPng(<ShareBackdrop {...shareSize(format)} />, format).then(
      (png) => `data:image/png;base64,${Buffer.from(png).toString("base64")}`,
    );
    backdrop.catch(() => backdrops.delete(format));
    backdrops.set(format, backdrop);
  }
  return { ...brand, backdrop: await backdrop };
}

// ---------------------------------------------------------------- card renderers

export async function renderTradeCardPng(idea: TradeIdea, lens: string): Promise<ArrayBuffer> {
  const brand = await brandFor("story");
  const playerIds = [...(idea.package.send ?? []), ...(idea.package.receive ?? [])]
    .filter((asset) => asset.asset_type !== "pick" && asset.player_id)
    .map((asset) => asset.player_id as string);
  const [partnerAvatar, ...shots] = await Promise.all([
    fetchImageDataUri(idea.partner_team_avatar_url),
    ...playerIds.map((id) => fetchImageDataUri(headshotUrl(id))),
  ]);
  const headshots = Object.fromEntries(playerIds.map((id, index) => [id, shots[index]]));
  return renderPng(
    <TradeShareCard idea={idea} brand={brand} images={{ headshots, partnerAvatar }} lens={valuationLensLabel(lens)} {...STORY_SIZE} />,
    "story",
  );
}

export async function renderPlayerCardPng(player: RankedPlayer, lens: string): Promise<ArrayBuffer> {
  const brand = await brandFor("story");
  const headshot = await fetchImageDataUri(headshotUrl(player.player_id));
  return renderPng(<PlayerShareCard player={player} brand={brand} headshot={headshot} lens={valuationLensLabel(lens)} {...STORY_SIZE} />, "story");
}

// ---------------------------------------------------------------- upstream API

export class UpstreamError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function apiBaseUrl(): string {
  // SHARE_CARD_API_BASE_URL lets a deployment point this server-side call
  // at an internal address; otherwise it's the same API the browser uses.
  return (process.env.SHARE_CARD_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
}

/** GET an API path as the signed-in caller (their own bearer token, passed
 * through unchanged), so the card can only ever show data that user's own
 * session can already see. */
export async function fetchUpstreamJson<T>(path: string, authorization: string): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}${path}`, {
      headers: { Authorization: authorization },
      signal: AbortSignal.timeout(30_000),
      cache: "no-store",
    });
  } catch {
    throw new UpstreamError(502, "Could not reach the API.");
  }
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {
      detail = "";
    }
    throw new UpstreamError(response.status, detail || `Upstream request failed (${response.status}).`);
  }
  return (await response.json()) as T;
}

const SAFE_ID = /^[A-Za-z0-9_.:-]{1,128}$/;
export function isSafeId(value: string | null): value is string {
  return Boolean(value && SAFE_ID.test(value));
}

export function jsonError(status: number, detail: string): Response {
  return Response.json({ detail }, { status, headers: { "Cache-Control": "no-store" } });
}
