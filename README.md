# Cursor Companion

Animated companion for KDE Plasma. It keeps your existing cursor theme and draws a small animated pet beside the pointer.

## Features

- Follows the mouse pointer on KDE Plasma 6.
- Uses Codex pet packages with `pet.json` and a spritesheet.
- Embeds Codex-Pets.net for browsing and saving downloads into a local collection.
- Provides a tray menu, pet manager, scale and offset controls, and optional autostart.

## Install From Source

```bash
python -m build
pip install --user dist/*.whl
cursor-companion
```

On Arch-based systems, install the runtime dependencies first:

```bash
sudo pacman -S python-pyqt6 python-pyqt6-webengine qt6-tools xdg-utils
```

`qt6-tools` provides `qdbus6` for the KDE cursor bridge, and `xdg-utils` provides `xdg-open` for opening pet folders from the manager.

## Local Data

The app stores configuration in `~/.config/cursor-companion/` and downloaded pets in `~/.local/share/cursor-companion/`.

## AUR Package

The `packaging/aur` directory contains the package files used for Arch User Repository distribution.

## Thanks

Cursor Companion includes a small browser view for [Codex-Pets.net](https://codex-pets.net/), which makes it easy to find and download Codex-compatible pet packages.

The site is powered by the open-source [codex-pet-share](https://github.com/portons/codex-pet-share) project. Thanks to that project and its maintainers for making a shared home for pixel pets.

## License

MIT
