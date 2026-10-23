import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExperienceLevelProvider } from "./ExperienceLevelContext";
import { AccountContent } from "@/components/AccountContent";
import { DashboardContent } from "@/components/DashboardContent";
import { TradeIdeaCardView } from "@/components/TradeIdeaCard";
import { api, type DashboardResponse, type DevicePreferencesResponse, type MeResponse, type TradeIdea } from "@/lib/api";
import { BEGINNER_HELP } from "@/lib/experienceCopy";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ session: { user: { id: "user-1" } } }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getDevicePreferences: vi.fn(),
      setExperienceLevel: vi.fn(),
    },
  };
});

function preferences(experience_level: DevicePreferencesResponse["experience_level"]): DevicePreferencesResponse {
  return { ok: true, ui_density: "guided", theme_mode: "dark", experience_level, last_league: null };
}

function withProvider(children: ReactNode) {
  return <ExperienceLevelProvider>{children}</ExperienceLevelProvider>;
}

const DASHBOARD: DashboardResponse = {
  ok: true,
  quiet: true,
  quiet_reason: "",
  reason: "",
  items: [],
  team_snapshot: {
    wins: 7,
    losses: 6,
    ties: 0,
    health_flag: "Stable",
    key_injuries_summary: "",
    top_injury_impact_summary: "",
    top_injury_impact_players: [],
    injured_starters: 0,
    average_age: 26.4,
    power_rank: 2,
    power_rank_tied: false,
    franchise_rank: 1,
    franchise_rank_tied: true,
    starter_rank: 3,
    starter_rank_tied: false,
    bench_rank: 5,
    bench_rank_tied: false,
  },
  entitlement: { is_premium: false, visible_count: 0, hidden_count: 0 },
};

const IDEA: TradeIdea = {
  partner_team_name: "Rival GM",
  partner_team_avatar_url: null,
  partner_team_archetype_label: "Rebuilding",
  partner_trade_tendency: "Neutral",
  rationale: "Clear value upgrade at a position of need.",
  trade_gain: 800,
  confidence_label: "Medium",
  market_realism_label: "Plausible",
  reasoning_tags: [],
  package: {
    send: [{ asset_type: "player", player_id: "a", name: "Sent Player", position: "RB", team: "SF", age: 27, score: 1200, tier: "starter" }],
    receive: [{ asset_type: "player", player_id: "b", name: "Got Player", position: "WR", team: "KC", age: 24, score: 2000, tier: "starter" }],
    value_edge: "+800",
    confidence: "Medium",
  },
  category: "Headline Recommendation",
  value_edge_band: "Favorable",
  impact_tag: "sell_high",
  landed_gm_target_player_ids: [],
  send_score: 1200,
  receive_score: 2000,
  recommendation_id: "rec-1",
};

const ME_USER: MeResponse["user"] = {
  id: "user-1",
  email: "test@example.com",
  entitlement: "free",
  sleeper_username: "",
  profile_status: "active",
  league_cap: 1,
};

function renderAccount() {
  return render(
    withProvider(
      <AccountContent
        user={ME_USER}
        communityOptedOut={false}
        onToggleCommunityOptOut={() => {}}
        pushCategories={null}
        onTogglePushCategory={() => {}}
        referral={null}
        referralError={null}
        onRetryReferral={() => {}}
        onOpenBillingPortal={async () => {}}
        onExportData={async () => {}}
        onDeleteAccount={async () => {}}
        onSignOut={() => {}}
      />,
    ),
  );
}

beforeEach(() => {
  vi.mocked(api.getDevicePreferences).mockReset();
  vi.mocked(api.setExperienceLevel).mockReset();
});

describe("experience level copy on Dashboard", () => {
  it("adds plain-language helper text and spells out labels for a beginner", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences("beginner"));
    render(withProvider(<DashboardContent leagueId="abc" leagueName="League" data={DASHBOARD} />));

    expect(await screen.findByText(`Power Rank: ${BEGINNER_HELP.powerRank}`)).toBeInTheDocument();
    expect(screen.getByText(`Franchise Rank: ${BEGINNER_HELP.franchiseRank}`)).toBeInTheDocument();
    expect(screen.getByText(BEGINNER_HELP.dashboardSnapshot)).toBeInTheDocument();
    expect(screen.getByText("Average Age")).toBeInTheDocument();
    expect(screen.queryByText("Avg Age")).not.toBeInTheDocument();
  });

  it.each([
    ["advanced", "advanced" as const],
    ["unset", null],
  ])("renders today's terse copy for %s", async (_name, level) => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences(level));
    const { container } = render(withProvider(<DashboardContent leagueId="abc" leagueName="League" data={DASHBOARD} />));

    await waitFor(() => expect(api.getDevicePreferences).toHaveBeenCalled());
    expect(screen.getByText("Avg Age")).toBeInTheDocument();
    expect(screen.queryByText(BEGINNER_HELP.powerRank)).not.toBeInTheDocument();
    expect(container.querySelector("[data-beginner-help]")).toBeNull();
  });
});

describe("experience level copy on Trade Hub idea cards", () => {
  it("explains Sell High, balance and realism for a beginner", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences("beginner"));
    render(withProvider(<TradeIdeaCardView idea={IDEA} leagueId="abc" />));

    expect(await screen.findByText(BEGINNER_HELP.impactSellHigh)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    expect(screen.getByText(BEGINNER_HELP.ideaBalance)).toBeInTheDocument();
    expect(screen.getByText(/Partner Acceptance · Plausible/)).toBeInTheDocument();
    expect(screen.getByText(BEGINNER_HELP.ideaRealism)).toBeInTheDocument();
  });

  it("keeps the terse card for an unset account", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences(null));
    const { container } = render(withProvider(<TradeIdeaCardView idea={IDEA} leagueId="abc" />));

    await waitFor(() => expect(api.getDevicePreferences).toHaveBeenCalled());
    fireEvent.click(screen.getByRole("button", { name: /view details/i }));
    expect(screen.getByText(/Realism · Plausible/)).toBeInTheDocument();
    expect(container.querySelector("[data-beginner-help]")).toBeNull();
  });
});

describe("Account page Explanations setting", () => {
  it("shows Advanced for an unset account and switches to Beginner, saving through /v1/preferences", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences(null));
    vi.mocked(api.setExperienceLevel).mockResolvedValue(preferences("beginner"));
    renderAccount();

    await waitFor(() => expect(api.getDevicePreferences).toHaveBeenCalled());
    const advanced = screen.getByRole("radio", { name: /advanced/i });
    const beginner = screen.getByRole("radio", { name: /beginner/i });
    expect(advanced).toHaveAttribute("aria-checked", "true");
    expect(beginner).toHaveAttribute("aria-checked", "false");

    fireEvent.click(beginner);
    await waitFor(() => expect(api.setExperienceLevel).toHaveBeenCalledWith("beginner"));
    expect(screen.getByRole("radio", { name: /beginner/i })).toHaveAttribute("aria-checked", "true");
  });

  it("restores the previous choice and shows an error when the save fails", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(preferences("beginner"));
    vi.mocked(api.setExperienceLevel).mockRejectedValue(new Error("network"));
    renderAccount();

    await waitFor(() => expect(screen.getByRole("radio", { name: /beginner/i })).toHaveAttribute("aria-checked", "true"));
    fireEvent.click(screen.getByRole("radio", { name: /advanced/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't save/i);
    expect(screen.getByRole("radio", { name: /beginner/i })).toHaveAttribute("aria-checked", "true");
  });
});
