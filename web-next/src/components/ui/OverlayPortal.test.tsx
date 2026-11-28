import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OverlayPortal } from "./OverlayPortal";

describe("OverlayPortal", () => {
  beforeEach(() => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
  });

  it("renders its children directly under <body>, outside the transformed/filtered tree", () => {
    const { container } = render(
      <div className="glass-surface" style={{ backdropFilter: "blur(4px)" }} data-testid="host">
        <OverlayPortal>
          <div data-testid="layer" className="fixed inset-0" />
        </OverlayPortal>
      </div>,
    );
    const layer = screen.getByTestId("layer");
    expect(layer.parentElement).toBe(document.body);
    expect(container.contains(layer)).toBe(false);
  });

  it("locks body scroll while mounted when asked, and releases on unmount", () => {
    const { unmount } = render(
      <OverlayPortal lockScroll>
        <div />
      </OverlayPortal>,
    );
    expect(document.body.style.position).toBe("fixed");
    unmount();
    expect(document.body.style.position).toBe("");
  });
});
