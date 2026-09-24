import * as pdfjsLib from "../vendor/pdfjs/pdf.js";
import {
  MAX_ZOOM,
  MIN_ZOOM,
  clampPage,
  nextTarget,
  nextZoom,
  zoomPercent,
} from "./viewer-state.js";

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  "../vendor/pdfjs/pdf.worker.js",
  import.meta.url,
).toString();
const annotationImagePath = new URL(
  "../vendor/pdfjs/images/",
  import.meta.url,
).toString();

const root = document.querySelector("[data-pdf-viewer]");

if (root) {
  initialiseViewer(root);
}

async function initialiseViewer(viewer) {
  const elements = getElements(viewer);
  const state = {
    document: null,
    linkService: null,
    annotationRenderer: null,
    currentPage: 0,
    targetPage: 1,
    totalPages: 0,
    zoomFactor: 1,
    rendering: false,
    forceRender: false,
    renderVersion: 0,
  };

  elements.previous.addEventListener("click", () => requestDelta(-1));
  elements.next.addEventListener("click", () => requestDelta(1));
  elements.zoomOut.addEventListener("click", () => requestZoom(-1));
  elements.zoomIn.addEventListener("click", () => requestZoom(1));
  elements.zoomFit.addEventListener("click", () => setZoom(1));

  let resizeTimer;
  window.addEventListener("resize", () => {
    window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      if (!state.document || !state.currentPage) return;
      requestRender();
    }, 150);
  });

  try {
    const loadingTask = pdfjsLib.getDocument({ url: viewer.dataset.pdfUrl });
    state.document = await loadingTask.promise;
    state.totalPages = state.document.numPages;
    state.linkService = createLinkService(state.document, {
      goToPage: requestPage,
      executeNamedAction,
    });
    elements.totalPage.textContent = String(state.totalPages);
    updateControls();
    await drainRenderQueue();
  } catch (error) {
    reportViewerError("load", error, viewer.dataset.pdfUrl);
    showError("Не удалось загрузить PDF. Обновите страницу или попробуйте позже.");
  }

  function requestDelta(delta) {
    requestPage(nextTarget(state.targetPage, delta, state.totalPages));
  }

  function requestPage(pageNumber) {
    if (!state.document) return;
    const targetPage = clampPage(pageNumber, state.totalPages);
    if (targetPage === state.targetPage && state.currentPage === targetPage) return;
    state.targetPage = targetPage;
    requestRender();
  }

  function executeNamedAction(action) {
    const namedActions = {
      FirstPage: 1,
      LastPage: state.totalPages,
      NextPage: state.targetPage + 1,
      PrevPage: state.targetPage - 1,
    };
    if (Object.hasOwn(namedActions, action)) {
      requestPage(namedActions[action]);
    }
  }

  function requestZoom(direction) {
    setZoom(nextZoom(state.zoomFactor, direction));
  }

  function setZoom(zoomFactor) {
    if (!state.document || zoomFactor === state.zoomFactor) return;
    state.zoomFactor = zoomFactor;
    elements.zoomLevel.textContent = `${zoomPercent(zoomFactor)}%`;
    requestRender();
  }

  function requestRender() {
    state.forceRender = true;
    state.renderVersion += 1;
    updateControls();
    void drainRenderQueue();
  }

  async function drainRenderQueue() {
    if (state.rendering || !state.document) return;
    state.rendering = true;
    let renderFailed = false;
    viewer.setAttribute("aria-busy", "true");

    try {
      while (state.currentPage !== state.targetPage || state.forceRender) {
        state.forceRender = false;
        const candidatePage = state.targetPage;
        const candidateZoom = state.zoomFactor;
        const candidateVersion = state.renderVersion;
        elements.loading.hidden = false;
        elements.loading.textContent = `Отрисовка страницы ${candidatePage}…`;

        const page = await state.document.getPage(candidatePage);
        const rendered = await renderOffscreen(
          page,
          elements.stage,
          candidateZoom,
          state.linkService,
        );

        if (
          candidatePage !== state.targetPage ||
          candidateZoom !== state.zoomFactor ||
          candidateVersion !== state.renderVersion
        ) {
          rendered.annotationRenderer.destroy();
          continue;
        }

        const scrollPosition = captureScrollPosition(elements.stage);
        state.annotationRenderer?.destroy();
        commitRenderedPage(elements, rendered, candidatePage, state.totalPages);
        state.annotationRenderer = rendered.annotationRenderer;
        restoreScrollPosition(elements.stage, scrollPosition);
        state.currentPage = candidatePage;
        elements.currentPage.textContent = String(candidatePage);
        elements.loading.hidden = true;
        elements.error.hidden = true;
        updateControls();
      }
    } catch (error) {
      renderFailed = true;
      reportViewerError("render", error, viewer.dataset.pdfUrl);
      showError("Не удалось отобразить страницу PDF.");
    } finally {
      state.rendering = false;
      viewer.setAttribute("aria-busy", "false");
      if (
        !renderFailed &&
        state.document &&
        (state.currentPage !== state.targetPage || state.forceRender)
      ) {
        void drainRenderQueue();
      }
    }
  }

  function updateControls() {
    const unavailable = !state.document || state.totalPages < 1;
    elements.previous.disabled = unavailable || state.targetPage <= 1;
    elements.next.disabled = unavailable || state.targetPage >= state.totalPages;
    elements.zoomOut.disabled = unavailable || state.zoomFactor <= MIN_ZOOM;
    elements.zoomIn.disabled = unavailable || state.zoomFactor >= MAX_ZOOM;
    elements.zoomFit.disabled = unavailable || state.zoomFactor === 1;
    elements.zoomLevel.textContent = `${zoomPercent(state.zoomFactor)}%`;
  }

  function showError(message) {
    elements.loading.hidden = true;
    elements.error.textContent = message;
    elements.error.hidden = false;
    elements.previous.disabled = true;
    elements.next.disabled = true;
    elements.zoomOut.disabled = true;
    elements.zoomIn.disabled = true;
    elements.zoomFit.disabled = true;
    viewer.setAttribute("aria-busy", "false");
  }
}

