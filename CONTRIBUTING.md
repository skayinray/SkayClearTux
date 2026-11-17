# Как помочь проекту

Спасибо за интерес к **SkayClearTux**! Ниже — как сообщить об ошибке, предложить
идею и прислать изменения.

## Куда обратиться

- **Вопросы, идеи, обмен опытом** — [GitHub Discussions](https://github.com/skayinray/SkayClearTux/discussions).
- **Ошибки и предложения** — [Issues](https://github.com/skayinray/SkayClearTux/issues/new/choose)
  (есть готовые шаблоны bug report и feature request).
- **Помощь и документация** — [SUPPORT.md](SUPPORT.md).
- **Уязвимости** — не в публичных Issues, см. [SECURITY.md](SECURITY.md).

Участвуя в проекте, вы соглашаетесь соблюдать [Кодекс поведения](CODE_OF_CONDUCT.md).

## Сообщить об ошибке

Создайте [Issue по шаблону](https://github.com/skayinray/SkayClearTux/issues/new?template=bug_report.yml)
и укажите:

- вашу ОС и её версию (Linux-дистрибутив, macOS, Windows);
- версию SkayClearTux (видна в разделе «О программе»);
- что вы делали, что ожидали и что получилось;
- при необходимости — вывод программы, скриншот или файл лога
  (путь к логу — в [SUPPORT.md](SUPPORT.md)).

## Предложить идею

Создайте [Issue по шаблону](https://github.com/skayinray/SkayClearTux/issues/new?template=feature_request.yml)
или начните обсуждение в Discussions. Опишите задачу и пользу — чем конкретнее,
тем лучше.

## Настройка окружения

Нужен **Python 3.11+**.

```bash
git clone https://github.com/skayinray/SkayClearTux.git
cd SkayClearTux
python -m venv .venv

# Linux / macOS:
.venv/bin/pip install -e ".[dev]"
.venv/bin/python SkayClearTux.py

# Windows (PowerShell):
.venv\Scripts\pip install -e ".[dev]"
.venv\Scripts\python SkayClearTux.py
```

Группа `dev` ставит `pytest`, `pytest-qt`, `pytest-cov`, `ruff`, `black`, `mypy`.

## Прислать изменения

1. Сделайте форк и ветку от актуального `main`:
   ```bash
   git checkout -b feature/korotkoe-imya
   ```
2. Внесите изменения и прогоните проверки (см. ниже).
3. Оформите Pull Request — шаблон подставится автоматически
   ([`.github/PULL_REQUEST_TEMPLATE.md`](.github/PULL_REQUEST_TEMPLATE.md)).
   Опишите, что изменено, зачем и как проверено; укажите номер Issue, если он есть.

## Проверки

Перед Pull Request'ом должны проходить:

```bash
# тесты: юнит-тесты бэкендов, cleaner, system_tools, updater и UI-тесты (pytest-qt)
.venv/bin/python -m pytest -q

# покрытие ядра (backends/ + cleaner.py) — порог 60%, как в CI
.venv/bin/python -m pytest -q --cov=skaycleartux.backends --cov=skaycleartux.cleaner \
    --cov-report=term-missing --cov-fail-under=60

# линтер — блокирует CI
.venv/bin/python -m ruff check skaycleartux tests tools

# синтаксис и дымовой тест интерфейса без экрана
.venv/bin/python -m compileall -q skaycleartux SkayClearTux.py tools tests
QT_QPA_PLATFORM=offscreen .venv/bin/python tools/smoke_test.py
```

`black` и `mypy` включены в мягком режиме (advisory): они подсказывают, но не
блокируют сборку, потому что проект исторически не форматировался black'ом.

UI-тесты запускаются в offscreen-режиме (`QT_QPA_PLATFORM=offscreen`), он уже
включён в `tests/conftest.py`. Если добавляете UI-тест, регистрируйте виджеты
через `qtbot.addWidget(...)`, иначе Qt-объекты уничтожаются после завершения
`QApplication` и процесс может упасть при выходе.

## Правила кода

- Python 3.11+, стиль — [PEP 8](https://peps.python.org/pep-0008/), длина строки
  до 100 символов.
- Весь системный код идёт через бэкенды `skaycleartux/backends/`. Если добавляете
  функцию для конкретной ОС — переопределяйте метод в нужном бэкенде, а в
  `BaseBackend` оставляйте безопасную заглушку.
- Команды запускайте **списком аргументов**, без `shell=True`, с таймаутом.
  Пользовательский ввод не подставляйте в строку команды.
- Любые обращения к внешним утилитам оборачивайте в `try/except` и предусматривайте
  понятное сообщение, если утилиты нет или нужны права администратора.
- Текст интерфейса — на русском. Не используйте эмодзи и редкие стрелки/знаки:
  Qt рисует их пустыми квадратами. Разрешены `– — … • · ± × ° « »`.
- Недоступную на текущей ОС функцию помечайте неактивной с подсказкой через
  `skaycleartux/ui_utils.py` (`mark_unavailable` / `mark_available`).

## Документация

- Обновите [docs/architecture.md](docs/architecture.md) или
  [docs/backends.md](docs/backends.md), если меняете структуру или контракт
  бэкендов.
- Добавьте запись в [CHANGELOG.md](CHANGELOG.md) (формат Keep a Changelog).
- Docstring'и публичных классов и функций — на русском, коротко и по делу.

## Лицензия

Отправляя изменения, вы соглашаетесь с тем, что они распространяются под
лицензией [MIT](LICENSE).
