/**
 * The one "share a branded card" flow every web share button uses: attach
 * the PNG through the Files-capable Web Share API when the browser can,
 * otherwise share the text, otherwise copy it. Pulled out of
 * ShareTradeButton so the player card's button shares the exact same
 * fallbacks instead of a second copy.
 *
 * Returns what actually happened so the caller can record a completed share
 * (e.g. Trade Hub's "Did this trade happen?" prompt) and show "Copied!".
 */

export type ShareOutcome = "shared-image" | "shared-text" | "copied" | "cancelled" | "failed";

async function shareTextOnly(text: string, title: string): Promise<ShareOutcome> {
  if (typeof navigator !== "undefined" && navigator.share) {
    try {
      await navigator.share({ text, title });
      return "shared-text";
    } catch {
      // Cancelled or rejected: fall through to the clipboard so the button
      // never silently does nothing.
    }
  }
  try {
    await navigator.clipboard.writeText(text);
    return "copied";
  } catch {
    return "failed";
  }
}

export async function shareImageOrText({
  fetchImage,
  filename,
  text,
  title,
  onPreparingImage,
}: {
  /** Omit to skip straight to the text share. */
  fetchImage?: () => Promise<Blob>;
  filename: string;
  text: string;
  title: string;
  onPreparingImage?: (preparing: boolean) => void;
}): Promise<ShareOutcome> {
  const filesCapable =
    typeof navigator !== "undefined" &&
    typeof navigator.share === "function" &&
    typeof navigator.canShare === "function";

  if (filesCapable && fetchImage) {
    onPreparingImage?.(true);
    try {
      const blob = await fetchImage();
      const file = new File([blob], filename, { type: "image/png" });
      if (navigator.canShare({ files: [file] })) {
        await navigator.share({ files: [file], text, title });
        onPreparingImage?.(false);
        return "shared-image";
      }
      // Text works here but this file was rejected: use the text path.
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        // The user closed the share sheet on purpose.
        onPreparingImage?.(false);
        return "cancelled";
      }
      // The PNG fetch failed (network, a stale id's 404) or the platform
      // rejected the file: fall back to the text share.
    }
    onPreparingImage?.(false);
  }

  return shareTextOnly(text, title);
}
