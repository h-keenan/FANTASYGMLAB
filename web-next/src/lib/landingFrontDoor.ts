/**
 * Which front door the signed-out landing shows: "email" (the email sign-in form, the original behaviour) or "connect"
 * (the one-field Sleeper connect form, guest-first; lib/connectFlow.ts). One switch: set NEXT_PUBLIC_LANDING_FRONT_DOOR=connect
 * at build time, or change the default below. Defaults to "email" until the product owner decides.
 */
export type LandingFrontDoor = "connect" | "email";

export function parseLandingFrontDoor(value: string | undefined | null): LandingFrontDoor {
  return value === "connect" ? "connect" : "email";
}

export const LANDING_FRONT_DOOR: LandingFrontDoor = parseLandingFrontDoor(process.env.NEXT_PUBLIC_LANDING_FRONT_DOOR);
