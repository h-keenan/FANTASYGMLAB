import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FreeLimitNote } from "./FreeLimitNote";

const auth = vi.hoisted(() => ({ isGuest: false }));
vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ isGuest: auth.isGuest }) }));

describe("FreeLimitNote", () => {
  beforeEach(() => {
    auth.isGuest = false;
  });

  it("shows the server's limit with an Upgrade link for a Free account", () => {
    render(<FreeLimitNote kind="cap" noun="GM Targets" limit={3} used={2} isPremium={false} />);
    expect(screen.getByText("Free: 2 of 3 GM Targets")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upgrade/ })).toHaveAttribute("href", "/premium");
  });

  it("asks a guest to create an account first", () => {
    auth.isGuest = true;
    render(<FreeLimitNote kind="cap" noun="GM Targets" limit={3} used={0} isPremium={false} />);
    expect(screen.getByRole("link", { name: /Create an account/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Upgrade/ })).not.toBeInTheDocument();
  });

  it("renders nothing for Premium or when the server sent no limit", () => {
    const { container, rerender } = render(<FreeLimitNote kind="cap" noun="x" limit={3} used={1} isPremium />);
    expect(container).toBeEmptyDOMElement();
    rerender(<FreeLimitNote kind="cap" noun="x" limit={undefined} used={1} isPremium={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
