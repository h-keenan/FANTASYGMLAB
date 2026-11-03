import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { FeaturesContent } from "./FeaturesContent";
import { FEATURE_GROUPS, FEATURE_ITEMS } from "@/lib/featureCatalog";

const LEAGUE = { id: "L1", name: "Test League" };

describe("FeaturesContent", () => {
  it("renders every group and every feature as a link for the current league", () => {
    render(<FeaturesContent league={LEAGUE} isPro={true} />);
    for (const group of FEATURE_GROUPS) expect(screen.getByRole("heading", { name: group.title })).toBeInTheDocument();
    for (const item of FEATURE_ITEMS) expect(screen.getByTestId(`feature-${item.id}`)).toHaveAttribute("href");
    expect(screen.getByTestId("feature-waivers")).toHaveAttribute("href", "/waivers/L1?name=Test%20League");
    expect(screen.getByTestId("feature-news")).toHaveAttribute("href", "/news");
    expect(screen.getByTestId("features-subtitle")).toHaveTextContent("Test League");
  });

  it("marks only the Pro-gated features, and only for a Free account", () => {
    const { unmount } = render(<FeaturesContent league={LEAGUE} isPro={false} />);
    for (const item of FEATURE_ITEMS) {
      const marker = within(screen.getByTestId(`feature-${item.id}`)).queryByTestId("nav-pro-marker");
      expect(marker !== null, item.id).toBe(Boolean(item.pro));
    }
    unmount();
    render(<FeaturesContent league={LEAGUE} isPro={true} />);
    expect(screen.queryByTestId("nav-pro-marker")).toBeNull();
  });

  it("shows no Pro markers while the plan is unknown", () => {
    render(<FeaturesContent league={LEAGUE} isPro={null} />);
    expect(screen.queryByTestId("nav-pro-marker")).toBeNull();
  });

  it("sends league tools to Home when no league is known", () => {
    render(<FeaturesContent league={null} isPro={true} />);
    expect(screen.getByTestId("feature-waivers")).toHaveAttribute("href", "/");
    expect(screen.getByTestId("feature-portfolio")).toHaveAttribute("href", "/portfolio");
    expect(screen.getByTestId("features-subtitle")).toHaveTextContent("Pick a league");
  });
});
