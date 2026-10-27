"""Regression checks use temporary homes; never change the running desktop."""

import configparser
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = (
    Path(__file__).parents[1]
    / "common/appearance/.local/share/desktop-themes/manager.py"
)
SPEC = importlib.util.spec_from_file_location("theme_manager", SOURCE)
themes = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(themes)
CLI_SPEC = importlib.util.spec_from_file_location(
    "theme_cli", SOURCE.with_name("cli.py")
)
cli = importlib.util.module_from_spec(CLI_SPEC)
with patch.dict(sys.modules, {"manager": themes}):
    CLI_SPEC.loader.exec_module(cli)


class SnapshotTests(unittest.TestCase):
    def test_template_hooks_cannot_mutate_original_sources_during_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tracked.conf"
            source.write_bytes(b"original without newline")
            path = root / "app.conf"
            path.symlink_to("tracked.conf")
            snapshot = themes.capture_files([path])
            themes.restore_working_files(snapshot)
            path.write_text("Noctalia template output\n")
            themes.restore_links(snapshot)
            self.assertTrue(path.is_symlink())
            self.assertEqual(source.read_bytes(), b"original without newline")

    def test_dangling_stow_directory_is_materialized_and_restored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            themes_directory = root / "themes"
            themes_directory.symlink_to("missing-repository-directory")
            generated = themes_directory / "noctalia.conf"
            snapshot = themes.capture_files([generated])
            themes.detach_files([generated])
            generated.write_text("generated palette")
            self.assertFalse((root / "missing-repository-directory").exists())
            themes.restore_files(snapshot)
            self.assertTrue(themes_directory.is_symlink())
            self.assertFalse(themes_directory.exists())

    def test_switch_detaches_stow_files_and_restores_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            repository.mkdir()
            (repository / "settings.ini").write_text("original")
            (repository / "colors.css").write_text("colors")
            home = root / "home"
            home.mkdir()
            folded = home / "gtk"
            folded.symlink_to("../repo")
            individual = home / "kitty.conf"
            individual.symlink_to("../repo/settings.ini")
            paths = [folded / "settings.ini", folded / "colors.css", individual]
            snapshot = themes.capture_files(paths)
            themes.detach_files(paths)
            for path in paths:
                path.write_text("Glyph")
            self.assertEqual((repository / "settings.ini").read_text(), "original")
            self.assertEqual((repository / "colors.css").read_text(), "colors")
            themes.restore_files(snapshot)
            self.assertEqual(os.readlink(folded), "../repo")
            self.assertEqual(os.readlink(individual), "../repo/settings.ini")
            self.assertEqual(individual.read_text(), "original")

    def test_saved_glyph_restores_regular_files_after_original_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repo"
            repository.mkdir()
            (repository / "settings").write_text("original")
            folded = root / "app"
            folded.symlink_to("repo")
            path = folded / "settings"
            original = themes.capture_files([path])
            themes.detach_files([path])
            path.write_text("personal Glyph settings")
            glyph = themes.capture_files([path])
            themes.restore_files(original)
            themes.restore_files(glyph)
            self.assertFalse(folded.is_symlink())
            self.assertEqual(path.read_text(), "personal Glyph settings")
            self.assertEqual((repository / "settings").read_text(), "original")

    def test_restore_removes_generated_files_and_preserves_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings, generated = root / "settings", root / "generated"
            settings.write_bytes(b"private\x00settings")
            settings.chmod(0o600)
            snapshot = themes.capture_files([settings, generated])
            settings.write_text("changed")
            settings.chmod(0o644)
            generated.write_text("generated")
            themes.restore_files(snapshot)
            self.assertEqual(settings.read_bytes(), b"private\x00settings")
            self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
            self.assertFalse(generated.exists())


class ManagerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.environment = patch.dict(
            os.environ,
            {
                "HOME": str(root),
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_STATE_HOME": str(root / "state"),
                "NOCTALIA_CONFIG_HOME": str(root / "config"),
                "NOCTALIA_STATE_HOME": str(root / "state"),
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.manager = themes.ThemeManager()
        provider_status = patch.object(
            self.manager, "profile_provider_enabled", return_value=True
        )
        provider_status.start()
        self.addCleanup(provider_status.stop)
        self.settings = self.manager.settings
        self.settings.parent.mkdir(parents=True)
        self.settings.write_text('[theme]\nmode = "dark"\n')
        self.manager.paths = [self.settings]

    def test_provider_enable_waits_for_background_activation(self):
        with (
            patch.object(
                self.manager,
                "profile_provider_enabled",
                side_effect=[False, False, True],
            ),
            patch.object(themes, "run") as command,
            patch.object(themes.time, "sleep") as waiting,
        ):
            self.manager.ensure_profile_provider()
        command.assert_called_once_with(
            "noctalia", "msg", "plugins", "enable", themes.PROFILE_PROVIDER
        )
        waiting.assert_called_once_with(0.05)

    def test_provider_enable_timeout_reports_failure(self):
        with (
            patch.object(self.manager, "profile_provider_enabled", return_value=False),
            patch.object(themes, "run"),
            patch.object(themes.time, "monotonic", side_effect=[0, 31]),
            self.assertRaisesRegex(RuntimeError, "did not enable the profile provider"),
        ):
            self.manager.ensure_profile_provider()

    def test_provider_status_reads_the_effective_native_config(self):
        with patch.object(themes, "run", return_value="['dotfiles/desktop-profiles']"):
            self.assertTrue(themes.ThemeManager.profile_provider_enabled(self.manager))

    def test_profile_list_marks_actual_current_profile_without_shell_queries(self):
        (self.manager.directory / "current").write_text("glyph")
        with patch.object(themes, "run") as command:
            profiles = self.manager.profile_list()
        command.assert_not_called()
        self.assertEqual(profiles["current"], "glyph")
        self.assertEqual(
            [profile["id"] for profile in profiles["profiles"]], ["original", "glyph"]
        )
        self.assertTrue(Path(profiles["profiles"][1]["icon"]).is_file())

    def test_cli_lists_real_profiles_without_opening_a_window(self):
        output = io.StringIO()
        with (
            patch.object(cli, "ThemeManager", return_value=self.manager),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(cli.main(["list"]), 0)
        self.assertEqual(json.loads(output.getvalue())["current"], "original")

    def test_menu_uses_native_provider_and_configured_prefix(self):
        with (
            patch.object(self.manager, "ensure_profile_provider") as enable,
            patch.object(cli, "run", side_effect=['"."', "ok"]) as command,
        ):
            cli.open_provider(self.manager)
        enable.assert_called_once()
        self.assertEqual(
            command.call_args.args,
            ("noctalia", "msg", "panel-toggle", "launcher", ".profile"),
        )

    def test_provider_switch_failure_reports_error_in_shell_notification(self):
        errors = io.StringIO()
        with (
            patch.object(cli, "ThemeManager", return_value=self.manager),
            patch.object(
                self.manager, "apply", side_effect=RuntimeError("Invalid keybinding")
            ),
            patch.object(cli, "notify") as notify,
            contextlib.redirect_stderr(errors),
        ):
            self.assertEqual(cli.main(["switch", "glyph"]), 1)
        self.assertIn("Invalid keybinding", errors.getvalue())
        notify.assert_called_once_with(
            "Could not switch desktop profile", "Invalid keybinding", "critical"
        )

    def test_provider_switch_success_notifies_after_apply(self):
        with (
            patch.object(cli, "ThemeManager", return_value=self.manager),
            patch.object(self.manager, "apply") as apply,
            patch.object(cli, "notify") as notify,
        ):
            self.assertEqual(cli.main(["switch", "glyph"]), 0)
        apply.assert_called_once_with("glyph")
        notify.assert_called_once_with("Desktop profile", "Using Glyph", "normal")

    def test_theme_captures_shortcuts_motion_and_complete_shell_config(self):
        for relative in (
            "niri/cfg/keybinds.kdl",
            "niri/cfg/animation.kdl",
            "noctalia/config.toml",
            "noctalia/layout.toml",
        ):
            path = self.manager.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("original")
        with patch.object(themes, "run", return_value="ok"):
            snapshot = self.manager.snapshot()
        for relative in (
            "niri/cfg/keybinds.kdl",
            "niri/cfg/animation.kdl",
            "noctalia/config.toml",
            "noctalia/layout.toml",
        ):
            self.assertIn(str(self.manager.config / relative), snapshot["files"])

    def test_full_shell_and_keybindings_round_trip_without_cross_theme_leaks(self):
        originals = {
            "niri/cfg/keybinds.kdl": "original launcher shortcut",
            "niri/cfg/animation.kdl": "original spring animation",
            "noctalia/config.toml": '[bar.main]\nposition = "top"\n',
            "noctalia/layout.toml": "[shell.launcher]\napp_grid = true\n",
        }
        for relative, content in originals.items():
            path = self.manager.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        def create_glyph():
            (self.manager.config / "niri/cfg/keybinds.kdl").write_text(
                "Glyph launcher shortcut"
            )
            (self.manager.config / "niri/cfg/animation.kdl").write_text(
                "Glyph eased motion"
            )
            (self.manager.config / "noctalia/config.toml").write_text(
                '[bar.main]\nposition = "left"\n'
            )
            (self.manager.config / "noctalia/layout.toml").unlink()
            self.settings.write_text("")

        with (
            patch.object(themes, "run", return_value="ok"),
            patch.object(themes, "reload_apps"),
            patch.object(self.manager, "reload_theme"),
            patch.object(self.manager, "sync_apps"),
            patch.object(self.manager, "create_glyph", side_effect=create_glyph),
        ):
            self.manager.apply("glyph")
            bindings = self.manager.config / "niri/cfg/keybinds.kdl"
            bindings.write_text("my Glyph shortcuts")
            custom_shell = self.manager.noctalia_config / "custom.toml"
            custom_shell.write_text("[shell.launcher]\nwidth = 500\n")
            self.manager.apply("original")
            for relative, content in originals.items():
                self.assertEqual((self.manager.config / relative).read_text(), content)
            self.assertFalse(custom_shell.exists())
            self.manager.apply("glyph")
            self.assertEqual(bindings.read_text(), "my Glyph shortcuts")
            self.assertIn("width = 500", custom_shell.read_text())
            self.assertFalse((self.manager.noctalia_config / "layout.toml").exists())

    def test_legacy_active_glyph_upgrades_with_original_bindings_preserved(self):
        bindings = self.manager.config / "niri/cfg/keybinds.kdl"
        bindings.parent.mkdir(parents=True)
        bindings.write_text("original shared bindings")
        with patch.object(themes, "run", return_value="ok"):
            original = self.manager.snapshot()
        original["files"].pop(str(bindings))
        self.manager.save("original", original)
        (self.manager.directory / "current").write_text("glyph")

        def create_glyph():
            bindings.write_text("new independent Glyph bindings")

        with (
            patch.object(themes, "run", return_value="ok"),
            patch.object(themes, "reload_apps"),
            patch.object(self.manager, "reload_theme"),
            patch.object(self.manager, "sync_apps"),
            patch.object(
                self.manager, "create_glyph", side_effect=create_glyph
            ) as create,
        ):
            self.manager.apply("glyph")
            create.assert_called_once()
            self.assertTrue((self.manager.directory / "glyph-v1.json").exists())
            self.assertEqual(self.manager.active_revision, 2)
            self.manager.apply("original")
            self.assertEqual(bindings.read_text(), "original shared bindings")

    def test_glyph_icons_install_offline_and_preserve_existing_artwork(self):
        directory = self.manager.home / "data"
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(directory)}):
            self.manager.install_glyph_icons()
            icons = directory / "icons/YAMIS"
            self.assertTrue((icons / "LICENSE").is_file())
            alias = icons / "apps/scalable/zen-browser.svg"
            self.assertTrue(alias.is_symlink())
            artwork = alias.read_bytes()
            self.assertTrue(artwork.startswith(b"<?xml") or b"<svg" in artwork)
            alias.resolve().write_bytes(b"my custom Zen icon")
            self.manager.install_glyph_icons()
            self.assertEqual(alias.read_bytes(), b"my custom Zen icon")

    def test_icon_switch_restores_original_and_preserves_other_gui_settings(self):
        originals = {
            "gtk-3.0/settings.ini": "[Settings]\ngtk-font-name=Custom 12\ngtk-icon-theme-name=Pop\n",
            "gtk-4.0/settings.ini": "[Settings]\ngtk-icon-theme-name=Pop\n",
            "xsettingsd/xsettingsd.conf": 'Net/IconThemeName "Pop"\n',
            "qt5ct/qt5ct.conf": "[Appearance]\nstyle=Custom\nicon_theme=Pop\n",
            "qt6ct/qt6ct.conf": "[Appearance]\nicon_theme=Pop\n",
        }
        for relative, text in originals.items():
            path = self.manager.config / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        gtk2 = self.manager.home / ".gtkrc-2.0"
        gtk2.write_text('gtk-icon-theme-name="Pop"\n')
        self.manager.paths += [self.manager.config / name for name in originals]
        self.manager.paths.append(gtk2)
        with patch.object(themes, "run", return_value="'Pop'") as command:
            original = self.manager.snapshot()
            self.manager.configure_glyph_icons()
            command.assert_called_with(
                "gsettings", "set", "org.gnome.desktop.interface", "icon-theme", "YAMIS"
            )
            settings = configparser.ConfigParser()
            settings.read(self.manager.config / "qt5ct/qt5ct.conf")
            self.assertEqual(settings["Appearance"]["style"], "Custom")
            self.assertEqual(settings["Appearance"]["icon_theme"], "YAMIS")
            gtk3 = self.manager.config / "gtk-3.0/settings.ini"
            self.assertIn("gtk-font-name=Custom 12", gtk3.read_text())
            self.assertIn("gtk-icon-theme-name=YAMIS", gtk3.read_text())
            self.manager.restore(original)
            for relative, text in originals.items():
                self.assertEqual((self.manager.config / relative).read_text(), text)
            self.assertEqual(gtk2.read_text(), 'gtk-icon-theme-name="Pop"\n')
            self.assertIn(
                unittest.mock.call(
                    "gsettings",
                    "set",
                    "org.gnome.desktop.interface",
                    "icon-theme",
                    "'Pop'",
                ),
                command.call_args_list,
            )

    def test_font_update_preserves_icons_qt_styles_and_monospace_fonts(self):
        for version in ("3.0", "4.0"):
            path = self.manager.config / f"gtk-{version}/settings.ini"
            path.parent.mkdir(parents=True)
            path.write_text(
                "[Settings]\ngtk-font-name=Previous 11\ngtk-icon-theme-name=MyIcons\n"
            )
        legacy = self.manager.config / "xsettingsd/xsettingsd.conf"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('Net/IconThemeName "MyIcons"\n')
        for toolkit in ("qt5ct", "qt6ct"):
            path = self.manager.config / f"{toolkit}/{toolkit}.conf"
            path.parent.mkdir()
            path.write_text(
                "[Appearance]\nstyle=MyStyle\n[Fonts]\nfixed=MyMono\ngeneral=Previous\n"
            )
        with patch.object(themes, "run") as command:
            self.manager.configure_glyph_fonts()
        command.assert_called_once_with(
            "gsettings",
            "set",
            "org.gnome.desktop.interface",
            "font-name",
            "Glyph UI 11",
        )
        for version in ("3.0", "4.0"):
            text = (self.manager.config / f"gtk-{version}/settings.ini").read_text()
            self.assertIn("gtk-font-name=Glyph UI 11", text)
            self.assertIn("gtk-icon-theme-name=MyIcons", text)
        for toolkit in ("qt5ct", "qt6ct"):
            settings = configparser.ConfigParser()
            settings.read(self.manager.config / f"{toolkit}/{toolkit}.conf")
            self.assertEqual(settings["Appearance"]["style"], "MyStyle")
            self.assertEqual(settings["Fonts"]["fixed"], "MyMono")
            self.assertTrue(settings["Fonts"]["general"].startswith('"Glyph UI,11,'))

    def test_mode_change_preserves_gui_fonts_and_qt_style(self):
        (self.manager.directory / "current").write_text("glyph")
        for version in ("3.0", "4.0"):
            path = self.manager.config / f"gtk-{version}/settings.ini"
            path.parent.mkdir(parents=True)
            path.write_text("[Settings]\ngtk-font-name=My custom font 12\n")
        qt = self.manager.config / "qt5ct/qt5ct.conf"
        qt.parent.mkdir()
        qt.write_text("[Appearance]\nstyle=my-custom-style\n")
        with (
            patch.object(themes, "run", return_value="light"),
            patch.object(themes, "reload_apps"),
        ):
            self.manager.sync_apps()
        self.assertIn(
            "My custom font 12",
            (self.manager.config / "gtk-3.0/settings.ini").read_text(),
        )
        self.assertIn("my-custom-style", qt.read_text())

    def test_failed_apply_restores_settings_and_active_preset(self):
        def create_glyph():
            self.settings.write_text('[theme]\nmode = "light"\n')

        with (
            patch.object(themes, "run", return_value="ok"),
            patch.object(themes, "reload_apps"),
            patch.object(self.manager, "create_glyph", side_effect=create_glyph),
            patch.object(
                self.manager,
                "reload_theme",
                side_effect=[RuntimeError("render failed"), None],
            ),
            self.assertRaisesRegex(RuntimeError, "render failed"),
        ):
            self.manager.apply("glyph")
        self.assertEqual(self.manager.current, "original")
        self.assertEqual(
            tomllib.loads(self.settings.read_text())["theme"]["mode"], "dark"
        )
        backup = self.manager.directory / "original.json"
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_gui_changes_survive_round_trip(self):
        def create_glyph():
            self.settings.write_text(
                '[theme]\nmode = "dark"\ncustom_palette = "Glyph"\n'
            )

        with (
            patch.object(themes, "run", return_value="ok"),
            patch.object(themes, "reload_apps"),
            patch.object(self.manager, "reload_theme"),
            patch.object(self.manager, "sync_apps"),
            patch.object(self.manager, "create_glyph", side_effect=create_glyph),
        ):
            self.manager.apply("glyph")
            self.settings.write_text(
                '[theme]\nmode = "light"\ncustom_palette = "Glyph"\n'
            )
            self.manager.apply("original")
            self.assertEqual(
                tomllib.loads(self.settings.read_text())["theme"]["mode"], "dark"
            )
            self.manager.apply("glyph")
            self.assertEqual(
                tomllib.loads(self.settings.read_text())["theme"]["mode"], "light"
            )

    def test_unavailable_shell_leaves_files_unchanged(self):
        with (
            patch.object(
                themes, "run", side_effect=RuntimeError("noctalia is not running")
            ),
            self.assertRaisesRegex(RuntimeError, "not running"),
        ):
            self.manager.apply("glyph")
        self.assertEqual(self.manager.current, "original")
        self.assertFalse((self.manager.directory / "original.json").exists())

    def test_missing_original_is_reported_instead_of_relabeling_glyph(self):
        with self.assertRaisesRegex(
            RuntimeError, "original desktop snapshot is missing"
        ):
            self.manager.stage_theme("original")

    def test_concurrent_switch_is_rejected(self):
        with (
            self.manager.locked(),
            self.assertRaisesRegex(RuntimeError, "in progress"),
            self.manager.locked(),
        ):
            self.fail("Concurrent switch acquired the lock")

    def test_template_completion_must_arrive_before_apply_returns(self):
        calls = []

        def command(*arguments):
            calls.append(arguments)

        with (
            patch.object(themes, "run", side_effect=command),
            patch.object(
                themes.time,
                "sleep",
                side_effect=lambda _: self.manager.acknowledge_templates(),
            ) as waiting,
        ):
            self.manager.reload_theme()
        waiting.assert_called_once()
        self.assertEqual(calls[-1], ("noctalia", "msg", "templates-apply"))


class PresetTests(unittest.TestCase):
    def test_widget_layout_uses_logical_monitor_sizes(self):
        output = {"name": "DP-1", "logical": {"width": 1280, "height": 720}}
        config = tomllib.loads(
            themes.glyph_desktop({"DP-1": output, "off": {"logical": None}})
        )
        desktop = config["desktop_widgets"]
        self.assertEqual(len(desktop["widget_order"]), 5)
        clock = desktop["widget"]["glyph-DP-1-clock"]
        self.assertEqual(clock["output"], "DP-1")
        self.assertAlmostEqual(clock["cx"], 1280 * 0.29)
        self.assertEqual(clock["settings"]["font_family"], "Glyph Dots")

    def test_no_active_monitor_reports_an_error(self):
        with self.assertRaisesRegex(RuntimeError, "no active monitors"):
            themes.glyph_desktop({"off": {"logical": None}})

    def test_both_palette_variants_have_readable_text(self):
        palette = json.loads((themes.ASSETS / "presets/glyph/Glyph.json").read_text())
        for mode in ("dark", "light"):
            colors = palette[mode]
            self.assertNotEqual(colors["mSurface"], colors["mOnSurface"])
            self.assertEqual(len(colors["terminal"]["normal"]), 8)
            self.assertEqual(len(colors["terminal"]["bright"]), 8)


if __name__ == "__main__":
    unittest.main()
