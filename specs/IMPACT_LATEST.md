# Анализ влияния: Bootstrap, ESR и модальный PDF

Дата: 2026-09-27. План: `specs/BOOTSTRAP_ESR_MODAL_PLAN.md`.

## Цель

Весь публичный интерфейс на Bootstrap; автоматический modal PDF; целая страница и кнопки в доступном viewport на экране 1920×1080; проверенная работа в ALT-пакетах Firefox ESR 140.14.0-alt1 и Яндекс Браузер 25.2.4.1000-alt1.

## Зависимости и затрагиваемые файлы

- `wagtail_pdf/templates/base.html`: общий CSS/JS, контейнеры, шапка, skip-link; влияет на все публичные страницы.
- `catalog/templates/catalog/home_page.html`, `document_index_page.html`: Bootstrap layout, карточки, ссылки, пустое состояние.
- `wagtail_pdf/templates/404.html`, `500.html`: проверить наследование и оформление при изменении базового шаблона.
- `catalog/templates/catalog/pdf_document_page.html`: modal, trigger, header, stage, toolbar, доступные состояния загрузки/ошибки.
- `catalog/static/catalog/css/catalog.css`: убрать дубли Bootstrap, ограничить modal по высоте, оставить PDF-геометрию; проверить конфликты с annotation CSS.
- `catalog/static/catalog/js/pdf-viewer.js`: lifecycle modal, измерения после показа, fit по двум осям, очередь/отмена, обработка ошибок импорта и worker.
- `catalog/static/catalog/js/viewer-state.js`: чистый расчёт fitScale, сохранение zoom/navigation контрактов.
- `scripts/copy-pdfjs.mjs`, `package.json`, `package-lock.json`: локальные Bootstrap assets; выбор сборки PDF.js только после диагностики; согласованные vendor-версии и лицензии.
- `catalog/tests/test_pages.py`: существующие проверки точных class-строк и количества кнопок потребуют замены на контракты публичного поведения.
- `catalog/tests/test_browser.py`: добавить modal lifecycle, bounds вместо только visibility, разные viewport, Firefox и проверки отказов bootstrap/import/worker.
- `catalog/static/catalog/js/viewer-state.test.mjs`: покрыть вписывание по ширине и высоте.
- `README.md`, `specs/state.yaml`: новый интерфейс, поддерживаемые пакеты, условия ручной приёмки.

## Сохраняемые контракты

Публичные URL, фильтрация черновиков, Wagtail-публикация, проверка PDF и page_count неизменны. Модели и миграции не затрагиваются. Навигация, zoom, аннотации, безопасные ссылки и отключённый PDF scripting сохраняются. Wagtail admin не переводится на Bootstrap.

## Покрытие

- Серверные тесты: главная/каталог/документ, публикация и валидация.
- JS unit: границы страниц и zoom.
- Browser smoke: только Chromium, загрузка, навигация, zoom, аннотации, ошибка PDF, resize.
- Пробелы: реальные целевые пакеты, modal/focus/reopen, ошибки импорта/worker, fit по высоте и полное вхождение элементов в viewport.

## Связанные планы

Release-index и epic story IDs отсутствуют. Новый план заменяет UI-требования `PDF_VIEWER_CHANGE_PLAN.md` и продолжает его незавершённую LAN-проверку. Предыдущая ошибка inline-валидации админки с этим изменением не связана.

## Risk: High

Меняется общий публичный каркас и асинхронный цикл PDF. Точная причина браузерного сбоя пока не подтверждена; существующие тесты не покрывают целевые браузеры. Риска удаления данных в этом плане нет.

## Рекомендация

Сначала воспроизвести несовместимость на указанных ALT-пакетах. UI-изменения выполнять отдельными RED/GREEN шагами. Не считать Bootstrap или legacy PDF.js доказанным исправлением до повторного прогона исходного сценария. Общий gate — автотесты плюс протокол двух реальных браузеров.
