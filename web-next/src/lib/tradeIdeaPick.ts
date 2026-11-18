/**
 * What a pick row in a trade idea says beyond its label: the projected draft slot (from the ORIGINAL owner's
 * projected finish, the same model that values the pick) and whose pick it is. Pure, so it is shared byte-for-byte
 * between web and mobile (scripts/check_lib_twins.mjs) and runs under the node test runner.
 */

export interface IdeaPickFields {
  projected_slot_label?: string | null;
  projected_range?: string | null;
  original_team_name?: string | null;
  owner_team_name?: string | null;
}

/** "proj. 1.04 · Team's pick" (the owner's own pick drops the second part); null when nothing is known. */
export function pickProjectionLine(asset: IdeaPickFields): string | null {
  const slot = asset.projected_slot_label ? `proj. ${asset.projected_slot_label}` : asset.projected_range ? `proj. ${asset.projected_range}` : null;
  const original = asset.original_team_name?.trim();
  const owner = asset.owner_team_name?.trim();
  const whose = original && original !== owner ? `${original}${original.endsWith('s') ? "'" : "'s"} pick` : null;
  const line = [slot, whose].filter(Boolean).join(' · ');
  return line || null;
}

/** The partner-fit line shown on an idea ("Fills their TE hole · they're contending"), or null when the server sent none. */
export function partnerFitLine(reason: string | null | undefined): string | null {
  const text = (reason ?? '').trim();
  return text ? text : null;
}

function ordinalRound(round: number): string {
  const teen = round % 100 >= 11 && round % 100 <= 13;
  const suffix = teen ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[round % 10] ?? "th";
  return `${round}${suffix}`;
}

/** The one short pick label every trade surface shows: "2027 2nd" (never "2027 Round 2", which wraps in a half-width card).
 * Reads the season and round from the server label ("2027 Round 2", "2027 R2", "2027 2nd round") or the explicit fields;
 * anything it cannot parse (a "(Pick 1.04)" label) is returned as it came. */
export function pickCompactLabel(label: string | null | undefined, season?: number | string | null, round?: number | string | null): string {
  const text = (label ?? "").trim();
  const match = text.match(/^(\d{4})\s+(?:round\s+|r)(\d{1,2})\b/i) ?? text.match(/^(\d{4})\s+(\d{1,2})(?:st|nd|rd|th)\b/i);
  if (match) return `${match[1]} ${ordinalRound(Number(match[2]))}`;
  const year = season != null && String(season).trim() !== "" ? String(season) : null;
  const rnd = round != null && String(round).trim() !== "" ? Number(round) : null;
  if (!text && year && rnd) return `${year} ${ordinalRound(rnd)}`;
  return text || "Draft pick";
}
