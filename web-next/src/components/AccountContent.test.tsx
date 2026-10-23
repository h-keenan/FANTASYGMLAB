import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccountContent } from "./AccountContent";
import type { MeResponse, PushCategory } from "@/lib/api";

function user(overrides: Partial<MeResponse["user"]>): MeResponse["user"] {
  return {
    id: "user-1",
    email: "gm@example.com",
    entitlement: "free",
    sleeper_username: "",
    profile_status: "ok",
    league_cap: 1,
    ...overrides,
  };
}

const ALL_CATEGORIES_ON: Record<PushCategory, boolean> = {
  top_priority: true,
  watch: true,
  recap: true,
  injury: true,
};

function renderContent(overrides: Partial<Parameters<typeof AccountContent>[0]> = {}) {
  const props: Parameters<typeof AccountContent>[0] = {
    user: user({}),
    communityOptedOut: false,
    onToggleCommunityOptOut: vi.fn(),
    pushCategories: ALL_CATEGORIES_ON,
    onTogglePushCategory: vi.fn(),
    referral: null,
    referralError: null,
    onRetryReferral: vi.fn(),
    onOpenBillingPortal: vi.fn().mockResolvedValue(undefined),
    onExportData: vi.fn().mockResolvedValue(undefined),
    onDeleteAccount: vi.fn().mockResolvedValue(undefined),
    onSignOut: vi.fn(),
    ...overrides,
  };
  render(<AccountContent {...props} />);
  return props;
}

describe("AccountContent", () => {
  it("shows identity: email, linked Sleeper username, and plan", () => {
    renderContent({ user: user({ email: "zach@example.com", sleeper_username: "zachgm", entitlement: "premium" }) });

    expect(screen.getByText("zach@example.com")).toBeInTheDocument();
    expect(screen.getByText("zachgm")).toBeInTheDocument();
    expect(screen.getByText("Premium")).toBeInTheDocument();
  });

  it("shows 'Not linked' when no Sleeper username is on the profile", () => {
    renderContent({ user: user({ sleeper_username: "" }) });
    expect(screen.getByText("Not linked")).toBeInTheDocument();
  });

  it("shows an Upgrade link (not Manage Billing) for a free account", () => {
    renderContent({ user: user({ entitlement: "free" }) });
    expect(screen.getByRole("link", { name: "Upgrade to Premium" })).toHaveAttribute("href", "/premium");
    expect(screen.queryByText("Manage Billing")).not.toBeInTheDocument();
  });

  it("shows the trial end date for a trialing account and hides a past one", () => {
    const future = new Date(Date.now() + 2 * 86400000).toISOString();
    renderContent({ user: user({ entitlement: "premium", trial_ends_at: future }) });
    expect(screen.getByText(/^Trial ends /)).toBeInTheDocument();
  });

  it("does not show a trial line when the end date has passed", () => {
    const past = new Date(Date.now() - 86400000).toISOString();
    renderContent({ user: user({ entitlement: "premium", trial_ends_at: past }) });
    expect(screen.queryByText(/^Trial ends /)).not.toBeInTheDocument();
  });

  it("shows Manage Billing (not an upgrade link) for a premium account and opens the portal", () => {
    const onOpenBillingPortal = vi.fn().mockResolvedValue(undefined);
    renderContent({ user: user({ entitlement: "premium" }), onOpenBillingPortal });

    expect(screen.queryByRole("link", { name: "Upgrade to Premium" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Manage Billing" }));
    expect(onOpenBillingPortal).toHaveBeenCalledTimes(1);
  });

  it("shows the Community Trade Feed opt-out toggle and calls onToggleCommunityOptOut with the flipped value", () => {
    const onToggleCommunityOptOut = vi.fn();
    renderContent({ communityOptedOut: false, onToggleCommunityOptOut });

    expect(screen.getByText("I don't want MY trades to appear in this feed")).toBeInTheDocument();
    const toggles = screen.getAllByRole("switch");
    const communityToggle = toggles[0];
    expect(communityToggle).toHaveAttribute("aria-checked", "false");

    fireEvent.click(communityToggle);
    expect(onToggleCommunityOptOut).toHaveBeenCalledWith(true);
  });

  it("renders all 4 push notification category toggles and calls onTogglePushCategory per-category", () => {
    const onTogglePushCategory = vi.fn();
    renderContent({ pushCategories: { ...ALL_CATEGORIES_ON, injury: false }, onTogglePushCategory });

    expect(screen.getByText("Top Priority moves")).toBeInTheDocument();
    expect(screen.getByText("Watch items")).toBeInTheDocument();
    expect(screen.getByText("Weekly recaps")).toBeInTheDocument();
    expect(screen.getByText("Injury updates")).toBeInTheDocument();

    const injuryRow = screen.getByText("Injury updates").closest("div")?.parentElement;
    const injuryToggle = injuryRow?.querySelector('[role="switch"]');
    expect(injuryToggle).toHaveAttribute("aria-checked", "false");
    expect(injuryToggle).toHaveTextContent("Off");

    fireEvent.click(injuryToggle as Element);
    expect(onTogglePushCategory).toHaveBeenCalledWith("injury", true);
  });

  it("hides the push notifications block entirely when pushCategories is null", () => {
    renderContent({ pushCategories: null });
    expect(screen.queryByText("Push notifications")).not.toBeInTheDocument();
  });

  it("calls onExportData when Export my data is clicked", () => {
    const onExportData = vi.fn().mockResolvedValue(undefined);
    renderContent({ onExportData });

    fireEvent.click(screen.getByRole("button", { name: "Export my data" }));
    expect(onExportData).toHaveBeenCalledTimes(1);
  });

  it("calls onSignOut when Sign out is clicked", () => {
    const onSignOut = vi.fn();
    renderContent({ onSignOut });

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("requires a second confirm click before calling onDeleteAccount, and Cancel backs out without calling it", () => {
    const onDeleteAccount = vi.fn().mockResolvedValue(undefined);
    renderContent({ onDeleteAccount });

    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    expect(onDeleteAccount).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Confirm delete" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("button", { name: "Confirm delete" })).not.toBeInTheDocument();
    expect(onDeleteAccount).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Delete account" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }));
    expect(onDeleteAccount).toHaveBeenCalledTimes(1);
  });
});

describe("AccountContent replay tour", () => {
  it("opens the feature tour from Account without a preference write", () => {
    renderContent();
    fireEvent.click(screen.getByRole("button", { name: "Replay the tour" }));
    expect(document.querySelector("[data-onboarding-root]")).not.toBeNull();
    expect(screen.queryByText("How much dynasty experience do you have?")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(document.querySelector("[data-onboarding-root]")).toBeNull();
  });
});