function getElements(viewer) {
  return {
    stage: viewer.querySelector("[data-pdf-stage]"),
    page: viewer.querySelector("[data-pdf-page]"),
    canvas: viewer.querySelector("[data-pdf-canvas]"),
    annotationLayer: viewer.querySelector("[data-annotation-layer]"),
    loading: viewer.querySelector("[data-loading]"),
    error: viewer.querySelector("[data-error]"),
    currentPage: viewer.querySelector("[data-current-page]"),
    totalPage: viewer.querySelector("[data-total-pages]"),
    previous: viewer.querySelector("[data-previous]"),
    next: viewer.querySelector("[data-next]"),
    zoomOut: viewer.querySelector("[data-zoom-out]"),
    zoomIn: viewer.querySelector("[data-zoom-in]"),
    zoomFit: viewer.querySelector("[data-zoom-fit]"),
    zoomLevel: viewer.querySelector("[data-zoom-level]"),
  };
}

async function renderOffscreen(page, stage, zoomFactor, linkService) {
  const baseViewport = page.getViewport({ scale: 1 });
  const availableWidth = Math.max(stage.clientWidth - 32, 1);
  const fitScale = availableWidth / baseViewport.width;
  const effectiveScale = fitScale * zoomFactor;
  const viewport = page.getViewport({ scale: effectiveScale });
  const outputScale = Math.min(window.devicePixelRatio || 1, 2);
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d", { alpha: false });

  canvas.width = Math.floor(viewport.width * outputScale);
  canvas.height = Math.floor(viewport.height * outputScale);
  canvas.style.width = `${viewport.width}px`;
  canvas.style.height = `${viewport.height}px`;

  const annotationsPromise = page.getAnnotations({ intent: "display" });
  await page.render({
    canvasContext: context,
    viewport,
    transform:
      outputScale === 1
        ? null
        : [outputScale, 0, 0, outputScale, 0, 0],
  }).promise;

  const annotationDiv = document.createElement("div");
  annotationDiv.className = "annotationLayer";
  annotationDiv.dataset.annotationLayer = "";
  const annotationRenderer = new pdfjsLib.AnnotationLayer({
    div: annotationDiv,
    page,
    viewport: viewport.clone({ dontFlip: true }),
    linkService,
  });
  await annotationRenderer.render({
    annotations: await annotationsPromise,
    imageResourcesPath: annotationImagePath,
    renderForms: true,
    enableScripting: false,
    hasJSActions: false,
    fieldObjects: null,
  });
  annotationDiv.style.width = `${viewport.width}px`;
  annotationDiv.style.height = `${viewport.height}px`;
  secureExternalLinks(annotationDiv);

  return {
    canvas,
    annotationDiv,
    annotationRenderer,
    cssWidth: viewport.width,
    cssHeight: viewport.height,
  };
}

