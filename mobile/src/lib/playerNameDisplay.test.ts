// Run with: node --experimental-strip-types --test src/lib/playerNameDisplay.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { fitPlayerName, shortPlayerName, splitPlayerName } from './playerNameDisplay.ts';

const CASES: Array<[string, string]> = [
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


for (const [input, expected] of CASES) {
  test(`shortPlayerName ${JSON.stringify(input)}`, () => {
    assert.equal(shortPlayerName(input), expected);
    assert.equal(shortPlayerName(expected), expected);
  });
}

test('null and undefined', () => {
  assert.equal(shortPlayerName(null), '');
  assert.equal(shortPlayerName(undefined), '');
});

test('splitPlayerName separates suffix and flags whole names', () => {
  assert.deepEqual(splitPlayerName('Michael Penix Jr.'), {
    first: 'Michael',
    surname: 'Penix',
    suffix: 'Jr.',
    whole: false,
    firstIsInitials: false,
  });
  assert.equal(splitPlayerName('Ravens D/ST').whole, true);
  assert.equal(splitPlayerName('T.J. Hockenson').firstIsInitials, true);
});

test('fitPlayerName', () => {
  assert.equal(fitPlayerName('Josh Allen', 14), 'Josh Allen');
  assert.equal(fitPlayerName('Rhamondre Stevenson', 14), 'R. Stevenson');
});
