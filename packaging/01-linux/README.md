# Linux packages

Builds an AppImage, `.deb` and `.rpm` from the same PyInstaller bundle. Tested on glibc 2.35+ distributions.

## Use a release

```sh
chmod +x SkayClearTux-*-x86_64.AppImage
./SkayClearTux-*-x86_64.AppImage
```

Without FUSE:

```sh
APPIMAGE_EXTRACT_AND_RUN=1 ./SkayClearTux-*-x86_64.AppImage
```

`install.sh` puts the AppImage in `~/.local/bin`, installs the icon and adds a desktop entry.

Packages:

```sh
sudo apt install ./SkayClearTux-*-amd64.deb
sudo dnf install ./SkayClearTux-*-x86_64.rpm
```

## Build

```sh
python -m pip install -e ".[build]"
pyinstaller --noconfirm --clean --windowed --name SkayClearTux \
  --add-data "skaycleartux/assets:skaycleartux/assets" \
  --icon skaycleartux/assets/tux.png --exclude-module tkinter SkayClearTux.py
VERSION=1.5.3.2 bash packaging/01-linux/make_appimage.sh
VERSION=1.5.3.2 bash packaging/01-linux/make_deb.sh    # needs dpkg-deb
VERSION=1.5.3.2 bash packaging/01-linux/make_rpm.sh    # needs rpmbuild
```

`make_deb.sh` and `make_rpm.sh` share `stage_tree.sh`. The release workflow uses the same scripts.
