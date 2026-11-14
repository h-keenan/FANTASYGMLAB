import { afterEach, describe, expect, it, vi } from "vitest";

import { installOverlayHistory } from "./overlayHistory";
import { createOverlayStack } from "./overlayStack";

const flush = () => new Promise<void>((resolve) => queueMicrotask(resolve));

describe("overlay history integration", () => {
  let dispose: (() => void) | null = null;
  afterEach(() => {
    dispose?.();
    dispose = null;
    vi.restoreAllMocks();
  });

  function setup() {
    const stack = createOverlayStack();
    const handle = installOverlayHistory(stack, window);
    dispose = handle.dispose;
    return { stack, handle };
  }

  it("pushes one history entry per open overlay, keeping the page's own history state", async () => {
    const push = vi.spyOn(window.history, "pushState");
    window.history.replaceState({ __NA: true }, "");
    const { stack } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => {} });
    stack.open({ id: "b", kind: "sheet", title: "B", dismiss: () => {} });
    await flush();
    expect(push).toHaveBeenCalledTimes(2);
    expect(push.mock.calls[1][0]).toMatchObject({ __NA: true, fgOverlay: 2 });
  });

  it("the browser/phone back button dismisses only the newest overlay", async () => {
    const closed: string[] = [];
    const { stack } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => closed.push("a") });
    stack.open({ id: "b", kind: "sheet", title: "B", dismiss: () => closed.push("b") });
    await flush();
    window.dispatchEvent(new PopStateEvent("popstate"));
    expect(closed).toEqual(["b"]);
  });

  it("closing in code pops its history entries once per batch and swallows the resulting popstate", async () => {
    const go = vi.spyOn(window.history, "go").mockImplementation(() => {});
    const closed: string[] = [];
    const { stack } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => closed.push("a") });
    stack.open({ id: "b", kind: "sheet", title: "B", dismiss: () => closed.push("b") });
    await flush();
    stack.close("b");
    stack.close("a"); // the X: both close in one commit
    await flush();
    expect(go).toHaveBeenCalledTimes(1);
    expect(go).toHaveBeenCalledWith(-2);
    window.dispatchEvent(new PopStateEvent("popstate")); // the traversal we caused
    expect(closed).toEqual([]); // swallowed: nothing is dismissed twice
  });

  it("reset forgets our entries without touching history (route change)", async () => {
    const go = vi.spyOn(window.history, "go").mockImplementation(() => {});
    const { stack, handle } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => {} });
    await flush();
    handle.reset();
    stack.close("a");
    await flush();
    expect(go).not.toHaveBeenCalled();
  });

  it("closing a pop-up for an in-app link tap does not walk history back over the navigation", async () => {
    const go = vi.spyOn(window.history, "go").mockImplementation(() => {});
    const { stack } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => {} });
    await flush();
    const link = document.createElement("a");
    link.href = "/gm-game";
    document.body.appendChild(link);
    link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    stack.close("a"); // the row's onClose
    await flush();
    expect(go).not.toHaveBeenCalled();
    link.remove();
  });

  it("an external or new-tab link does not suppress Back", async () => {
    const go = vi.spyOn(window.history, "go").mockImplementation(() => {});
    const { stack } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => {} });
    await flush();
    const link = document.createElement("a");
    link.href = "https://example.com/x";
    document.body.appendChild(link);
    link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true, button: 0 }));
    stack.close("a");
    await flush();
    expect(go).toHaveBeenCalledWith(-1);
    link.remove();
  });

  it("markNavigating covers programmatic router.push", async () => {
    const go = vi.spyOn(window.history, "go").mockImplementation(() => {});
    const { stack, handle } = setup();
    stack.open({ id: "a", kind: "sheet", title: "A", dismiss: () => {} });
    await flush();
    handle.markNavigating();
    stack.close("a");
    await flush();
    expect(go).not.toHaveBeenCalled();
  });
});
