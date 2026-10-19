import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SignInForm } from "./SignInForm";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

async function fillAgeGate() {
  // Appears asynchronously here — signIn's mocked promise must resolve
  // and the resulting setNeedsAgeGate(true) must flush before this field
  // exists in the DOM.
  fireEvent.change(await screen.findByLabelText("Birth month"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Birth day"), { target: { value: "1" } });
  fireEvent.change(screen.getByLabelText("Birth year"), { target: { value: "1990" } });
  fireEvent.click(screen.getByRole("button", { name: "Confirm date of birth" }));
}

// coridian_, 2026-10-18: "Redo the entire auth create account page... Just
// an email to get started" — step 1 is email-only; every other field
// (password, the age gate) only appears after continuing past it.
function continuePastEmailStep(email: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

function enterPasswordAndContinue(password: string) {
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
}

// Zach, 2026-10-18, all caps: "EMAIL AUTH STILL FUCKING BROKEN, I PUT THE
// EMAIL IN, THEN IT ASKS ME TO SIGN IN OR CREATE ACCOUNT WHEN THAT SHOULD
// BE AUTOMATICALLY DONE." There is no more sign-in/create-account choice
// at all — every test below drives the single unified flow: attempt
// signIn, and only on failure fall back to signUp.
describe("SignInForm", () => {
  const signIn = vi.fn();
  const signUp = vi.fn();
  const signInWithOAuth = vi.fn();

  beforeEach(() => {
    signIn.mockReset();
    signUp.mockReset();
    signInWithOAuth.mockReset();
    vi.mocked(useAuth).mockReturnValue({
      session: null,
      loading: false,
      signIn,
      signUp,
      signInWithOAuth,
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      deleteAccount: vi.fn(),
      isGuest: false,
    });
  });

  it("shows only an email field until Continue is pressed", () => {
    render(<SignInForm onSignedIn={vi.fn()} />);

    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.queryByLabelText("Password")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeInTheDocument();
  });

  // Google/Apple both enabled and verified working in Supabase, 2026-10-18.
  it("offers Google and Apple sign-in alongside email, on the very first screen", async () => {
    signInWithOAuth.mockResolvedValue({ error: null });
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));
    await waitFor(() => expect(signInWithOAuth).toHaveBeenCalledWith("google"));
  });

  it("calls signInWithOAuth for Apple too", async () => {
    signInWithOAuth.mockResolvedValue({ error: null });
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with Apple" }));
    await waitFor(() => expect(signInWithOAuth).toHaveBeenCalledWith("apple"));
  });

  it("shows the OAuth error inline instead of silently failing", async () => {
    signInWithOAuth.mockResolvedValue({ error: "Provider not configured" });
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Continue with Google" }));

    expect(await screen.findByText("Provider not configured")).toBeInTheDocument();
  });

  it("signs in immediately on a correct password, with no sign-in/create-account choice shown at all", async () => {
    signIn.mockResolvedValue({ error: null });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("existing@example.com");
    expect(screen.queryByRole("tab", { name: "Sign in" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "Create account" })).not.toBeInTheDocument();
    enterPasswordAndContinue("password1");

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(signIn).toHaveBeenCalledWith("existing@example.com", "password1");
    expect(signUp).not.toHaveBeenCalled();
  });

  it("falls back to signUp only after signIn fails, confirming age first", async () => {
    signIn.mockResolvedValue({ error: "Invalid login credentials" });
    signUp.mockResolvedValue({ error: null, signedIn: true });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("new@example.com");
    enterPasswordAndContinue("password1");

    await waitFor(() => expect(signIn).toHaveBeenCalledWith("new@example.com", "password1"));
    // Age confirmation only appears once signIn has actually failed — an
    // existing user who gets their password right never sees it.
    expect(await screen.findByLabelText("Birth month")).toBeInTheDocument();
    expect(signUp).not.toHaveBeenCalled();

    await fillAgeGate();

    await waitFor(() => expect(signUp).toHaveBeenCalledWith("new@example.com", "password1"));
    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
  });

  it("shows a dedicated, unmissable Check your email screen when confirmation is still pending", async () => {
    signIn.mockResolvedValue({ error: "Invalid login credentials" });
    signUp.mockResolvedValue({ error: null, signedIn: false });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("new@example.com");
    enterPasswordAndContinue("password1");
    await fillAgeGate();

    await waitFor(() => expect(signUp).toHaveBeenCalledWith("new@example.com", "password1"));
    expect(onSignedIn).not.toHaveBeenCalled();
    // coridian_, 2026-10-18: "I create an account. It doesn't say
    // anything" — a small text notice folded back into the sign-in form
    // was too easy to miss; this is now its own full screen.
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeInTheDocument();
    expect(screen.getByText(/new@example\.com/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Back to sign in" }));
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
  });

  // coridian_, 2026-10-18: root cause of "create account... it just says
  // invalid" — Supabase's anti-enumeration signUp response for an
  // ALREADY-registered email is indistinguishable from "needs
  // confirmation" except for an empty `identities` array. That same signal
  // now means something more specific here: signIn already failed first,
  // so "already exists" means the real password was wrong, not missing.
  it("reports a wrong password (not a generic error) when signUp's already-exists signal fires after a failed sign-in", async () => {
    signIn.mockResolvedValue({ error: "Invalid login credentials" });
    signUp.mockResolvedValue({
      error: "An account with this email already exists. Try signing in instead.",
      signedIn: false,
    });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("already@example.com");
    enterPasswordAndContinue("wrong-password");
    await fillAgeGate();

    expect(await screen.findByText("Incorrect password. Try again.")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(screen.queryByRole("heading", { name: "Check your email" })).not.toBeInTheDocument();
  });

  it("surfaces a real signUp error (not the confirmation notice) when it isn't the already-exists case", async () => {
    signIn.mockResolvedValue({ error: "Invalid login credentials" });
    signUp.mockResolvedValue({ error: "Password should be at least 6 characters", signedIn: false });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    continuePastEmailStep("dupe@example.com");
    enterPasswordAndContinue("short1");
    await fillAgeGate();

    expect(await screen.findByText("Password should be at least 6 characters")).toBeInTheDocument();
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
