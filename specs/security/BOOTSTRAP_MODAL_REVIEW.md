# Security review: Bootstrap PDF modal

Scope: working-tree changes from `a090155`, branch `feat/bootstrap-pdf-modal`.
Review type: self-review, not independent review.

## Result

No new actionable security findings identified in the changed production paths.
This is a bounded code review, not a guarantee that the application is secure.

- Templates retain Django autoescaping for titles, descriptions and PDF URLs.
- The loader imports a developer-defined module URL, not a URL from PDF content.
- Error messages use `textContent`, not `innerHTML`.
- PDF scripting remains disabled. External links retain the existing
  `http`/`https`/`mailto` allowlist and `noopener noreferrer` attributes.
- No changes to authorization, document serving, models, publication or migrations.
- No CSP, CORS or transport-security relaxations.
- Bootstrap 5.3.8 is pinned. Vendor files are local, with Bootstrap and Popper
  MIT notices. PDF.js remains version 6.3.289, now using the official legacy
  main and worker together. No custom polyfills or downgrade were introduced.
- `npm ci` reports zero dependency vulnerabilities for the installed graph.
- No credentials or session cookies were added to repository files.

The missing Map upsert API failure is reproduced and covered by regression
checks. Browser versions, not ALT Linux, define the compatibility question.
Actual user-browser acceptance is still pending and is not closed by this review.
