/** Verdict-card copy helpers: the backend sends the same lineup sentence in
 * both `lineup_model.explanation` and `rationale`. Show each sentence once. */

function splitSentences(text: string): string[] {
  return (text || "")
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function norm(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/** Removes from `text` any sentence already present in `seen` (case and
 * punctuation insensitive). Returns the remaining text. */
export function dropRepeatedSentences(text: string, seen: string[]): string {
  const seenSet = new Set(seen.flatMap(splitSentences).map(norm));
  return splitSentences(text)
    .filter((s) => !seenSet.has(norm(s)))
    .join(" ");
}

/** First `max` sentences of `text` as a short summary. */
export function shortSummary(text: string, max = 1): string {
  return splitSentences(text).slice(0, max).join(" ");
}
