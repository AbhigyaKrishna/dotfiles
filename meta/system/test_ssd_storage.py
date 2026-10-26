"""Filesystem regression checks; never mounts disks or changes host settings."""

import importlib.machinery
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader(
    "ssd_storage", str(Path(__file__).with_name("ssd-storage"))
)
spec = importlib.util.spec_from_loader(loader.name, loader)
storage = importlib.util.module_from_spec(spec)
loader.exec_module(storage)


class StorageTests(unittest.TestCase):
    def test_storage_parent_allows_canonical_cache_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            disk = base / "ssd"
            disk.mkdir()
            parent = disk / "system-storage"
            parent.mkdir(mode=0o700)
            cache = base / "user-cache"
            cache.mkdir()
            entries = [
                {"target": str(cache), "destination": "users/cache", "mode": 0o700}
            ]
            with (
                patch.object(storage, "SSD", disk),
                patch.object(storage, "STORAGE", parent),
                patch.object(storage, "CONFIG", base / "configuration"),
                patch.object(storage.os, "chown"),
            ):
                storage.prepare_storage(entries)
            self.assertEqual(parent.stat().st_mode & 0o777, 0o711)
            self.assertEqual((parent / "users/cache").stat().st_mode & 0o777, 0o700)

    def test_failed_backup_keeps_published_versions_and_local_snapshots(self):
        with tempfile.TemporaryDirectory() as directory:
            backups = Path(directory)
            published = backups / "20261008T010000Z"
            published.mkdir()
            (published / "recovery-file").write_text("keep me")
            with (
                patch.object(storage, "mount_nvme"),
                patch.object(storage, "create_backup_snapshots", return_value=[]),
                patch.object(
                    storage,
                    "copy_backup_snapshots",
                    side_effect=RuntimeError("disk full"),
                ),
                patch.object(storage, "run") as commands,
                patch.object(storage, "minimal_snapshots") as cleanup,
                self.assertRaisesRegex(RuntimeError, "disk full"),
            ):
                storage.backup_locked(backups)
            cleanup.assert_not_called()
            commands.assert_called_once_with("umount", storage.TOP)
            self.assertEqual((published / "recovery-file").read_text(), "keep me")
            self.assertEqual(list(backups.glob("20??????T??????Z")), [published])

    def test_successful_backup_is_published_before_pruning(self):
        with tempfile.TemporaryDirectory() as directory:
            backups = Path(directory)
            for day in range(1, 9):
                (backups / f"202609{day:02d}T010000Z").mkdir()

            def assert_published():
                versions = sorted(backups.glob("20??????T??????Z"))
                self.assertEqual(len(versions), 9)
                self.assertTrue((versions[-1] / "README").is_file())
                self.assertFalse((backups / ".incomplete").exists())

            with (
                patch.object(storage, "mount_nvme"),
                patch.object(storage, "create_backup_snapshots", return_value=[]),
                patch.object(storage, "copy_backup_snapshots"),
                patch.object(storage, "copy_version"),
                patch.object(storage, "run"),
                patch.object(
                    storage, "minimal_snapshots", side_effect=assert_published
                ),
            ):
                storage.backup_locked(backups)
            self.assertEqual(len(list(backups.glob("20??????T??????Z"))), 7)
            self.assertFalse((backups / "20260901T010000Z").exists())

    def test_application_caches_keep_settings_and_escape_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            cache = home / ".config/Code - Insiders/Code Cache"
            cache.mkdir(parents=True)
            (home / ".config/Code - Insiders/User").mkdir()
            paths = storage.application_caches(home)
            self.assertEqual(paths, [".config/Code - Insiders/Code Cache"])
            entries = [{"target": str(cache), "destination": paths[0]}]
            rendered = storage.render_fstab("", entries)
            self.assertIn("Code\\040-\\040Insiders/Code\\040Cache", rendered)
            self.assertEqual(storage.render_fstab(rendered, entries), rendered)

    def test_fstab_replaces_only_storage_targets_and_is_idempotent(self):
        original = (
            "# retain comments\n"
            "UUID=nvme / btrfs subvol=/@ 0 0\n"
            "UUID=nvme /var/cache btrfs subvol=/@cache 0 0\n"
            "tmpfs /tmp tmpfs mode=1777 0 0\n"
            "UUID=nvme /var/log btrfs subvol=/@log 0 0\n"
            "UUID=ssd /run/media/abhigya/SSD ext4 defaults 0 2\n"
        )
        entries = [{"target": "/var/cache", "destination": "cache"}]
        rendered = storage.render_fstab(original, entries)
        self.assertIn("UUID=nvme /var/log btrfs subvol=/@log 0 0\n", rendered)
        self.assertIn("UUID=ssd /run/media/abhigya/SSD ext4 defaults 0 2\n", rendered)
        self.assertNotIn("subvol=/@cache", rendered)
        targets = [
            line.split()[1]
            for line in rendered.splitlines()
            if line and not line.startswith("#")
        ]
        self.assertEqual(targets.count("/tmp"), 1)
        self.assertEqual(targets.count("/var/cache"), 1)
        self.assertEqual(storage.render_fstab(rendered, entries), rendered)

    def test_move_preserves_links_metadata_and_retries_partial_transfer(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            destination = base / "destination"
            (source / "nested").mkdir(parents=True)
            destination.mkdir()
            payload = source / "nested" / "payload"
            payload.write_text("cached content")
            payload.chmod(0o640)
            os.link(payload, source / "hardlink")
            (source / "symlink").symlink_to("nested/payload")
            (destination / "already-moved").write_text("keep from interrupted run")
            # A same-size, same-mtime partial destination must not be mistaken
            # for a good copy when the interrupted migration is retried.
            (destination / "nested").mkdir()
            partial = destination / "nested" / "payload"
            partial.write_text("broken content")
            os.utime(
                partial, ns=(payload.stat().st_atime_ns, payload.stat().st_mtime_ns)
            )
            storage.move_directory(source, destination)
            self.assertEqual(list(source.iterdir()), [])
            self.assertEqual(
                (destination / "nested/payload").read_text(), "cached content"
            )
            self.assertEqual(
                (destination / "already-moved").read_text(), "keep from interrupted run"
            )
            self.assertEqual(
                (destination / "nested/payload").stat().st_mode & 0o777, 0o640
            )
            self.assertEqual(
                (destination / "nested/payload").stat().st_ino,
                (destination / "hardlink").stat().st_ino,
            )
            self.assertEqual(os.readlink(destination / "symlink"), "nested/payload")
            storage.move_directory(source, destination)
            self.assertEqual(
                (destination / "nested/payload").read_text(), "cached content"
            )

    def test_failed_transfer_does_not_clear_remaining_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source"
            source.mkdir()
            payload = source / "payload"
            payload.write_text("keep me")
            with self.assertRaises(subprocess.CalledProcessError):
                storage.move_directory(
                    source, Path(directory) / "missing" / "destination"
                )
            self.assertEqual(payload.read_text(), "keep me")

    def test_backup_versions_share_unchanged_files_and_preserve_old_content(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            (source / "stable").write_text("unchanged")
            changed = source / "changed"
            changed.write_text("before")
            (source / ".cache").mkdir()
            (source / ".cache" / "ignored").write_text("disposable")
            first = base / "first"
            second = base / "second"
            storage.copy_version(source, first, excludes=(".cache",))
            timestamp = changed.stat().st_mtime_ns
            changed.write_text("after!")
            os.utime(changed, ns=(timestamp, timestamp))
            storage.copy_version(source, second, previous=first, excludes=(".cache",))
            self.assertEqual((first / "changed").read_text(), "before")
            self.assertEqual((second / "changed").read_text(), "after!")
            self.assertEqual(
                (first / "stable").stat().st_ino, (second / "stable").stat().st_ino
            )
            self.assertFalse((second / ".cache").exists())


if __name__ == "__main__":
    unittest.main()
