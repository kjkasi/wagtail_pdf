import shutil
import tempfile
from io import BytesIO

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from pypdf import PdfWriter
from wagtail.documents import get_document_model

from catalog.models import PageComment, PdfDocumentPage
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

    def make_page(self, document, comments):
        page = PdfDocumentPage(
            title="Документ",
            slug="document",
            description="Описание",
            pdf_document=document,
        )
        for number, text in comments:
            page.page_comments.add(
                PageComment(page_number=number, comment=text)
            )
        return page

    def test_reads_page_count_and_accepts_complete_comments(self):
        document = self.make_document(pages=2)
        page = self.make_page(document, [(1, "Первый"), (2, "Второй")])

        page.clean()

        self.assertEqual(page.page_count, 2)
        self.assertEqual(get_pdf_page_count(document), 2)

    def test_rejects_non_pdf_extension(self):
        document = self.make_document(name="sample.txt", content=b"not a pdf")
        page = self.make_page(document, [])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("pdf_document", raised.exception.error_dict)
        self.assertIn("расширение PDF", str(raised.exception))

    def test_rejects_corrupt_pdf(self):
        document = self.make_document(content=b"%PDF-not-valid")
        page = self.make_page(document, [])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("повреждён", str(raised.exception))

    def test_rejects_duplicate_page_numbers(self):
        document = self.make_document()
        page = self.make_page(document, [(1, "A"), (1, "B"), (2, "C")])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn(NON_FIELD_ERRORS, raised.exception.error_dict)
        self.assertIn("не должен повторяться", str(raised.exception))

    def test_rejects_out_of_range_page_number(self):
        document = self.make_document()
        page = self.make_page(document, [(1, "A"), (2, "B"), (3, "C")])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("выходит за пределы PDF", str(raised.exception))

    def test_requires_one_comment_for_every_page(self):
        document = self.make_document(pages=3)
        page = self.make_page(document, [(1, "A"), (3, "C")])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("Добавьте комментарии для страниц: 2", str(raised.exception))

    def test_rejects_visually_empty_rich_text(self):
        document = self.make_document(pages=1)
        page = self.make_page(document, [(1, "<p>&nbsp;</p>")])

        with self.assertRaises(ValidationError) as raised:
            page.clean()

        self.assertIn("Комментарий не должен быть пустым", str(raised.exception))

    def test_comment_number_must_be_positive(self):
        comment = PageComment(page_number=0, comment="Текст")

        with self.assertRaises(ValidationError) as raised:
            comment.clean()

        self.assertIn("page_number", raised.exception.error_dict)
