import assert from "node:assert/strict";
import test from "node:test";

import {
  MAX_ZOOM,
  MIN_ZOOM,
  clampPage,
  clampZoom,
  nextTarget,
  nextZoom,
  zoomPercent,
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

test("zoom is bounded between 50 and 300 percent", () => {
  assert.equal(clampZoom(0.1), MIN_ZOOM);
  assert.equal(clampZoom(4), MAX_ZOOM);
  assert.equal(clampZoom(1.25), 1.25);
});

test("zoom changes in exact 25 percent steps", () => {
  assert.equal(nextZoom(1, 1), 1.25);
  assert.equal(nextZoom(1, -1), 0.75);
  assert.equal(nextZoom(MAX_ZOOM, 1), MAX_ZOOM);
  assert.equal(nextZoom(MIN_ZOOM, -1), MIN_ZOOM);
  assert.equal(zoomPercent(1.25), 125);
});
