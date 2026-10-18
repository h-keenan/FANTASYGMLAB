import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInForm } from "./SignInForm";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

function fillAgeGate() {
  fireEvent.change(screen.getByLabelText("Birth month"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Birth day"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Birth year"), { target: { value: "1990" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm date of birth" }));
}

// coridian_, 2026-10-18: "Redo the entire auth create account page... Just
// an email to get started" — step 1 is email-only; every other field
// (password, the sign-in/create-account toggle, the age gate) only
// appears after continuing past it.
function continuePastEmailStep(email: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

describe("SignInForm", () => {
  const signIn = vi.fn();
  const signUp = vi.fn();

  beforeEach(() => {
    signIn.mockReset();
    signUp.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      session: null,
      loading: false,
      signIn,
      signUp,
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      isGuest: false,
    });
  });

  it("shows only an email field until Continue is pressed", () => {
    render(<SignInForm onSignedIn={vi.fn()} />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  it("shows a dedicated, unmissable Check your email screen when confirmation is still pending", async () => {
    signUp.mockResolvedValue({ error: null, signedIn: false });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("new@example.com");
    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(signUp).toHaveBeenCalledWith("new@example.com", "password1"));
    expect(onSignedIn).not.toHaveBeenCalled();
    // coridian_, 2026-10-18: "I create an account. It doesn't say
    // anything" — a small text notice folded back into the sign-in form
    // was too easy to miss; this is now its own full screen.
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText(/new@example\.com/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  // coridian_, 2026-10-18: root cause of "create account... it just says
  // invalid" — Supabase's anti-enumeration signUp response for an
  // ALREADY-registered email is indistinguishable from "needs
  // confirmation" except for an empty `identities` array. AuthContext now
  // surfaces a real, specific error for this case instead of silently
  // treating it as "check your email."
  it("surfaces a clear error when signUp returns Supabase's already-registered signal", async () => {
    signUp.mockResolvedValue({
      error: "An account with this email already exists. Try signing in instead.",
      signedIn: false,
    });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("already@example.com");
    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("An account with this email already exists. Try signing in instead.")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(screen.queryByRole("heading", { name: "Check your email" })).not.toBeInTheDocument();
  });

  it("calls onSignedIn immediately after sign-up when the project auto-confirms email", async () => {
    signUp.mockResolvedValue({ error: null, signedIn: true });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("new@example.com");
    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Check your email to confirm your account/)).not.toBeInTheDocument();
  });

  it("calls onSignedIn after a successful sign-in", async () => {
    signIn.mockResolvedValue({ error: null });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("existing@example.com");
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(signIn).toHaveBeenCalledWith("existing@example.com", "password1");
  });

  it("surfaces a sign-up error instead of the confirmation notice", async () => {
    signUp.mockResolvedValue({ error: "Email already registered" });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("dupe@example.com");
    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(screen.queryByText(/Check your email to confirm/)).not.toBeInTheDocument();
  });

  it("goes back to the email step without losing the typed email", () => {
    render(<SignInForm onSignedIn={vi.fn()} />);

    continuePastEmailStep("back@example.com");
    expect(screen.getByText("← back@example.com")).toBeInTheDocument();

    fireEvent.click(screen.getByText("← back@example.com"));
    expect(screen.getByLabelText("Email")).toHaveValue("back@example.com");
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
  });
});
