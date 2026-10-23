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

  it("text-only when no image", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    setNav({ clipboard: { writeText } });
    expect(await shareImageOrText({ ...args, fetchImage: undefined })).toBe("copied");
  });
});
