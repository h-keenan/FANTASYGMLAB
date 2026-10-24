import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

function mockAuth(session: unknown) {
  vi.mocked(useAuth).mockReturnValue({ session, loading: false } as never);
}

describe("DesktopSidebar founder entry", () => {
  it("hides Founder Analytics for an ordinary account", () => {
    mockAuth({ user: { id: "u1", app_metadata: {} } });
    render(<DesktopSidebar />);
    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("ignores a client-editable user_metadata flag", () => {
    mockAuth({ user: { id: "u1", app_metadata: {}, user_metadata: { founder_ops: true } } });
    render(<DesktopSidebar />);
    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("shows a link to /founder-analytics when app_metadata.founder_ops is true", () => {
    mockAuth({ user: { id: "f1", app_metadata: { founder_ops: true } } });
    render(<DesktopSidebar />);
    expect(screen.getByText("Founder Analytics").closest("a")).toHaveAttribute("href", "/founder-analytics");
  });
});
