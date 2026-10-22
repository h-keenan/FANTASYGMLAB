import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SheetHandle } from "@/components/SheetHandle";
import { useSheetDragDismiss } from "./useSheetDragDismiss";

function Sheet({ onDismiss }: { onDismiss: () => void }) {
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss });
  return (
    <div ref={sheetRef} style={sheetStyle} data-testid="sheet">
      <SheetHandle />
      <div data-testid="scroll" style={{ overflowY: "auto" }}>
        <p data-testid="content">Long content</p>
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
});
