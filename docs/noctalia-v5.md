# Native Noctalia v5

The desktop runs the `noctalia` package, supervised by `noctalia.service`.
`noctalia-shell.service` and its `qs -c noctalia-shell` command are retired.
V5 uses a native Wayland runtime rather than QML; the old Qt compatibility
override must not be recreated for this configuration.

## Configuration and startup

- `desktop/niri/.config/noctalia/config.toml`: bar, launcher pins, dock,
  wallpaper, wallpaper-derived dark palette, GTK templates, lock and idle policy.
- `desktop/niri/.config/systemd/user/noctalia.service`: supervised startup.
- `desktop/niri/.config/niri/cfg/keybinds.kdl`: native `noctalia msg` commands.
- `common/bin/.local/bin/niri-power-action`: native lock IPC; existing power
  source, lid grace, docking and suspend-then-hibernate decisions remain here.

After installing the packages and stowing the niri profile:

```sh
systemctl --user disable --now noctalia-shell.service # if the legacy unit exists
systemctl --user daemon-reload
systemctl --user enable --now noctalia.service
noctalia config validate
niri validate
```

GUI overrides live in `~/.local/state/noctalia/settings.toml` and take precedence
over the tracked config. Keep runtime state out of the repository. The wallpaper
path must exist locally; select another image in Settings when rebuilding on
another machine.

## Preserved behavior

Lock after 600 seconds on either power source. On battery, blank at 660 seconds
and suspend at 1200 seconds. On mains, blank at 1200 seconds without suspending.
Keep the five-second pre-action fade. Lid handling still ignores docked closes
and delays battery suspend for ten minutes unless charge is critically low.

`Mod+Space` opens the launcher, `Mod+V` opens clipboard history,
`Mod+Shift+Tab` opens searchable window results (`/win`), `Mod+Alt+L` locks,
`Mod+Shift+Q` opens the session menu, and `Mod+Shift+I` toggles caffeine.
Media, audio, brightness and power-button bindings use native IPC.

Clipboard history and selection persistence are native. Legacy cliphist data
is retained on disk; v5 does not read that history. No clipboard contents are
exported during migration.

## Plugins and user data

| V4 feature | V5 replacement |
| --- | --- |
| Cloudflare WARP | `levi/warp:warp` |
| Todo | `baizhu/paged-todo:bar` |
| Notes scratchpad | `noctalia/notes:notes` |
| Privacy indicator | built-in `privacy` widget |
| Screen recorder | `noctalia/screen_recorder:recorder` |
| Mini Docker | `8bury/mini-docker:mini-docker` |

The tracked `[plugins].enabled` list makes these available on a fresh install;
the shell fetches compatible implementations from its default official and
community sources. Recorder dependencies are `gpu-screen-recorder` and `slurp`.

Paged Todo imports the legacy plugin's settings on first load and writes its
data to `~/.local/state/noctalia/plugins/data/baizhu/paged-todo/todos.json`.
The migration preserved all 11 task records, pages and selected page exactly.
The 813-character legacy scratchpad was copied verbatim to
`~/Documents/Notes/scratchpad.md`, the native Notes plugin's scratchpad file.
The old JSON files remain untouched. User content is not copied into dotfiles.

Catwalk, parallax wallpaper and the old fancy audiovisualizer are retained as
legacy plugin files without being loaded by v5. They have no direct migration
in this configuration. Desktop widget placements were empty in v4.

## Verification and recovery

```sh
systemctl --user status noctalia.service
journalctl --user -b -u noctalia.service
noctalia msg status
noctalia config validate
niri validate
```

Verified after restarting: service active with zero automatic restarts, five
plugins loaded, bar/dock/wallpaper created, and launcher, window search,
clipboard, todo, notes and session panels responding to IPC. All 17 bindings
use supported native command verbs. The service unit, Niri configuration,
Noctalia configuration, shell syntax and whitespace checks pass.

Lock/unlock authentication, timed idle actions, suspend/hibernate, recording,
VPN toggles and container mutations were not exercised. The log still reports
optional catalog requests with `Connection timed out after 10000 milliseconds`
and unavailable Bluetooth devices with `br-connection-page-timeout` or
`br-connection-create-socket`; these do not prevent shell startup.

Migration backups are under
`~/.local/state/noctalia/migration-v5-20261017-234924/`. They contain the old
service, bindings, autostart, user template TOML, app settings and Quickshell
override. Legacy plugin data remains under `~/.config/noctalia/plugins/`.

To undo the live transition, disable `noctalia.service`, restore the backed-up
files and local override, reload systemd, and re-enable the old service. A
working v4 QML package must also be reinstalled: the currently installed
`noctalia-shell` 5.2.1 package contains native source files and cannot launch
through Quickshell. Restoring only the override would reproduce the original
failure.

References: [running v5](https://docs.noctalia.dev/noctalia/getting-started/running-the-shell/),
[configuration layers](https://docs.noctalia.dev/noctalia/configuration/),
[plugins](https://docs.noctalia.dev/noctalia/plugins/).
