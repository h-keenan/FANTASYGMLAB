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
    const short = screen.getByText("S. Barkley");
    expect(short).toHaveAttribute("aria-hidden", "true");
    const el = short.parentElement as HTMLElement;
    expect(el.getAttribute("title")).toBe("Saquon Barkley");
    // WCAG 2.5.3: sighted users see the short form, assistive tech reads the full name.
    expect(screen.getByText("Saquon Barkley")).toHaveClass("sr-only");
    expect(el.className).not.toContain("truncate");
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

  it("when even the short form overflows it steps the font down, then wraps; it never truncates", () => {
    setWidths(300, 40);
    render(<PlayerName name="Jonathan Brisker" />);
    const short = screen.getByText("J. Brisker");
    const el = short.closest("[data-player-name-stage]") as HTMLElement;
    expect(el.getAttribute("data-player-name-stage")).toBe("4");
    expect(el.className).toContain("whitespace-normal");
    expect(el.className).not.toMatch(/truncate|ellipsis|line-clamp/);
    expect(short.getAttribute("style")).toContain("font-size: 0.85em");
  });
});
