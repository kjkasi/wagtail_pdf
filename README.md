# Wagtail PDF

Публичный каталог PDF-документов со встроенным просмотрщиком на PDF.js. Просмотрщик показывает аннотации, которые уже находятся в PDF; отдельные комментарии в Wagtail не используются.

## Возможности

- каталог опубликованных PDF-документов;
- навигация кнопками «Назад» и «Вперёд»;
- масштаб 50–300% с шагом 25% и сбросом «По ширине»;
- ссылки, заметки, выделения и другие поддерживаемые аннотации PDF.js;
- адаптивная почти полноэкранная область просмотра;
- локальные PDF.js, worker, CSS и изображения без внешнего CDN.

JavaScript-действия из PDF не выполняются. Внешние ссылки открываются в новой вкладке с `noopener noreferrer`.

## Требования

- Python 3.12.10;
- Node.js 24.

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

```bash
python manage.py create_demo
```

Команда идемпотентно создаёт каталог и трёхстраничный PDF. Первая страница содержит встроенные заметку, выделение, внешнюю и внутреннюю ссылки.

## Доступ по локальной сети

1. Узнайте IPv4-адрес компьютера командой `ipconfig` (Windows) или `ip addr` (Linux).
2. Запустите сервер на всех локальных интерфейсах:

   ```bash
   python manage.py runserver 0.0.0.0:8000 --noreload
   ```

3. Если Windows Defender Firewall запрашивает разрешение, разрешите Python доступ только для частной сети. Если запроса нет, создайте входящее правило для TCP-порта 8000 в частном профиле.
4. На другом компьютере откройте `http://<IPv4-адрес>:8000`. Не используйте в браузере `0.0.0.0` или `localhost`.

Если PDF не загружается, откройте DevTools → Network и проверьте ответы для:

- `catalog/js/pdf-viewer.js`;
- `catalog/vendor/pdfjs/pdf.js`;
- `catalog/vendor/pdfjs/pdf.worker.js`;
- `catalog/vendor/pdfjs/pdf_viewer.css`;
- `/documents/<id>/<filename>.pdf`.

Все ответы должны иметь статус `200`; PDF должен возвращаться как `application/pdf`. Консоль просмотрщика сообщает этап `load` или `render` и URL без query-параметров. `runserver` предназначен только для разработки и не должен публиковаться в интернете.

## Проверки

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
npm run build:vendor
npm run test:js
python -m playwright install chromium  # один раз
pytest
```

Браузерный smoke-тест использует origin `127.0.0.1`, проверяет загрузку PDF.js и PDF, навигацию, стабильность toolbar, zoom, annotation layer и обработку ошибки загрузки.

## Зафиксированные версии

- Python 3.12.10;
- Django 5.2.17 LTS;
- Wagtail 7.4.3 LTS;
- pypdf 6.19.0;
- PDF.js (`pdfjs-dist`) 6.3.289;
- Playwright 1.63.0 (только для браузерного smoke-теста).
