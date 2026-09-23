---
bug_id: BUG-2026-09-23T224339
status: fixed
severity: high
scope: admin
priority: high
title: PDF document page cannot be created in the admin
---

# BUG-2026-09-23T224339: PDF document page cannot be created in the admin

## Problem

A Wagtail editor cannot create a PDF document page. A valid PDF and one non-empty comment for each PDF page still produce the message «Страница не может быть создана из-за ошибок при проверке.»

Expected behavior: a complete, valid page submission is saved and redirects to the normal Wagtail success destination.

Security impact: **NONE** — no security exploit path was identified.

## Root Cause Analysis

### Phase 1 — Reproduce

The defect was reproduced on Python 3.12, Django 5.2, and Wagtail 7.4 by submitting the actual Wagtail page-creation endpoint with a valid two-page PDF and two valid inline comments. The endpoint returned the edit form instead of a redirect. The parent form reported that comments for pages 1 and 2 were missing.

### Phase 2 — Isolate

The uploaded document is readable and its page count is detected correctly. Both inline comment forms validate and contain page numbers 1 and 2 with non-empty rich text. During parent model validation, however, the in-memory child relation is empty. Saving the validated inline formset into the in-memory cluster immediately exposes both comments.

### Phase 3 — Hypotheses

1. **Confirmed candidate:** parent validation runs before inline formsets are copied into the in-memory model cluster. Falsification: inspect the child relation before and after an explicit non-committing formset save.
2. PDF parsing rejects the document. Falsification: call the page-count reader directly and inspect field errors.
3. Rich-text values are rejected as empty. Falsification: inspect the inline forms' cleaned values and errors.

Hypotheses 2 and 3 were falsified: PDF parsing returns two pages, and both inline forms are valid with visible text.

### Phase 4 — Verify

The child relation contains zero comments when parent model validation runs, while the bound inline formset contains two valid comments. After the framework's non-committing formset save, the same relation contains page numbers 1 and 2. This confirms a validation-order mismatch: cross-child model validation executes before Wagtail/modelcluster attaches submitted inline objects.

The bug is a missing admin-form integration rather than invalid user data. Risk level: **Low**; the fix is limited to validation ordering for this page type.

## TDD Fix Plan

1. **RED**: Submit a complete PDF page through the Wagtail page-creation endpoint and assert that it redirects and persists the page with all comments.
   **GREEN**: Add a page admin form that stages a valid inline comment formset in the in-memory cluster before parent model validation, and configure the PDF page type to use it.
   **verify**: `./.venv/Scripts/python.exe -m pytest catalog/tests/test_admin.py -q`

2. **RED**: Retain the model validation tests for missing, duplicate, out-of-range, and empty comments.
   **GREEN**: Keep existing model validation behavior unchanged while integrating the admin form.
   **verify**: `./.venv/Scripts/python.exe -m pytest catalog/tests/test_validation.py -q`

**REFACTOR**: Keep the ordering adapter in a named form class and document why the non-committing formset save is required.

## Acceptance Criteria

- [x] A valid PDF page can be created in Wagtail admin.
- [x] All submitted page comments are persisted.
- [x] Missing, duplicate, out-of-range, and empty comments remain invalid.
- [x] All new tests pass.
- [x] Existing tests still pass.

## Resolution

**Fixed:** 2026-09-23
**Root cause confirmed:** Parent model validation read the child relation before Wagtail/modelcluster staged the submitted inline comments.
**Fix applied:** A page admin form now stages a valid comment formset in the in-memory cluster before parent model validation.
**Hardening added:** An admin-endpoint integration regression test proves that a complete two-page submission redirects and persists both comments.
**Generalization sweep:** One project instance of this defect class was found and fixed; evidence is recorded in `specs/verifications/generalize-sweep-BUG-2026-09-23-pdf-inline-validation.json`.
**Evidence:** 16 Python tests and 3 JavaScript tests pass; manual endpoint proof returned HTTP 302 and persisted comment pages `[1, 2]`.
**Commits:** `4a4d4d5 test(admin): cover PDF page creation with inline comments`; `ca74693 fix(admin): stage PDF comments before page validation`.
