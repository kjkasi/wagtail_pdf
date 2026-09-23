from pathlib import Path

from django.core.exceptions import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def get_pdf_page_count(document) -> int:
    """Return the number of pages in a Wagtail document or raise a user-facing error."""
    if document is None or not getattr(document, "file", None):
        raise ValidationError("Выберите PDF-документ.")

    filename = getattr(document.file, "name", "")
    if Path(filename).suffix.lower() != ".pdf":
        raise ValidationError("Файл должен иметь расширение PDF.")

    file_object = document.file
    try:
        file_object.open("rb")
        file_object.seek(0)
        header = file_object.read(5)
        file_object.seek(0)
        if header != b"%PDF-":
            raise ValidationError("Выбранный файл не является PDF.")
        reader = PdfReader(file_object, strict=True)
        if reader.is_encrypted:
            raise ValidationError("Защищённые паролем PDF не поддерживаются.")
        page_count = len(reader.pages)
    except ValidationError:
        raise
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise ValidationError("PDF повреждён или не может быть прочитан.") from exc
    finally:
        try:
            file_object.seek(0)
        except (OSError, ValueError):
            pass

    if page_count < 1:
        raise ValidationError("PDF должен содержать хотя бы одну страницу.")
    return page_count
