/**
 * Privacy mode: display-only masking of personal identifiers so the owner can
 * take marketing screenshots. Copied from web-next/src/lib/privacy.ts (keep the key lists in lockstep).
 *
 * Everything funnels through ONE response transformer (`maskPayload`) that the
 * API clients run on every parsed JSON response, plus `unmaskPayload` that
 * maps masked labels back to the real values on every outgoing write body, so
 * a masked label can never be saved to the server. Real NFL player names and
 * headshots are untouched. See docs/privacy-mode.md for the field list.
 */

const COUNTER_STORAGE_KEY = "fd_privacy_labels";

export type MaskKind = "person" | "handle" | "team" | "league";

/** Response keys whose string value is a person / team / league identifier. */
const KEY_KIND: Record<string, MaskKind> = {
  owner_name: "person",
  display_name: "person",
  current_manager_name: "person",
  manager: "person",
  username: "handle",
  sleeper_username: "handle",
  owner_handle: "handle",
  owner_username: "handle",
  team_name: "team",
  owner_team_name: "team",
  current_team_name: "team",
  original_team_name: "team",
  partner_team_name: "team",
  primary_team: "team",
  secondary_team: "team",
  fantasy_team: "team",
  original_team: "team",
  source_team_name: "team",
  league_name: "league",
  last_league_name: "league",
};
/** Keys holding string arrays of identifiers. */
const ARRAY_KEY_KIND: Record<string, MaskKind> = {
  partners: "team",
  league_names: "league",
};
const AVATAR_KEYS = new Set(["avatar_url", "avatar_id", "team_avatar_url", "partner_team_avatar_url", "avatar", "picture"]);
const EMAIL_KEYS = new Set(["email", "user_email"]);
export const MASKED_EMAIL = "hidden@example.com";
/** String values under these keys are never scanned for embedded names. */
const FREE_TEXT_SKIP = /(^|_)(id|ids|url|name|player_name|position|team|opponent|lens|status|type|kind|key)$/i;

const GENERATED = [/^Manager \d+$/, /^manager_\d+$/, /^Team [A-Z]+$/, /^Sample (Dynasty )?League( \d+)?$/];

export function isGeneratedLabel(value: string): boolean {
  return GENERATED.some((re) => re.test(value));
}

function letters(n: number): string {
  let out = "";
  let x = n;
  while (x > 0) {
    x -= 1;
    out = String.fromCharCode(65 + (x % 26)) + out;
    x = Math.floor(x / 26);
  }
  return out;
}

function labelFor(kind: MaskKind, n: number): string {
  switch (kind) {
    case "person":
      return `Manager ${n}`;
    case "handle":
      return `manager_${n}`;
    case "team":
      return `Team ${letters(n)}`;
    case "league":
      return n === 1 ? "Sample League" : n === 2 ? "Sample Dynasty League" : `Sample League ${n}`;
  }
}

