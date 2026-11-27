import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformBadge } from "./PlatformBadge";
import { CONNECT_PLATFORMS } from "@/lib/connectFlow";

describe("PlatformBadge", () => {
  it("renders a token-colored monogram for every connect platform, with no raw hex", () => {
    for (const p of CONNECT_PLATFORMS) {
      const { unmount } = render(<PlatformBadge platform={p.key} />);
      const badge = screen.getByTestId(`platform-badge-${p.key}`);
      expect(badge).toHaveTextContent(p.label[0].toUpperCase());
      expect(badge.getAttribute("style")).toContain(`--color-platform-${p.key}`);
      expect(badge.getAttribute("style")).not.toMatch(/#[0-9a-f]{3,6}/i);
      unmount();
    }
  });
});
