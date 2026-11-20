#!/usr/bin/env node
// Guard: raw client storage must not bypass the user-scoped helper.
//
// Per-user local state goes through `userGet/userSet/userRemove` (web-next/src/lib/userStorage.ts) or
// `userStorage.get/set/remove` (mobile/src/lib/userStorage.ts), which store under `u:<userId>:<key>` and are
// removed by the single account purge. Docs: docs/audits/2026-11-account-isolation.md.
//
// This check fails when a non-test source file in web-next/src or mobile/src touches localStorage, sessionStorage,
// AsyncStorage, SecureStore, MMKV or IndexedDB and is not in ALLOWED below. Every allowed file carries a reason:
//   device  - holds only a device preference or an anonymous identifier, so it is global on purpose
//   purged  - unscoped on purpose (read before a user exists), but listed in accountScope.ts PURGE_UNSCOPED_KEYS
//   keyed   - already keyed by user id in its own key shape, kept across sign-out (progress flags only)
//   helper  - the scoped helpers and the purge itself
//   auth    - Supabase auth storage or the auth flow; off limits to this mechanism
// Adding a file here is a decision: pick the right category and say why. Stale entries fail too.
//
// Usage: node scripts/check_storage_keys.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export const ALLOWED = {
  // ---- helpers
  "web-next/src/lib/userStorage.ts": "helper: web scoped storage and purge",
  "mobile/src/lib/userStorage.ts": "helper: app scoped storage (AsyncStorage binding)",
  // ---- auth (off limits)
  "web-next/src/lib/supabase.ts": "auth: Supabase auth storage adapter",
  "mobile/src/lib/supabase.ts": "auth: Supabase auth storage adapter",
  "web-next/src/lib/landingPending.ts": "auth: inline script that looks for the Supabase token key",
  "web-next/src/context/AuthContext.tsx": "auth: return-path and session-ended notes, cleared by the purge",
  "mobile/src/context/AuthContext.tsx": "auth: auth-scope marker, drives the purge",
  "web-next/src/lib/protectedRouteReturn.ts": "purged: return path written before sign-in (fd_protected_route_return_path)",
  "web-next/src/lib/tradeBridge.ts": "purged: trade handed from the public analyzer to sign-in (fd_pending_bridge_trade_v1)",
  "web-next/src/context/ValuationLensContext.tsx": "purged: detected lens per league, read by an inline script (fgl.detectedLens.v1)",
  "web-next/src/lib/earlyFetch.ts": "purged: inline script reads the lens map",
  // ---- keyed already, kept
  "web-next/src/components/StartHereCard.tsx": "keyed: fd:start-here:v1:<user>",
  "mobile/src/components/StartHereCard.tsx": "keyed: fd:start-here:v1:<user>",
  "web-next/src/lib/onboardingProgress.ts": "keyed: fgl:onboarding:<step>:<user>",
  "web-next/src/components/SinceLastVisitStrip.tsx": "keyed: fd:last-visit:v1:<user>:<league>",
  "web-next/src/app/leagues/page.tsx": "keyed: portfolio snapshot fd:portfolio:v1:<user>:<lens>, purged on sign-out",
  "mobile/src/lib/alertReads.ts": "keyed: AsyncStorage binding of the pending alert reads (scope = user:league inside the store)",
  "mobile/src/lib/effectsPrefs.ts": "device: AsyncStorage binding of the effects preferences",
  "mobile/src/lib/analytics.ts": "device: AsyncStorage binding of the anonymous analytics ids and queue",
  "web-next/src/lib/alertReadSync.ts": "keyed: pending alert reads, scope = user:league inside the store",
  // ---- device level
  "web-next/src/context/DisplayPreferencesContext.tsx": "device: theme and density",
  "web-next/src/lib/displayPreferences.ts": "device: theme and density (inline script)",
  "mobile/src/context/ThemeModeContext.tsx": "device: theme",
  "mobile/src/context/DensityContext.tsx": "device: density",
  "mobile/src/context/ExperienceLevelContext.tsx": "device: experience level copy",
  "mobile/src/context/ShowcaseModeContext.tsx": "device: screenshot mode",
  "mobile/src/context/OnboardingContext.tsx": "device: per-install first-run gate (documented follow-up to scope)",
  "mobile/src/context/CollegeInterestContext.tsx": "device: per-install prompt state (documented follow-up to scope)",
  "web-next/src/components/SimToControl.tsx": "device: sim-to control layout",
  "mobile/src/components/SimToControl.tsx": "device: sim-to control layout",
  "web-next/src/lib/useSimCelebrations.ts": "device: animation toggle",
  "mobile/src/lib/useSimCelebrationsNative.ts": "device: animation toggle",
  "web-next/src/lib/useShellNav.ts": "device: navigation style",
  "web-next/src/components/Collapsible.tsx": "device: section expanded state",
  "mobile/src/components/Collapsible.tsx": "device: section expanded state",
  "web-next/src/components/ui/CompactModule.tsx": "device: module expanded state",
  "mobile/src/components/CompactModule.tsx": "device: module expanded state",
  "web-next/src/components/ui/PillOrb.tsx": "device: orb coachmark seen",
  "mobile/src/components/GmOrb.tsx": "device: orb coachmark seen",
  "mobile/src/lib/orbPosition.ts": "device: orb position",
  "mobile/src/lib/viewModePreference.ts": "device: list or grid layout",
  "web-next/src/components/Tabs.tsx": "device: selected tab, session lifetime",
  "web-next/src/lib/ageGateStorage.ts": "device: age gate",
  "mobile/src/lib/ageGate.ts": "device: age gate",
  "mobile/src/lib/pushPermissionPromptStorage.ts": "device: OS permission prompt dismissal",
  "web-next/src/lib/privacy.ts": "device: privacy masking choice and session labels",
  "web-next/src/lib/analytics.ts": "device: anonymous analytics ids",
  "web-next/src/lib/attribution.ts": "device: first-touch attribution and referral, captured before sign-in",
  "mobile/src/lib/referralCapture.ts": "device: referral code captured before sign-in",
  "mobile/src/lib/queryClient.ts": "device: React Query persister, user-rooted keys, cleared by clearAuthenticatedQueryCache",
};

