# SkayClearTux 1.3.2 — тихие окна, автообновление и Discord из коробки

Исправление самых заметных багов и удобное обновление: на Windows больше нет
всплывающих окон консоли, автообновления AppImage работают без ручной настройки,
а Discord Rich Presence получил поддержку Windows.

---

## Что исправлено

### Windows: никаких всплывающих cmd/PowerShell
- Все фоновые системные команды (процессы, службы, сеть, железо, winget, WMI и
  др.) запускаются скрытно через `CREATE_NO_WINDOW`/скрытый `STARTUPINFO`.
- Перезапуск после обновления на Windows тоже выполняется без лишних окон.

### Автообновление работает «из коробки»
- Если адрес манифеста не задан, приложение автоматически проверяет официальный
  релиз: `https://github.com/skayinray/SkayClearTux/releases/latest/download/latest.json`.
- Релизный CI теперь публикует `latest.json` вместе с артефактами (включая
  SHA-256 AppImage), поэтому новые версии находятся и устанавливаются сами.
- Для запущенного AppImage обновление скачивается, проверяется по контрольной
  сумме и применяется автоматически.

### Discord Rich Presence на всех платформах
- IPC-клиент умеет работать не только с Unix-сокетами, но и с именованными
  каналами Windows (`\\.\pipe\discord-ipc-N`).
- Активность можно включить в настройках (по умолчанию включена). Для показа
  статуса нужен Application ID вашего приложения Discord.

### Сборка и пакеты
- Версии приложения, AppImage, `.deb` и `.rpm` синхронизированы с тегом релиза.
- Workflow сборки публикует актуальные артефакты и `latest.json`.

---

## Установка

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.3.2-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.3.2-amd64.deb` | `sudo apt install ./SkayClearTux-1.3.2-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.3.2-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.3.2-x86_64.rpm` |
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
