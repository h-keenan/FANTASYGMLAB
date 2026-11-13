import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { PlayerName } from "@/components/PlayerName";

const proto = HTMLElement.prototype;
const origScroll = Object.getOwnPropertyDescriptor(proto, "scrollWidth");
const origClient = Object.getOwnPropertyDescriptor(proto, "clientWidth");

function setWidths(scroll: number, client: number) {
  Object.defineProperty(proto, "scrollWidth", { configurable: true, get: () => scroll });
  Object.defineProperty(proto, "clientWidth", { configurable: true, get: () => client });
}

afterEach(() => {
  if (origScroll) Object.defineProperty(proto, "scrollWidth", origScroll);
  else delete (proto as unknown as Record<string, unknown>).scrollWidth;
  if (origClient) Object.defineProperty(proto, "clientWidth", origClient);
  else delete (proto as unknown as Record<string, unknown>).clientWidth;
});

describe("PlayerName", () => {
  it("renders the full name when it fits", () => {
    setWidths(100, 140);
    render(<PlayerName name="Saquon Barkley" />);
    const el = screen.getByText("Saquon Barkley");
    expect(el.getAttribute("data-player-name")).toBe("full");
  });

  it("switches to initial + surname when the full name overflows, keeping the full name accessible", () => {
    setWidths(160, 90);
    render(<PlayerName name="Saquon Barkley" />);
    const el = screen.getByText("S. Barkley");
    expect(el.getAttribute("title")).toBe("Saquon Barkley");
    expect(el.getAttribute("aria-label")).toBe("Saquon Barkley");
    expect(el.className).toContain("truncate");
  });

  it("keeps suffixes and multi-word surnames when shortening", () => {
    setWidths(200, 90);
    const { unmount } = render(<PlayerName name="Michael Penix Jr." />);
    expect(screen.getByText("M. Penix Jr.")).toBeTruthy();
    unmount();
    render(<PlayerName name="Amon-Ra St. Brown" />);
    expect(screen.getByText("A. St. Brown")).toBeTruthy();
  });

  it("never shortens a name that cannot shrink (defense, mononym)", () => {
    setWidths(200, 90);
    render(<PlayerName name="Ravens D/ST" />);
    expect(screen.getByText("Ravens D/ST")).toBeTruthy();
  });

  it("renders nothing visible for an empty name without crashing", () => {
    setWidths(0, 0);
    const { container } = render(<PlayerName name={null} />);
    expect(container.textContent).toBe("");
  });
});
