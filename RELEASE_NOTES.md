# SkayClearTux 1.3.0 — не только Arch

Linux-версия перестала быть привязанной к Arch. Теперь SkayClearTux сам
определяет менеджер пакетов дистрибутива и работает с ним: **pacman, apt,
dnf, zypper, apk**. Плюс к AppImage добавлены пакеты **`.deb`** и **`.rpm`**.

---

## Главное

### Один Linux для всех дистрибутивов

Новый модуль `skaycleartux/backends/linux_pkg.py` определяет дистрибутив по
`/etc/os-release` (поля `ID` и `ID_LIKE`) и по наличию утилит, а затем
предоставляет единый интерфейс для:

- поиска, установки и удаления пакетов;
- файлов пакета, владельца файла и подробной информации о пакете;
- проверки и установки обновлений системы.

| Дистрибутивы | Менеджер |
|--------------|----------|
| Arch, Manjaro, EndeavourOS, Garuda, CachyOS, Artix | `pacman` |
| Debian, Ubuntu, Mint, Pop!_OS, Kali, Raspberry Pi OS | `apt` / `dpkg` |
| Fedora, RHEL, CentOS, Rocky, AlmaLinux, Amazon Linux | `dnf` / `rpm` |
| openSUSE Leap/Tumbleweed, SLES | `zypper` / `rpm` |
| Alpine, postmarketOS | `apk` |

Если менеджер определить не удалось, программа не падает, а честно сообщает
об этом — как и на любой другой ОС для недоступных функций.

### Очистка подстраивается под систему

Категории «Кэш пакетов» и «Пакеты-сироты» теперь зависят от дистрибутива:

| Менеджер | Кэш | Сироты |
|----------|-----|--------|
| pacman | `paccache -rk1` (или `pacman -Sc`) | `pacman -Rns` |
| apt | `apt-get clean` | `apt-get autoremove` |
| dnf | `dnf clean all` | `dnf autoremove` |
| zypper | `zypper clean --all` | `zypper remove --clean-deps` |
| apk | `apk cache clean` | не поддерживается |

Категория кэша AUR (`yay`/`paru`) появляется только там, где хелпер установлен.

### Новые пакеты

Кроме переносимого AppImage в релизе теперь есть:

- `SkayClearTux-1.3.0-amd64.deb` — для Debian/Ubuntu и производных;
- `SkayClearTux-1.3.0-x86_64.rpm` — для Fedora/RHEL/openSUSE и производных.

## Изменения

- Версия — **1.3.0**.
- Пакетные методы `LinuxBackend` стали тонкими обёртками над `linux_pkg`.
- Категория очистки `pacman-cache` переименована в `pkg-cache`.
- CI собирает `.deb`/`.rpm` и прикладывает их к релизу.

## Исправления

- На не-Arch системах разделы «Пакеты» и «Обновления» больше не пытаются
  вызвать `pacman`.

---

## Установка

| Платформа | Файл | Запуск |
|-----------|------|--------|
| Linux (любой) | `SkayClearTux-1.3.0-x86_64.AppImage` | `chmod +x` и запустить |
| Debian/Ubuntu | `SkayClearTux-1.3.0-amd64.deb` | `sudo apt install ./SkayClearTux-1.3.0-amd64.deb` |
| Fedora/RHEL/openSUSE | `SkayClearTux-1.3.0-x86_64.rpm` | `sudo dnf install ./SkayClearTux-1.3.0-x86_64.rpm` |
| Windows | `SkayClearTux-windows.zip` | распаковать, запустить `SkayClearTux.exe` |
| macOS | `SkayClearTux.dmg` | открыть образ, перетащить в «Программы» |

> **Первый запуск на macOS.** Приложение не подписано — щёлкните по нему правой
> кнопкой → **Открыть** → **Открыть**.

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
