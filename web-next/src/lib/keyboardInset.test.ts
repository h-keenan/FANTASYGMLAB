import { describe, expect, it } from "vitest";

import { isEditableFocus, keyboardInset, shouldScrollIntoView } from "./keyboardInset";

describe("keyboardInset", () => {
  it("is the height of the viewport the keyboard covers", () => {
    expect(keyboardInset(844, { height: 504, offsetTop: 0, scale: 1 })).toBe(340);
    expect(keyboardInset(844, { height: 544, offsetTop: 0, scale: 1 })).toBe(300);
  });
  it("is 0 when no text field is focused, however small the visual viewport is (the stale-iOS-viewport crop)", () => {
    expect(keyboardInset(844, { height: 504, offsetTop: 0, scale: 1 }, false)).toBe(0);
    expect(keyboardInset(844, { height: 504, offsetTop: 0, scale: 1 }, true)).toBe(340);
  });
  it("never lets a bad reading claim more than 60% of the screen", () => {
    expect(keyboardInset(844, { height: 100, offsetTop: 0, scale: 1 }, true)).toBe(Math.round(844 * 0.6));
  });
  it("knows which focused elements raise a keyboard", () => {
    const text = document.createElement("input"); text.type = "search";
    const box = document.createElement("input"); box.type = "checkbox";
    expect(isEditableFocus(text)).toBe(true);
    expect(isEditableFocus(document.createElement("textarea"))).toBe(true);
    expect(isEditableFocus(box)).toBe(false);
    expect(isEditableFocus(document.createElement("button"))).toBe(false);
    expect(isEditableFocus(null)).toBe(false);
  });
  it("ignores browser-chrome jitter, pinch zoom and a missing visualViewport", () => {
    expect(keyboardInset(844, { height: 800, offsetTop: 0, scale: 1 })).toBe(0);
    expect(keyboardInset(844, { height: 500, offsetTop: 0, scale: 2 })).toBe(0);
    expect(keyboardInset(844, null)).toBe(0);
  });
  it("scrolls text inputs in pop-ups into view, never other controls or page inputs", () => {
    const dlg = document.createElement("div");
    dlg.className = "ui-sheet";
    const input = document.createElement("input");
    input.type = "search";
    const box = document.createElement("input");
    box.type = "checkbox";
    dlg.append(input, box);
    document.body.append(dlg);
    expect(shouldScrollIntoView(input)).toBe(true);
    expect(shouldScrollIntoView(box)).toBe(false);
    const pageInput = document.createElement("input");
    document.body.append(pageInput);
    expect(shouldScrollIntoView(pageInput)).toBe(false);
    expect(shouldScrollIntoView(null)).toBe(false);
  });
});
