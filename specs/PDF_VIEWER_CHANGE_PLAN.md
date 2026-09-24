# План изменения PDF-просмотрщика

## 1. Принятые решения

- Редакторские комментарии удаляются полностью: публичный блок, Wagtail inline, модель `PageComment`, валидация и сохранённые записи.
- Аннотации берутся из самого PDF. Создание аннотаций в Wagtail не входит в работу.
- PDF занимает почти всё доступное окно браузера.
- Панель управления закрепляется внутри просмотрщика и не меняет положение при переходе между книжными и альбомными страницами.
- Масштабирование выполняется кнопками «−», «+» и «По ширине». Предлагаемые границы: 50–300%, шаг 25%.
- Скрипты из PDF не выполняются. Внешние ссылки из аннотаций открываются безопасно.

## 2. Изменение требований

### REMOVED: редакторские комментарии

**До:** для каждой страницы PDF обязателен отдельный rich-text комментарий; он редактируется в Wagtail и показывается справа от PDF.

**После:** модель и данные комментариев удалены; публикация PDF от них не зависит; на публичной странице нет панели и JSON комментариев.

### MODIFIED: размер просмотрщика

**До:** PDF занимает около 7/11 ширины контента, а высота зависит от пропорций страницы.

**После:** просмотрщик занимает ширину страницы и большую часть высоты окна (`dvh` с разумной минимальной высотой); заголовок документа остаётся компактным.

### MODIFIED: навигация

**До:** панель находится после canvas и перемещается по вертикали при изменении высоты страницы.

**После:** панель закреплена в постоянной области просмотрщика; её координаты и размеры не зависят от ориентации страницы и масштаба.

### ADDED: масштабирование

Пользователь может увеличить, уменьшить или снова вписать PDF по ширине. Масштаб ограничен, отображается в процентах и сохраняется при перелистывании.

### ADDED: встроенные аннотации

Поверх canvas отображается PDF.js annotation layer: ссылки, текстовые заметки, выделения и другие поддерживаемые PDF.js аннотации. Слой использует тот же viewport и масштаб, что и canvas.

### ADDED: доступ по локальной сети

Основной сценарий должен работать при открытии страницы с другого компьютера по `http://<LAN-IP>:8000`, включая загрузку JS, worker и `/documents/...pdf`.

## 3. Критерии приёмки

1. Редактор создаёт и публикует `PdfDocumentPage` без комментариев.
2. После миграции таблицы/модели `PageComment` нет; старые записи удалены намеренно.
3. На публичной странице отсутствуют `.comment-panel`, `data-comment` и `pdf-comments`.
4. На desktop PDF занимает всю ширину области контента и не менее большей части видимой высоты; mobile остаётся работоспособным.
5. Позиция кнопок «Назад» и «Вперёд» не меняется при переключении между книжной и альбомной страницами.
6. Быстрые повторные переходы по-прежнему не показывают устаревшую страницу.
7. «+», «−» и «По ширине» изменяют масштаб в заданных границах; текущий процент виден пользователю.
8. После перелистывания выбранный масштаб сохраняется.
9. Встроенная тестовая ссылка/заметка/выделение присутствует в `.annotationLayer` и совпадает с canvas при zoom и resize.
10. JavaScript actions из PDF отключены; внешняя ссылка не получает доступ к `window.opener`.
11. Со второго компьютера HTML, модули PDF.js, worker и PDF возвращаются успешно, после чего canvas и annotation layer видимы.
12. При реальной ошибке загрузки пользователь видит понятное сообщение, а в консоль записывается URL и этап сбоя без чувствительных данных.

## 4. Порядок реализации

### Шаг 0. Закрыть предыдущий поток и сохранить данные

Текущий `specs/state.yaml` указывает `active_flow: fix_bug` и `handoff.next_skill: release-branch`. Перед новой веткой нужно завершить или явно отложить этот поток.

До миграции сделать резервную копию БД либо экспорт `PageComment`, несмотря на принятое решение удалить данные. Это оставляет путь восстановления при ошибке миграции.

**Проверка:**

```bash
.venv/Scripts/python.exe manage.py dumpdata catalog.PageComment --indent 2 > page-comments-backup.json
```

### Шаг 1. Сначала зафиксировать новое поведение тестами

Изменить тесты до реализации:

- `catalog/tests/test_admin.py`: страница создаётся без inline formset комментариев;
- `catalog/tests/test_validation.py`: остаются проверки расширения, повреждения PDF и `page_count`; удаляются проверки комментариев;
- `catalog/tests/test_pages.py`: шаблон не содержит панели/JSON комментариев и содержит zoom/annotation DOM;
- `catalog/static/catalog/js/viewer-state.test.mjs`: добавить pure helpers для ограничения масштаба и вычисления следующего zoom;
- `catalog/tests/test_browser.py`: использовать PDF с книжной и альбомной страницами и встроенными аннотациями; проверить стабильные координаты toolbar, zoom и annotation layer.

