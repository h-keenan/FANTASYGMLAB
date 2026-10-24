// Dev-only: lets the Deno-style tests run under `bun test --preload` on machines
// without Deno. The real, supported runner is `deno test`. Not deployed.
import { test } from "bun:test";

(globalThis as unknown as { Deno: unknown }).Deno = {
  test: (name: string, fn: () => unknown) => test(name, fn as () => Promise<void>),
};
