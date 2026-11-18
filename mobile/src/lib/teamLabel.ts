/**
 * The one team label the pickers show: "Team name · Owner". When the two are the same words (a team nobody renamed shows
 * the username twice: "patrickshea · patrickshea") only one is kept; the compare ignores case and surrounding spaces.
 * Pure, shared byte-for-byte between web and mobile (scripts/check_lib_twins.mjs).
 */
export function teamPickerLabel(teamName: string | null | undefined, ownerName: string | null | undefined, fallback = ""): string {
  const team = (teamName ?? "").trim();
  const owner = (ownerName ?? "").trim();
  if (team && owner && team.toLowerCase() !== owner.toLowerCase()) return `${team} · ${owner}`;
  return team || owner || fallback;
}
