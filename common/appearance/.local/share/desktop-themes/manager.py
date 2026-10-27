"""Desktop presets with private snapshots and reversible Stow symlink handling."""

import base64
import configparser
import fcntl
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import tomllib
from contextlib import contextmanager
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
PROFILE_PROVIDER = "dotfiles/desktop-profiles"
PROFILE_REVISION = tomllib.loads((ASSETS / "presets/glyph/theme.toml").read_text())[
    "revision"
]
SHARED_NIRI_FILES = {
    "monitors.kdl",
    "cfg/input.kdl",
    "cfg/display.kdl",
    "cfg/lid.kdl",
    "cfg/autostart.kdl",
}
CONFIG_FILES = (
    "noctalia/palettes/Glyph.json",
    "gtk-3.0/settings.ini",
    "gtk-3.0/gtk.css",
    "gtk-3.0/noctalia.css",
    "gtk-3.0/noctalia-extensions.css",
    "gtk-4.0/settings.ini",
    "gtk-4.0/gtk.css",
    "gtk-4.0/noctalia.css",
    "gtk-4.0/noctalia-extensions.css",
    "qt5ct/qt5ct.conf",
    "qt5ct/colors/noctalia.conf",
    "qt6ct/qt6ct.conf",
    "qt6ct/colors/noctalia.conf",
    "xsettingsd/xsettingsd.conf",
    "Kvantum/kvantum.kvconfig",
    "kitty/kitty.conf",
    "kitty/styling.conf",
    "kitty/fonts.conf",
    "kitty/current-theme.conf",
    "kitty/themes/noctalia.conf",
    "kitty/desktop-theme.conf",
    "alacritty/alacritty.toml",
    "alacritty/themes/noctalia.toml",
    "niri/config.kdl",
    "niri/noctalia.kdl",
    "btop/btop.conf",
    "btop/themes/noctalia.theme",
)
GNOME_KEYS = (
    "gtk-theme",
    "color-scheme",
    "font-name",
    "icon-theme",
    "cursor-theme",
    "cursor-size",
)


