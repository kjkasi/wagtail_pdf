from django.urls import path

from .views import download_pdf

app_name = "catalog"

urlpatterns = [
    path("pdf/<int:page_id>/", download_pdf, name="download_pdf"),
]
