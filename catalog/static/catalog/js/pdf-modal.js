// Keep modal controls independent of the PDF.js module graph.
(function () {
  const modalElement = document.querySelector("[data-pdf-modal]");
  const opener = document.querySelector("[data-pdf-open]");
  if (!modalElement || !opener) return;

  const viewer = modalElement.querySelector("[data-pdf-viewer]");
  const moduleUrl = new URL("pdf-viewer.js", document.currentScript.src).href;
  let controller;
  let controllerPromise;
  let visible = false;

  if (!window.bootstrap || !window.bootstrap.Modal) {
    const error = document.querySelector("[data-modal-error]");
    error.textContent = "Не удалось открыть просмотрщик PDF. Обновите страницу.";
    error.hidden = false;
    opener.disabled = true;
    return;
  }

  const modal = window.bootstrap.Modal.getOrCreateInstance(modalElement);
  modalElement.addEventListener("shown.bs.modal", function () {
    visible = true;
    if (controller) {
      controller.open();
      return;
    }
    if (!controllerPromise) {
      controllerPromise = import(moduleUrl)
        .then(function (module) {
          controller = module.initialiseViewer(viewer);
          if (visible) controller.open();
        })
        .catch(function () {
          viewer.querySelector("[data-loading]").hidden = true;
          const error = viewer.querySelector("[data-error]");
          error.textContent = "Не удалось запустить просмотрщик PDF. Обновите страницу или попробуйте другой браузер.";
          error.hidden = false;
          viewer.setAttribute("aria-busy", "false");
        });
    }
  });
  modalElement.addEventListener("hide.bs.modal", function () {
    visible = false;
    if (controller) controller.close();
  });
  modalElement.addEventListener("hidden.bs.modal", function () {
    opener.focus();
  });
  // Wrap Tab before it can move into the browser chrome (no focusin event).
  modalElement.addEventListener("keydown", function (event) {
    if (event.key !== "Tab") return;
    const focusable = Array.from(modalElement.querySelectorAll(
      'a[href], button, input, select, textarea, [tabindex], [contenteditable="true"]',
    )).filter(function (element) {
      return !element.disabled && element.tabIndex >= 0 &&
        element.getClientRects().length > 0 &&
        getComputedStyle(element).visibility !== "hidden";
    });
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && (document.activeElement === first || document.activeElement === modalElement)) {
      event.preventDefault();
      (last || modalElement).focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      (first || modalElement).focus();
    }
  });
  opener.addEventListener("click", function () { modal.show(opener); });
  modal.show(opener);
})();
