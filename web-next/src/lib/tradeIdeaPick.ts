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
  const whose = original && original !== owner ? `${original}'s pick` : null;
  const line = [slot, whose].filter(Boolean).join(' · ');
  return line || null;
}

/** The partner-fit line shown on an idea ("Fills their TE hole · they're contending"), or null when the server sent none. */
export function partnerFitLine(reason: string | null | undefined): string | null {
  const text = (reason ?? '').trim();
  return text ? text : null;
}
