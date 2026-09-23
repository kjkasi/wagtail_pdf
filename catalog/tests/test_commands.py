import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import DocumentIndexPage, PageComment, PdfDocumentPage


class CreateDemoCommandTests(TestCase):
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

    def test_command_is_idempotent_and_creates_complete_document(self):
        output = StringIO()

        call_command("create_demo", stdout=output)
        call_command("create_demo", stdout=output)

        self.assertEqual(DocumentIndexPage.objects.count(), 1)
        self.assertEqual(PdfDocumentPage.objects.count(), 1)
        page = PdfDocumentPage.objects.get()
        self.assertEqual(page.page_count, 3)
        self.assertTrue(page.live)
        self.assertEqual(PageComment.objects.filter(page=page).count(), 3)
        self.assertIn("Демо создано", output.getvalue())
