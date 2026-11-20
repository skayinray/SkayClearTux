# SkayClearTux 1.5.3.2 — мини-исправление интерфейса главного экрана

Мини-багфикс: текст и элементы главного экрана (дашборда) лучше подстраиваются под разрешение/размер окна, чтобы не обрезаться и не выходить за границы на небольших экранах.

---

## Исправлено
- **Главный экран (дашборд):** переработана компоновка верхнего блока (статус и подсказка теперь располагаются вертикально с переносом строк), чтобы текст корректно помещался при меньшей ширине окна.
- **Масштаб и читаемость:** уменьшены размеры заголовков/метрик/бейджа и отступы, сужена боковая панель и снижено минимальное допустимое разрешение окна — интерфейс главного меню удобнее отображается на экранах с небольшим разрешением.

---

## Установка

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.5.3.2-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.5.3.2-amd64.deb` | `sudo apt install ./SkayClearTux-1.5.3.2-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.5.3.2-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.5.3.2-x86_64.rpm` |
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
