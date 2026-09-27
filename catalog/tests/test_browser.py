import shutil
import tempfile
from io import BytesIO
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfWriter
from pypdf.annotations import Highlight, Link, Text
from pypdf.generic import ArrayObject, FloatObject
from wagtail.documents import get_document_model
from wagtail.models import Collection, Locale, Page, Site

from catalog.models import DocumentIndexPage, HomePage, PdfDocumentPage


class ViewerBrowserSmokeTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)

    def setUp(self):
        home = HomePage.objects.first()
        if home is None:
            Locale.objects.get_or_create(language_code=settings.LANGUAGE_CODE)
            root = cast(Page | None, Page.get_first_root_node())
            if root is None:
                # Treebeard's classmethod decorator loses its callable signature.
                root = cast(Page, cast(Any, Page).add_root(
                    instance=Page(title="Root", slug="root")
                ))
            home = cast(HomePage, cast(Any, root).add_child(
                instance=HomePage(title="Главная", slug="home")
            ))
            Site.objects.create(hostname="localhost", root_page=home, is_default_site=True)
        index = cast(Any, home).add_child(
            instance=DocumentIndexPage(title="Документы", slug="documents")
        )
        index.save_revision().publish()

        writer = PdfWriter()
        for width, height in [(595, 842), (842, 595), (595, 842)]:
            writer.add_blank_page(width=width, height=height)
        writer.add_annotation(
            page_number=0,
            annotation=Text(
                rect=(40, 760, 70, 790),
                text="Встроенная заметка",
            ),
        )
        writer.add_annotation(
            page_number=0,
            annotation=Highlight(
                rect=(90, 690, 270, 720),
                quad_points=ArrayObject(
                    [
                        FloatObject(value)
                        for value in (90, 720, 270, 720, 90, 690, 270, 690)
                    ]
                ),
            ),
        )
        writer.add_annotation(
            page_number=0,
            annotation=Link(
                rect=(90, 630, 270, 665),
                url="https://example.com",
            ),
        )
        writer.add_annotation(
            page_number=0,
            annotation=Link(
                rect=(90, 570, 270, 605),
                target_page_index=1,
            ),
        )
        output = BytesIO()
        writer.write(output)
        if Collection.get_first_root_node() is None:
            cast(Any, Collection).add_root(name="Root")
        pdf = get_document_model().objects.create(
            title="Browser smoke PDF",
            file=ContentFile(output.getvalue(), name="browser-smoke.pdf"),
        )

        instance = PdfDocumentPage(
            title="Очень длинное название PDF для проверки доступности кнопок " * 4,
            slug="viewer-smoke",
            description="Тест навигации.",
            pdf_document=pdf,
        )
        self.document_page = index.add_child(instance=instance)
        self.document_page.save_revision().publish()

    def test_stable_responsive_layout_navigation_and_loading_error(self):
        page_url = (
            self.live_server_url.replace("localhost", "127.0.0.1")
            + self.document_page.url
        )
        with sync_playwright() as playwright:
            for engine in (playwright.chromium, playwright.firefox):
                with self.subTest(engine=engine.name):
                    browser = engine.launch(headless=True)
                    try:
                        self._exercise_viewer(browser, page_url)
                    finally:
                        browser.close()

    def test_modal_lifecycle_and_close_during_loading(self):
        page_url = self.live_server_url + self.document_page.url
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context()
            try:
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                held_requests = []
                page.route("**/documents/*/*.pdf", lambda route: held_requests.append(route))
                with page.expect_request("**/documents/*/*.pdf"):
                    page.goto(page_url, wait_until="domcontentloaded")
                modal = page.locator("[data-pdf-modal]")
                expect(modal).to_be_visible()
                expect(page.locator("[data-loading]")).to_be_visible()
                page.locator("[data-pdf-close]").click()
                expect(modal).to_be_hidden()
                expect(page.locator("[data-pdf-open]")).to_be_focused()
                self.assertEqual(len(held_requests), 1)
                held_requests[0].fulfill(response=held_requests[0].fetch())
                expect(page.locator("[data-total-pages]")).to_have_text("3")
                expect(page.locator("[data-current-page]")).to_have_text("—")
                page.locator("[data-pdf-open]").click()
                expect(page.locator("[data-current-page]")).to_have_text("1")
                page.locator("[data-next]").click()
                expect(page.locator("[data-current-page]")).to_have_text("2")
                page.locator("[data-zoom-in]").click()
                expect(page.locator("[data-pdf-viewer]")).to_have_attribute("aria-busy", "false")
                for _ in range(12):
                    page.keyboard.press("Tab")
                    self.assertTrue(
                        modal.evaluate("el => el.contains(document.activeElement)"),
                        page.evaluate("document.activeElement.outerHTML.slice(0, 500)"),
                    )
                page.locator("[data-pdf-close]").focus()
                page.keyboard.press("Shift+Tab")
                self.assertTrue(modal.evaluate("el => el.contains(document.activeElement)"))
                page.keyboard.press("Escape")
                expect(modal).to_be_hidden()
                expect(page.locator("[data-pdf-open]")).to_be_focused()
                expect(page.get_by_text("Тест навигации.", exact=True)).to_be_visible()
                page.set_viewport_size({"width": 1000, "height": 700})
                page.locator("[data-pdf-open]").click()
                expect(page.locator("[data-pdf-viewer]")).to_have_attribute("aria-busy", "false")
                expect(page.locator("[data-current-page]")).to_have_text("2")
                expect(page.locator("[data-zoom-level]")).to_have_text("125%")
                # Close in the same event turn as a new render request.
                page.evaluate("""() => {
                    window.hiddenCommits = 0;
                    const modal = document.querySelector('[data-pdf-modal]');
                    new MutationObserver(() => {
                        if (!modal.classList.contains('show')) window.hiddenCommits++;
                    }).observe(document.querySelector('[data-pdf-page]'), {childList: true});
                    document.querySelector('[data-next]').click();
                    queueMicrotask(() => document.querySelector('[data-pdf-close]').click());
                }""")
                expect(modal).to_be_hidden()
                page.set_viewport_size({"width": 900, "height": 600})
                expect(page.locator("[data-current-page]")).to_have_text("2")
                page.locator("[data-pdf-open]").click()
                expect(page.locator("[data-current-page]")).to_have_text("3")
                self.assertEqual(page.evaluate("window.hiddenCommits"), 0)
                self.assertEqual(len(held_requests), 1)
                self.assertEqual(errors, [])
            finally:
                context.close()
                browser.close()

    def test_viewer_without_native_map_upsert_in_page_and_worker(self):
        # Firefox 140 lacks these APIs (MDN: Firefox 144 / Chrome 145).
        # This simulates API availability, not an entire old browser engine.
        missing_apis = """
            delete Map.prototype.getOrInsert;
            delete Map.prototype.getOrInsertComputed;
        """
        page_url = self.live_server_url + self.document_page.url

        def old_worker_environment(route):
            response = route.fetch()
            route.fulfill(response=response, body=missing_apis + response.text())

        with sync_playwright() as playwright:
            for engine in (playwright.chromium, playwright.firefox):
                with self.subTest(engine=engine.name):
                    browser = engine.launch(headless=True)
                    page = browser.new_page()
                    try:
                        errors = []
                        def capture_error(error, captured=errors):
                            captured.append(str(error))
                            print("compatibility error:", str(error))

                        page.on("pageerror", capture_error)
                        page.on("console", lambda message: print("compatibility:", message.text))
                        page.add_init_script(missing_apis)
                        page.route("**/pdf.worker.js", old_worker_environment)
                        page.goto(page_url)
                        probe = page.evaluate("""async () => {
                            const lib = await import('/static/catalog/vendor/pdfjs/pdf.js');
                            lib.GlobalWorkerOptions.workerSrc = '/static/catalog/vendor/pdfjs/pdf.worker.js';
                            const task = lib.getDocument({
                                url: document.querySelector('[data-pdf-viewer]').dataset.pdfUrl,
                            });
                            const pdf = await task.promise;
                            try {
                                const first = await pdf.getPage(1);
                                const canvas = document.createElement('canvas');
                                await first.render({canvasContext: canvas.getContext('2d'),
                                    viewport: first.getViewport({scale: 1})}).promise;
                                return 'rendered';
                            } catch (error) {
                                return String(error);
                            } finally {
                                await task.destroy();
                            }
                        }""")
                        self.assertEqual(probe, "rendered")
                        expect(page.locator("[data-current-page]")).to_have_text("1", timeout=10_000)
                        self._assert_fit_bounds(page, 595, 842)
                        layer = page.locator("[data-annotation-layer]")
                        expect(layer.locator(".textAnnotation")).to_have_count(1)
                        layer.locator("[data-internal-link] a").click()
                        expect(page.locator("[data-current-page]")).to_have_text("2")
                        self.assertEqual(errors, [])
                    finally:
                        browser.close()

    def test_modal_stacks_above_wagtail_userbar(self):
        user = get_user_model().objects.create_superuser(username="viewer-admin")
        self.client.force_login(user)
        page_url = self.live_server_url + self.document_page.url
        session = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(device_scale_factor=2)
            try:
                context.add_cookies([{
                    "name": settings.SESSION_COOKIE_NAME,
                    "value": session,
                    "url": self.live_server_url,
                }])
                page = context.new_page()
                page.goto(page_url)
                expect(page.locator("[data-current-page]")).to_have_text("1")
                trigger = page.locator("wagtail-userbar [data-wagtail-userbar-trigger]")
                expect(trigger).to_be_visible()
                self.assertTrue(trigger.evaluate("""el => {
                    const r = el.getBoundingClientRect();
                    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
                    return document.querySelector('[data-pdf-modal]').contains(hit);
                }"""))
                self._assert_fit_bounds(page, 595, 842)
                self.assertAlmostEqual(page.locator("[data-pdf-canvas]").evaluate(
                    "el => el.width / el.getBoundingClientRect().width"
                ), 2, delta=0.01)
                page.locator("[data-pdf-close]").click()
                expect(trigger).to_be_visible()
            finally:
                context.close()
                browser.close()

    def test_dependency_failures_leave_errors_and_working_close_button(self):
        page_url = self.live_server_url + self.document_page.url
        failures = [
            ("**/pdf-viewer.js", "Не удалось запустить"),
            ("**/vendor/pdfjs/pdf.js", "Не удалось запустить"),
            ("**/pdf.worker.js", "Не удалось загрузить PDF"),
        ]
        with sync_playwright() as playwright:
            for engine in (playwright.chromium, playwright.firefox):
                browser = engine.launch(headless=True)
                try:
                    for pattern, message in failures:
                        with self.subTest(engine=engine.name, resource=pattern):
                            page = browser.new_page()
                            try:
                                errors = []
                                page.on("pageerror", lambda error, captured=errors: captured.append(str(error)))
                                page.route(pattern, lambda route: route.abort())
                                page.goto(page_url)
                                expect(page.locator("[data-error]")).to_contain_text(message, timeout=15_000)
                                expect(page.locator("[data-loading]")).to_be_hidden()
                                page.locator("[data-pdf-close]").click()
                                expect(page.locator("[data-pdf-open]")).to_be_focused()
                                page.locator("[data-pdf-open]").click()
                                expect(page.locator("[data-error]")).to_be_visible()
                                page.keyboard.press("Escape")
                                expect(page.locator("[data-pdf-modal]")).to_be_hidden()
                                self.assertEqual(errors, [])
                            finally:
                                page.close()
                    page = browser.new_page()
                    try:
                        page.route("**/bootstrap.bundle.min.js", lambda route: route.abort())
                        page.goto(page_url)
                        expect(page.locator("[data-modal-error]")).to_be_visible()
                        expect(page.locator("[data-pdf-open]")).to_be_disabled()
                        expect(page.get_by_text("Тест навигации.", exact=True)).to_be_visible()
                    finally:
                        page.close()
                finally:
                    browser.close()

    def test_fit_geometry_in_chromium_and_firefox(self):
        page_url = self.live_server_url + self.document_page.url
        sizes = [(1920, 1080), (1920, 900), (1280, 720), (390, 844)]
        with sync_playwright() as playwright:
            for engine in (playwright.chromium, playwright.firefox):
                browser = engine.launch(headless=True)
                try:
                    for width, height in sizes:
                        with self.subTest(engine=engine.name, width=width, height=height):
                            context = browser.new_context(viewport={"width": width, "height": height})
                            try:
                                page = context.new_page()
                                errors = []
                                page.on("pageerror", lambda error, captured=errors: captured.append(str(error)))
                                page.goto(page_url)
                                expect(page.locator("[data-current-page]")).to_have_text("1")
                                self._assert_fit_bounds(page, 595, 842)
                                toolbar = page.locator(".viewer-toolbar").bounding_box()
                                page.locator("[data-next]").click()
                                expect(page.locator("[data-current-page]")).to_have_text("2")
                                self._assert_fit_bounds(page, 842, 595)
                                self.assertEqual(toolbar, page.locator(".viewer-toolbar").bounding_box())
                                page.locator("[data-zoom-in]").evaluate(
                                    "el => { for (let i = 0; i < 8; i++) el.click(); }"
                                )
                                expect(page.locator("[data-zoom-level]")).to_have_text("300%")
                                expect(page.locator("[data-pdf-viewer]")).to_have_attribute("aria-busy", "false")
                                self._assert_layers_align(page)
                                self.assertTrue(page.locator("[data-pdf-stage]").evaluate(
                                    "el => el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight"
                                ))
                                page.locator("[data-pdf-stage]").evaluate("el => { el.scrollLeft = 0; el.scrollTop = 0; }")
                                stage = page.locator("[data-pdf-stage]").bounding_box()
                                canvas = page.locator("[data-pdf-canvas]").bounding_box()
                                assert stage is not None and canvas is not None
                                self.assertGreaterEqual(canvas["x"], stage["x"])
                                self.assertGreaterEqual(canvas["y"], stage["y"])
                                self.assertEqual(toolbar, page.locator(".viewer-toolbar").bounding_box())
                                self.assertEqual(page.evaluate("window.scrollY"), 0)
                                page.locator("[data-zoom-fit]").click()
                                self._assert_fit_bounds(page, 842, 595)
                                page.set_viewport_size({"width": 800, "height": 600})
                                self._assert_fit_bounds(page, 842, 595)
                                self.assertEqual(errors, [])
                            finally:
                                context.close()
                finally:
                    browser.close()

    def _assert_fit_bounds(self, page, page_width, page_height):
        page.wait_for_function("""([width, height]) => {
            const stage = document.querySelector('[data-pdf-stage]');
            const canvas = document.querySelector('[data-pdf-canvas]');
            const style = getComputedStyle(stage);
            const w = stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
            const h = stage.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom);
            const scale = Math.min(w / width, h / height);
            const box = canvas.getBoundingClientRect();
            return document.querySelector('[data-pdf-viewer]').getAttribute('aria-busy') === 'false'
                && Math.abs(box.width - width * scale) <= 1
                && Math.abs(box.height - height * scale) <= 1;
        }""", arg=[page_width, page_height], timeout=10_000)
        bounds = page.locator("[data-pdf-canvas], .viewer-toolbar, [data-pdf-modal] button").evaluate_all("""
            elements => elements.map(el => {
                const r = el.getBoundingClientRect();
                return {label: el.textContent || el.getAttribute('aria-label'),
                    x: r.x, y: r.y, right: r.right, bottom: r.bottom,
                    width: innerWidth, height: innerHeight};
            })
        """)
        for box in bounds:
            self.assertGreaterEqual(box["x"], -1, box)
            self.assertGreaterEqual(box["y"], -1, box)
            self.assertLessEqual(box["right"], box["width"] + 1, box)
            self.assertLessEqual(box["bottom"], box["height"] + 1, box)
        overflow = page.locator("[data-pdf-stage]").evaluate(
            "el => [el.scrollWidth - el.clientWidth, el.scrollHeight - el.clientHeight]"
        )
        self.assertLessEqual(max(overflow), 1)
        self._assert_layers_align(page)

    def _exercise_viewer(self, browser, page_url):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            browser_page = context.new_page()
            browser_page.on("console", lambda message: print("browser console:", message.text))
            failures = []
            browser_page.on("pageerror", lambda error: failures.append(str(error)))
            browser_page.on("requestfailed", lambda request: failures.append(request.url))
            browser_page.on("response", lambda response: (
                failures.append(f"{response.status}: {response.url}")
                if response.status >= 400 else None
            ))
            browser_page.goto(page_url, wait_until="domcontentloaded")

            canvas = browser_page.locator("[data-pdf-canvas]")
            expect(canvas).to_be_visible(timeout=15_000)
            expect(browser_page.locator("[data-current-page]")).to_have_text("1")
            expect(browser_page.locator("[data-previous]")).to_be_disabled()
            expect(browser_page.locator("[data-zoom-level]")).to_have_text("100%")

            annotation_layer = browser_page.locator("[data-annotation-layer]")
            expect(annotation_layer.locator(".textAnnotation")).to_have_count(1)
            expect(annotation_layer.locator(".highlightAnnotation")).to_have_count(1)
            expect(annotation_layer.locator(".linkAnnotation")).to_have_count(2)
            external_link = annotation_layer.locator(
                'a[href^="https://example.com"]'
            )
            expect(external_link).to_have_attribute("target", "_blank")
            self.assertIn(
                "noopener",
                external_link.get_attribute("rel"),
            )
            self._assert_layers_align(browser_page)

            annotation_layer.locator("[data-internal-link] a").click()
            expect(browser_page.locator("[data-current-page]")).to_have_text("2")
            browser_page.locator("[data-previous]").click()
            expect(browser_page.locator("[data-current-page]")).to_have_text("1")

            initial_canvas_width = canvas.evaluate(
                "element => element.getBoundingClientRect().width"
            )
            browser_page.locator("[data-zoom-in]").click()
            expect(browser_page.locator("[data-zoom-level]")).to_have_text("125%")
            browser_page.wait_for_function(
                "width => document.querySelector('[data-pdf-canvas]').getBoundingClientRect().width > width",
                arg=initial_canvas_width,
            )
            self._assert_layers_align(browser_page)

            viewer_box = browser_page.locator(".viewer-shell").bounding_box()
            toolbar_box = browser_page.locator(".viewer-toolbar").bounding_box()
            self.assertGreaterEqual(viewer_box["width"], 1150)
            self.assertGreaterEqual(viewer_box["height"], 630)

            browser_page.locator("[data-next]").evaluate(
                "button => { button.click(); button.click(); }"
            )
            expect(browser_page.locator("[data-current-page]")).to_have_text(
                "3", timeout=15_000
            )
            expect(browser_page.locator("[data-next]")).to_be_disabled()
            expect(browser_page.locator("[data-zoom-level]")).to_have_text("125%")
            browser_page.locator("[data-zoom-fit]").click()
            expect(browser_page.locator("[data-zoom-level]")).to_have_text("100%")
            final_toolbar_box = browser_page.locator(".viewer-toolbar").bounding_box()
            for key in ("x", "y", "width", "height"):
                self.assertAlmostEqual(toolbar_box[key], final_toolbar_box[key], delta=1)

            browser_page.locator("[data-previous]").click()
            expect(browser_page.locator("[data-current-page]")).to_have_text("2")
            expect(browser_page.locator("[data-comment]")).to_have_count(0)

            browser_page.set_viewport_size({"width": 390, "height": 844})
            expect(browser_page.locator(".viewer-shell")).to_be_visible()
            expect(browser_page.locator(".viewer-toolbar")).to_be_visible()

            self.assertEqual(failures, [])
            error_messages = []
            error_page = context.new_page()
            error_page.on(
                "console",
                lambda message: error_messages.append(message.text),
            )
            error_page.route("**/documents/*/*.pdf", lambda route: route.abort())
            error_page.goto(page_url, wait_until="domcontentloaded")
            expect(error_page.locator("[data-error]")).to_be_visible(
                timeout=15_000
            )
            expect(error_page.locator("[data-error]")).to_contain_text(
                "Не удалось загрузить PDF"
            )
            self.assertTrue(
                any(
                    '"stage":"load"' in message
                    and "/documents/" in message
                    for message in error_messages
                ),
                error_messages,
            )
        finally:
            context.close()

    def _assert_layers_align(self, browser_page):
        canvas_box = browser_page.locator("[data-pdf-canvas]").bounding_box()
        annotation_box = browser_page.locator(
            "[data-annotation-layer]"
        ).bounding_box()
        for key in ("x", "y", "width", "height"):
            self.assertAlmostEqual(canvas_box[key], annotation_box[key], delta=1)
