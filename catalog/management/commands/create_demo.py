from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from pypdf import PdfWriter
from wagtail.documents import get_document_model

from catalog.models import (
    DocumentIndexPage,
    HomePage,
    PageComment,
    PdfDocumentPage,
)


class Command(BaseCommand):
    help = "Создать демонстрационный трёхстраничный PDF и комментарии."

    def handle(self, *args, **options):
        home = HomePage.objects.first()
        if home is None:
            raise RuntimeError("Главная страница не найдена. Сначала выполните migrate.")

        index = (
            home.get_children()
            .type(DocumentIndexPage)
            .specific()
            .filter(slug="documents")
            .first()
        )
        if index is None:
            index = home.add_child(
                instance=DocumentIndexPage(
                    title="Документы",
                    slug="documents",
                    intro="<p>Демонстрационный каталог PDF-документов.</p>",
                )
            )
        index.save_revision().publish()

        document_model = get_document_model()
        document = document_model.objects.filter(title="Демонстрационный PDF").first()
        if document is None:
            document = document_model.objects.create(
                title="Демонстрационный PDF",
                file=ContentFile(_make_pdf(), name="demo.pdf"),
            )

        page = (
            index.get_children()
            .type(PdfDocumentPage)
            .specific()
            .filter(slug="demo")
            .first()
        )
        if page is None:
            page = PdfDocumentPage(
                title="Демонстрационный документ",
                slug="demo",
                description="Три страницы для проверки просмотрщика и комментариев.",
                pdf_document=document,
            )
            _add_comments(page)
            page = index.add_child(instance=page)
        else:
            page.title = "Демонстрационный документ"
            page.description = "Три страницы для проверки просмотрщика и комментариев."
            page.pdf_document = document
            page.page_comments.all().delete()
            _add_comments(page)
            page.full_clean()
            page.save()
        page.save_revision().publish()

        self.stdout.write(self.style.SUCCESS(f"Демо создано: {page.url}"))


def _make_pdf() -> bytes:
    writer = PdfWriter()
    for width, height in [(595, 842), (842, 595), (595, 842)]:
        writer.add_blank_page(width=width, height=height)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def _add_comments(page):
    comments = [
        "<p><strong>Страница 1.</strong> Введение в демонстрационный документ.</p>",
        "<p><strong>Страница 2.</strong> Альбомная страница проверяет масштабирование.</p>",
        "<p><strong>Страница 3.</strong> Финальный комментарий.</p>",
    ]
    for page_number, comment in enumerate(comments, start=1):
        page.page_comments.add(
            PageComment(page_number=page_number, comment=comment)
        )
