export const MIN_ZOOM = 0.5;
export const MAX_ZOOM = 3;
export const ZOOM_STEP = 0.25;

export function clampPage(pageNumber, totalPages) {
  if (!Number.isInteger(totalPages) || totalPages < 1) {
    return 1;
  }
  return Math.min(Math.max(pageNumber, 1), totalPages);
}

export function nextTarget(currentTarget, delta, totalPages) {
  return clampPage(currentTarget + delta, totalPages);
}

export function clampZoom(zoomFactor) {
  if (!Number.isFinite(zoomFactor)) return 1;
  return Math.min(Math.max(zoomFactor, MIN_ZOOM), MAX_ZOOM);
}

export function nextZoom(currentZoom, direction) {
  const delta = Math.sign(direction) * ZOOM_STEP;
  return clampZoom(Math.round((currentZoom + delta) * 100) / 100);
}

export function zoomPercent(zoomFactor) {
  return Math.round(clampZoom(zoomFactor) * 100);
}
