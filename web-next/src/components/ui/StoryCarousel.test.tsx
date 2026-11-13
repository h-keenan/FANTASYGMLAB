import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { overlayStack } from "@/lib/overlayStack";
import { StoryCarousel, type StoryPage } from "./StoryCarousel";

const pages: StoryPage[] = [
  { key: "a", label: "First", content: <p>page A</p> },
  { key: "b", label: "Second", content: <button type="button">inner action</button>, footer: <button type="button">Fix it</button> },
  { key: "c", label: "Third", content: <p>page C</p>, footer: <button type="button">Finish</button> },
];

describe("StoryCarousel", () => {
  it("is a labeled modal dialog with one progress segment per page and a close X", () => {
    render(<StoryCarousel title="Week 4 recap" pages={pages} onClose={() => {}} />);
    expect(screen.getByRole("dialog", { name: "Week 4 recap" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "1");
    expect(screen.getAllByRole("button", { name: /^Go to / })).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Close Week 4 recap" })).toBeInTheDocument();
    expect(screen.getByText("page A")).toBeInTheDocument();
  });

  it("arrow keys and the arrow buttons move between pages; Escape and the X close", () => {
    const onClose = vi.fn();
    render(<StoryCarousel title="Recap" pages={pages} onClose={onClose} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    expect(screen.getByRole("button", { name: "Fix it" })).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "ArrowLeft" });
    expect(screen.getByText("page A")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(screen.getByText("page C")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Next page" })).toBeNull(); // the last page ends in its own CTA
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Close Recap" }));
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it("tapping the stage advances, tapping a control inside never flips the page, a swipe goes back and forth", () => {
    render(<StoryCarousel title="Recap" pages={pages} onClose={() => {}} />);
    const stage = screen.getByTestId("story-stage");
    fireEvent.pointerDown(stage, { clientX: 300, clientY: 200 });
    fireEvent.pointerUp(stage, { clientX: 300, clientY: 200 });
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    const inner = screen.getByRole("button", { name: "inner action" });
    fireEvent.pointerDown(inner, { clientX: 300, clientY: 200 });
    fireEvent.pointerUp(inner, { clientX: 300, clientY: 200 });
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    fireEvent.pointerDown(stage, { clientX: 200, clientY: 200 });
    fireEvent.pointerUp(stage, { clientX: 100, clientY: 205 }); // swipe left = next
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "3");
    fireEvent.pointerDown(stage, { clientX: 100, clientY: 200 });
    fireEvent.pointerUp(stage, { clientX: 220, clientY: 200 }); // swipe right = back
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
  });

  it("follows the overlay rule: a card opened on top hides it (state kept), Back returns to the same page, the X closes everything", () => {
    const onClose = vi.fn();
    render(<StoryCarousel title="Recap" pages={pages} onClose={onClose} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "ArrowRight" });
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2");
    act(() => {
      overlayStack.open({ id: "card", kind: "sheet", title: "Player card", dismiss: () => overlayStack.close("card") });
    });
    expect(screen.getByTestId("story-carousel")).toHaveAttribute("hidden");
    act(() => {
      overlayStack.close("card");
    });
    expect(screen.getByTestId("story-carousel")).not.toHaveAttribute("hidden");
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "2"); // same page
    fireEvent.click(screen.getByRole("button", { name: "Close Recap" }));
    expect(onClose).toHaveBeenCalled();
  });
});
