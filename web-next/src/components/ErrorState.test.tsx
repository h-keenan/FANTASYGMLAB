import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("shows the message and calls onRetry when the button is pressed", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="The request timed out. Check your connection and try again." onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("The request timed out");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