Тестовый PDF создавать через уже установленный `pypdf` (`pypdf.annotations.Text`, `Highlight` или `Link`), без нового пакета.

**Проверка ожидаемого RED:**

```bash
npm run test:js
.venv/Scripts/python.exe -m pytest catalog/tests/test_admin.py catalog/tests/test_validation.py catalog/tests/test_pages.py catalog/tests/test_browser.py -q
```

### Шаг 2. Полностью удалить комментарии

Изменения:

- `catalog/models.py`:
  - удалить `PageComment`, `InlinePanel`, `ParentalKey`, `Orderable`, `RichTextField` и helpers, используемые только комментариями;
  - удалить `PdfDocumentPage.base_form_class` и проверку полноты комментариев;
  - сохранить определение и проверку `page_count`;
- удалить `catalog/forms.py`, если после изменения в нём не останется кода;
- создать новую Django migration с `DeleteModel(PageComment)`;
- `catalog/templates/catalog/pdf_document_page.html`: удалить aside и `json_script`;
- `catalog/static/catalog/js/pdf-viewer.js`, `viewer-state.js`: удалить чтение и обновление комментариев;
- `catalog/management/commands/create_demo.py`: не создавать комментарии, изменить описание demo;
- обновить импорты и тестовые фабрики.

**Проверка:**

```bash
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
.venv/Scripts/python.exe -m pytest catalog/tests/test_admin.py catalog/tests/test_validation.py catalog/tests/test_pages.py catalog/tests/test_commands.py -q
```

### Шаг 3. Сделать почти полноэкранную и стабильную раскладку

Изменения:

- `catalog/templates/catalog/pdf_document_page.html`:
  - заменить двухколоночный `.viewer-grid` на единый `.viewer-shell`;
  - поместить canvas и будущий annotation layer в общий `position: relative` контейнер страницы;
  - перенести навигацию и zoom в одну toolbar;
- `catalog/static/catalog/css/catalog.css`:
  - для `.document-page .page-shell` увеличить допустимую ширину;
  - задать viewer высоту через `100dvh` с fallback на `vh`;
  - сделать stage отдельной прокручиваемой областью;
  - закрепить toolbar (`position: sticky`) в границах viewer;
  - задать кнопкам постоянные размеры и не менять DOM-порядок при состоянии `disabled`;
  - сохранить адаптивность и видимый keyboard focus.

Стабильность проверять сравнением `bounding_box()` toolbar и кнопок до/после перехода между страницами разной ориентации.

**Проверка:**

```bash
.venv/Scripts/python.exe -m pytest catalog/tests/test_browser.py -q
```

### Шаг 4. Добавить масштабирование

Разделить состояние:

- `fitScale` — масштаб вписывания по ширине;
- `zoomFactor` — пользовательский коэффициент;
- `effectiveScale = fitScale * zoomFactor`;
- минимальный/максимальный предел и шаг находятся в `viewer-state.js` и покрыты unit-тестами.

В `pdf-viewer.js`:

- добавить обработчики zoom out/in/fit;
- повторно использовать существующую очередь рендера и offscreen canvas;
- при resize пересчитывать `fitScale`, но не терять выбранный пользовательский zoom;
- сохранять центр/прокрутку по возможности без скачка toolbar;
- блокировать «−»/«+» на границах и показывать процент через `aria-live` без избыточных объявлений.

**Проверка:**

```bash
npm run test:js
.venv/Scripts/python.exe -m pytest catalog/tests/test_browser.py -q
```

### Шаг 5. Добавить PDF.js annotation layer

Использовать API уже зафиксированного `pdfjs-dist 6.3.289` `[OK]`; новый runtime package не нужен.

Подтверждённый локальным кодом PDF.js контракт:

- аннотации читаются через `page.getAnnotations({ intent: "display" })`;
- `AnnotationLayer` получает `div`, `page`, `viewport.clone({ dontFlip: true })` и link service;
- затем вызывается `annotationLayer.render({ annotations, renderForms, ... })`.

Изменения:

- `scripts/copy-pdfjs.mjs`: копировать официальный CSS для annotation layer (и web-модуль, только если выбран официальный `SimpleLinkService`);
- шаблон: подключить vendor CSS и добавить контейнер `.annotationLayer` поверх canvas;
- `pdf-viewer.js`:
  - получать аннотации текущей страницы;
  - создавать слой только для актуального `targetPage`;
  - передавать точно тот же viewport, что использован для canvas;
  - атомарно заменять canvas и annotation layer, чтобы быстрые переходы не смешивали страницы;
  - пересоздавать слой при zoom и resize;
  - оставить `enableScripting: false`;
  - настроить безопасные внешние ссылки и внутреннюю навигацию по страницам;
  - уничтожать/очищать старый слой перед заменой.