function commitRenderedPage(elements, rendered, pageNumber, totalPages) {
  rendered.canvas.dataset.pdfCanvas = "";
  rendered.canvas.setAttribute(
    "aria-label",
    `Страница ${pageNumber} из ${totalPages}`,
  );
  elements.page.style.width = `${rendered.cssWidth}px`;
  elements.page.style.height = `${rendered.cssHeight}px`;
  elements.page.replaceChildren(rendered.canvas, rendered.annotationDiv);
  elements.canvas = rendered.canvas;
  elements.annotationLayer = rendered.annotationDiv;
}

function createLinkService(pdfDocument, navigation) {
  return {
    addLinkAttributes(link, url) {
      let parsedUrl;
      try {
        parsedUrl = new URL(url, window.location.href);
      } catch {
        return;
      }
      if (!["http:", "https:", "mailto:"].includes(parsedUrl.protocol)) {
        return;
      }
      link.href = parsedUrl.href;
      link.title = parsedUrl.href;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    },
    getDestinationHash() {
      return "#pdf-destination";
    },
    getAnchorUrl(anchor = "") {
      return anchor || "#";
    },
    async goToDestination(destination) {
      const pageNumber = await resolveDestinationPage(pdfDocument, destination);
      if (pageNumber !== null) navigation.goToPage(pageNumber);
    },
    executeNamedAction(action) {
      navigation.executeNamedAction(action);
    },
    async executeSetOCGState() {},
    async getAttachmentContent() {
      return null;
    },
  };
}

async function resolveDestinationPage(pdfDocument, destination) {
  const explicitDestination =
    typeof destination === "string"
      ? await pdfDocument.getDestination(destination)
      : destination;
  if (!Array.isArray(explicitDestination)) return null;

  const [pageReference] = explicitDestination;
  if (Number.isInteger(pageReference)) return pageReference + 1;
  try {
    return (await pdfDocument.getPageIndex(pageReference)) + 1;
  } catch {
    return null;
  }
}

function secureExternalLinks(annotationLayer) {
  for (const link of annotationLayer.querySelectorAll('a[target="_blank"]')) {
    link.rel = "noopener noreferrer";
  }
}

function reportViewerError(stage, error, pdfUrl) {
  let safeUrl = "invalid-url";
  try {
    const parsedUrl = new URL(pdfUrl, window.location.href);
    safeUrl = `${parsedUrl.origin}${parsedUrl.pathname}`;
  } catch {
    // Keep the fallback and never log a raw, potentially sensitive URL.
  }
  console.error(
    "PDF viewer failure",
    JSON.stringify({
      stage,
      url: safeUrl,
      error: error?.name || "Error",
    }),
  );
}

function captureScrollPosition(stage) {
  return {
    x: stage.scrollWidth
      ? (stage.scrollLeft + stage.clientWidth / 2) / stage.scrollWidth
      : 0.5,
    y: stage.scrollHeight
      ? (stage.scrollTop + stage.clientHeight / 2) / stage.scrollHeight
      : 0.5,
  };
}

function restoreScrollPosition(stage, position) {
  stage.scrollLeft = position.x * stage.scrollWidth - stage.clientWidth / 2;
  stage.scrollTop = position.y * stage.scrollHeight - stage.clientHeight / 2;
}
