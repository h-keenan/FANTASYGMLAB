const KEY = "fgl:age-gate-passed";

/**
 * Device-local "this browser already cleared the age gate" boolean, same key
 * and semantics as mobile/src/lib/ageGate.ts. Only the boolean is stored,
 * never the entered date of birth. Needed for OAuth (Google/Apple), where the
 * page navigates away after the gate and a returning adult should not be
 * asked again on every sign-in.
 */
export function hasPassedAgeGate(): boolean {
  try {
    return window.localStorage.getItem(KEY) === "true";
  } catch {
    return false;
  }
}

export function setPassedAgeGate(): void {
  try {
    window.localStorage.setItem(KEY, "true");
  } catch {
    // Best effort: worst case the gate shows again next time.
  }
}
