// Minimal assertions so tests need no network imports (works offline).
function stable(v: unknown): string {
  return JSON.stringify(v, (_k, val) =>
    val && typeof val === "object" && !Array.isArray(val)
      ? Object.fromEntries(Object.entries(val as Record<string, unknown>).sort(([a], [b]) => a.localeCompare(b)))
      : val
  );
}
export function assert(cond: unknown, msg = "assertion failed"): asserts cond {
  if (!cond) throw new Error(msg);
}
export function assertEquals(actual: unknown, expected: unknown, msg = ""): void {
  if (stable(actual) !== stable(expected)) {
    throw new Error(`${msg} expected ${stable(expected)} got ${stable(actual)}`);
  }
}
export async function assertRejects(fn: () => Promise<unknown>, contains = ""): Promise<void> {
  try {
    await fn();
  } catch (e) {
    if (contains && !String((e as Error).message).includes(contains)) {
      throw new Error(`rejected with "${(e as Error).message}", wanted to include "${contains}"`);
    }
    return;
  }
  throw new Error("expected rejection");
}
