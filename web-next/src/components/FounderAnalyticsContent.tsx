import {
  FOUNDER_ANALYTICS_WINDOWS,
  type FounderAnalyticsNamedCount,
  type FounderAnalyticsReport,
} from "@/lib/api";
import { SnapshotTile } from "@/components/SnapshotTile";

/**
 * Founder-only internal product analytics (coridian_, 2026-10-19: "just put
 * it in the orb menu for the specific account(s) listed on supabase"). Pure
 * presentation over whatever GET /v1/founder/analytics returns — every
 * number here is modules.founder_analytics.build_report's own aggregation
 * (session/signup/feature-adoption rollups, "storage honesty"), never
 * recomputed client-side. This page can only be reached by an account whose
 * own Supabase Auth app_metadata carries `founder_ops: true`; anyone else
 * hitting the backing endpoint gets a real 403 (see FounderAnalyticsPage /
 * services/mobile_api_service.py's get_founder_analytics).
 *
 * Deliberately lean: this mirrors the Streamlit "Founder Ops" page's own
 * read-only, no-conversion-math posture (modules/founder_analytics.py's
 * module docstring — "Does not invent conversion rates") rather than adding
 * new charts or derived metrics on top of the real counts.
 */
function sectionLabel(text: string) {
  return (
    <h2 className="text-xs font-bold uppercase" style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}>
      {text}
    </h2>
  );
}

