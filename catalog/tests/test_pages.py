import shutil
import tempfile
from io import BytesIO

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from pypdf import PdfWriter
from wagtail.documents import get_document_model
from wagtail.models import Page

from catalog.models import (
    DocumentIndexPage,
    HomePage,
    PageComment,
    PdfDocumentPage,
)


class CatalogPageTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        cls.settings_override = override_settings(MEDIA_ROOT=cls.media_root)
        cls.settings_override.enable()

    @classmethod
    def tearDownClass(cls):
        cls.settings_override.disable()
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.home = HomePage.objects.get()
        self.index = self.home.add_child(
            instance=DocumentIndexPage(
                title="Документы",
                slug="documents",
                intro="<p>Выберите документ.</p>",
            )
        )
        self.index.save_revision().publish()

    def add_document(self, title, slug, *, live, comment="Комментарий"):
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=400)
        output = BytesIO()
        writer.write(output)
        document = get_document_model().objects.create(
            title=title,
            file=ContentFile(output.getvalue(), name=f"{slug}.pdf"),
        )
        instance = PdfDocumentPage(
            title=title,
            slug=slug,
            description=f"Описание: {title}",
            pdf_document=document,
            live=live,
        )
        instance.page_comments.add(PageComment(page_number=1, comment=comment))
        page = self.index.add_child(instance=instance)
        if live:
            page.save_revision().publish()
        else:
            page.live = False
            page.save(update_fields=["live"])
        return page

    def test_catalog_shows_live_document_and_hides_draft(self):
        self.add_document("Опубликован", "published", live=True)
        self.add_document("Черновик", "draft", live=False)

        response = self.client.get(self.index.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Опубликован")
        self.assertNotContains(response, "Черновик")
        self.assertTemplateUsed(response, "catalog/document_index_page.html")

    def test_catalog_has_clear_empty_state(self):
        response = self.client.get(self.index.url)

        self.assertContains(response, "Документов пока нет")

    def test_home_links_to_catalog(self):
        response = self.client.get(self.home.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.index.url)
        self.assertTemplateUsed(response, "catalog/home_page.html")

    def test_document_page_includes_local_viewer_and_safe_comment_json(self):
        page = self.add_document(
            "Документ",
            "document",
            live=True,
            comment='<p>Текст </script><script>alert("x")</script></p>',
        )

        response = self.client.get(page.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "catalog/pdf_document_page.html")
        self.assertContains(response, 'id="pdf-comments"')
        self.assertContains(response, "catalog/js/pdf-viewer.js")
        self.assertContains(response, 'aria-live="polite"', count=3)
        self.assertContains(response, 'data-previous disabled')
        self.assertContains(response, 'data-next disabled')
        self.assertContains(response, 'type="button"', count=2)
        self.assertNotContains(response, "</script><script>alert")
        self.assertContains(response, "\\u003C/script\\u003E")

    def test_page_type_restrictions(self):
        self.assertEqual(
            HomePage.creatable_subpage_models(), [DocumentIndexPage]
        )
        self.assertEqual(
            DocumentIndexPage.creatable_subpage_models(), [PdfDocumentPage]
        )
        self.assertEqual(PdfDocumentPage.creatable_subpage_models(), [])
        self.assertEqual(Page.objects.get(pk=self.home.pk).specific_class, HomePage)
