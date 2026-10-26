# SSD storage on this host

The NVMe is Btrfs; the SATA SSD is ext4, UUID
`9fed50af-aba4-46c4-92e7-5a8ebf9f7f37`, mounted at
`/run/media/abhigya/SSD`. Native Btrfs snapshots must stay on their filesystem
([Btrfs documentation](https://btrfs.readthedocs.io/en/latest/Subvolumes.html)).
This setup puts disposable storage and seven daily recovery backup versions
on the SSD and keeps a small set of native snapshots for quick recovery.

## Install and activate

From the dotfiles repository:

```sh
meta/system/ssd-storage plan         # print proposed fstab, change nothing
sudo meta/system/ssd-storage install
```

Save your work and reboot when convenient. The installer does not reboot,
move active caches, or prune snapshots. The first boot moves roughly 120 GB
plus application caches before starting applications, so allow extra time.
Progress appears on the boot console and in the migration service journal.
The SSD becomes required for boot: mounts deliberately fail rather than
silently accumulate cache files on the NVMe if the SSD is unavailable.

The installer checks the actual disk UUIDs and subvolume layout, preserves
the original fstab and Snapper configurations under `/etc/ssd-storage`, and
validates the replacement fstab before activating it. It adds a sticky bit
to the currently world-writable SSD mountpoint to protect the root-owned
`system-storage` directory from replacement by other accounts.
The parent uses mode `0711` so applications can traverse canonical cache and
temporary paths. Backup directories remain root-only, and user cache directories
retain their own ownership and permissions.

## Storage moved

Bind mounts retain existing paths, including applications that ignore XDG
environment variables. `/tmp` becomes SSD-backed rather than RAM-backed;
`/var/tmp` and `/var/cache` also use the SSD.

For the installing user, the script moves:

- `~/.cache`, `~/.gradle`, and `~/.npm`.
- Cargo registry/Git caches, Bun install cache, and Go module/checksum caches.
- Maven repository/wrapper caches, NuGet package/HTTP caches, pnpm store,
  Dart package cache, Android cache, and Rustup temporary/download directories.
- Existing application cache directories within three levels of `~/.config`,
  including Electron, browser and editor caches. Settings and profiles remain
  in their original locations.

The exact list is recorded in `/etc/ssd-storage/entries.json`. Re-running the
installer discovers new application caches and schedules their migration at
the next boot. It does not follow symlinked configuration directories.

Project-local `node_modules`, Rust `target`, Gradle `build`, arbitrary custom
cache paths, Docker images/volumes, IDE installations, and game libraries
remain where they are. These mix project or application state with caches and
cannot all be redirected safely by one global setting.

The migration runs before `local-fs.target`. It checks the SSD identity every
boot and moves each file using rsync checksums and `--fsync`. Source files are
removed only after successful transfers. Interrupted moves resume without
deleting files already copied to the SSD. Existing NVMe snapshots can keep
the old cache extents allocated until their retention expires.

## Recovery backups and local retention

`ssd-storage-backup.timer` runs daily and after boot. It takes temporary
read-only Btrfs snapshots of `@`, `@home`, `@root`, and `@srv`, then copies
them to `SSD/system-storage/backups/<UTC timestamp>/`. The boot partition is
copied separately. The temporary snapshots are removed afterward; they are
never added to Snapper or the boot menu.

Backups preserve file ownership, permissions, ACLs, extended attributes,
symlinks and hard links. Unchanged files share hard links with the previous
backup. Treat backup directories as read-only: edit a recovered copy rather
than a file inside a backup, because unchanged files can belong to several
versions. The directory remains root-only to protect private files.

Each source is captured separately, so this is not an atomic snapshot across
all filesystems or an application-aware database backup. Nested subvolumes
are not included automatically. Logs, swap, temporary files, moved caches,
and older Snapper recovery points are excluded. Existing snapshot history is
not archived to the SSD; the first backup preserves the current system and
home state before the local history is reduced.

A completed backup is flushed and published before any local cleanup. Failed
copies remain unpublished and do not trigger snapshot pruning. The next run
discards only its incomplete staging directory and retries. Seven completed
SSD versions are kept. After a successful backup, root and home Snapper configs
retain four regular numbered snapshots, two important numbered snapshots,
and one hourly/one daily timeline snapshot. Snapper's minimum ages and its
separate cleanup categories still apply; snapshots without a cleanup algorithm
are unaffected. `snap-pac` and boot-menu snapshot integration stay enabled.

## Verify after reboot

```sh
findmnt -T /tmp
findmnt -T /var/cache
findmnt -T ~/.cache
findmnt -T ~/go/pkg/mod
systemctl status ssd-storage-migrate.service
journalctl -b -u ssd-storage-migrate.service
systemctl list-timers ssd-storage-backup.timer
sudo systemctl start ssd-storage-backup.service
journalctl -u ssd-storage-backup.service
sudo snapper -c root get-config
sudo snapper -c home get-config
df -h / /run/media/abhigya/SSD
```

The moved paths should resolve to `/dev/sda1`/ext4. Inspect backup versions
with `sudo ls /run/media/abhigya/SSD/system-storage/backups`.

To recover an individual home file, copy it from
`<version>/home/<user>/<relative path>` to a separate recovery directory,
inspect it, then replace the working file. `root` corresponds to `/`,
`root-home` to `/root`, `srv` to `/srv`, and `boot` to `/boot`. Full system
restoration requires a rescue environment and restoring each filesystem
separately; the SSD backup is not a directly bootable snapshot.

## Cancel or recover the configuration

Before the first reboot, cancellation leaves all cache data on the NVMe:

```sh
sudo cp /etc/ssd-storage/original.fstab /etc/fstab
sudo systemctl disable --now ssd-storage-backup.timer
sudo systemctl daemon-reload
```

After migration, do this from a rescue session with applications stopped.
Restore fstab and reboot to its original mounts first; keep the SSD attached.
Caches remain intact on the SSD. Copy any needed cache or Gradle configuration
back from the destinations listed in `/etc/ssd-storage/entries.json`; missing
disposable cache files will otherwise be regenerated. Do not delete the SSD
storage directory while the bind mounts are active.

Original Snapper policies can be restored independently:

```sh
sudo cp /etc/ssd-storage/snapper-root /etc/snapper/configs/root
sudo cp /etc/ssd-storage/snapper-home /etc/snapper/configs/home
```

Configuration rollback cannot restore snapshots already pruned after a
successful backup. Keep the SSD backups available for file recovery.

## Local checks

```sh
python3 -B meta/system/test_ssd_storage.py
ruff check meta/system/ssd-storage meta/system/test_ssd_storage.py
ruff format --check meta/system/ssd-storage meta/system/test_ssd_storage.py
```
