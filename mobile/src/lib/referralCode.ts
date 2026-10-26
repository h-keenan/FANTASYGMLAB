/** Pure ref-code parsing, kept free of React Native imports so node tests can load it. */
/** The sanitized `ref` query value of a URL, or '' (exported for tests). */
export function parseReferralCode(url: string | null | undefined): string {
  if (!url) return '';
  const match = /[?&]ref=([^&#]*)/.exec(url);
  if (!match) return '';
  let value = match[1];
  try {
    value = decodeURIComponent(value);
  } catch {
    // keep the raw value; sanitized below
  }
  return value.replace(/[^A-Za-z0-9_-]/g, '').slice(0, 64);
}

