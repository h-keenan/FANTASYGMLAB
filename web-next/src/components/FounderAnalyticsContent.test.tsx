import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FounderAnalyticsContent } from "./FounderAnalyticsContent";
import type { FounderAnalyticsReport } from "@/lib/api";

function report(overrides: Partial<FounderAnalyticsReport> = {}): FounderAnalyticsReport {
  return {
    window_key: "7d",
    window_label: "Last 7 days",
    measured: true,
    event_count: 128,
    sessions: 42,
    anonymous_users: 30,
    hashed_accounts: 12,
    product_modules: [
      { module: "trade_hub", users: 10, sessions: 12, views: 20, meaningful_interactions: 5 },
    ],
    decision_engagement: [{ event: "trade_hub_opened", label: "Trade Hub opened", count: 7 }],
    premium: [{ event: "premium_viewed", label: "Premium page opens", count: 3 }],
    checkout_intervals: { monthly: 2 },
    errors: { ValueError: 1 },
    error_sessions: 1,
    performance: { startup_complete: { p50: 400, p90: 900, p95: 1200, n: 20 } },
    startup_latency_buckets: { fast: 15 },
    storage: {
      kind: "supabase",
      file_name: "analytics_events",
      directory: "supabase",
      exists: true,
      size_bytes: 0,
      writes_enabled: true,
      retention_days: 120,
      survives_render_deploy: true,
      multi_instance: "Durable Supabase table — counts are cluster-wide across every instance.",
      scope_label: "All app instances (Supabase-backed) — not host-local.",
    },
    unavailable: [],
    partial_notes: ["Counts are measured events from the durable Supabase log."],
    ...overrides,
  };
}

describe("FounderAnalyticsContent", () => {
  it("renders the storage honesty banner, summary tiles, and named-count sections", () => {
    render(<FounderAnalyticsContent data={report()} windowKey="7d" onWindowChange={vi.fn()} />);

    expect(screen.getByText("Founder Analytics")).toBeInTheDocument();
    expect(screen.getByText("Durable — Supabase")).toBeInTheDocument();
    expect(screen.getByText("All app instances (Supabase-backed) — not host-local.")).toBeInTheDocument();

    expect(screen.getByText("128")).toBeInTheDocument(); // event_count tile
    expect(screen.getByText("42")).toBeInTheDocument(); // sessions tile

    expect(screen.getByText("trade hub")).toBeInTheDocument();
    expect(screen.getByText("Trade Hub opened")).toBeInTheDocument();
    expect(screen.getByText("Premium page opens")).toBeInTheDocument();
    expect(screen.getByText("ValueError")).toBeInTheDocument();
  });

  it("flags a host-local-only report instead of implying it's the all-user total", () => {
    render(
      <FounderAnalyticsContent
        data={report({
          storage: {
            kind: "host_local_jsonl",
            file_name: "launch_analytics.jsonl",
            directory: "data",
            exists: true,
            size_bytes: 4096,
            writes_enabled: true,
            retention_days: 120,
            survives_render_deploy: false,
            multi_instance: "Each Render instance has its own disk file. Totals are not cluster-wide.",
            scope_label: "This host file only — Supabase not available; not all-user totals.",
          },
        })}
        windowKey="7d"
        onWindowChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Host-local only")).toBeInTheDocument();
    expect(screen.getByText("This host file only — Supabase not available; not all-user totals.")).toBeInTheDocument();
  });

  it("calls onWindowChange when a different time window is selected", () => {
    const onWindowChange = vi.fn();
    render(<FounderAnalyticsContent data={report()} windowKey="7d" onWindowChange={onWindowChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Last 30 days" }));

    expect(onWindowChange).toHaveBeenCalledWith("30d");
  });

  it("shows an honest empty state instead of a blank section when there is no data", () => {
    render(
      <FounderAnalyticsContent
        data={report({ product_modules: [], decision_engagement: [], errors: {} })}
        windowKey="7d"
        onWindowChange={vi.fn()}
      />,
    );

    expect(screen.getByText("No feature-adoption events in this window.")).toBeInTheDocument();
    expect(screen.getByText("No events recorded in this window.")).toBeInTheDocument();
    expect(screen.getByText("No errors recorded in this window.")).toBeInTheDocument();
  });

  it("surfaces an unavailable-data notice when the backend reports one", () => {
    render(
      <FounderAnalyticsContent
        data={report({ unavailable: ["No analytics file on this host yet."] })}
        windowKey="7d"
        onWindowChange={vi.fn()}
      />,
    );

    expect(screen.getByText("No analytics file on this host yet.")).toBeInTheDocument();
  });

  it("shows ESPN import outcomes only when failures were recorded", () => {
    const { rerender } = render(<FounderAnalyticsContent data={report()} windowKey="7d" onWindowChange={vi.fn()} />);
    expect(screen.queryByTestId("espn-import-outcomes")).toBeNull();
    rerender(
      <FounderAnalyticsContent
        data={report({
          espn_import_outcomes: { espn_private: 3, espn_not_found: 1, espn_error: 0, total_failed: 4, private_pct: 75 },
        })}
        windowKey="7d"
        onWindowChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("espn-import-outcomes")).toHaveTextContent("private 3 (75%)");
  });
});
