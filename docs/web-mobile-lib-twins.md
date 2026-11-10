# Web / mobile lib twins

`web-next/src/lib` and `mobile/src/lib` keep hand-maintained copies of the
same pure-TS modules. There is no shared workspace package (Metro and Next
resolve imports differently, and the two trees have separate lockfiles), so
drift is prevented by a check instead.

## The check

`node scripts/check_lib_twins.mjs` (no install needed) classifies every
same-named non-test file pair:

- **SHARED markers**: files with `// SHARED BEGIN` / `// SHARED END` must have
  the same code between the markers (comments, imports, quote style and
  whitespace ignored). Automatic.
- **IDENTICAL**: byte-identical (generated files, import-free modules).
- **MIRRORED**: same code; only comments, import specifiers, quote style and
  trailing commas may differ.
- **DIVERGED**: acknowledged debt. Platform glue that is meant to differ, plus
  pure logic that has already drifted. The check fails when a DIVERGED file
  converges (promote it), so the list only shrinks.

A new same-named file in both trees fails until it is classified. CI runs it
in the `lib-twins` job on any change under `web-next/` or `mobile/`, and
`web-next/src/lib/libTwins.test.ts` runs it under `npm test`.

To reconcile a DIVERGED file: make the two copies match, add SHARED markers or
move it to MIRRORED, delete it from DIVERGED.

## api.ts types

`web-next/src/lib/api.ts` (287 exported types) and `mobile/src/lib/api.ts`
(269) duplicate response types by hand and stay in the DIVERGED list. They
cannot be generated cleanly today: the FastAPI service disables OpenAPI
(`openapi_url=None`) and none of its ~139 routes declare a `response_model`,
so there is no schema to generate from. The principled path is: add
`response_model` Pydantic models per route, enable the schema, emit one
`api-types.generated.ts` into both trees (like `tradeValueBands.generated.ts`),
and have a `IDENTICAL` entry guard it. Until then, edit types in both files
together.
