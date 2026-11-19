import { headers } from "next/headers";

import { NONCE_HEADER } from "@/lib/csp";

/** The per-request CSP nonce set by src/proxy.ts, or undefined (no proxy run, e.g. a unit test). Server components only. */
export async function getNonce(): Promise<string | undefined> {
  return (await headers()).get(NONCE_HEADER) ?? undefined;
}
