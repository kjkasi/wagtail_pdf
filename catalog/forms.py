from wagtail.admin.forms.pages import WagtailAdminPageForm


class PdfDocumentPageForm(WagtailAdminPageForm):
    def clean(self):
        cleaned_data = super().clean()
        comments = self.formsets.get("page_comments")
        if comments is not None and comments.is_valid():
            # Parent model validation needs the submitted children in the
            # in-memory cluster; modelcluster normally stages them only on save.
            comments.save(commit=False)
        return cleaned_data
