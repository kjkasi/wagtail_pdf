export function clampPage(pageNumber, totalPages) {
  if (!Number.isInteger(totalPages) || totalPages < 1) {
    return 1;
  }
  return Math.min(Math.max(pageNumber, 1), totalPages);
}

export function nextTarget(currentTarget, delta, totalPages) {
  return clampPage(currentTarget + delta, totalPages);
}

export function commentForPage(comments, pageNumber) {
  const comment = comments[String(pageNumber)];
  return typeof comment === "string" && comment.trim()
    ? comment
    : null;
}