Не копировать стили annotation layer вручную выборочными фрагментами: использовать CSS той же версии, что и PDF.js, чтобы DOM и стили не разошлись после обновления.

**Проверка:**

```bash
npm run build:vendor
npm run test:js
.venv/Scripts/python.exe -m pytest catalog/tests/test_browser.py -q
```

### Шаг 6. Воспроизвести и устранить LAN-ошибку без догадок

Текущая проверка с этой машины по `http://192.168.1.189:8000` успешна, поэтому этап начинается со сбора фактов на проблемном компьютере.

1. Запустить:

   ```bash
   .venv/Scripts/python.exe manage.py runserver 0.0.0.0:8000 --noreload
   ```

2. На другом компьютере открыть `http://<LAN-IP>:8000`, а не `0.0.0.0` и не `localhost`.
3. В DevTools сохранить Console и Network HAR.
4. Проверить статусы и MIME для:
   - `catalog/js/pdf-viewer.js`;
   - `catalog/vendor/pdfjs/pdf.js`;
   - `catalog/vendor/pdfjs/pdf.worker.js`;
   - `/documents/<id>/<filename>.pdf`.
5. Зафиксировать браузер и версию, итоговый URL PDF, текст исключения PDF.js и наличие запроса в журнале Django.

Ветвление исправления:

- нет запроса в Django — проверить URL, firewall и сетевой профиль Windows;
- `404` static/worker — исправить static routing/build vendor;
- `404/403` PDF — исправить document/media routing и URL;
- MIME/HTML вместо JS/PDF — исправить маршрут или ответ;
- syntax/API error только в конкретном браузере — определить поддерживаемые браузеры либо выбрать совместимую сборку PDF.js;
- secure-context/CSP/CORS error — исправить конкретный заголовок или схему после воспроизведения, а не ослаблять политику глобально.

Добавить regression smoke-тест с сервером, доступным не через `localhost`, насколько это стабильно для CI, и описать LAN-запуск/Windows Firewall в `README.md`.

**Проверка:** ручной прогон со второго устройства плюс сохранённый HAR/скриншот; автоматическая часть:

```bash
.venv/Scripts/python.exe -m pytest catalog/tests/test_browser.py -q
```

### Шаг 7. Обновить документацию и выполнить полный gate

Обновить:

- `README.md` — новое назначение, управление zoom, встроенные аннотации, LAN-инструкция;
- `specs/planning-context.yaml` — убрать обязательные комментарии и исключение аннотаций;
- `specs/IMPLEMENTATION_PLAN.md` — пометить исходный план как исторический либо актуализировать разделы 3–10;
- demo-команду и её help-текст.

**Полная проверка:**

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py makemigrations --check --dry-run
npm run build:vendor
npm run test:js
.venv/Scripts/python.exe -m pytest -q
```

## 5. Риски и меры

| Риск | Мера |
|---|---|
| Потеря нужных комментариев | Явный backup перед необратимой миграцией; миграцию выполнять отдельным коммитом. |
| Annotation layer не совпадает с canvas | Один viewport/effective scale для обоих слоёв; browser-тест после zoom и resize. |
| Гонка при быстром листании | Коммитить canvas и annotation layer только если candidate всё ещё равен `targetPage`. |
| Большой PDF медленно масштабируется | Рендерить только текущую страницу, debounce resize, ограничить `devicePixelRatio` и max zoom. |
| Toolbar закрывает PDF | Зарезервировать её высоту внутри viewer, а не накладывать поверх содержимого без отступа. |
| Ссылки/скрипты в PDF | Отключить PDF scripting; безопасные атрибуты внешних ссылок; тест на `window.opener`. |
| LAN-дефект останется случайным | Считать его закрытым только после воспроизведения и проверки со второго физического устройства. |

## 6. Вне объёма

- создание и редактирование аннотаций на сайте;
- сохранение заполненных PDF-форм;
- свободное рисование поверх PDF;
- поиск, миниатюры, печать и скачивание;
- production-развёртывание и HTTPS-инфраструктура;
- одновременный показ нескольких страниц.

## 7. Рекомендуемое разбиение на коммиты

1. `test(viewer): define comment-free viewer behavior`
2. `refactor(catalog): remove page comments and validation`
3. `feat(viewer): stabilize near-fullscreen layout`
4. `feat(viewer): add bounded zoom controls`
5. `feat(viewer): render embedded PDF annotations`
6. `fix(viewer): support verified LAN loading scenario`
7. `docs(viewer): update usage and architecture notes`
