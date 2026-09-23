import json
import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfWriter
from wagtail.documents import get_document_model

from catalog.models import DocumentIndexPage, HomePage, PdfDocumentPage


class PdfDocumentAdminTests(TestCase):
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
        self.user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(self.user)
        home = HomePage.objects.get()
        self.index = home.add_child(
            instance=DocumentIndexPage(
                title="Документы",
                slug="documents",
            )
        )

    def test_editor_can_create_pdf_page_with_comment_for_every_page(self):
        document = self._make_document(pages=2)

        response = self.client.post(
            reverse(
                "wagtailadmin_pages:add",
                args=("catalog", "pdfdocumentpage", self.index.pk),
            ),
            {
                "title": "Новый документ",
                "slug": "new-document",
                "description": "Описание",
                "pdf_document": str(document.pk),
                "page_comments-TOTAL_FORMS": "2",
                "page_comments-INITIAL_FORMS": "0",
                "page_comments-MIN_NUM_FORMS": "1",
                "page_comments-MAX_NUM_FORMS": "1000",
                "page_comments-0-page_number": "1",
                "page_comments-0-comment": self._rich_text("Первый"),
                "page_comments-0-id": "",
                "page_comments-0-ORDER": "1",
                "page_comments-0-DELETE": "",
                "page_comments-1-page_number": "2",
                "page_comments-1-comment": self._rich_text("Второй"),
                "page_comments-1-id": "",
                "page_comments-1-ORDER": "2",
                "page_comments-1-DELETE": "",
                "action-publish": "action-publish",
            },
        )

        self.assertEqual(response.status_code, 302)
        page = PdfDocumentPage.objects.get(slug="new-document")
        self.assertEqual(page.page_count, 2)
        self.assertEqual(
            list(page.page_comments.values_list("page_number", flat=True)),
            [1, 2],
        )

    @staticmethod
    def _make_document(*, pages):
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=300, height=400)
        output = BytesIO()
        writer.write(output)
        return get_document_model().objects.create(
            title="sample.pdf",
            file=ContentFile(output.getvalue(), name="sample.pdf"),
        )

    @staticmethod
    def _rich_text(value):
        return json.dumps(
            {
                "blocks": [
                    {
                        "key": "abcde",
                        "type": "unstyled",
                        "depth": 0,
                        "text": value,
                        "inlineStyleRanges": [],
                        "entityRanges": [],
                    }
                ],
                "entityMap": {},
            }
        )
