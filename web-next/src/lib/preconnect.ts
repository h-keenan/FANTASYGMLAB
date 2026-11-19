/**
 * Origins the first screen talks to (the Desk API for data, Supabase for the session). Opening those connections
 * (DNS + TCP + TLS) while the JS bundle is still downloading takes a full round trip off the first API request,
 * which on a phone connection is the largest single wait after the bundle itself.
 */
export function preconnectOrigins(urls: Array<string | undefined>): string[] {
  const out: string[] = [];
  for (const raw of urls) {
    if (!raw) continue;
    try {
      const u = new URL(raw);
      if ((u.protocol === "https:" || u.protocol === "http:") && !out.includes(u.origin)) out.push(u.origin);
    } catch {
      // A malformed env value must never break the page shell.
    }
  }
  return out;
}