function NamedCountList({ items }: { items: FounderAnalyticsNamedCount[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        No events recorded in this window.
      </p>
    );
  }
  return (
    <div className="glass-surface flex flex-col">
      {items.map((item, index) => (
        <div
          key={item.event}
          className="flex items-center justify-between gap-3 px-3 py-2"
          style={
            index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
          }
        >
          <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
            {item.label}
          </span>
          <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
            {item.count.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

export function FounderAnalyticsContent({
  data,
  windowKey,
  onWindowChange,
}: {
  data: FounderAnalyticsReport;
  windowKey: string;
  onWindowChange: (key: string) => void;
}) {
  const storage = data.storage;
  const isDurable = storage.kind === "supabase";
  const errorEntries = Object.entries(data.errors);
  const performanceEntries = Object.entries(data.performance);
  const checkoutEntries = Object.entries(data.checkout_intervals);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Founder
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Founder Analytics</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Internal product usage for {data.window_label.toLowerCase()} — visible only to founder accounts.
        </p>
      </header>

      <div className="flex gap-2 flex-wrap" role="group" aria-label="Time window">
        {FOUNDER_ANALYTICS_WINDOWS.map((option) => {
          const active = option.value === windowKey;
          return (
            <button
              key={option.value}
              type="button"
              onClick={() => onWindowChange(option.value)}
              aria-pressed={active}
              className="px-3 py-1.5 text-xs font-bold"
              style={{
                borderRadius: "var(--radius-pill)",
                border: `var(--border-width-default) solid ${active ? "var(--color-accent)" : "var(--color-border)"}`,
                background: active ? "var(--color-accent-soft)" : "transparent",
                color: active ? "var(--color-accent)" : "var(--color-text-secondary)",
              }}
            >
              {option.label}
            </button>
          );
        })}
      </div>

      {/* "Storage honesty" — whether these counts are the durable,
          cluster-wide Supabase log or just this one host's local JSONL
          fallback (modules/founder_analytics.py's _storage_honesty). Shown
          first and prominently so a founder never mistakes a single-instance
          snapshot for the real cross-instance total. */}
      <div
        className="glass-surface flex flex-col gap-1 p-4"
        style={{ borderColor: isDurable ? "var(--color-success)" : "var(--color-warning)" }}
      >
        <span
          className="text-xs font-bold uppercase"
          style={{ color: isDurable ? "var(--color-success)" : "var(--color-warning)", letterSpacing: "0.03em" }}
        >
          {isDurable ? "Durable — Supabase" : "Host-local only"}
        </span>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {storage.scope_label}
        </p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {storage.multi_instance} Retention {storage.retention_days} days. Writes{" "}
          {storage.writes_enabled ? "enabled" : "disabled"}.
        </p>
      </div>

      {data.unavailable.length > 0 ? (
        <div
          className="flex flex-col gap-1 px-3 py-2 text-sm"
          style={{ background: "var(--color-warning-soft)", border: "var(--border-width-default) solid var(--color-warning)" }}
        >
          {data.unavailable.map((note, index) => (
            <span key={index}>{note}</span>
          ))}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-3">
        <SnapshotTile label="Events" value={data.event_count.toLocaleString()} />
        <SnapshotTile label="Sessions" value={data.sessions.toLocaleString()} />
        <SnapshotTile label="Anonymous users" value={data.anonymous_users.toLocaleString()} />
        <SnapshotTile label="Accounts" value={data.hashed_accounts.toLocaleString()} />
      </div>

      <section className="flex flex-col gap-2">
        {sectionLabel("Feature adoption")}
        {data.product_modules.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No feature-adoption events in this window.
          </p>
        ) : (
          <div className="glass-surface flex flex-col">
            {data.product_modules.map((module, index) => (
              <div
                key={module.module}
                className="flex items-center justify-between gap-3 px-3 py-2"
                style={
                  index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
                }
              >
                <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {module.module.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-right" style={{ color: "var(--color-text-muted)" }}>
                  {module.views.toLocaleString()} views · {module.users.toLocaleString()} users ·{" "}
                  {module.sessions.toLocaleString()} sessions
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      {data.platforms ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="platform-split">
          Events by platform:{" "}
          {Object.entries(data.platforms).map(([platform, count], index) => (
            <span key={platform}>
              {index > 0 ? " · " : ""}
              {platform} {count.toLocaleString()}
            </span>
          ))}
        </p>
      ) : null}

      {data.feature_use && data.feature_use.length > 0 ? (
        <section className="flex flex-col gap-2">
          {sectionLabel("Feature use (web + mobile)")}
          <div className="glass-surface flex flex-col">
            {data.feature_use.map((row, index) => (
              <div
                key={`${row.feature}:${row.action}`}
                className="flex items-center justify-between gap-3 px-3 py-2"
                style={
                  index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
                }
              >
                <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {row.feature.replace(/_/g, " ")} · {row.action.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-right" style={{ color: "var(--color-text-muted)" }}>
                  {row.total.toLocaleString()} · web {row.web} / ios {row.ios} / android {row.android} · free {row.free}
                  / pro {row.pro}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {data.onboarding_funnel && data.onboarding_funnel.steps.length > 0 ? (
        <section className="flex flex-col gap-2" data-testid="onboarding-funnel">
          {sectionLabel("Onboarding funnel")}
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {data.onboarding_funnel.started_users.toLocaleString()} users started
            {data.onboarding_funnel.completion_rate_pct !== null
              ? ` · completion ${data.onboarding_funnel.completion_rate_pct}%`
              : ""}
            {data.onboarding_funnel.skip_rate_pct !== null ? ` · skip rate ${data.onboarding_funnel.skip_rate_pct}%` : ""}
            {Object.keys(data.onboarding_funnel.experience).length > 0
              ? ` · experience ${Object.entries(data.onboarding_funnel.experience)
                  .map(([key, v]) => `${key} ${v.pct}%`)
                  .join(" / ")}`
              : ""}
          </p>
          <div className="glass-surface flex flex-col">
            {data.onboarding_funnel.steps.map((row, index) => (
              <div
                key={row.step}
                className="flex items-center justify-between gap-3 px-3 py-2"
                style={
                  index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
                }
              >
                <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {row.step.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-right" style={{ color: "var(--color-text-muted)" }}>
                  {row.users.toLocaleString()} users
                  {row.drop_off_pct !== null ? ` · drop-off ${row.drop_off_pct}%` : ""}
                  {row.skipped_users > 0 ? ` · skipped ${row.skipped_users}` : ""}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="flex flex-col gap-2">
        {sectionLabel("Decision engagement")}
        <NamedCountList items={data.decision_engagement} />
      </section>

      <section className="flex flex-col gap-2">
        {sectionLabel("Premium funnel")}
        <NamedCountList items={data.premium} />
        {checkoutEntries.length > 0 ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Checkout starts by interval:{" "}
            {checkoutEntries.map(([interval, count], index) => (
              <span key={interval}>
                {index > 0 ? ", " : ""}
                {interval} ({count.toLocaleString()})
              </span>
            ))}
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        {sectionLabel("Errors")}
        {errorEntries.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No errors recorded in this window.
          </p>
        ) : (
          <div className="glass-surface flex flex-col">
            {errorEntries.map(([errorClass, count], index) => (
              <div
                key={errorClass}
                className="flex items-center justify-between gap-3 px-3 py-2"
                style={
                  index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
                }
              >
                <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                  {errorClass}
                </span>
                <span className="text-sm font-bold" style={{ color: "var(--color-danger)" }}>
                  {count.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {data.error_sessions.toLocaleString()} session{data.error_sessions === 1 ? "" : "s"} saw at least one error.
        </p>
      </section>

      {performanceEntries.length > 0 ? (
        <section className="flex flex-col gap-2">
          {sectionLabel("Performance (ms)")}
          <div className="glass-surface flex flex-col">
            {performanceEntries.map(([name, stat], index) => (
              <div
                key={name}
                className="flex items-center justify-between gap-3 px-3 py-2"
                style={
                  index > 0 ? { borderTop: "var(--border-width-default) solid var(--color-border)" } : undefined
                }
              >
                <span className="text-sm" style={{ color: "var(--color-text-primary)" }}>
                  {name.replace(/_/g, " ")}
                </span>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  p50 {stat.p50 ?? "—"} · p90 {stat.p90 ?? "—"} · p95 {stat.p95 ?? "—"} (n={stat.n})
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {data.partial_notes.length > 0 ? (
        <ul className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {data.partial_notes.map((note, index) => (
            <li key={index}>{note}</li>
          ))}
        </ul>
      ) : null}
    </main>
  );
}
