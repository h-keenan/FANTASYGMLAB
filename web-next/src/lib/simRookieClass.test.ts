import { afterEach, describe, expect, it } from "vitest";

import {
  SIM_GENERATED_CLASS_LABEL,
  SIM_GENERATED_CLASS_NOTICE,
  simGeneratedClassLabel,
  simPlayerIsGenerated,
  simRookieClassChip,
  simRookieNoticeKey,
  simSetupDynastyNote,
} from "./simGame";
import { isSimRookieNoticeSeen, setSimRookieNoticeSeen } from "./simRookieNotice";

describe("generated rookie class disclosure", () => {
  afterEach(() => window.localStorage.clear());

  it("has the owner-approved notice and chip label", () => {
    expect(SIM_GENERATED_CLASS_NOTICE).toBe("These rookies are simulated, not the real NFL draft class. Names and talent are generated for the game.");
    expect(SIM_GENERATED_CLASS_LABEL).toBe("Generated class");
  });

  it("appends the strength flavor only for a known strength", () => {
    expect(simGeneratedClassLabel("strong")).toBe("Generated class - strong");
    expect(simGeneratedClassLabel("weak")).toBe("Generated class - weak");
    expect(simGeneratedClassLabel("average")).toBe("Generated class - average");
    expect(simGeneratedClassLabel("bogus")).toBe("Generated class");
    expect(simGeneratedClassLabel(null)).toBe("Generated class");
  });

  it("builds the chip from the offseason payload, null for older saves", () => {
    expect(simRookieClassChip({ rookie_class: { generated: true, strength: "average", size: 48 } })).toBe("Generated class - average");
    expect(simRookieClassChip({ rookie_class: { generated: false, strength: "average" } })).toBeNull();
    expect(simRookieClassChip({})).toBeNull();
    expect(simRookieClassChip(null)).toBeNull();
  });

  it("flags generated rows only when the backend says so", () => {
    expect(simPlayerIsGenerated({ generated: true })).toBe(true);
    expect(simPlayerIsGenerated({ generated: false })).toBe(false);
    expect(simPlayerIsGenerated({})).toBe(false);
  });

  it("mentions simulated rookie classes in the dynasty setup note, both starts", () => {
    expect(simSetupDynastyNote({ start: "fresh", mode: "dynasty" })).toMatch(/rookie classes are simulated/);
    expect(simSetupDynastyNote({ start: "league", mode: "dynasty" })).toMatch(/rookie classes are simulated/);
    expect(simSetupDynastyNote({ start: "fresh", mode: "redraft" })).toBeNull();
  });

  it("remembers the dismissal per game id and survives blocked storage", () => {
    expect(simRookieNoticeKey("g1")).not.toBe(simRookieNoticeKey("g2"));
    expect(isSimRookieNoticeSeen("g1")).toBe(false);
    setSimRookieNoticeSeen("g1");
    expect(isSimRookieNoticeSeen("g1")).toBe(true);
    expect(isSimRookieNoticeSeen("g2")).toBe(false);
    const original = Storage.prototype.getItem;
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    try {
      expect(isSimRookieNoticeSeen("g1")).toBe(false);
    } finally {
      Storage.prototype.getItem = original;
    }
  });
});