const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "build", "coverage", ".expo"]);
const PATTERN = /\b(localStorage|sessionStorage|AsyncStorage|SecureStore|MMKV|createMMKV|indexedDB)\b/;

function* walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    if (SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walk(full);
    else if (/\.(ts|tsx|js|jsx|mjs)$/.test(entry.name) && !/\.(test|spec)\./.test(entry.name)) yield full;
  }
}

function stripComments(source) {
  return source.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:'"`])\/\/.*$/gm, "$1");
}

export function findViolations() {
  const violations = [];
  const used = new Set();
  for (const base of ["web-next/src", "mobile/src"]) {
    const dir = path.join(root, base);
    if (!existsSync(dir)) continue;
    for (const file of walk(dir)) {
      const rel = path.relative(root, file).split(path.sep).join("/");
      if (!PATTERN.test(stripComments(readFileSync(file, "utf8")))) continue;
      used.add(rel);
      if (!(rel in ALLOWED)) violations.push(rel);
    }
  }
  const stale = Object.keys(ALLOWED).filter((rel) => !used.has(rel));
  return { violations, stale };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const { violations, stale } = findViolations();
  if (violations.length || stale.length) {
    for (const rel of violations) {
      console.error(
        `${rel}: touches client storage outside the user-scoped helper. Use userGet/userSet (web) or userStorage (app), ` +
          `or add the file to ALLOWED in scripts/check_storage_keys.mjs with a category and reason.`,
      );
    }
    for (const rel of stale) console.error(`${rel}: listed in ALLOWED but no longer touches client storage; remove it.`);
    process.exit(1);
  }
  console.log(`Storage key guard passed (${Object.keys(ALLOWED).length} allowed files).`);
}
