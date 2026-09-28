from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .models import PdfDocumentPage


@require_GET
def download_pdf(request, page_id):
    page = get_object_or_404(
        PdfDocumentPage.objects.live().public(),
        pk=page_id,
    )
    document = page.pdf_document
    if document is None:
        raise Http404("The PDF document is missing.")

    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.filename,
        content_type="application/pdf",
    )
