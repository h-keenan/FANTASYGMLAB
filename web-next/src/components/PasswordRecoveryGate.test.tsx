import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PasswordRecoveryGate } from "./PasswordRecoveryGate";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("PasswordRecoveryGate", () => {
  const completeRecovery = vi.fn();
  const signOut = vi.fn();

  beforeEach(() => {
    completeRecovery.mockReset();
    signOut.mockReset();
  });

  function mockAuth(recoveryPending: boolean) {
    vi.mocked(useAuth).mockReturnValue({
      session: null,
      loading: false,
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInAsGuest: vi.fn(),
      signOut,
      deleteAccount: vi.fn(),
      upgradeGuestWithEmail: vi.fn(),
      callbackNotice: null,
      isGuest: false,
      resetPassword: vi.fn(),
      recoveryPending,
      completeRecovery,
    });
  }

  it("renders nothing when no recovery is pending", () => {
    mockAuth(false);
    const { container } = render(<PasswordRecoveryGate />);
    expect(container).toBeEmptyDOMElement();
  });

  it("blocks with a set-new-password form when a recovery is pending", () => {
    mockAuth(true);
    render(<PasswordRecoveryGate />);
    expect(screen.getByRole("heading", { name: "Set a new password" })).toBeInTheDocument();
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm new password")).toBeInTheDocument();
  });

  it("rejects mismatched passwords locally, without calling completeRecovery", async () => {
    mockAuth(true);
    render(<PasswordRecoveryGate />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "newpass1" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "different1" } });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByText("Passwords don't match.")).toBeInTheDocument();
    expect(completeRecovery).not.toHaveBeenCalled();
  });

  it("submits the new password when both fields match", async () => {
    completeRecovery.mockResolvedValue({ error: null });
    mockAuth(true);
    render(<PasswordRecoveryGate />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "newpass1" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "newpass1" } });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    await waitFor(() => expect(completeRecovery).toHaveBeenCalledWith("newpass1"));
  });

  it("shows a real error from completeRecovery instead of silently failing", async () => {
    completeRecovery.mockResolvedValue({ error: "Password should be at least 6 characters" });
    mockAuth(true);
    render(<PasswordRecoveryGate />);
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "short" } });
    fireEvent.click(screen.getByRole("button", { name: "Set new password" }));

    expect(await screen.findByText("Password should be at least 6 characters")).toBeInTheDocument();
  });

  it("offers an escape hatch that signs out instead of forcing completion", () => {
    mockAuth(true);
    render(<PasswordRecoveryGate />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel and sign out" }));
    expect(signOut).toHaveBeenCalledTimes(1);
  });
});
