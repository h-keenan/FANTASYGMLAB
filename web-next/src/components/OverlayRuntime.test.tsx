import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/x" }));

import { OverlayRuntime } from "@/components/OverlayRuntime";
import { Sheet } from "@/components/ui/Sheet";
import { overlayStack } from "@/lib/overlayStack";

afterEach(() => overlayStack.closeAll());

describe("OverlayRuntime", () => {
  it("owns the one scroll lock: locked while any pop-up is open, restored exactly when the last closes", () => {
    document.body.style.overflow = "scroll";
    const { rerender } = render(
      <>
        <OverlayRuntime />
        <Sheet open onClose={() => {}} title="A">a</Sheet>
        <Sheet open onClose={() => {}} title="B">b</Sheet>
      </>,
    );
    expect(document.body.style.overflow).toBe("hidden");
    expect(document.body.hasAttribute("data-overlay-open")).toBe(true);
    rerender(
      <>
        <OverlayRuntime />
        <Sheet open={false} onClose={() => {}} title="A">a</Sheet>
        <Sheet open onClose={() => {}} title="B">b</Sheet>
      </>,
    );
    expect(document.body.style.overflow).toBe("hidden"); // still one open: not unlocked early
    rerender(
      <>
        <OverlayRuntime />
        <Sheet open={false} onClose={() => {}} title="A">a</Sheet>
        <Sheet open={false} onClose={() => {}} title="B">b</Sheet>
      </>,
    );
    expect(document.body.style.overflow).toBe("scroll");
    expect(document.body.hasAttribute("data-overlay-open")).toBe(false);
  });
});
