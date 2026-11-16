import { describe, expect, it } from "vitest";

import { parseLandingFrontDoor } from "@/lib/landingFrontDoor";

describe("landing front door flag", () => {
  it("defaults to the one-field connect form and only switches back on an explicit email", () => {
    expect(parseLandingFrontDoor(undefined)).toBe("connect");
    expect(parseLandingFrontDoor("")).toBe("connect");
    expect(parseLandingFrontDoor("nonsense")).toBe("connect");
    expect(parseLandingFrontDoor("connect")).toBe("connect");
    expect(parseLandingFrontDoor("email")).toBe("email");
  });
});
