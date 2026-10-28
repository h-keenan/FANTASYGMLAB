import { SEO_REVALIDATE_SECONDS } from "./site";

/**
 * Server-side client for GET /v1/public/dynasty-values: the anonymous,
 * league-agnostic value board (default 12-team PPR dynasty, 1QB or Superflex).
 * Never carries league, roster or account data.
 */
export type ValueFormat = "1qb" | "superflex";

export interface PublicPlayer {
  player_id: string;
  name: string;
  position: string;
  team: string | null;
  age: number | null;
  years_exp: number | null;
  status: string | null;
  injury_status: string | null;
  /** Rankings value (no age curve). */
  score: number;
  /** What a trade is priced with: `score` with the same neutral-posture age curve the
   * in-app Analyzer applies (modules/public_dynasty_values.py). Absent on older API builds. */
  trade_score?: number;
  overall_rank: number;
  position_rank: number;
  tier: string | null;
  overall_rating: number | null;
  trend: string | null;
}

export interface PublicBoard {
  format: ValueFormat;
  /** True when the board was valued with the tight-end premium setting. */
  tep: boolean;
  scoring: string;
  teams: number;
  generated_at: string;
  source_updated_at: string;
  players: PublicPlayer[];
}

/** Top-N overall players that get their own page. */
export const PLAYER_PAGE_LIMIT = 300;

function isPlayer(value: unknown): value is PublicPlayer {
  if (!value || typeof value !== "object") return false;
  const p = value as Record<string, unknown>;
  return (
    typeof p.player_id === "string" &&
    typeof p.name === "string" &&
    typeof p.position === "string" &&
    typeof p.score === "number" &&
    typeof p.overall_rank === "number" &&
    typeof p.position_rank === "number"
  );
}

export function parseBoard(value: unknown): PublicBoard | null {
  if (!value || typeof value !== "object") return null;
  const b = value as Record<string, unknown>;
  if (!Array.isArray(b.players) || typeof b.source_updated_at !== "string") return null;
  const players = b.players.filter(isPlayer);
  if (players.length === 0) return null;
  return {
    format: b.format === "superflex" ? "superflex" : "1qb",
    tep: b.tep === true,
    scoring: typeof b.scoring === "string" ? b.scoring : "PPR",
    teams: typeof b.teams === "number" ? b.teams : 12,
    generated_at: typeof b.generated_at === "string" ? b.generated_at : b.source_updated_at,
    source_updated_at: b.source_updated_at,
    players,
  };
}

function apiBases(): string[] {
  // Server-side only. Prefer the Docker-network address (the public URL
  // can hang/block server fetches); the default keeps SEO pages working
  // even when the container was started without API_INTERNAL_URL.
  const bases = [
    process.env.API_INTERNAL_URL || "http://mobile-api:8080",
    process.env.NEXT_PUBLIC_API_BASE_URL || "",
  ];
  return bases.filter((b, i) => /^https?:\/\//.test(b) && bases.indexOf(b) === i);
}

/**
 * Throws on any transport/server failure so ISR keeps serving the previous
 * good page instead of caching an empty one. Returns the parsed board.
 */
export async function fetchBoard(format: ValueFormat, tep = false): Promise<PublicBoard> {
  let lastError: unknown = new Error("no API base URL configured");
  for (const base of apiBases()) {
    try {
      const response = await fetch(`${base}/v1/public/dynasty-values?format=${format}${tep ? "&tep=true" : ""}`, {
        next: { revalidate: SEO_REVALIDATE_SECONDS },
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok) throw new Error(`public dynasty values unavailable (${response.status})`);
      const board = parseBoard(await response.json());
      if (!board) throw new Error("public dynasty values payload was empty or malformed");
      return board;
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

/** Players at one position, best first. */
export function playersAt(board: PublicBoard, positionUpper: string): PublicPlayer[] {
  return board.players.filter((p) => p.position === positionUpper).sort((a, b) => a.position_rank - b.position_rank);
}

/** "2026-10-25" style date for the visible "last updated" line. */
export function formatUpdated(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso.slice(0, 10);
  return date.toISOString().slice(0, 10);
}
