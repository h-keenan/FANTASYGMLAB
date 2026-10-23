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

export type ShareOutcome =
  | "shared-image"
  | "shared-text"
  | "copied"
  | "copied-image"
  | "saved-image"
  | "cancelled"
  | "failed";

/** True for any outcome where the user actually got something to share. */
export function isCompletedShare(outcome: ShareOutcome): boolean {
  return outcome !== "cancelled" && outcome !== "failed";
}

/** Desktop fallback 1: put the PNG itself on the clipboard. */
async function copyImage(blob: Blob): Promise<boolean> {
  try {
    if (
      typeof navigator === "undefined" ||
      !navigator.clipboard ||
      typeof navigator.clipboard.write !== "function" ||
      typeof ClipboardItem === "undefined"
    ) {
      return false;
    }
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    return true;
  } catch {
    return false;
  }
}

/** Desktop fallback 2: download the PNG through a temporary anchor. */
function saveImage(blob: Blob, filename: string): boolean {
  try {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    return true;
  } catch {
    return false;
  }
}

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

/** True when this browser can attach files through the Web Share API. */
export function canShareFiles(blob?: Blob): boolean {
  const capable =
    typeof navigator !== "undefined" &&
    typeof navigator.share === "function" &&
    typeof navigator.canShare === "function";
  if (!capable || !blob) return capable;
  try {
    return navigator.canShare({ files: [new File([blob], "card.png", { type: "image/png" })] });
  } catch {
    return false;
  }
}

/** Short, privacy-safe error name (never the message) for analytics. */
export function shareErrorName(error: unknown): string {
  const raw = error instanceof Error && error.name ? error.name : "Error";
  return raw.replace(/[^A-Za-z0-9_]/g, "").slice(0, 40) || "Error";
}

export async function shareImageOrText({
  fetchImage,
  preparedBlob,
  filename,
  text,
  title,
  onPreparingImage,
  onImageFailed,
}: {
  /** Omit to skip straight to the text share. */
  fetchImage?: () => Promise<Blob>;
  /** A PNG already built ahead of the tap. iOS Safari only lets
   * navigator.share run inside the tap's user-activation window, so when this
   * is given NOTHING is awaited before the share call. */
  preparedBlob?: Blob | null;
  /** Called when the image could not be built or shared, before the
   * fallback runs, so the UI never degrades silently. */
  onImageFailed?: (error: unknown, stage: "build" | "share") => void;
  filename: string;
  text: string;
  title: string;
  onPreparingImage?: (preparing: boolean) => void;
}): Promise<ShareOutcome> {
  const filesCapable = canShareFiles();

  if (preparedBlob || fetchImage) {
    let blob: Blob | null = preparedBlob ?? null;
    if (!blob && fetchImage) {
      onPreparingImage?.(true);
      try {
        blob = await fetchImage();
      } catch (error) {
        // The PNG fetch failed (network, a stale id's 404): text fallback.
        onImageFailed?.(error, "build");
      }
    }
    if (blob) {
      try {
        if (filesCapable) {
          const file = new File([blob], filename, { type: "image/png" });
          if (navigator.canShare({ files: [file] })) {
            await navigator.share({ files: [file], text, title });
            onPreparingImage?.(false);
            return "shared-image";
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") {
          // The user closed the share sheet on purpose.
          onPreparingImage?.(false);
          return "cancelled";
        }
        // The platform rejected the file: fall through to copy/save.
        onImageFailed?.(error, "share");
      }
      // No Files-capable share (typically desktop): still give them the PNG.
      if (await copyImage(blob)) {
        onPreparingImage?.(false);
        return "copied-image";
      }
      if (saveImage(blob, filename)) {
        onPreparingImage?.(false);
        return "saved-image";
      }
    }
    onPreparingImage?.(false);
  }

  return shareTextOnly(text, title);
}
