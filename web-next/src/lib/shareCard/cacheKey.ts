/** Stable cache key for a browser-rendered share card: a hash of its inputs. */
export function shareCardCacheKey(input: unknown): string {
  const json = JSON.stringify(input) ?? "";
  let h1 = 5381;
  let h2 = 52711;
  for (let i = 0; i < json.length; i += 1) {
    const c = json.charCodeAt(i);
    h1 = ((h1 << 5) + h1) ^ c;
    h2 = ((h2 << 5) + h2 + c) | 0;
  }
  return `analyzer:${(h1 >>> 0).toString(36)}${(h2 >>> 0).toString(36)}:${json.length}`;
}
