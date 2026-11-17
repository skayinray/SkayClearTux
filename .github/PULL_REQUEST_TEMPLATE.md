<!-- Спасибо за вклад в SkayClearTux! Заполните чек-лист и опишите изменения. -->

## Что изменено

<!-- Кратко: что и зачем. Если правка закрывает Issue — укажите #номер. -->

Закрывает #

## Как проверено

<!-- Команды и результаты. Например:
     .venv/bin/python -m pytest -q
     QT_QPA_PLATFORM=offscreen .venv/bin/python tools/smoke_test.py
-->

## Чек-лист

- [ ] Ветка создана от актуального `main`
- [ ] Код собирается: `python -m compileall -q skaycleartux SkayClearTux.py`
- [ ] Тесты проходят: `python -m pytest -q`
- [ ] Дымовой тест проходит: `QT_QPA_PLATFORM=offscreen python tools/smoke_test.py`
- [ ] Линтер без ошибок: `python -m ruff check skaycleartux tests tools`
- [ ] Публичный API и структура модулей сохранены (или описано, почему изменены)
- [ ] Системные вызовы идут через `skaycleartux/backends/`, без `shell=True`
- [ ] Текст интерфейса на русском, без эмодзи и «квадратных» глифов
- [ ] Обновлены `README.md` / `docs/` / `CHANGELOG.md`, если нужно

## Скриншоты (для изменений интерфейса)

<!-- Перетащите изображения сюда -->
