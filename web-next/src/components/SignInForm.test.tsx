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
      isGuest: false,
    });
  });

  it("does not call onSignedIn after a successful sign-up when email confirmation is still pending", async () => {
    signUp.mockResolvedValue({ error: null, signedIn: false });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(signUp).toHaveBeenCalledWith("new@example.com", "password1"));
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(await screen.findByText(/Check your email to confirm your account/)).toBeInTheDocument();
    // Flipped back to the sign-in form, not left stuck on create-account.
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("calls onSignedIn immediately after sign-up when the project auto-confirms email", async () => {
    signUp.mockResolvedValue({ error: null, signedIn: true });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(/Check your email to confirm your account/)).not.toBeInTheDocument();
  });

  it("calls onSignedIn after a successful sign-in", async () => {
    signIn.mockResolvedValue({ error: null });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "existing@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1));
  });

  it("surfaces a sign-up error instead of the confirmation notice", async () => {
    signUp.mockResolvedValue({ error: "Email already registered" });
    const onSignedIn = vi.fn();
    render(<SignInForm onSignedIn={onSignedIn} />);

    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    fillAgeGate();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "dupe@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password1" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Email already registered")).toBeInTheDocument();
    expect(onSignedIn).not.toHaveBeenCalled();
    expect(screen.queryByText(/Check your email to confirm/)).not.toBeInTheDocument();
  });

  it("shows Google/Apple buttons immediately in sign-in mode", () => {
    render(<SignInForm onSignedIn={vi.fn()} />);

    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /continue with apple/i })).toBeInTheDocument();
  });

  it("gates Google/Apple buttons behind the age gate in create-account mode", () => {
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "New here? Create account" }));
    expect(screen.queryByRole("button", { name: /continue with google/i })).not.toBeInTheDocument();

    fillAgeGate();
    expect(screen.getByRole("button", { name: /continue with google/i })).toBeInTheDocument();
  });

  it("calls signInWithOAuth with the right provider", async () => {
    signInWithOAuth.mockResolvedValue({ error: null });
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /continue with apple/i }));

    await waitFor(() => expect(signInWithOAuth).toHaveBeenCalledWith("apple"));
  });

  it("surfaces an OAuth error instead of silently doing nothing", async () => {
    signInWithOAuth.mockResolvedValue({ error: "Unsupported provider: provider is not enabled" });
    render(<SignInForm onSignedIn={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /continue with google/i }));

    expect(await screen.findByText(/unsupported provider/i)).toBeInTheDocument();
  });
});
