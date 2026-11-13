import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ConfirmInPlace } from "./ConfirmInPlace";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("ConfirmInPlace tap-again (button)", () => {
  it("does nothing on the first tap, acts on the second", async () => {
    const onConfirm = vi.fn();
    render(<ConfirmInPlace label="Sign out" onConfirm={onConfirm} />);
    const button = screen.getByRole("button", { name: /sign out/i });
    fireEvent.click(button);
    expect(onConfirm).not.toHaveBeenCalled();
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("status")).toHaveTextContent("Tap again to confirm");
    await act(async () => {
      fireEvent.click(button);
    });
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("reverts by itself after 4 seconds", () => {
    const onConfirm = vi.fn();
    render(<ConfirmInPlace label="Sign out" onConfirm={onConfirm} />);
    const button = screen.getByRole("button", { name: /sign out/i });
    fireEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(button).not.toHaveAttribute("aria-expanded");
    fireEvent.click(button);
    expect(onConfirm).not.toHaveBeenCalled();
  });
});

describe("ConfirmInPlace ask (icon / row)", () => {
  it("asks, focuses the safe choice, and Keep cancels without acting", () => {
    const onConfirm = vi.fn();
    render(<ConfirmInPlace variant="icon" label="Delete game" prompt="Delete this game?" confirmLabel="Delete" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Delete game" }));
    expect(screen.getByRole("group", { name: "Delete this game?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep" })).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.queryByRole("group")).toBeNull();
    expect(screen.getByRole("button", { name: "Delete game" })).toHaveFocus();
  });

  it("confirms, showing the working state until the promise settles", async () => {
    let resolve!: () => void;
    const onConfirm = vi.fn(() => new Promise<void>((r) => (resolve = r)));
    render(<ConfirmInPlace variant="row" label="Remove" prompt="Remove it?" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    });
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Keep" })).toBeDisabled();
    await act(async () => resolve());
    expect(screen.queryByRole("group")).toBeNull();
  });

  it("shows an error with Retry when the action fails, and retries", async () => {
    const onConfirm = vi.fn().mockRejectedValueOnce(new Error("x")).mockResolvedValueOnce(undefined);
    render(<ConfirmInPlace variant="row" label="Remove" prompt="Remove it?" errorText="Could not remove." onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    });
    expect(screen.getAllByText("Could not remove.").length).toBeGreaterThan(0);
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    });
    expect(onConfirm).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole("group")).toBeNull();
  });

  it("treats a false return as failure, and Escape cancels", async () => {
    const onConfirm = vi.fn(() => false);
    render(<ConfirmInPlace variant="row" label="Remove" prompt="Remove it?" onConfirm={onConfirm} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByRole("group")).toBeInTheDocument();
    fireEvent.keyDown(screen.getByRole("group"), { key: "Escape" });
    expect(screen.queryByRole("group")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await act(async () => {
      fireEvent.click(screen.getAllByRole("button", { name: "Remove" }).at(-1)!);
    });
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("plain ask mode renders a bare text trigger with the caller's own look", () => {
    render(<ConfirmInPlace plain variant="row" mode="ask" label="Remove" triggerClassName="my-link" prompt="Remove it?" onConfirm={() => {}} />);
    const trigger = screen.getByRole("button", { name: "Remove" });
    expect(trigger).toHaveClass("my-link");
    expect(trigger.className).not.toContain("px-4");
  });
});
