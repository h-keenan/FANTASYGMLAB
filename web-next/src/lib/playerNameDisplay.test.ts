import { describe, expect, it } from "vitest";

import { fitPlayerName, shortPlayerName, splitPlayerName } from "./playerNameDisplay";

const CASES: ReadonlyArray<readonly [string, string]> = [
  ["Saquon Barkley", "S. Barkley"],
  ["Michael Penix Jr.", "M. Penix Jr."],
  ["Amon-Ra St. Brown", "A. St. Brown"],
  ["Jaxon Smith-Njigba", "J. Smith-Njigba"],
  ["Marvin Harrison Jr.", "M. Harrison Jr."],
  ["Kenneth Walker III", "K. Walker III"],
  ["Deebo Samuel Sr.", "D. Samuel Sr."],
  ["Patrick Mahomes II", "P. Mahomes II"],
  ["Odell Beckham Jr", "O. Beckham Jr"],
  ["Ken Griffey IV", "K. Griffey IV"],
  ["Jason Van Dyke", "J. Van Dyke"],
  ["Emmanuel De La Cruz", "E. De La Cruz"],
  ["Christian McCaffrey", "C. McCaffrey"],
  ["Mac Jones", "M. Jones"],
  ["Rhamondre Stevenson", "R. Stevenson"],
  ["Michael O'Connell", "M. O'Connell"],
  ["Ja'Marr Chase", "J. Chase"],
  ["D'Andre Swift", "D. Swift"],
  ["Wan'Dale Robinson", "W. Robinson"],
  ["T.J. Hockenson", "T.J. Hockenson"],
  ["C.J. Stroud", "C.J. Stroud"],
  ["D.K. Metcalf", "D.K. Metcalf"],
  ["A.J. Brown", "A.J. Brown"],
  ["CJ Stroud", "CJ Stroud"],
  ["J. Cook", "J. Cook"],
  ["Ravens D/ST", "Ravens D/ST"],
  ["49ers DST", "49ers DST"],
  ["Chiefs DEF", "Chiefs DEF"],
  ["Neymar", "Neymar"],
  ["Álvaro Núñez", "Á. Núñez"],
  ["Ömer Yıldız", "Ö. Yıldız"],
  ["Zoë Kravitz-Lee", "Z. Kravitz-Lee"],
  ["  Justin   Jefferson  ", "J. Jefferson"],
  ["", ""],
  ["   ", ""],
];

describe("shortPlayerName", () => {
  it.each(CASES.map(([a, b]) => [a, b]))("%j -> %j", (input, expected) => {
    expect(shortPlayerName(input)).toBe(expected);
  });

  it("is idempotent", () => {
    for (const [input] of CASES) {
      const once = shortPlayerName(input);
      expect(shortPlayerName(once)).toBe(once);
    }
  });

  it("handles null and undefined", () => {
    expect(shortPlayerName(null)).toBe("");
    expect(shortPlayerName(undefined)).toBe("");
  });

  it("keeps a decomposed accent attached to the initial", () => {
    expect(shortPlayerName("Álvaro Nuñez")).toBe("Á. Nuñez");
  });
});

describe("splitPlayerName", () => {
  it("separates first, surname and suffix", () => {
    expect(splitPlayerName("Michael Penix Jr.")).toEqual({
      first: "Michael",
      surname: "Penix",
      suffix: "Jr.",
      whole: false,
      firstIsInitials: false,
    });
    expect(splitPlayerName("Amon-Ra St. Brown").surname).toBe("St. Brown");
    expect(splitPlayerName("T.J. Hockenson").firstIsInitials).toBe(true);
  });

  it("marks mononyms, defenses and empties as whole", () => {
    expect(splitPlayerName("Neymar").whole).toBe(true);
    expect(splitPlayerName("Ravens D/ST").whole).toBe(true);
    expect(splitPlayerName("").whole).toBe(true);
  });
});

describe("fitPlayerName", () => {
  it("returns the full name when it fits and the short form otherwise", () => {
    expect(fitPlayerName("Josh Allen", 14)).toBe("Josh Allen");
    expect(fitPlayerName("Rhamondre Stevenson", 14)).toBe("R. Stevenson");
    expect(fitPlayerName(null, 14)).toBe("");
  });
});
