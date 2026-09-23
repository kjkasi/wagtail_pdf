import assert from "node:assert/strict";
import test from "node:test";

import {
  clampPage,
  commentForPage,
  nextTarget,
} from "./viewer-state.js";

test("page numbers are clamped to document boundaries", () => {
  assert.equal(clampPage(-10, 3), 1);
  assert.equal(clampPage(2, 3), 2);
  assert.equal(clampPage(20, 3), 3);
});

test("navigation uses the latest requested page", () => {
  assert.equal(nextTarget(1, 1, 4), 2);
  assert.equal(nextTarget(4, 1, 4), 4);
  assert.equal(nextTarget(1, -1, 4), 1);
});

test("missing and blank comments use the defensive fallback", () => {
  const comments = { "1": "<p>Первый</p>", "2": "  " };
  assert.equal(commentForPage(comments, 1), "<p>Первый</p>");
  assert.equal(commentForPage(comments, 2), null);
  assert.equal(commentForPage(comments, 3), null);
});
