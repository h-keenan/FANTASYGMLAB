import { act, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { getPillState, resetPillStore, setPillBarPresent } from "./bottomPillStore";
import { useBottomPillContext } from "./useBottomPillContext";

function Page({ id = "team" }: { id?: string }) {
  const owns = useBottomPillContext({ id, label: "T", tabs: [{ key: "a", label: "A" }], activeKey: "a", onSelect: () => {} });
  return <span data-testid="owns">{String(owns)}</span>;
}

describe("useBottomPillContext", () => {
  beforeEach(() => {
    resetPillStore();
  });
  it("registers on mount, clears shortly after unmount", async () => {
    const { unmount } = render(<Page />);
    expect(getPillState().ctx?.id).toBe("team");
    unmount();
    await act(async () => { await new Promise((r) => setTimeout(r, 350)); });
    expect(getPillState().ctx).toBeNull();
  });
  it("tells the page to drop its own tab row only while the pill bar is on screen", () => {
    render(<Page />);
    expect(screen.getByTestId("owns")).toHaveTextContent("false");
    act(() => setPillBarPresent(true));
    expect(screen.getByTestId("owns")).toHaveTextContent("true");
    act(() => setPillBarPresent(false));
    expect(screen.getByTestId("owns")).toHaveTextContent("false");
  });
});
