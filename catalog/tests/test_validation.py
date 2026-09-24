import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from pypdf import PdfWriter
from wagtail.documents import get_document_model

from catalog.models import PdfDocumentPage
from catalog.pdf_utils import get_pdf_page_count


class PdfValidationTests(TestCase):
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

    def make_document(self, *, pages=2, name="sample.pdf", content=None):
        if content is None:
            writer = PdfWriter()
            for _ in range(pages):
                writer.add_blank_page(width=300, height=400)
            output = BytesIO()
            writer.write(output)
            content = output.getvalue()
        return get_document_model().objects.create(
            title=name,
            file=ContentFile(content, name=name),
        )

    @staticmethod
    def make_page(document):
        return PdfDocumentPage(
            title="Документ",
            slug="document",
            description="Описание",
            pdf_document=document,
        )

    def test_reads_and_stores_page_count_without_comments(self):
        document = self.make_document(pages=2)
        page = self.make_page(document)

        page.clean()

        self.assertEqual(page.page_count, 2)
        self.assertEqual(get_pdf_page_count(document), 2)

    def test_rejects_non_pdf_extension(self):
        document = self.make_document(name="sample.txt", content=b"not a pdf")
        page = self.make_page(document)

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("pdf_document", raised.exception.error_dict)
        self.assertIn("расширение PDF", str(raised.exception))

    def test_rejects_corrupt_pdf(self):
        document = self.make_document(content=b"%PDF-not-valid")
        page = self.make_page(document)

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("повреждён", str(raised.exception))
