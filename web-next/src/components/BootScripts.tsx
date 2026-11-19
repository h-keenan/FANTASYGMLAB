import { THEME_BOOT_SCRIPT } from "@/lib/displayPreferences";
import { buildEarlyFetchScript } from "@/lib/earlyFetch";
import { preconnectOrigins } from "@/lib/preconnect";

/**
 * The <head> preconnects and the two inline boot scripts, rendered by app/layout.tsx. Both inline scripts carry the
 * per-request CSP nonce (src/proxy.ts) so they run under a nonce-based policy without 'unsafe-inline'.
 * Open the API and auth connections while the bundle downloads (lib/preconnect.ts); the early-fetch script starts Today's
 * first-paint request before the bundle loads and lib/api.ts reuses it (lib/earlyFetch.ts).
 */
export function BootScripts({ nonce, apiBase, storageKey }: { nonce?: string; apiBase: string; storageKey: string }) {
  return (
    <>
      {preconnectOrigins([process.env.NEXT_PUBLIC_API_BASE_URL, process.env.NEXT_PUBLIC_SUPABASE_URL]).map((origin) => (
        <link key={origin} rel="preconnect" href={origin} crossOrigin="anonymous" />
      ))}
      <script nonce={nonce} dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      <script nonce={nonce} dangerouslySetInnerHTML={{ __html: buildEarlyFetchScript({ apiBase, storageKey }) }} />
    </>
  );
}
