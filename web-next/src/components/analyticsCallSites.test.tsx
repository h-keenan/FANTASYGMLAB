import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const trackUse = vi.fn();
const trackClientError = vi.fn();
const trackFeatureUse = vi.fn();
vi.mock("@/lib/analytics", () => ({
  trackUse: (...args: unknown[]) => trackUse(...args),
  trackClientError: (...args: unknown[]) => trackClientError(...args),
  trackFeatureUse: (...args: unknown[]) => trackFeatureUse(...args),
  trackPageView: vi.fn(),
}));

import { ErrorState } from "./ErrorState";
import { PremiumUpsellCard } from "./PremiumUpsellCard";
import { ReferralCard } from "./ReferralCard";
import { TradeHubFilters } from "./TradeHubFilters";
import GlobalError from "@/app/error";
import type { ReferralStatusResponse } from "@/lib/api";

beforeEach(() => {
  trackUse.mockClear();
  trackClientError.mockClear();
  trackFeatureUse.mockClear();
});

describe("analytics call sites", () => {
  it("PremiumUpsellCard records gate_seen on mount and upsell_tapped on click, keyed by kicker", () => {
    render(
      <PremiumUpsellCard kicker="Exposure" upsell={null} fallbackTitle="t" fallbackBody="b" bare />,
    );
    expect(trackUse).toHaveBeenCalledWith("exposure", "gate_seen", { tier: "free" });
    fireEvent.click(screen.getByText(/Upgrade/));
    expect(trackUse).toHaveBeenCalledWith("exposure", "upsell_tapped", { tier: "free" });
  });

  it("ErrorState reports a route_error with a coarse class only (never the message)", () => {
    render(<ErrorState message="The request timed out. Check your connection and try again." />);
    expect(trackClientError).toHaveBeenCalledWith("route_error", null, { status: 0 });
  });

  it("ErrorState reports an unclassified error without a status", () => {
    render(<ErrorState message="Something odd" />);
    expect(trackClientError).toHaveBeenCalledWith("route_error", null, { status: undefined });
  });

  it("app/error.tsx reports application_error for an uncaught render error", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const err = new TypeError("boom");
    render(<GlobalError error={err} reset={() => {}} />);
    expect(trackClientError).toHaveBeenCalledWith("application_error", err);
  });

  it("TradeHubFilters emits trade_hub_filters/filter_changed for a position pick", () => {
    const ideas = [
      { impact_tag: "buy_low", package: { send: [{ asset_type: "player", position: "RB" }], receive: [{ asset_type: "player", position: "WR" }] } },
      { impact_tag: "sell_high", package: { send: [{ asset_type: "player", position: "TE" }], receive: [{ asset_type: "player", position: "QB" }] } },
    ] as never;
    const onChange = vi.fn();
    render(<TradeHubFilters ideas={ideas} filter={{ impact: null, position: null }} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /^All/ }));
    expect(trackUse).toHaveBeenCalledWith(
      "trade_hub_filters",
      "filter_changed",
      expect.objectContaining({ props: expect.objectContaining({ item_kind: "position", result: "all" }) }),
    );
    expect(onChange).toHaveBeenCalled();
  });

  it("ReferralCard records referral_sent when the invite link is copied", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    const referral = {
      link: "https://fantasydesk.app/r/abc123",
      referrals_per_comp_month: 3,
      connected_count: 0,
      comp_months_granted: 0,
      max_comp_months: 6,
      comp_is_active: false,
      comp_until: null,
    } as ReferralStatusResponse;

    render(<ReferralCard referral={referral} error={null} onRetry={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Copy link/ }));
    await vi.waitFor(() => expect(writeText).toHaveBeenCalledWith(referral.link));

    expect(trackFeatureUse).toHaveBeenCalledWith(
      "referral_sent",
      expect.objectContaining({ dedupe: false, props: expect.objectContaining({ source_surface: "account" }) }),
    );
  });
});
