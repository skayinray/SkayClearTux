#!/usr/bin/env bash
# Сборка .rpm-пакета SkayClearTux (Fedora, RHEL, openSUSE и др.).
#
# Требуется: собранный бандл PyInstaller в dist/SkayClearTux и rpmbuild.
#   VERSION=1.4.0 bash packaging/01-linux/make_rpm.sh
set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=stage_tree.sh
source "$HERE/stage_tree.sh"

BUILD="$ROOT/build"
STAGE="$BUILD/rpm/stage"
TOPDIR="$BUILD/rpmbuild"

if [ ! -d "$ROOT/dist/$NAME" ]; then
    echo "Нет dist/$NAME — сначала соберите бандл PyInstaller."
    exit 1
fi
if ! command -v rpmbuild >/dev/null 2>&1; then
    echo "Нужен rpmbuild (пакет rpm)."
    exit 1
fi

echo "==> Готовлю дерево файлов"
stage_linux_tree "$STAGE"

echo "==> Спецификация пакета"
rm -rf "$TOPDIR"
mkdir -p "$TOPDIR"/{BUILD,RPMS,SOURCES,SPECS,SRPMS,BUILDROOT}

cat > "$TOPDIR/SPECS/skaycleartux.spec" <<EOF
Name:           skaycleartux
Version:        $VER
Release:        1%{?dist}
Summary:        Универсальный помощник для Linux

License:        MIT
URL:            https://github.com/skayinray/SkayClearTux
BuildArch:      x86_64

%description
SkayClearTux — кроссплатформенный системный помощник: очистка системы,
мониторинг, процессы и службы, пакеты и обновления, сеть и порты, железо
и диски, журнал, файрвол, твики, хэши, резервное копирование, темы и
шахматы с ботом.

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}
cp -a $STAGE/. %{buildroot}/

%files
/opt/$NAME
/usr/bin/skaycleartux
/usr/share/applications/skaycleartux.desktop
/usr/share/icons/hicolor/256x256/apps/skaycleartux.png

%changelog
EOF

echo "==> Собираю .rpm"
rpmbuild -bb --define "_topdir $TOPDIR" "$TOPDIR/SPECS/skaycleartux.spec"

RPM=$(find "$TOPDIR/RPMS" -name "*.rpm" | head -n1)
cp "$RPM" "$BUILD/$NAME-$VER-x86_64.rpm"

echo "==> Готово:"
ls -la "$BUILD/$NAME-$VER-x86_64.rpm"
