/**
 * Which front door the signed-out landing shows: "connect" (the one-field Sleeper connect form, guest-first;
 * lib/connectFlow.ts) or "email" (the email sign-in form, the original behaviour). Defaults to "connect" (product decision
 * 2026-11-16); set NEXT_PUBLIC_LANDING_FRONT_DOOR=email at build time to switch back.
 */
export type LandingFrontDoor = "connect" | "email";

export function parseLandingFrontDoor(value: string | undefined | null): LandingFrontDoor {
  return value === "email" ? "email" : "connect";
}

export const LANDING_FRONT_DOOR: LandingFrontDoor = parseLandingFrontDoor(process.env.NEXT_PUBLIC_LANDING_FRONT_DOOR);
