# Noctalia 4.x with Qt 6.12

Legacy recovery only. The desktop now runs native Noctalia v5 using
`desktop/niri/.config/noctalia/config.toml` and `noctalia.service`.
Do not apply this QML override to v5. See [migration notes](../../docs/noctalia-v5.md).

Qt 6.12 introduces a `QtQuick.Color` singleton that shadows the legacy shell's
`qs.Commons.Color`. The result is undefined theme colors and errors such as
`Property 'smartAlpha' of object QQuickColor is not a function`.

Run `python3 meta/system/noctalia-qt-compat` as the desktop user, then
`systemctl --user restart noctalia-shell.service`. The helper creates a local
`~/.config/quickshell/noctalia-shell` override, pins unversioned QtQuick imports
to 6.11, and links unchanged files to the installed package. Existing Noctalia
settings, colors, service commands and IPC bindings continue to be used.
The same import fix is applied to installed plugin QML files, with originals
saved under `~/.cache/noctalia-qt-compat/plugins-original` (on the SSD here).
Plugin updates may require reapplying the import fix.

This is a compatibility workaround for the installed 4.x QML shell. Quickshell
still needs rebuilding against the installed Qt version to remove its ABI
warning. After updating the shell package, move the local override aside and
check whether the package works without it; the copied QML files do not update
automatically. The helper refuses to overwrite an existing override.

References: [Qt Color singleton](https://doc.qt.io/qt-6.12/qml-qtquick-color.html),
[versioned QML imports](https://doc.qt.io/qt-6/qtqml-syntax-imports.html).

## Rebuilding noctalia-qs 0.0.12

The unmodified AUR source fails with Qt 6.12's metatype completeness checks in
Hyprland, i3/Sway and PipeWire. `patches/noctalia-qs-qt612-bindables.patch` moves
pointer binding methods into implementation files and adds `Q_MOC_INCLUDE`
declarations so metadata compilation sees complete property types. The local
`noctalia-qs.PKGBUILD` applies this patch and labels the package `0.0.12-2.1`.
All compositor integrations remain enabled.

The build workspace is under `~/.cache`, which is SSD-backed on this host.
To reproduce the build from the dotfiles repository:

```sh
mkdir -p ~/.cache/noctalia-qs-qt612
cp meta/system/noctalia-qs.PKGBUILD ~/.cache/noctalia-qs-qt612/PKGBUILD
cp meta/system/patches/noctalia-qs-qt612-bindables.patch ~/.cache/noctalia-qs-qt612/
cd ~/.cache/noctalia-qs-qt612
CMAKE_BUILD_PARALLEL_LEVEL=2 makepkg --syncdeps --install
systemctl --user restart noctalia-shell.service
```

Build as your normal user; makepkg requests sudo only for dependency installation
and package installation. A plain `paru -S --aur --rebuild noctalia-qs` uses the
unpatched AUR recipe. Keep the QML color override after this rebuild: the source
patch fixes compilation and the Qt ABI mismatch, while the override fixes the
separate `Color` name collision.

Reference: [Qt metatype and forward-declared property types](https://doc.qt.io/qt-6/qmetatype.html).
