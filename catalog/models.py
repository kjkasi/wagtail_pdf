from django.core.exceptions import ValidationError
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page

from .pdf_utils import get_pdf_page_count


class HomePage(Page):
    intro = RichTextField(
        blank=True,
        default="",
        verbose_name="Краткое описание",
    )

    content_panels = Page.content_panels + [FieldPanel("intro")]
    parent_page_types = ["wagtailcore.Page"]
    subpage_types = ["catalog.DocumentIndexPage"]
    max_count = 1

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["catalog_index"] = (
            self.get_children()
            .live()
            .public()
            .type(DocumentIndexPage)
            .specific()
            .first()
        )
        return context

    class Meta:
        verbose_name = "главная страница"


class DocumentIndexPage(Page):
    intro = RichTextField(
        blank=True,
        default="",
        verbose_name="Описание каталога",
    )

    content_panels = Page.content_panels + [FieldPanel("intro")]
    parent_page_types = ["catalog.HomePage"]
    subpage_types = ["catalog.PdfDocumentPage"]
    max_count_per_parent = 1

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["documents"] = (
            self.get_children()
            .live()
            .public()
            .type(PdfDocumentPage)
            .specific()
        )
        return context

    class Meta:
        verbose_name = "каталог документов"


class PdfDocumentPage(Page):
    description = models.TextField(verbose_name="Краткое описание")
    pdf_document = models.ForeignKey(
        "wagtaildocs.Document",
        null=True,
        blank=False,
        on_delete=models.PROTECT,
        related_name="pdf_pages",
        verbose_name="PDF-документ",
    )
    page_count = models.PositiveIntegerField(
        default=0,
        editable=False,
        verbose_name="Количество страниц",
    )

    content_panels = Page.content_panels + [
        FieldPanel("description"),
        FieldPanel("pdf_document"),
    ]
    parent_page_types = ["catalog.DocumentIndexPage"]
    subpage_types = []

    def clean(self):
        super().clean()
        errors = {}

        try:
            document = self.pdf_document if self.pdf_document_id else None
            page_count = get_pdf_page_count(document)
        except ValidationError as exc:
            errors["pdf_document"] = exc.messages
            page_count = 0
        else:
            self.page_count = page_count

        if errors:
            raise ValidationError(errors)

    class Meta:
        verbose_name = "PDF-документ"
