import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import manifest from "@/app/manifest";
import { GET as llms } from "@/app/llms.txt/route";
import { AppStoreModules } from "@/components/AppStoreModules";
import { LandingSeasonal } from "@/components/LandingSeasonal";
import { AppCta } from "@/components/seo/SeoChrome";
import { APP_STORE_LINKS } from "@/lib/appStoreLinks";

vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn(), trackUse: vi.fn() }));

describe("LandingSeasonal", () => {
  it("leads with playoff schedules in the fantasy playoffs and tags links as site_cta", () => {
    render(<LandingSeasonal now={new Date("2026-12-15T15:00:00Z")} />);
    const root = screen.getByTestId("landing-seasonal");
    expect(root.getAttribute("data-stage")).toBe("fantasy_playoffs");
    const hrefs = Array.from(root.querySelectorAll("a")).map((a) => a.getAttribute("href"));
    expect(hrefs[0]).toMatch(/^\/fantasy-playoff-strength-of-schedule\?utm_source=landing&utm_medium=site_cta&utm_campaign=seasonal&utm_content=fantasy_playoffs$/);
    expect(hrefs[1]).toContain("/gm-game?quickstart=1&utm_source=landing");
  });

  it("switches to rookie content after the draft", () => {
    render(<LandingSeasonal now={new Date("2027-05-20T15:00:00Z")} />);
    expect(screen.getByRole("link", { name: "Dynasty rookie rankings" }).getAttribute("href")).toContain("/dynasty-rookie-rankings?");
  });
});

describe("AppCta on public SEO pages", () => {
  it("offers sample league first, then Fantasy Sim and the app, each UTM-tagged with the page campaign", () => {
    render(<AppCta title="t" body="b" campaign="player_page" content="bijan-robinson" />);
    const links = screen.getAllByRole("link");
    expect(links.map((l) => l.textContent)).toEqual(["Try a sample league", "Play a quick Fantasy Sim game", "Open FantasyDesk"]);
    for (const l of links) {
      const href = l.getAttribute("href")!;
      expect(href).toContain("utm_source=seo");
      expect(href).toContain("utm_medium=site_cta");
      expect(href).toContain("utm_campaign=player_page");
      expect(href).toContain("utm_content=bijan-robinson");
    }
  });
});

describe("App Store messaging", () => {
  it("says Coming soon for iPhone (no public listing, verified 2026-11-26) and points iPhone users to the web app", () => {
    expect(APP_STORE_LINKS.appStoreUrl).toBeNull();
    render(<AppStoreModules />);
    expect(screen.getByText("Coming soon")).toBeTruthy();
    expect(screen.getByTestId("iphone-web-note").textContent).toMatch(/works in your browser/);
  });

  it("drops the iPhone note once an App Store URL exists", () => {
    render(<AppStoreModules links={{ ...APP_STORE_LINKS, appStoreUrl: "https://apps.apple.com/app/id1" }} />);
    expect(screen.queryByTestId("iphone-web-note")).toBeNull();
  });
});

describe("manifest and llms.txt", () => {
  it("manifest is installable (name, start_url, standalone, 192 and 512 icons)", () => {
    const m = manifest();
    expect(m.display).toBe("standalone");
    expect(m.start_url).toMatch(/^\//);
    expect((m.icons ?? []).map((i) => i.sizes)).toEqual(["192x192", "512x512"]);
  });

  it("llms.txt is plain text and links only absolute public pages", async () => {
    const res = llms();
    expect(res.headers.get("content-type")).toContain("text/plain");
    const body = await res.text();
    expect(body.startsWith("# FantasyDesk")).toBe(true);
    expect(body).toContain("https://app.fantasygmlab.com/trade-analyzer");
    expect(body).not.toMatch(/\/dashboard|\/leagues|\/sample-league/);
  });
});
