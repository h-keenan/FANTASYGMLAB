import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AppStoreModules } from "./AppStoreModules";
import { APP_STORE_LINKS } from "@/lib/appStoreLinks";

const NONE = { appStoreUrl: null, playStoreUrl: null, appStoreBadgeSrc: null, playStoreBadgeSrc: null };

describe("AppStoreModules", () => {
  it("ships with both stores unset (neither app is publicly live yet)", () => {
    expect(APP_STORE_LINKS.appStoreUrl).toBeNull();
    expect(APP_STORE_LINKS.playStoreUrl).toBeNull();
  });

  it("renders both slots as Coming soon with no link when URLs are null", () => {
    const { container } = render(<AppStoreModules links={NONE} />);

    const appStore = screen.getByRole("group", { name: /App Store app for iPhone: coming soon/ });
    const googlePlay = screen.getByRole("group", { name: /Google Play app for Android: coming soon/ });
    expect(within(appStore).getByText("Coming soon")).toBeInTheDocument();
    expect(within(googlePlay).getByText("Coming soon")).toBeInTheDocument();
    expect(container.querySelector("a")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    // No official badge artwork in the coming-soon state.
    expect(container.querySelector("img")).toBeNull();
  });

  it("ignores a badge src while its URL is still null", () => {
    const { container } = render(<AppStoreModules links={{ ...NONE, appStoreBadgeSrc: "/badges/app-store.svg" }} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });

  it("turns a slot into a real link once its URL is set, leaving the other coming soon", () => {
    render(<AppStoreModules links={{ ...NONE, appStoreUrl: "https://apps.apple.com/app/id123" }} />);

    const link = screen.getByRole("link", { name: "Download on the App Store" });
    expect(link).toHaveAttribute("href", "https://apps.apple.com/app/id123");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByRole("group", { name: /Google Play app for Android: coming soon/ })).toBeInTheDocument();
  });

  it("links both stores when both URLs are set", () => {
    render(
      <AppStoreModules
        links={{
          ...NONE,
          appStoreUrl: "https://apps.apple.com/app/id123",
          playStoreUrl: "https://play.google.com/store/apps/details?id=com.example",
        }}
      />,
    );
    expect(screen.getByRole("link", { name: "Get it on Google Play" })).toHaveAttribute(
      "href",
      "https://play.google.com/store/apps/details?id=com.example",
    );
    expect(screen.getAllByRole("link")).toHaveLength(2);
    expect(screen.queryByText("Coming soon")).toBeNull();
  });

  it("renders the official badge artwork inside the link once both URL and badge are set", () => {
    render(
      <AppStoreModules
        links={{
          ...NONE,
          playStoreUrl: "https://play.google.com/store/apps/details?id=x",
          playStoreBadgeSrc: "/badges/google-play.png",
        }}
      />,
    );
    const link = screen.getByRole("link", { name: "Get it on Google Play" });
    expect(within(link).getByRole("img", { name: "Get it on Google Play" })).toHaveAttribute(
      "src",
      "/badges/google-play.png",
    );
  });
});
