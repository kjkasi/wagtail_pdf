import shutil
import tempfile
from io import BytesIO

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.files.base import ContentFile
from django.test import override_settings
from playwright.sync_api import expect, sync_playwright
from pypdf import PdfWriter
from wagtail.documents import get_document_model

from catalog.models import (
    DocumentIndexPage,
    HomePage,
    PageComment,
    PdfDocumentPage,
)


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
        for number, comment in enumerate(
            ["Первый комментарий", "Второй комментарий", "Третий комментарий"],
            start=1,
        ):
            instance.page_comments.add(
                PageComment(page_number=number, comment=f"<p>{comment}</p>")
            )
        self.document_page = index.add_child(instance=instance)
        self.document_page.save_revision().publish()

    def test_navigation_mobile_layout_and_loading_error(self):
        page_url = self.live_server_url + self.document_page.url
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                self._exercise_viewer(browser, page_url)
            finally:
                browser.close()

    def _exercise_viewer(self, browser, page_url):
        context = browser.new_context(viewport={"width": 390, "height": 844})
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
            expect(browser_page.locator("[data-comment]")).to_contain_text(
                "Первый комментарий"
            )
            expect(browser_page.locator("[data-previous]")).to_be_disabled()

            browser_page.locator("[data-next]").evaluate(
                "button => { button.click(); button.click(); }"
            )
            expect(browser_page.locator("[data-current-page]")).to_have_text(
                "3", timeout=15_000
            )
            expect(browser_page.locator("[data-comment]")).to_contain_text(
                "Третий комментарий"
            )
            expect(browser_page.locator("[data-next]")).to_be_disabled()

            browser_page.locator("[data-previous]").click()
            expect(browser_page.locator("[data-current-page]")).to_have_text("2")
            expect(browser_page.locator("[data-comment]")).to_contain_text(
                "Второй комментарий"
            )

            pdf_box = browser_page.locator(".pdf-panel").bounding_box()
            comment_box = browser_page.locator(".comment-panel").bounding_box()
            self.assertGreater(comment_box["y"], pdf_box["y"])

            error_page = context.new_page()
            error_page.route("**/documents/*/*.pdf", lambda route: route.abort())
            error_page.goto(page_url, wait_until="domcontentloaded")
            expect(error_page.locator("[data-error]")).to_be_visible(
                timeout=15_000
            )
            expect(error_page.locator("[data-error]")).to_contain_text(
                "Не удалось загрузить PDF"
            )
        finally:
            context.close()
