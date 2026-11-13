import { describe, expect, it } from "vitest";

import { orbPlacement, orbStyleFromPlacement } from "./orbViewport";

const vv = (o: Partial<Parameters<typeof orbPlacement>[0]> = {}) => ({ height: 700, width: 390, offsetTop: 0, offsetLeft: 0, scale: 1, ...o });

describe("orbPlacement", () => {
  it("bottom edge is offsetTop + height", () => {
    expect(orbPlacement(vv())?.bottomPx).toBe(700);
    expect(orbPlacement(vv({ offsetTop: 48, height: 652 }))?.bottomPx).toBe(700);
    expect(orbPlacement(vv({ offsetTop: 120, height: 600 }))?.bottomPx).toBe(720);
  });
  it("centers horizontally on the visual viewport", () => {
    expect(orbPlacement(vv())?.centerXPx).toBe(195);
    expect(orbPlacement(vv({ offsetLeft: 100, width: 195, scale: 2 }))?.centerXPx).toBe(197.5);
  });
  it("counter-scales under pinch zoom", () => {
    expect(orbPlacement(vv({ scale: 2 }))?.scale).toBe(0.5);
    expect(orbPlacement(vv())?.scale).toBe(1);
  });
  it("rejects unusable viewports so the CSS fallback stays in force", () => {
    expect(orbPlacement(vv({ height: 0 }))).toBeNull();
    expect(orbPlacement(vv({ height: NaN }))).toBeNull();
    expect(orbPlacement(vv({ width: -1 }))).toBeNull();
  });
  it("treats a bogus scale as 1", () => {
    expect(orbPlacement(vv({ scale: 0 }))?.scale).toBe(1);
  });
});

describe("orbStyleFromPlacement", () => {
  it("anchors by top from the visual bottom, with safe-area margin", () => {
    const s = orbStyleFromPlacement({ bottomPx: 700, centerXPx: 195, scale: 1 });
    expect(s.top).toBe("calc(700px - 3.25rem * 1 - max(12px, env(safe-area-inset-bottom, 0px)) * 1)");
    expect(s.bottom).toBe("auto");
    expect(s.left).toBe("195px");
    expect(s.transform).toBe("translate3d(-50%, 0, 0) scale(1)");
  });
});
