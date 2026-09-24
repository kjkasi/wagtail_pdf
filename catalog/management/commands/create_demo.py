from io import BytesIO

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Highlight, Link, Text
from pypdf.generic import ArrayObject, FloatObject
from wagtail.documents import get_document_model

from catalog.models import DocumentIndexPage, HomePage, PdfDocumentPage


class Command(BaseCommand):
    help = "Создать демонстрационный трёхстраничный PDF для просмотрщика."

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
        elif not _has_annotations(document):
            document.file.save(
                "demo.pdf",
                ContentFile(_make_pdf()),
                save=True,
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
                description="Три страницы разной ориентации со встроенными PDF-аннотациями.",
                pdf_document=document,
            )
            page = index.add_child(instance=page)
        else:
            page.title = "Демонстрационный документ"
            page.description = "Три страницы разной ориентации со встроенными PDF-аннотациями."
            page.pdf_document = document
            page.full_clean()
            page.save()
        page.save_revision().publish()

        self.stdout.write(self.style.SUCCESS(f"Демо создано: {page.url}"))


def _has_annotations(document) -> bool:
    try:
        document.file.open("rb")
        return bool(PdfReader(document.file).pages[0].annotations)
    except Exception:
        return False
    finally:
        document.file.close()


def _make_pdf() -> bytes:
    writer = PdfWriter()
    for width, height in [(595, 842), (842, 595), (595, 842)]:
        writer.add_blank_page(width=width, height=height)
    writer.add_annotation(
        page_number=0,
        annotation=Text(
            rect=(40, 760, 70, 790),
            text="Встроенная заметка PDF",
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
    return output.getvalue()
