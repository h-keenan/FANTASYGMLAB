import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";

import { SimSheet } from "@/components/SimGameParts";
import { Sheet } from "@/components/ui/Sheet";
import { overlayStack } from "@/lib/overlayStack";

function Flow() {
  const [a, setA] = useState(true);
  const [b, setB] = useState(false);
  return (
    <>
      <Sheet open={a} onClose={() => setA(false)} title="Trade picker">
        <input aria-label="search" defaultValue="" />
        <button onClick={() => setB(true)}>Open card</button>
      </Sheet>
      {b ? (
        <SimSheet title="Player card" onClose={() => setB(false)}>
          <p>card body</p>
        </SimSheet>
      ) : null}
    </>
  );
}

afterEach(() => overlayStack.closeAll());

describe("one pop-up at a time", () => {
  it("opening a pop-up from another replaces it on screen, keeps the first mounted with its state, and shows Back", () => {
    render(<Flow />);
    const input = screen.getByLabelText("search") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "kelce" } });
    fireEvent.click(screen.getByText("Open card"));
    // the picker is hidden (display:none) but still mounted with its typed text
    const picker = screen.getByLabelText("search").closest(".ui-sheet-backdrop") as HTMLElement;
    expect(picker.hidden).toBe(true);
    expect((screen.getByLabelText("search") as HTMLInputElement).value).toBe("kelce");
    expect(screen.getByText("card body")).toBeVisible();
    expect(screen.getByTestId("overlay-back")).toHaveTextContent("Back to Trade picker");
    // Back returns to the picker with its selection intact
    fireEvent.click(screen.getByTestId("overlay-back"));
    expect(screen.queryByText("card body")).toBeNull();
    expect((screen.getByLabelText("search").closest(".ui-sheet-backdrop") as HTMLElement).hidden).toBe(false);
    expect((screen.getByLabelText("search") as HTMLInputElement).value).toBe("kelce");
  });

  it("the X closes everything and returns to the page", () => {
    render(<Flow />);
    fireEvent.click(screen.getByText("Open card"));
    fireEvent.click(screen.getByRole("button", { name: "Close Player card" }));
    expect(screen.queryByText("card body")).toBeNull();
    expect(screen.queryByLabelText("search")).toBeNull();
    expect(overlayStack.size()).toBe(0);
  });

  it("the first pop-up has no Back button", () => {
    render(<Flow />);
    expect(screen.queryByTestId("overlay-back")).toBeNull();
  });
});