function hash(value: string): string {
  // FNV-1a; only used to avoid persisting real names in sessionStorage.
  let h = 0x811c9dc5;
  for (let i = 0; i < value.length; i++) {
    h ^= value.charCodeAt(i);
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h.toString(36);
}

type CounterTable = Record<string, Record<string, number>>;

export interface PrivacyStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export interface Masker {
  /** Stable generic label for a real identifier (idempotent). */
  label(kind: MaskKind, real: string): string;
  /** Mask a parsed API response (returns a new structure, input untouched). */
  mask<T>(value: T): T;
  /** Replace masked labels in an outgoing body with their real values. */
  unmask<T>(value: T): T;
}

export function createMasker(storage?: PrivacyStorage | null): Masker {
  let counters: CounterTable = {};
  try {
    const raw = storage?.getItem(COUNTER_STORAGE_KEY);
    if (raw) counters = JSON.parse(raw) as CounterTable;
  } catch {
    counters = {};
  }
  const forward = new Map<string, string>(); // `${kind}:${real}` -> label
  const reverse = new Map<string, string>(); // label -> real
  const known = new Map<string, string>(); // real -> label (for free-text scrubbing)
  let textPattern: RegExp | null = null;

  const persist = () => {
    try {
      storage?.setItem(COUNTER_STORAGE_KEY, JSON.stringify(counters));
    } catch {
      // storage is a convenience only
    }
  };

  function label(kind: MaskKind, real: string): string {
    if (isGeneratedLabel(real)) return real;
    const fk = `${kind}:${real}`;
    const cached = forward.get(fk);
    if (cached) return cached;
    const table = (counters[kind] ||= {});
    const h = hash(real);
    let n = table[h];
    if (!n) {
      n = Object.keys(table).length + 1;
      table[h] = n;
      persist();
    }
    const out = labelFor(kind, n);
    forward.set(fk, out);
    if (!reverse.has(out)) reverse.set(out, real);
    if (real.trim().length >= 3) {
      known.set(real.trim(), out);
      textPattern = null;
    }
    return out;
  }

  function scrub(text: string): string {
    if (known.size === 0 || text.length < 3) return text;
    if (!textPattern) {
      const names = [...known.keys()].sort((a, b) => b.length - a.length).map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
      textPattern = new RegExp(`(?<![\\w])(?:${names.join("|")})(?![\\w])`, "g");
    }
    return text.replace(textPattern, (match, offset: number, whole: string) => {
      // A single-word name touching another capitalized word is probably an
      // NFL player ("Chris Olave"), not the manager called "Chris".
      if (!/\s/.test(match)) {
        const before = /([A-Z][a-z]+) $/.exec(whole.slice(0, offset));
        const after = /^ ([A-Z][a-z]+)/.exec(whole.slice(offset + match.length));
        if (before || after) return match;
      }
      return known.get(match) ?? match;
    });
  }

  function walk(node: unknown, parentKey: string | null, depth: number): unknown {
    if (depth > 40 || node === null || typeof node !== "object") {
      if (typeof node === "string" && parentKey !== null && !FREE_TEXT_SKIP.test(parentKey)) return scrub(node);
      return node;
    }
    if (Array.isArray(node)) {
      const kind = parentKey ? ARRAY_KEY_KIND[parentKey] : undefined;
      return node.map((item) =>
        kind && typeof item === "string" && item ? label(kind, item) : walk(item, parentKey, depth + 1),
      );
    }
    const obj = node as Record<string, unknown>;
    const isPlayerish = "player_id" in obj || "position" in obj;
    const out: Record<string, unknown> = {};
    // Structural pass first so every name in this object is registered before
    // sibling free-text fields are scrubbed.
    const deferred: string[] = [];
    for (const [key, value] of Object.entries(obj)) {
      if (AVATAR_KEYS.has(key)) {
        out[key] = value === null || value === undefined ? value : null;
      } else if (EMAIL_KEYS.has(key) && typeof value === "string" && value) {
        out[key] = MASKED_EMAIL;
      } else if (typeof value === "string" && value && key in KEY_KIND) {
        out[key] = label(KEY_KIND[key], value);
      } else if (key === "name" && typeof value === "string" && value && !isPlayerish) {
        if ("league_id" in obj) out[key] = label("league", value);
        else if ("roster_id" in obj || "owner_name" in obj || "owner_handle" in obj) out[key] = label("team", value);
        else out[key] = value;
      } else {
        deferred.push(key);
      }
    }
    for (const key of deferred) out[key] = walk(obj[key], key, depth + 1);
    return out;
  }

  function unwalk(node: unknown, depth: number): unknown {
    if (typeof node === "string") return reverse.get(node) ?? node;
    if (depth > 40 || node === null || typeof node !== "object") return node;
    if (Array.isArray(node)) return node.map((item) => unwalk(item, depth + 1));
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(node as Record<string, unknown>)) out[key] = unwalk(value, depth + 1);
    return out;
  }

  return {
    label,
    mask: <T,>(value: T) => walk(value, null, 0) as T,
    unmask: <T,>(value: T) => unwalk(value, 0) as T,
  };
}

