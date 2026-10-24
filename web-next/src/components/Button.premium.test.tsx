import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button, ButtonLink } from "@/components/Button";

function luminance(hex: string) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("premium Button variant", () => {
  it("renders gold fill with the glow class, keeping its accessible name", () => {
    render(<Button variant="premium">Manage Billing</Button>);
    const btn = screen.getByRole("button", { name: "Manage Billing" });
    expect(btn.className).toContain("premium-glow");
    expect(btn.style.background).toContain("--color-premium-fill");
  });

  it("drops the gold fill when disabled and renders as a link too", () => {
    render(
      <>
        <Button variant="premium" disabled>
          Subscribe
        </Button>
        <ButtonLink href="/premium" variant="premium">
          Upgrade →
        </ButtonLink>
      </>,
    );
    expect(screen.getByRole("button", { name: "Subscribe" }).style.background).toContain("--color-surface-muted");
    expect(screen.getByRole("link", { name: "Upgrade →" }).className).toContain("premium-glow");
  });

  it("keeps ink on gold at AA in both themes (tokens in globals.css)", () => {
    const css = readFileSync(path.join(__dirname, "../app/globals.css"), "utf8");
    const fills = [...css.matchAll(/--color-premium-fill:\s*(#[0-9a-f]{6})/gi)].map((m) => m[1]);
    const inks = [...css.matchAll(/--color-on-premium:\s*(#[0-9a-f]{6})/gi)].map((m) => m[1]);
    expect(fills.length).toBeGreaterThanOrEqual(2);
    expect(inks.length).toBe(fills.length);
    fills.forEach((fill, i) => expect(contrast(fill, inks[i])).toBeGreaterThanOrEqual(7));
  });
});
