# Wagtail PDF

Публичный каталог PDF-документов с редакторскими комментариями к каждой странице.

## Требования

- Python 3.12.10
- Node.js 24 (для установки локальной сборки PDF.js)

## Локальный запуск

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm install
npm run build:vendor
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Админка: <http://127.0.0.1:8000/admin/>.

## Демонстрационные данные

После миграций выполните идемпотентную команду:

```bash
python manage.py create_demo
```

Она создаёт каталог, трёхстраничный PDF и по одному комментарию на страницу.

## Проверки

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm run test:js
python -m playwright install chromium  # один раз
pytest
```

## Зафиксированные версии

- Python 3.12.10
- Django 5.2.17 LTS
- Wagtail 7.4.3 LTS
- pypdf 6.19.0
- PDF.js (`pdfjs-dist`) 6.3.289
- Playwright 1.63.0 (только для браузерного smoke-теста)

PDF.js и worker копируются из npm-пакета в локальные static-файлы командой `npm run build:vendor`; внешний CDN не используется.
