import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SleeperImportForm } from "./SleeperImportForm";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      lookupSleeperLeagues: vi.fn(),
      linkSleeperUsername: vi.fn(),
      saveLeague: vi.fn(),
    },
  };
});

describe("SleeperImportForm", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "user-1" } } as never,
      loading: false,
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      isGuest: false,
    });
  });

  it("always shows an explanation of what Sleeper is, with a link to sleeper.com", () => {
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    expect(screen.getByText(/connects to your existing/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /create a free one at sleeper\.com/i })[0]).toHaveAttribute(
      "href",
      "https://sleeper.com",
    );
  });

  it("shows a sleeper.com signup CTA when the username genuinely has no Sleeper account", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: false,
      status: "user_not_found",
      username: "nobody",
      leagues: [],
      message: "No Sleeper account matched that username. Check spelling and try again.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "nobody" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/no sleeper account matched/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/don't have a sleeper account/i);
  });

  it("does not show the no-account CTA for an unrelated lookup failure", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: false,
      status: "no_eligible_leagues",
      username: "someone",
      leagues: [],
      message: "No eligible leagues found for that username.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).not.toHaveTextContent(/don't have a sleeper account/i);
  });
});
