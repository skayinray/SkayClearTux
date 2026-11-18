# SkayClearTux 1.3.3 — здоровье системы, отчёты и удобный Discord

Новый полезный функционал на главной странице и улучшения Discord Rich Presence,
чтобы активность было проще включить.

---

## Что нового

### Оценка здоровья системы
- На главной странице появилась карточка **«Здоровье системы»**: оценка 0–100,
  уровень состояния и рекомендации.
- Оценка учитывает текущие метрики: заполненность диска и памяти, температуру,
  заряд батареи и нагрузку на ЦП.

### Экспорт отчёта о системе (HTML)
- Кнопка **«Сохранить отчёт о системе (HTML)»** на главной собирает сводный
  отчёт в один файл.
- В отчёт входят обзор системы, метрики, сеть, диагностика и сведения об
  оборудовании — удобно для анализа и отправки.

### Discord Rich Presence — проще настроить
- Application ID можно задать не только в настройках, но и через переменные
  окружения `SKAYCLEARTUX_DISCORD_CLIENT_ID` / `DISCORD_CLIENT_ID` (удобно для
  сборок/окружений «из коробки»).
- В настройках отображается **статус подключения** к Discord и есть кнопка
  быстрого перехода в Discord Developer Portal.
- Поддержка Windows named pipes и Unix-сокетов сохранена, активность показывается
  пока приложение открыто.

> **Важно:** для отображения Rich Presence по-прежнему нужен валидный Discord
> Application (Client) ID (свой или встроенный в сборку). Без ID Discord не может
> показать активность — это требование платформы.

---

## Установка

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.3.3-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.3.3-amd64.deb` | `sudo apt install ./SkayClearTux-1.3.3-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.3.3-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.3.3-x86_64.rpm` |
| Windows | `SkayClearTux-windows.zip` | распаковать, запустить `SkayClearTux.exe` |
| macOS | `SkayClearTux.dmg` | открыть образ, перетащить в «Программы» |

> **macOS (первый запуск).** Приложение не подписано — щёлкните правой кнопкой →
> **Открыть** → **Открыть**.

Из исходников:

```bash
git clone https://github.com/skayinray/SkayClearTux.git
cd SkayClearTux
python -m venv .venv
.venv/bin/pip install PySide6
.venv/bin/python SkayClearTux.py
```

---

**Полный список изменений:** [CHANGELOG.md](https://github.com/skayinray/SkayClearTux/blob/main/CHANGELOG.md)

Создатель: [t.me/imneedasleep](https://t.me/imneedasleep)
