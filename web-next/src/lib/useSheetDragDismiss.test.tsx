import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SheetHandle } from "@/components/SheetHandle";
import { useSheetDragDismiss } from "./useSheetDragDismiss";

function Sheet({ onDismiss }: { onDismiss: () => void }) {
  const { sheetRef, sheetStyle, backdropStyle } = useSheetDragDismiss({ onDismiss });
  return (
    <div style={backdropStyle} data-testid="backdrop">
    <div ref={sheetRef} style={sheetStyle} data-testid="sheet">
      <SheetHandle />
      <div data-testid="scroll" style={{ overflowY: "auto" }}>
        <p data-testid="content">Long content</p>
      </div>
    </div>
    </div>
  );
}

function swipe(target: Element, points: Array<[number, number]>) {
  const [first, ...rest] = points;
  fireEvent.touchStart(target, { touches: [{ clientX: first[0], clientY: first[1] }] });
  for (const [x, y] of rest) {
    fireEvent.touchMove(target, { touches: [{ clientX: x, clientY: y }] });
  }
  fireEvent.touchEnd(target, { touches: [] });
}

function setScrolled(element: HTMLElement, scrollTop: number) {
  Object.defineProperty(element, "scrollHeight", { configurable: true, value: 2000 });
  Object.defineProperty(element, "clientHeight", { configurable: true, value: 500 });
  element.scrollTop = scrollTop;
}

describe("useSheetDragDismiss", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("fades the backdrop while the sheet follows the finger, and starts from the handle over scrolled content", () => {
    const onDismiss = vi.fn();
    render(<Sheet onDismiss={onDismiss} />);
    setScrolled(screen.getByTestId("scroll"), 300);
    const handle = document.querySelector("[data-sheet-handle]") as Element;
    fireEvent.touchStart(handle, { touches: [{ clientX: 100, clientY: 100 }] });
    fireEvent.touchMove(handle, { touches: [{ clientX: 100, clientY: 130 }] });
    fireEvent.touchMove(handle, { touches: [{ clientX: 100, clientY: 160 }] });
    expect(Number(screen.getByTestId("backdrop").style.getPropertyValue("--sheet-drag"))).toBeGreaterThanOrEqual(0);
    expect(screen.getByTestId("sheet").style.transform).toContain("translate3d");
    fireEvent.touchEnd(handle, { touches: [] });
  });

  it("closes on a long downward drag when the content is at its top", () => {
    const onDismiss = vi.fn();
    render(<Sheet onDismiss={onDismiss} />);
    swipe(screen.getByTestId("content"), [
      [100, 100],
      [100, 130],
      [100, 200],
      [100, 320],
    ]);
    act(() => vi.advanceTimersByTime(300));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("springs back on a short drag", () => {
    const onDismiss = vi.fn();
    render(<Sheet onDismiss={onDismiss} />);
    swipe(screen.getByTestId("content"), [
      [100, 100],
      [100, 115],
    ]);
    act(() => vi.advanceTimersByTime(1000));
    // A 15px pull is under both the distance and the flick minimum.
    expect(onDismiss).not.toHaveBeenCalled();
    expect(screen.getByTestId("sheet").style.transform).toBe("");
  });

  it("never closes while scrolling back up inside scrolled content", () => {
    const onDismiss = vi.fn();
    render(<Sheet onDismiss={onDismiss} />);
    setScrolled(screen.getByTestId("scroll"), 300);
    swipe(screen.getByTestId("content"), [
      [100, 100],
      [100, 200],
      [100, 400],
    ]);
    act(() => vi.advanceTimersByTime(1000));
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("always drags from the handle, even when the content is scrolled", () => {
    const onDismiss = vi.fn();
    const { container } = render(<Sheet onDismiss={onDismiss} />);
    setScrolled(screen.getByTestId("scroll"), 300);
    const handle = container.querySelector("[data-sheet-handle]")!;
    swipe(handle, [
      [100, 10],
      [100, 60],
      [100, 260],
    ]);
    act(() => vi.advanceTimersByTime(300));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("ignores horizontal swipes", () => {
    const onDismiss = vi.fn();
    render(<Sheet onDismiss={onDismiss} />);
    swipe(screen.getByTestId("content"), [
      [100, 100],
      [200, 120],
      [300, 300],
    ]);
    act(() => vi.advanceTimersByTime(1000));
    expect(onDismiss).not.toHaveBeenCalled();
  });

  it("does not render per touchmove: the live transform survives a re-render", () => {
    const { rerender } = render(<Sheet onDismiss={vi.fn()} />);
    const handle = document.querySelector("[data-sheet-handle]") as Element;
    fireEvent.touchStart(handle, { touches: [{ clientX: 100, clientY: 100 }] });
    fireEvent.touchMove(handle, { touches: [{ clientX: 100, clientY: 130 }] });
    fireEvent.touchMove(handle, { touches: [{ clientX: 100, clientY: 180 }] });
    const live = screen.getByTestId("sheet").style.transform;
    expect(live).toContain("translate3d");
    rerender(<Sheet onDismiss={vi.fn()} />);
    expect(screen.getByTestId("sheet").style.transform).toBe(live);
  });
});

function Peek({ onDismiss, onSnap }: { onDismiss: () => void; onSnap: (s: number) => void }) {
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss, snapPoints: [0.5, 1], snap: 0.5, onSnapChange: onSnap });
  return (
    <div ref={sheetRef} style={sheetStyle} data-testid="peek">
      <SheetHandle />
    </div>
  );
}

describe("useSheetDragDismiss snap points", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("rests at the peek, drags up to full, and dismisses down from the peek", () => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ height: 800, width: 390, top: 0, left: 0, right: 390, bottom: 800, x: 0, y: 0, toJSON() {} } as DOMRect);
    const onDismiss = vi.fn();
    const onSnap = vi.fn();
    render(<Peek onDismiss={onDismiss} onSnap={onSnap} />);
    const peek = screen.getByTestId("peek");
    act(() => vi.advanceTimersByTime(50));
    expect(peek.style.transform).toContain("400px");
    const handle = document.querySelector("[data-sheet-handle]") as Element;
    swipe(handle, [[100, 500], [100, 470], [100, 300], [100, 120]]);
    act(() => vi.advanceTimersByTime(400));
    expect(onSnap).toHaveBeenCalledWith(1);
    expect(peek.style.transform).toBe("");
    // Down from full lands on the peek first, not closed.
    swipe(handle, [[100, 100], [100, 130], [100, 330], [100, 520]]);
    act(() => vi.advanceTimersByTime(400));
    expect(onDismiss).not.toHaveBeenCalled();
    expect(onSnap).toHaveBeenLastCalledWith(0.5);
    vi.restoreAllMocks();
  });
});
