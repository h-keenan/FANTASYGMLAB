import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AgeGate } from "./AgeGate";

function fillAndSubmit(month: string, day: string, year: string) {
  fireEvent.change(screen.getByLabelText("Birth month"), { target: { value: month } });
  fireEvent.change(screen.getByLabelText("Birth day"), { target: { value: day } });
  fireEvent.change(screen.getByLabelText("Birth year"), { target: { value: year } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm date of birth" }));
}

describe("AgeGate", () => {
  it("calls onConfirmed for a valid adult date of birth", () => {
    const onConfirmed = vi.fn();
    render(<AgeGate onConfirmed={onConfirmed} />);

    fillAndSubmit("1", "1", "1990");

    expect(onConfirmed).toHaveBeenCalledTimes(1);
  });

  it("blocks an under-13 date of birth instead of confirming", () => {
    const onConfirmed = vi.fn();
    render(<AgeGate onConfirmed={onConfirmed} />);
    const thisYear = new Date().getFullYear();

    fillAndSubmit("1", "1", String(thisYear - 10));

    expect(onConfirmed).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent(/must be at least/i);
  });

  // The real bug: SignInForm nests this inside its own <form> during
  // create-account — without stopPropagation, confirming a birthdate also
  // bubbles the submit event into that outer form, silently firing a
  // signUp/signIn call with blank email/password before the user has
  // typed anything.
  it("does not let its submit bubble into an ancestor form", () => {
    const onConfirmed = vi.fn();
    const outerSubmit = vi.fn((event: React.FormEvent) => event.preventDefault());
    render(
      <form onSubmit={outerSubmit}>
        <AgeGate onConfirmed={onConfirmed} />
      </form>,
    );

    fillAndSubmit("1", "1", "1990");

    expect(onConfirmed).toHaveBeenCalledTimes(1);
    expect(outerSubmit).not.toHaveBeenCalled();
  });
});
