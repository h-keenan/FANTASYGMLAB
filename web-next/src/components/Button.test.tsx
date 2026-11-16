import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "@/components/Button";

describe("Button disabledReason", () => {
  it("shows the reason under a disabled button and links it with aria-describedby", () => {
    render(<Button disabled disabledReason="Pick one to continue">Continue</Button>);
    const reason = screen.getByText("Pick one to continue");
    expect(screen.getByRole("button", { name: "Continue" })).toHaveAttribute("aria-describedby", reason.id);
  });

  it("shows nothing once the button is enabled", () => {
    render(<Button disabledReason="Pick one to continue">Continue</Button>);
    expect(screen.queryByText("Pick one to continue")).toBeNull();
  });
});
