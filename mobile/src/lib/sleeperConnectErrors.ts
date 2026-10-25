/**
 * Single copy source for the Sleeper "connect a league" error states.
 * Web twin: web-next/src/lib/sleeperConnectErrors.ts (kept identical in
 * content; the test next to each file pins the strings).
 *
 * Why: analytics showed most failed connects were `user_not_found` (people
 * typing a display name / email) or `no_leagues`, and the server's one-line
 * message gave them no way forward. The status codes come from
 * modules/sleeper_leagues.py; this maps each to plain guidance. No data is
 * invented here: it is instructional copy only.
 */

export type SleeperConnectErrorKind = "user_not_found" | "no_leagues" | "network" | "other";

export interface SleeperConnectError {
  kind: SleeperConnectErrorKind;
  /** The one-line "what happened". */
  message: string;
  /** Optional "what to do next" line. */
  hint: string;
  /** Show the "Try a sample league" button under the error. */
  offerSample: boolean;
  /** Show the "create a free Sleeper account" help. */
  offerSleeperSignup: boolean;
}

const USERNAME_HINT =
  "Use your Sleeper username, not your display name or email. In Sleeper, open your profile (or Settings); the username is the handle shown under your name.";

const NO_LEAGUES_HINT =
  "We check this season and last season. Make sure this is the account that is in your league, or try again once your league for this season exists on Sleeper. You can also try a different username.";

const NETWORK_HINT = "Check your connection and tap the button to try again. Your username is still filled in.";

export function describeSleeperConnectError(input: {
  status?: string | null;
  username?: string;
  serverMessage?: string | null;
}): SleeperConnectError {
  const name = (input.username || "").trim();
  const quoted = name ? `"${name}"` : "that username";
  switch (input.status) {
    case "user_not_found":
      return {
        kind: "user_not_found",
        message: `We couldn't find a Sleeper user named ${quoted}.`,
        hint: USERNAME_HINT,
        offerSample: true,
        offerSleeperSignup: true,
      };
    case "no_leagues":
      return {
        kind: "no_leagues",
        message: `No leagues found on Sleeper for ${quoted} this season or last season.`,
        hint: NO_LEAGUES_HINT,
        offerSample: true,
        offerSleeperSignup: false,
      };
    case "unavailable":
    case "network":
      return {
        kind: "network",
        message: "We couldn't reach Sleeper or FantasyDesk just now.",
        hint: NETWORK_HINT,
        offerSample: false,
        offerSleeperSignup: false,
      };
    default:
      return {
        kind: "other",
        message: (input.serverMessage || "").trim() || "Something went wrong. Please try again.",
        hint: "",
        offerSample: false,
        offerSleeperSignup: false,
      };
  }
}

/** True for a thrown request failure that is a connectivity/server problem. */
export function isConnectivityFailure(error: unknown): boolean {
  const status = (error as { status?: unknown } | null)?.status;
  if (typeof status === "number") return status === 0 || status >= 500;
  // A bare fetch/network exception with no HTTP status.
  return error instanceof Error;
}
