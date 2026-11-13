import { describe, expect, it } from "vitest";

import { keyboardInset, shouldScrollIntoView } from "./keyboardInset";

describe("keyboardInset", () => {
  it("is the height of the viewport the keyboard covers", () => {
    expect(keyboardInset(844, { height: 504, offsetTop: 0, scale: 1 })).toBe(340);
    expect(keyboardInset(844, { height: 544, offsetTop: 0, scale: 1 })).toBe(300);
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
