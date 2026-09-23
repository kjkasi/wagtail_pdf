import * as pdfjsLib from "../vendor/pdfjs/pdf.js";
import {
  commentForPage,
  nextTarget,
} from "./viewer-state.js";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "../vendor/pdfjs/pdf.worker.js",
  import.meta.url,
).toString();

const root = document.querySelector("[data-pdf-viewer]");

if (root) {
  initialiseViewer(root);
}

async function initialiseViewer(viewer) {
  const elements = getElements(viewer);
  const comments = readComments();
  const state = {
    document: null,
    currentPage: 0,
    targetPage: 1,
    totalPages: 0,
    rendering: false,
    forceRender: false,
  };

  elements.previous.addEventListener("click", () => requestDelta(-1));
  elements.next.addEventListener("click", () => requestDelta(1));

  let resizeTimer;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      if (!state.document || !state.currentPage) return;
      state.forceRender = true;
      void drainRenderQueue();
    }, 150);
  });

  try {
    const loadingTask = pdfjsLib.getDocument({ url: viewer.dataset.pdfUrl });
    state.document = await loadingTask.promise;
    state.totalPages = state.document.numPages;
    elements.totalPage.textContent = String(state.totalPages);
    updateControls();
    await drainRenderQueue();
  } catch (error) {
    console.error("PDF loading failed", error);
    showError("Не удалось загрузить PDF. Обновите страницу или попробуйте позже.");
  }

  function requestDelta(delta) {
    if (!state.document) return;
    state.targetPage = nextTarget(
      state.targetPage,
      delta,
      state.totalPages,
    );
    updateControls();
    void drainRenderQueue();
  }

  async function drainRenderQueue() {
    if (state.rendering || !state.document) return;
    state.rendering = true;
    viewer.setAttribute("aria-busy", "true");

    try {
      while (
        state.currentPage !== state.targetPage ||
        state.forceRender
      ) {
        state.forceRender = false;
        const candidate = state.targetPage;
        elements.loading.hidden = false;
        elements.loading.textContent = `Отрисовка страницы ${candidate}…`;

        const page = await state.document.getPage(candidate);
        const rendered = await renderOffscreen(page, elements.stage);

        if (candidate !== state.targetPage) {
          continue;
        }

        commitCanvas(elements.canvas, rendered);
        state.currentPage = candidate;
        updateComment(candidate);
        elements.currentPage.textContent = String(candidate);
        elements.canvas.setAttribute(
          "aria-label",
          `Страница ${candidate} из ${state.totalPages}`,
        );
        elements.canvas.hidden = false;
        elements.loading.hidden = true;
        elements.error.hidden = true;
        updateControls();
      }
    } catch (error) {
      console.error("PDF rendering failed", error);
      showError("Не удалось отобразить страницу PDF.");
    } finally {
      state.rendering = false;
      viewer.setAttribute("aria-busy", "false");
      if (
        state.document &&
        (state.currentPage !== state.targetPage || state.forceRender)
      ) {
        void drainRenderQueue();
      }
    }
  }

  function updateComment(pageNumber) {
    const html = commentForPage(comments, pageNumber);
    elements.commentPage.textContent = String(pageNumber);
    if (html) {
      elements.comment.innerHTML = html;
      return;
    }
    elements.comment.textContent =
      "Для этой страницы комментарий не найден.";
  }

  function updateControls() {
    const unavailable = !state.document || state.totalPages < 1;
    elements.previous.disabled = unavailable || state.targetPage <= 1;
    elements.next.disabled =
      unavailable || state.targetPage >= state.totalPages;
  }

  function showError(message) {
    elements.loading.hidden = true;
    elements.error.textContent = message;
    elements.error.hidden = false;
    elements.previous.disabled = true;
    elements.next.disabled = true;
    viewer.setAttribute("aria-busy", "false");
  }
}

function getElements(viewer) {
  return {
    stage: viewer.querySelector("[data-pdf-stage]"),
    canvas: viewer.querySelector("[data-pdf-canvas]"),
    loading: viewer.querySelector("[data-loading]"),
    error: viewer.querySelector("[data-error]"),
    comment: viewer.querySelector("[data-comment]"),
    commentPage: viewer.querySelector("[data-comment-page]"),
    currentPage: viewer.querySelector("[data-current-page]"),
    totalPage: viewer.querySelector("[data-total-pages]"),
    previous: viewer.querySelector("[data-previous]"),
    next: viewer.querySelector("[data-next]"),
  };
}

function readComments() {
  const data = document.getElementById("pdf-comments");
  if (!data) return {};
  try {
    return JSON.parse(data.textContent);
  } catch (error) {
    console.error("Comment data is invalid", error);
    return {};
  }
}

async function renderOffscreen(page, stage) {
  const baseViewport = page.getViewport({ scale: 1 });
  const availableWidth = Math.max(stage.clientWidth - 32, 1);
  const cssScale = availableWidth / baseViewport.width;
  const viewport = page.getViewport({ scale: cssScale });
  const outputScale = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { alpha: false });

  canvas.width = Math.floor(viewport.width * outputScale);
  canvas.height = Math.floor(viewport.height * outputScale);

  await page.render({
    canvasContext: context,
    viewport,
    transform:
      outputScale === 1
        ? null
        : [outputScale, 0, 0, outputScale, 0, 0],
  }).promise;

  return {
    canvas,
    cssWidth: viewport.width,
    cssHeight: viewport.height,
  };
}

function commitCanvas(target, rendered) {
  target.width = rendered.canvas.width;
  target.height = rendered.canvas.height;
  target.style.width = `${rendered.cssWidth}px`;
  target.style.height = `${rendered.cssHeight}px`;
  const context = target.getContext("2d", { alpha: false });
  context.drawImage(rendered.canvas, 0, 0);
}
