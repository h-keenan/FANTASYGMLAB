import { describe, expect, it } from "vitest";

import { parseLandingFrontDoor } from "@/lib/landingFrontDoor";

describe("landing front door flag", () => {
  it("defaults to the email sign-in form and only switches on an explicit connect", () => {
    expect(parseLandingFrontDoor(undefined)).toBe("email");
    expect(parseLandingFrontDoor("")).toBe("email");
    expect(parseLandingFrontDoor("nonsense")).toBe("email");
    expect(parseLandingFrontDoor("connect")).toBe("connect");
  });
});
