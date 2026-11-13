import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Sheet } from "./Sheet";

function Harness() {
  const [a, setA] = useState(false);
  const [b, setB] = useState(false);
  return (
    <div>
      <button onClick={() => setA(true)}>open a</button>
      <Sheet open={a} onClose={() => setA(false)} title="Sheet A">
        <button onClick={() => setB(true)}>open b</button>
      </Sheet>
      <Sheet open={b} onClose={() => setB(false)} title="Sheet B">
        <p>second</p>
      </Sheet>
    </div>
  );
}

describe("Sheet", () => {
  it("renders nothing while closed", () => {
    render(
      <Sheet open={false} onClose={() => {}} title="T">
        <p>body</p>
      </Sheet>,
    );
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("portals a labelled modal dialog to body and locks scroll", () => {
    const { baseElement, unmount } = render(
      <Sheet open onClose={() => {}} title="Hello" description="Sub">
        <p>body</p>
      </Sheet>,
    );
    const dialog = screen.getByRole("dialog", { name: "Hello" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("Sub");
    expect(dialog.closest(".ui-sheet-backdrop")?.parentElement).toBe(baseElement);
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).not.toBe("hidden");
  });

  it("closes on Escape, on the close button and on a backdrop press, not on a body press", () => {
    const onClose = vi.fn();
    render(
      <Sheet open onClose={onClose} title="T">
        <p>body</p>
      </Sheet>,
    );
    fireEvent.mouseDown(screen.getByText("body"));
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    fireEvent.click(screen.getByRole("button", { name: "Close T" }));
    fireEvent.mouseDown(document.querySelector(".ui-sheet-backdrop")!);
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("moves focus in on open and returns it to the trigger on close", () => {
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "open a" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole("button", { name: "Close Sheet A" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("traps Tab inside the dialog", () => {
    render(
      <Sheet open onClose={() => {}} title="T">
        <button>one</button>
        <button>two</button>
      </Sheet>,
    );
    screen.getByRole("button", { name: "two" }).focus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Tab" });
    expect(screen.getByRole("button", { name: "Close T" })).toHaveFocus();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Tab", shiftKey: true });
    expect(screen.getByRole("button", { name: "two" })).toHaveFocus();
  });

  it("never stacks: a second sheet hides the first, and closing it restores the first", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: "open a" }));
    fireEvent.click(screen.getByRole("button", { name: "open b" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: "Sheet B" })).toBeVisible();
    expect(screen.queryByRole("dialog", { name: "Sheet A" })).toBeNull();
    fireEvent.keyDown(screen.getByRole("dialog", { name: "Sheet B" }), { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Sheet A" })).toBeVisible();
  });
});
