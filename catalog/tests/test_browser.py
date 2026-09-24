import shutil
import tempfile
from io import BytesIO

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfWriter
from pypdf.annotations import Highlight, Link, Text
from pypdf.generic import ArrayObject, FloatObject
from wagtail.documents import get_document_model

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
        home = HomePage.objects.get()
        index = home.add_child(
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
        pdf = get_document_model().objects.create(
            title="Browser smoke PDF",
            file=ContentFile(output.getvalue(), name="browser-smoke.pdf"),
        )

        instance = PdfDocumentPage(
            title="Проверка просмотрщика",
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
            browser = playwright.chromium.launch(headless=True)
            try:
                self._exercise_viewer(browser, page_url)
            finally:
                browser.close()

    def _exercise_viewer(self, browser, page_url):
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        try:
            browser_page = context.new_page()
            browser_page.on("console", lambda message: print("browser console:", message.text))
            browser_page.on("pageerror", lambda error: print("browser error:", error))
            browser_page.on(
                "requestfailed",
                lambda request: print("browser request failed:", request.url),
            )
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
