import { describe, expect, it } from "vitest";

import { playoffSosInSeason, rookieContentInSeason, seasonalLanding, seasonMoment, withUtm } from "./seasonalLanding";

const at = (iso: string) => seasonMoment(new Date(iso));

describe("seasonMoment (mirrors modules/season_clock calendar rule)", () => {
  it("2026 kickoff is Thursday Sep 10; Nov 26 is regular-season week 12", () => {
    expect(at("2026-09-09T12:00:00Z")).toMatchObject({ stage: "training_camp", season: 2025 });
    expect(at("2026-09-10T18:00:00Z")).toMatchObject({ stage: "in_season", season: 2026, week: 1 });
    expect(at("2026-11-26T15:00:00Z")).toMatchObject({ stage: "in_season", season: 2026, week: 12 });
  });

  it("walks the fantasy playoffs and season end", () => {
    expect(at("2026-12-08T15:00:00Z")).toMatchObject({ stage: "playoff_push", week: 14 });
    expect(at("2026-12-15T15:00:00Z")).toMatchObject({ stage: "fantasy_playoffs", week: 15 });
    expect(at("2026-12-29T15:00:00Z")).toMatchObject({ stage: "fantasy_playoffs", week: 17 });
    expect(at("2027-01-05T15:00:00Z")).toMatchObject({ stage: "season_end", week: 18 });
  });

  it("the week rolls on Tuesday 6am ET, not at midnight", () => {
    expect(at("2026-12-08T09:00:00Z").week).toBe(13); // Tue 4am ET: still Monday night's week
    expect(at("2026-12-08T12:00:00Z").week).toBe(14); // Tue 7am ET
  });

  it("follows the offseason calendar", () => {
    expect(at("2027-01-20T15:00:00Z").stage).toBe("nfl_postseason");
    expect(at("2027-03-15T15:00:00Z").stage).toBe("free_agency");
    expect(at("2027-04-20T15:00:00Z").stage).toBe("draft_season");
    expect(at("2027-05-20T15:00:00Z").stage).toBe("post_draft");
    expect(at("2027-08-20T15:00:00Z").stage).toBe("training_camp");
  });
});

describe("seasonal content gates", () => {
  it("playoff SOS is timely only in weeks 9-17", () => {
    expect(playoffSosInSeason(at("2026-11-26T15:00:00Z"))).toBe(true);
    expect(playoffSosInSeason(at("2026-10-01T15:00:00Z"))).toBe(false);
    expect(playoffSosInSeason(at("2027-01-05T15:00:00Z"))).toBe(false);
    expect(playoffSosInSeason(at("2027-05-20T15:00:00Z"))).toBe(false);
  });

  it("rookie content only after the draft through camp", () => {
    expect(rookieContentInSeason(at("2027-05-20T15:00:00Z"))).toBe(true);
    expect(rookieContentInSeason(at("2027-08-20T15:00:00Z"))).toBe(true);
    expect(rookieContentInSeason(at("2027-02-01T15:00:00Z"))).toBe(false);
    expect(rookieContentInSeason(at("2026-11-26T15:00:00Z"))).toBe(false);
  });
});

describe("seasonalLanding copy", () => {
  it("has a CTA and a Fantasy Sim quickstart for every stage", () => {
    const dates = ["2026-11-26", "2026-12-08", "2026-12-15", "2027-01-05", "2027-01-20", "2027-03-15", "2027-04-20", "2027-05-20", "2027-08-20"];
    for (const d of dates) {
      const copy = seasonalLanding(at(`${d}T15:00:00Z`));
      expect(copy.headline.length).toBeGreaterThan(10);
      expect(copy.primary.href.startsWith("/")).toBe(true);
      expect(copy.secondary.href).toBe("/gm-game?quickstart=1");
      expect(`${copy.headline}${copy.body}`).not.toMatch(/—|–|\.\.\./); // repo copy rule: no dashes/ellipses
    }
  });

  it("leads with playoff schedules during the playoffs", () => {
    expect(seasonalLanding(at("2026-12-15T15:00:00Z")).primary.href).toBe("/fantasy-playoff-strength-of-schedule");
    expect(seasonalLanding(at("2026-11-26T15:00:00Z")).primary.href).toBe("/fantasy-playoff-strength-of-schedule");
    expect(seasonalLanding(at("2026-09-20T15:00:00Z")).primary.href).toBe("/trade-analyzer");
  });
});

describe("withUtm", () => {
  it("tags internal links as site_cta and preserves an existing query", () => {
    expect(withUtm("/sample-league", "player_page", "seo", "bijan")).toBe(
      "/sample-league?utm_source=player_page&utm_medium=site_cta&utm_campaign=seo&utm_content=bijan",
    );
    expect(withUtm("/gm-game?quickstart=1", "landing", "seasonal")).toBe(
      "/gm-game?quickstart=1&utm_source=landing&utm_medium=site_cta&utm_campaign=seasonal",
    );
  });
});
