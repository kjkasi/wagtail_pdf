from django.db import migrations


def create_homepage(apps, schema_editor):
    ContentType = apps.get_model("contenttypes.ContentType")
    Page = apps.get_model("wagtailcore.Page")
    Site = apps.get_model("wagtailcore.Site")
    HomePage = apps.get_model("catalog.HomePage")

    page_content_type = ContentType.objects.get(
        model="page", app_label="wagtailcore"
    )
    Page.objects.filter(
        content_type=page_content_type, slug="home", depth=2
    ).delete()

    homepage_content_type, _ = ContentType.objects.get_or_create(
        model="homepage", app_label="catalog"
    )
    homepage = HomePage.objects.create(
        title="Главная",
        draft_title="Главная",
        slug="home",
        content_type=homepage_content_type,
        path="00010001",
        depth=2,
        numchild=0,
        url_path="/home/",
    )
    Site.objects.create(
        hostname="localhost",
        port=8000,
        site_name="Каталог PDF-документов",
        root_page=homepage,
        is_default_site=True,
    )


def remove_homepage(apps, schema_editor):
    ContentType = apps.get_model("contenttypes.ContentType")
    HomePage = apps.get_model("catalog.HomePage")
    HomePage.objects.filter(slug="home", depth=2).delete()
    ContentType.objects.filter(model="homepage", app_label="catalog").delete()


class Migration(migrations.Migration):
    run_before = [("wagtailcore", "0053_locale_model")]
    dependencies = [("catalog", "0001_initial")]
    operations = [migrations.RunPython(create_homepage, remove_homepage)]
