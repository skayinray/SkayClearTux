# SkayClearTux 1.5.1 — исправления обновлений, интерфейса и шахмат

Багфикс-релиз: исправлена проверка обновлений (404), обновлён внешний вид и плавность интерфейса,
добавлен поиск по разделам и значки качества ходов прямо на шахматной доске.

---

## Что нового и исправлено

### Обновления
- **Исправлена ошибка `HTTP Error 404: Not Found`** при проверке обновлений: если прямой манифест недоступен,
  приложение получает `latest.json` из assets последнего релиза GitHub.

### Интерфейс и плавность
- **Обновлённый, более аккуратный дизайн** (навигация, карточки, поля, кнопки).
- **Поиск над категориями** в боковой панели — быстрый поиск разделов и функций.
- **Исправления обрезания текста** в элементах интерфейса.
- **Более плавная работа:** облегчены анимации переходов между страницами.

### Шахматы
- **Значки качества ходов над фигурой** на клетке назначения (как в онлайн-шахматах), помимо оценки в списке ходов.

---

## Установка

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.5.1-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.5.1-amd64.deb` | `sudo apt install ./SkayClearTux-1.5.1-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.5.1-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.5.1-x86_64.rpm` |
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
