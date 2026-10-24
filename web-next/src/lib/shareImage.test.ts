// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { shareImageOrText } from "@/lib/shareImage";

const blob = () => Promise.resolve(new Blob(["png"], { type: "image/png" }));
const args = { filename: "c.png", text: "t", title: "T", fetchImage: blob };

function setNav(value: Record<string, unknown>) {
  vi.stubGlobal("navigator", value);
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("shareImageOrText", () => {
  it("shares the file when Files-capable", async () => {
    const share = vi.fn().mockResolvedValue(undefined);
    setNav({ share, canShare: () => true });
    expect(await shareImageOrText(args)).toBe("shared-image");
    expect(share).toHaveBeenCalled();
  });

  it("copies the PNG to the clipboard when file share is unavailable", async () => {
    const write = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("ClipboardItem", class { constructor(public d: unknown) {} });
    setNav({ clipboard: { write } });
    expect(await shareImageOrText(args)).toBe("copied-image");
    expect(write).toHaveBeenCalledOnce();
  });

  it("downloads the PNG when the image clipboard is unsupported", async () => {
    setNav({ clipboard: { writeText: vi.fn() } });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    expect(await shareImageOrText(args)).toBe("saved-image");
    expect(click).toHaveBeenCalled();
  });

  it("falls back to text when the image fetch fails", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNav({ clipboard: { writeText } });
    expect(await shareImageOrText({ ...args, fetchImage: () => Promise.reject(new Error("404")) })).toBe("copied");
    expect(writeText).toHaveBeenCalledWith("t");
  });

  it("calls navigator.share synchronously with a prepared file (no await before share)", () => {
    const share = vi.fn().mockResolvedValue(undefined);
    setNav({ share, canShare: () => true });
    const pending = shareImageOrText({ filename: "c.png", text: "t", title: "T", preparedBlob: new Blob(["png"], { type: "image/png" }) });
    // Same tick as the "tap": share must already have been called.
    expect(share).toHaveBeenCalledTimes(1);
    const file = (share.mock.calls[0][0] as ShareData).files?.[0];
    expect(file?.name).toBe("c.png");
    expect(file?.type).toBe("image/png");
    return expect(pending).resolves.toBe("shared-image");
  });

  it("reports a rejected share (NotAllowedError) instead of hiding it", async () => {
    const err = new DOMException("expired", "NotAllowedError");
    setNav({ share: vi.fn().mockRejectedValue(err), canShare: () => true, clipboard: { writeText: vi.fn() } });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    const onImageFailed = vi.fn();
    const outcome = await shareImageOrText({ filename: "c.png", text: "t", title: "T", preparedBlob: new Blob(["p"]), onImageFailed });
    expect(onImageFailed).toHaveBeenCalledWith(err, "share");
    expect(outcome).toBe("saved-image");
  });

  it("reports a failed build before the text fallback", async () => {
    setNav({ clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    const onImageFailed = vi.fn();
    const e = new Error("x");
    await shareImageOrText({ ...args, fetchImage: () => Promise.reject(e), onImageFailed });
    expect(onImageFailed).toHaveBeenCalledWith(e, "build");
  });

  it("text-only when no image", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNav({ clipboard: { writeText } });
    expect(await shareImageOrText({ ...args, fetchImage: undefined })).toBe("copied");
  });
});
