import { env } from "@/lib/env";

/**
 * POST /api/lp: first-party beacon relay for the static marketing landing
 * (static/landing/index.html on the apex domain). The landing posts a
 * text/plain JSON body here (a "simple" cross-origin request, so no CORS
 * preflight and no third-party pixel); this forwards a strictly allowlisted
 * event to the analytics API (`POST /v1/e`, anonymous). Only three event names
 * and a few sanitized attribution props are ever relayed. Always answers 204
 * so a failure can never surface on the marketing page.
 */
const EVENTS = new Set(["landing_viewed", "primary_cta_clicked", "secondary_cta_clicked"]);
const PROP_KEYS = ["utm_source", "utm_medium", "utm_campaign", "referrer_host", "click_id"] as const;

function token(value: unknown, max = 40): string {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_.-]/g, "")
    .slice(0, max);
}

export async function POST(request: Request): Promise<Response> {
  try {
    const raw = await request.text();
    if (raw.length > 2048) return new Response(null, { status: 204 });
    const body = JSON.parse(raw) as { event?: unknown; props?: Record<string, unknown>; anon_id?: unknown };
    const event = String(body.event ?? "");
    const anonId = String(body.anon_id ?? "");
    if (!EVENTS.has(event) || !/^anon_[a-f0-9]{16}$/.test(anonId)) return new Response(null, { status: 204 });
    const props: Record<string, unknown> = { platform: "web", source_surface: "static_landing" };
    for (const key of PROP_KEYS) {
      const value = token(body.props?.[key], key === "referrer_host" ? 80 : 40);
      if (value) props[key] = value;
    }
    if (body.props?.has_ref === true) props.has_ref = true;
    await fetch(`${env.apiBaseUrl}/v1/e`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, props, anon_id: anonId }),
      signal: AbortSignal.timeout(4000),
    });
  } catch {
    // best-effort telemetry only
  }
  return new Response(null, { status: 204 });
}