def run(*arguments, env=None):
    try:
        result = subprocess.run(
            arguments, check=False, capture_output=True, text=True, timeout=30, env=env
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(
            f"{arguments[0]} {arguments[1]} timed out after 30 seconds"
        ) from error
    if result.returncode:
        reason = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{arguments[0]} {arguments[1]} failed: {reason}")
    return result.stdout.strip()


def write_private(path, content):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def remove_path(path):
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def linked_parents(path):
    return [parent for parent in reversed(path.parents) if parent.is_symlink()]


def capture_files(paths):
    entries = {}
    for path in paths:
        for parent in linked_parents(path):
            entries[str(parent)] = {"directory_link": os.readlink(parent)}
        if path.is_symlink():
            entries[str(path)] = {"link": os.readlink(path)}
            if path.is_file():
                entries[str(path)].update(file_contents(path))
        elif path.exists():
            entries[str(path)] = file_contents(path)
        else:
            entries[str(path)] = {"missing": True}
    return entries


def file_contents(path):
    return {
        "content": base64.b64encode(path.read_bytes()).decode(),
        "mode": path.stat().st_mode & 0o777,
    }


def detach_files(paths):
    """Keep template hooks from writing through Stow links into the repository."""
    for path in paths:
        for parent in linked_parents(path):
            with tempfile.TemporaryDirectory(dir=parent.parent) as directory:
                replacement = Path(directory) / "copy"
                if parent.exists():
                    shutil.copytree(parent, replacement, symlinks=True)
                else:
                    replacement.mkdir()
                parent.unlink()
                replacement.rename(parent)
        if path.is_symlink():
            content = path.read_bytes() if path.exists() else b""
            path.unlink()
            path.write_bytes(content)


def restore_files(entries):
    directories = {
        Path(name): entry["directory_link"]
        for name, entry in entries.items()
        if "directory_link" in entry
    }
    for name, entry in entries.items():
        path = Path(name)
        if path in directories or any(parent in directories for parent in path.parents):
            continue
        # An ancestor may have been a link in the outgoing preset.
        detach_files([path])
        remove_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if "link" in entry:
            path.symlink_to(entry["link"])
        elif "content" in entry:
            path.write_bytes(base64.b64decode(entry["content"]))
            path.chmod(entry["mode"])
    for directory, target in sorted(
        directories.items(), key=lambda item: len(item[0].parts)
    ):
        if any(parent in directories for parent in directory.parents):
            continue
        remove_path(directory)
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.symlink_to(target)


def restore_working_files(entries):
    working = {}
    for name, entry in entries.items():
        if "directory_link" in entry:
            continue
        if "link" in entry:
            # Older snapshots recorded only the link. Its target is still the
            # original source; materialize it before invoking any template hooks.
            if "content" not in entry:
                target = Path(name).parent / entry["link"]
                entry = file_contents(target) if target.is_file() else {"missing": True}
            else:
                entry = {key: value for key, value in entry.items() if key != "link"}
        working[name] = entry
    restore_files(working)


def restore_links(entries):
    for name, entry in sorted(
        entries.items(), key=lambda item: len(Path(item[0]).parts)
    ):
        if "directory_link" not in entry and "link" not in entry:
            continue
        path = Path(name)
        if linked_parents(path):
            continue
        remove_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(entry.get("directory_link", entry.get("link")))


class ThemeManager:
    def __init__(self):
        self.home = Path.home()
        self.config = Path(os.environ.get("XDG_CONFIG_HOME", self.home / ".config"))
        self.state = Path(os.environ.get("XDG_STATE_HOME", self.home / ".local/state"))
        self.noctalia_config = (
            Path(os.environ.get("NOCTALIA_CONFIG_HOME", self.config)) / "noctalia"
        )
        self.noctalia_state = (
            Path(os.environ.get("NOCTALIA_STATE_HOME", self.state)) / "noctalia"
        )
        self.directory = self.state / "desktop-themes"
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.settings = self.noctalia_state / "settings.toml"
        self.paths = [self.config / name for name in CONFIG_FILES]
        self.paths[0] = self.noctalia_config / "palettes/Glyph.json"
        self.paths += [
            self.home / ".gtkrc-2.0",
            self.home / ".icons/default/index.theme",
            self.settings,
        ]
        self.refresh_paths()

    def description(self, name):
        preset = ASSETS / "presets" / name
        metadata = tomllib.loads((preset / "theme.toml").read_text())
        if "icon" in metadata:
            metadata["icon"] = str(preset / metadata["icon"])
        return metadata

    def profile_list(self):
        return {
            "current": self.current,
            "profiles": [
                {"id": name, **self.description(name)} for name in ("original", "glyph")
            ],
        }

    def ensure_profile_provider(self):
        if self.profile_provider_enabled():
            return
        run("noctalia", "msg", "plugins", "enable", PROFILE_PROVIDER)
        # Plugin enable exports and activates on a background worker. Do not
        # finish the switch while the incoming shell still lacks its provider.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if self.profile_provider_enabled():
                return
            time.sleep(0.05)
        raise RuntimeError(
            "Noctalia did not enable the profile provider within 30 seconds"
        )

    def profile_provider_enabled(self):
        value = run("noctalia", "msg", "config-get", "plugins.enabled")
        return PROFILE_PROVIDER in tomllib.loads("enabled = " + value)["enabled"]

    def refresh_paths(self):
        paths = [self.noctalia_config / "config.toml"]
        for root, suffix in (
            (self.config / "niri", ".kdl"),
            (self.noctalia_config, ".toml"),
        ):
            for directory, children, files in os.walk(root, followlinks=True):
                children[:] = [
                    name for name in children if name not in ("plugins", "palettes")
                ]
                for name in files:
                    path = Path(directory) / name
                    if (
                        path.suffix == suffix
                        and path.relative_to(root).as_posix() not in SHARED_NIRI_FILES
                    ):
                        paths.append(path)
        for path in (ASSETS / "presets/glyph/niri").rglob("*.kdl"):
            paths.append(
                self.config / "niri" / path.relative_to(ASSETS / "presets/glyph/niri")
            )
        self.paths = list(dict.fromkeys([*self.paths, *paths]))

    @property
    def current(self):
        marker = self.directory / "current"
        return marker.read_text().strip() if marker.exists() else "original"

    @contextmanager
    def locked(self):
        with (self.directory / "lock").open("w") as stream:
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Another theme change is in progress") from error
            yield

    def snapshot(self):
        self.refresh_paths()
        return {
            "profile_revision": self.active_revision,
            "files": capture_files(self.paths),
            "gnome": {
                key: run("gsettings", "get", "org.gnome.desktop.interface", key)
                for key in GNOME_KEYS
            },
        }

    @property
    def active_revision(self):
        path = self.directory / "active-revision"
        return int(path.read_text()) if path.exists() else 1

    def set_current(self, name, revision):
        write_private(self.directory / "active-revision", str(revision).encode())
        write_private(self.directory / "current", name.encode())

    def save(self, name, snapshot):
        write_private(self.directory / f"{name}.json", json.dumps(snapshot).encode())

    def upgrade_original_snapshot(self):
        path = self.directory / "original.json"
        if not path.exists():
            return
        snapshot = json.loads(path.read_text())
        missing = [path for path in self.paths if str(path) not in snapshot["files"]]
        snapshot["files"].update(capture_files(missing))
        self.save("original", snapshot)

    def restore(self, snapshot):
        files = {str(path): {"missing": True} for path in self.paths}
        files.update(snapshot["files"])
        restore_working_files(files)
        for key, value in snapshot["gnome"].items():
            run("gsettings", "set", "org.gnome.desktop.interface", key, value)

    def render_glyph_settings(self):
        # Resolve the theme against native defaults, never the outgoing shell.
        with tempfile.TemporaryDirectory(prefix="desktop-theme-") as directory:
            root = Path(directory)
            config = root / "config/noctalia"
            config.mkdir(parents=True)
            preset = (ASSETS / "presets/glyph/noctalia.toml").read_text()
            preset = preset.replace(
                "@WALLPAPER@", json.dumps(str(ASSETS / "presets/glyph/wallpaper.svg"))
            )
            preset = preset.replace(
                "@NOTHING_ICON@", json.dumps(str(ASSETS / "presets/glyph/nothing.svg"))
            )
            outputs = json.loads(run("niri", "msg", "--json", "outputs"))
            preset += glyph_desktop(outputs)
            wallpaper = json.dumps(str(ASSETS / "presets/glyph/wallpaper.svg"))
            for output in outputs.values():
                if output.get("logical") is not None:
                    preset += f"\n[wallpaper.monitors.{json.dumps(output['name'])}]\npath = {wallpaper}\n"
            (config / "preset.toml").write_text(preset)
            environment = dict(
                os.environ,
                NOCTALIA_CONFIG_HOME=str(root / "config"),
                NOCTALIA_STATE_HOME=str(root / "state"),
            )
            defaults = run("noctalia", "config", "export", "full", env=environment)
            (config / "defaults.toml").write_text(defaults)
            merged = run("noctalia", "config", "export", env=environment)
        tomllib.loads(merged)
        return merged

    def create_glyph(self):
        merged = self.render_glyph_settings()
        # The profile owns the complete declarative layer; GUI overrides start
        # fresh and are saved separately with this theme on every switch.
        for path in self.noctalia_config.glob("*.toml"):
            path.unlink()
        write_private(self.noctalia_config / "config.toml", (merged + "\n").encode())
        write_private(self.settings, b"")
        palette = self.noctalia_config / "palettes/Glyph.json"
        palette.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ASSETS / "presets/glyph/Glyph.json", palette)
        self.style_terminals()
        self.install_glyph_icons()
        self.configure_glyph_icons()
        self.configure_glyph_apps()
        self.install_glyph_niri()

    def install_glyph_niri(self):
        source = ASSETS / "presets/glyph/niri"
        with tempfile.TemporaryDirectory(prefix="desktop-theme-niri-") as directory:
            staging = Path(directory) / "niri"
            shutil.copytree(self.config / "niri", staging)
            shutil.copytree(source, staging, dirs_exist_ok=True)
            run("niri", "validate", "--config", str(staging / "config.kdl"))
        for path in source.rglob("*.kdl"):
            target = self.config / "niri" / path.relative_to(source)
            write_private(target, path.read_bytes())

    def style_terminals(self):
        kitty = self.config / "kitty/desktop-theme.conf"
        shutil.copyfile(ASSETS / "presets/glyph/kitty.conf", kitty)
        with (self.config / "kitty/kitty.conf").open("a") as stream:
            stream.write("\ninclude desktop-theme.conf\ninclude themes/noctalia.conf\n")
        # Local colors override imports in Alacritty, so use its existing palette
        # as the baseline snapshot and leave palette ownership to the template.
        alacritty = self.config / "alacritty/alacritty.toml"
        text = alacritty.read_text()
        text = re.sub(
            r"(?ms)^\[colors\.(primary|normal|bright)\]\n.*?(?=^\[|\Z)", "", text
        )
        text = text.replace('decorations_theme_variant = "Dark"\n', "")
        text = re.sub(r"(?m)^opacity\s*=.*$", "opacity = 1.0", text)
        alacritty.write_text(text)

    def acknowledge_templates(self):
        write_private(self.directory / "ready", self.current.encode())

    def reload_theme(self):
        # IPC queues template work. The colors_changed hook runs only after the
        # renderer and its app hooks finish; restoring symlinks earlier races it.
        marker = self.directory / "ready"
        marker.unlink(missing_ok=True)
        run("noctalia", "msg", "config-reload")
        run("noctalia", "msg", "templates-apply")
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if marker.exists() and marker.read_text() == self.current:
                return
            time.sleep(0.1)
        raise RuntimeError(
            "Noctalia did not confirm theme application within 30 seconds"
        )

    def sync_apps(self):
        if self.current != "glyph":
            return
        mode = run("noctalia", "msg", "theme-mode-get")
        theme = "adw-gtk3" if mode == "light" else "adw-gtk3-dark"
        self.sync_gtk(theme, mode)
        self.sync_legacy_gtk(theme)
        reload_apps()

    def install_glyph_icons(self):
        directory = (
            Path(os.environ.get("XDG_DATA_HOME", self.home / ".local/share")) / "icons"
        )
        target = directory / "YAMIS"
        if (target / "index.theme").is_file():
            return
        directory.mkdir(parents=True, exist_ok=True)
        # Keep the upstream archive intact, including its license and aliases.
        with tempfile.TemporaryDirectory(
            prefix="glyph-icons-", dir=directory
        ) as staging:
            with tarfile.open(ASSETS / "presets/glyph/yamis.tar.gz") as archive:
                archive.extractall(staging, filter="data")
            Path(staging, "YAMIS").rename(target)

    def configure_glyph_icons(self):
        for version in ("3.0", "4.0"):
            path = self.config / f"gtk-{version}/settings.ini"
            path.write_text(
                replace_setting(path.read_text(), "gtk-icon-theme-name", "YAMIS", "=")
            )
        for path, key, separator in (
            (self.home / ".gtkrc-2.0", "gtk-icon-theme-name", "="),
            (self.config / "xsettingsd/xsettingsd.conf", "Net/IconThemeName", " "),
        ):
            text = path.read_text() if path.exists() else ""
            path.write_text(replace_setting(text, key, '"YAMIS"', separator))
        for toolkit in ("qt5ct", "qt6ct"):
            path = self.config / f"{toolkit}/{toolkit}.conf"
            settings = configparser.ConfigParser(interpolation=None)
            settings.optionxform = str
            settings.read(path)
            if not settings.has_section("Appearance"):
                settings.add_section("Appearance")
            settings["Appearance"]["icon_theme"] = "YAMIS"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w") as stream:
                settings.write(stream, space_around_delimiters=False)
        run("gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "YAMIS")

    def configure_glyph_apps(self):
        self.sync_qt()
        self.configure_glyph_fonts()

    def configure_glyph_fonts(self):
        for version in ("3.0", "4.0"):
            path = self.config / f"gtk-{version}/settings.ini"
            text = path.read_text()
            path.write_text(replace_setting(text, "gtk-font-name", "Glyph UI 11", "="))
        for path, key, separator in (
            (self.home / ".gtkrc-2.0", "gtk-font-name", "="),
            (self.config / "xsettingsd/xsettingsd.conf", "Gtk/FontName", " "),
        ):
            text = path.read_text() if path.exists() else ""
            path.write_text(replace_setting(text, key, '"Glyph UI 11"', separator))
        run(
            "gsettings",
            "set",
            "org.gnome.desktop.interface",
            "font-name",
            "Glyph UI 11",
        )
        self.configure_glyph_qt_fonts()

    def configure_glyph_qt_fonts(self):
        # QFont::toString representations for a regular 11-point UI font.
        fonts = {
            "qt5ct": "Glyph UI,11,-1,5,50,0,0,0,0,0",
            "qt6ct": "Glyph UI,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1,,0,0",
        }
        for toolkit, font in fonts.items():
            path = self.config / f"{toolkit}/{toolkit}.conf"
            settings = configparser.ConfigParser(interpolation=None)
            settings.optionxform = str
            settings.read(path)
            if not settings.has_section("Fonts"):
                settings.add_section("Fonts")
            settings["Fonts"]["general"] = json.dumps(font)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w") as stream:
                settings.write(stream, space_around_delimiters=False)

    def sync_gtk(self, theme, mode):
        for version in ("3.0", "4.0"):
            path = self.config / f"gtk-{version}/settings.ini"
            # The built-in CSS imports this even when no app extensions are enabled.
            (path.parent / "noctalia-extensions.css").touch(exist_ok=True)
            settings = configparser.ConfigParser()
            settings.optionxform = str
            settings.read(path)
            if not settings.has_section("Settings"):
                settings.add_section("Settings")
            settings["Settings"].update(
                {
                    "gtk-theme-name": theme,
                    "gtk-application-prefer-dark-theme": "0"
                    if mode == "light"
                    else "1",
                }
            )
            with path.open("w") as stream:
                settings.write(stream, space_around_delimiters=False)

    def sync_legacy_gtk(self, theme):
        path = self.config / "xsettingsd/xsettingsd.conf"
        text = path.read_text() if path.exists() else ""
        text = replace_setting(text, "Net/ThemeName", json.dumps(theme))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path = self.home / ".gtkrc-2.0"
        text = path.read_text() if path.exists() else ""
        text = replace_setting(text, "gtk-theme-name", json.dumps(theme), "=")
        path.write_text(text)

    def sync_qt(self):
        for toolkit in ("qt5ct", "qt6ct"):
            directory = self.config / toolkit
            directory.mkdir(parents=True, exist_ok=True)
            settings = configparser.ConfigParser(interpolation=None)
            settings.optionxform = str
            path = directory / f"{toolkit}.conf"
            settings.read(path)
            if not settings.has_section("Appearance"):
                settings.add_section("Appearance")
            settings["Appearance"].update(
                {
                    "style": "Fusion",
                    "custom_palette": "true",
                    "color_scheme_path": str(directory / "colors/noctalia.conf"),
                }
            )
            with path.open("w") as stream:
                settings.write(stream, space_around_delimiters=False)

    def apply(self, name):
        if name not in ("original", "glyph"):
            raise RuntimeError(f"Unknown preset: {name}")
        with self.locked():
            if self.current == name and (
                name == "original" or self.active_revision >= PROFILE_REVISION
            ):
                if name == "original" and self.active_revision < PROFILE_REVISION:
                    snapshot = self.snapshot()
                    snapshot["profile_revision"] = PROFILE_REVISION
                    self.save("original", snapshot)
                    self.set_current("original", PROFILE_REVISION)
                return
            run("noctalia", "msg", "status")
            self.ensure_profile_provider()
            previous = self.current
            previous_revision = self.active_revision
            if previous == "glyph" and previous_revision < PROFILE_REVISION:
                self.upgrade_original_snapshot()
            checkpoint = self.snapshot()
            self.save(previous, checkpoint)
            try:
                target = self.stage_theme(name)
                run("noctalia", "config", "validate")
                run(
                    "niri", "validate", "--config", str(self.config / "niri/config.kdl")
                )
                self.set_current(name, PROFILE_REVISION)
                self.reload_theme()
                self.ensure_profile_provider()
                self.sync_apps()
                if target is not None:
                    restore_links(target["files"])
                reload_apps()
            except Exception as error:
                self.rollback(previous, previous_revision, checkpoint, error)
                raise

    def stage_theme(self, name):
        path = self.directory / f"{name}.json"
        if not path.exists() and name == "original":
            raise RuntimeError("The original desktop snapshot is missing")
        if path.exists():
            snapshot = json.loads(path.read_text())
            if (
                name != "glyph"
                or snapshot.get("profile_revision", 1) >= PROFILE_REVISION
            ):
                self.restore(snapshot)
                return snapshot
            archive = self.directory / "glyph-v1.json"
            if not archive.exists():
                write_private(archive, path.read_bytes())
        detach_files(self.paths)
        self.create_glyph()
        return None

    def rollback(self, previous, revision, checkpoint, error):
        self.set_current(previous, revision)
        try:
            self.restore(checkpoint)
            self.reload_theme()
            self.ensure_profile_provider()
            restore_links(checkpoint["files"])
            reload_apps()
        except (OSError, RuntimeError, ValueError) as rollback_error:
            raise RuntimeError(
                f"{error}; restoring {previous} also failed: {rollback_error}. "
                f"Backup: {self.directory / (previous + '.json')}"
            ) from error


def replace_setting(text, key, value, separator=" "):
    pattern = rf"(?m)^{re.escape(key)}(?:\s*=|\s+).*?$"
    line = f"{key}{separator}{value}"
    if re.search(pattern, text):
        return re.sub(pattern, lambda match: line, text)
    return text.rstrip() + "\n" + line + "\n"


def glyph_desktop(outputs):
    """Place native widgets in each monitor's logical coordinate system."""
    widgets = []
    definitions = json.loads((ASSETS / "presets/glyph/desktop.json").read_text())
    for output in outputs.values():
        logical = output.get("logical")
        if logical is None:
            continue
        width, height = logical["width"], logical["height"]
        for definition in definitions:
            widget_id = f"glyph-{output['name']}-{definition['name']}"
            geometry = {
                "type": definition["type"],
                "output": output["name"],
                "cx": width * definition["x"],
                "cy": height * definition["y"],
                "box_width": width * definition["width"],
                "box_height": height * definition["height"],
            }
            settings = definition["settings"]
            widgets.append((widget_id, geometry, settings))
    if not widgets:
        raise RuntimeError(
            "Niri reports no active monitors for the Glyph desktop layout"
        )
    text = "\n[desktop_widgets]\nenabled = true\nschema_version = 2\n"
    text += "widget_order = " + json.dumps([widget[0] for widget in widgets]) + "\n"
    for widget_id, geometry, settings in widgets:
        for suffix, values in (("", geometry), (".settings", settings)):
            text += f"\n[desktop_widgets.widget.{json.dumps(widget_id)}{suffix}]\n"
            text += "".join(
                f"{key} = {json.dumps(value)}\n" for key, value in values.items()
            )
    return text


def reload_apps():
    for signal, process in (("-HUP", "xsettingsd"), ("-USR1", "kitty")):
        result = subprocess.run(
            ["pkill", signal, "-x", process],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(f"Could not reload {process}: {result.stderr.strip()}")
