# PDF.js 6.3.289: missing native Map upsert APIs

Status: API regression fixed and automatically verified; real-browser
acceptance pending. This does not close the user's full browser report.

## User correction

ALT Linux is not a condition of the failure. The package names in the original
plan were examples of affected browser versions. Do not require an ALT machine
as a prerequisite for investigating or fixing browser compatibility.

## Reproduce

The browser test removes `Map.prototype.getOrInsert` and
`Map.prototype.getOrInsertComputed` in both the page and worker realms.
It then opens the local, annotated three-page PDF fixture.

Command:

```bash
.venv/Scripts/python.exe -m pytest catalog/tests/test_browser.py -k without_native_map -q -s
```

Both Playwright Chromium 153.0.8010.12 and Firefox 155 fail with:

```text
TypeError: this[#methodPromises].getOrInsertComputed is not a function
```

Raw RED evidence: `../verifications/pdfjs-map-upsert-red.txt`.
This simulates missing browser APIs, not an entire Firefox 140 or Yandex engine.

## Isolate

- Importing standard PDF.js with the API removed succeeds. Import failure alone
  is not the confirmed cause in this reproduction.
- The PDF loads, but requesting/rendering its page fails.
- Standard `build/pdf.mjs` uses Map upsert in `WorkerTransport` method caching,
  `PDFPageProxy` render state, object caches and annotation processing.
- Standard `build/pdf.worker.mjs` also uses Map upsert. Main-only polyfills are
  insufficient for general document support.
- The isolated HTTP import experiment initially failed on module MIME typing.
  It was rerun with explicit JavaScript MIME; the results above are from that
  corrected harness. This harness issue is not attributed to the application.

## Hypothesize and verify

Hypothesis: the unpolyfilled standard build requires APIs absent in the given
browser generation. Removing those APIs must reproduce the failure, while
using the upstream polyfilled build must remove it.

The RED reproduction confirms the API failure. The upstream package README
recommends `legacy/` for environments lacking current JavaScript features.
An isolated import of legacy 6.3.289 restores the removed Map API in both engines.
The same browser regression passes after the main and worker switch, including
canvas rendering, annotation display and internal navigation.
GREEN evidence: `../verifications/pdfjs-map-upsert-green.txt`.
Full project gate: `../verifications/pdfjs-legacy-gates.txt` (17 Python tests,
23 subtests, 5 JS tests; Django check passes; no migration changes).

Sources checked on 2026-09-27:

- https://github.com/mozilla/pdf.js/wiki/Frequently-Asked-Questions
  Modern build targets latest browsers; legacy is the translated/polyfilled build.
- https://raw.githubusercontent.com/mdn/browser-compat-data/main/javascript/builtins/Map.json
  `getOrInsert` and `getOrInsertComputed`: Firefox 144, Chrome 145.
- Local `node_modules/pdfjs-dist/README.md`, version 6.3.289.

## Minimal fix and acceptance

Copy `legacy/build/pdf.mjs` and `legacy/build/pdf.worker.mjs` together.
Use matching `legacy/web` CSS and annotation resources from the same package.
Keep version 6.3.289 and existing link/security policies.

Acceptance: the RED test renders canvas and annotations and follows an internal
link after this switch. Then rerun the entire project gate.

Actual Firefox ESR 140.14 and Yandex 25.2.4.1000 still require verification on the
user's environment. Their OS and Yandex engine version are not established.
Do not claim that every reported failure is explained or that all older
browsers are supported.
