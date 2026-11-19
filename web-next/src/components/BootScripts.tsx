import { THEME_BOOT_SCRIPT } from "@/lib/displayPreferences";
import { buildEarlyFetchScript } from "@/lib/earlyFetch";
import { preconnectOrigins } from "@/lib/preconnect";
import { env } from "@/lib/env";
import { storageKey } from "@/lib/supabaseKeys";

/** The two inline boot script bodies. Constant per build (env + storage key only), so the CSP allows them by hash. */
export function BOOT_SCRIPTS(): string[] {
  return [THEME_BOOT_SCRIPT, buildEarlyFetchScript({ apiBase: env.apiBaseUrl, storageKey })];
}

/**
 * The <head> preconnects and the two inline boot scripts, rendered by app/layout.tsx. The scripts are constant per build, so
 * src/proxy.ts allows them by sha256 hash (lib/csp.ts); that is what lets the root layout avoid reading a per-request nonce
 * and keeps prerendered pages static.
 * Open the API and auth connections while the bundle downloads (lib/preconnect.ts); the early-fetch script starts Today's
 * first-paint request before the bundle loads and lib/api.ts reuses it (lib/earlyFetch.ts).
 */
export function BootScripts() {
  const [theme, early] = BOOT_SCRIPTS();
  return (
    <>
      {preconnectOrigins([process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NEXT_PUBLIC_SUPABASE_URL]).map((origin) => (
        <link key={origin} rel="preconnect" href={origin} crossOrigin="anonymous" />
      ))}
      <script dangerouslySetInnerHTML={{ __html: theme }} />
      <script dangerouslySetInnerHTML={{ __html: early }} />
    </>
  );
}
