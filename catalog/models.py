from html import unescape

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.utils.html import strip_tags
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page

from .forms import PdfDocumentPageForm
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
    base_form_class = PdfDocumentPageForm

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
        InlinePanel(
            "page_comments",
            label="Комментарий к странице",
            min_num=1,
        ),
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

        comments = list(self.page_comments.all())
        page_numbers = [comment.page_number for comment in comments]
        duplicate_numbers = sorted(
            {number for number in page_numbers if page_numbers.count(number) > 1}
        )
        if duplicate_numbers:
            errors[NON_FIELD_ERRORS] = [
                "Номер страницы не должен повторяться: "
                + ", ".join(map(str, duplicate_numbers))
                + "."
            ]

        if page_count:
            out_of_range = sorted(
                {
                    number
                    for number in page_numbers
                    if number is not None and not 1 <= number <= page_count
                }
            )
            if out_of_range:
                errors.setdefault(NON_FIELD_ERRORS, []).append(
                    "Номер страницы выходит за пределы PDF: "
                    + ", ".join(map(str, out_of_range))
                    + "."
                )

            present = {number for number in page_numbers if number is not None}
            missing = sorted(set(range(1, page_count + 1)) - present)
            if missing:
                errors.setdefault(NON_FIELD_ERRORS, []).append(
                    "Добавьте комментарии для страниц: "
                    + ", ".join(map(str, missing))
                    + "."
                )

        empty_comments = sorted(
            comment.page_number
            for comment in comments
            if not _has_visible_text(comment.comment)
            and comment.page_number is not None
        )
        if empty_comments:
            errors.setdefault(NON_FIELD_ERRORS, []).append(
                "Комментарий не должен быть пустым для страниц: "
                + ", ".join(map(str, empty_comments))
                + "."
            )

        if errors:
            raise ValidationError(errors)

    def comments_by_page(self):
        return {
            str(comment.page_number): str(comment.comment)
            for comment in self.page_comments.all().order_by("page_number")
        }

    class Meta:
        verbose_name = "PDF-документ"


class PageComment(Orderable):
    page = ParentalKey(
        PdfDocumentPage,
        on_delete=models.CASCADE,
        related_name="page_comments",
    )
    page_number = models.PositiveIntegerField(verbose_name="Номер страницы")
    comment = RichTextField(verbose_name="Комментарий")

    panels = [FieldPanel("page_number"), FieldPanel("comment")]

    def clean(self):
        super().clean()
        errors = {}
        if self.page_number is not None and self.page_number < 1:
            errors["page_number"] = "Номер страницы должен быть положительным."
        if not _has_visible_text(self.comment):
            errors["comment"] = "Комментарий не должен быть пустым."
        if errors:
            raise ValidationError(errors)

    class Meta(Orderable.Meta):
        ordering = ["page_number", "sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "page_number"],
                name="unique_comment_per_pdf_page",
            )
        ]
        verbose_name = "комментарий к странице"
        verbose_name_plural = "комментарии к страницам"


def _has_visible_text(value) -> bool:
    text = unescape(strip_tags(str(value or ""))).replace("\xa0", " ")
    return bool(text.strip())
