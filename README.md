# dotfiles

Linux dotfiles for CachyOS, managed with [GNU Stow](https://www.gnu.org/software/stow/).

Built so that desktop-agnostic configuration survives a change of desktop
environment. Shell, terminals, CLI tools and hardware settings live in one tier;
the compositor and its shell live in another; theming in a third. Switching
desktops means swapping one tier, not rebuilding the setup.

## Layout

```
common/     always stowed — shell, terminals, CLI tools, hardware, env
theme/      GTK/Qt look — exactly one active
desktop/    compositor / DE — exactly one active
profiles/   which packages each profile turns on
meta/       things that cannot be symlinked (enabled systemd user units)
```

Each package mirrors the path it installs to, relative to `$HOME`:

```
common/terminals/.config/kitty/kitty.conf   →   ~/.config/kitty/kitty.conf
theme/adw-dark/.gtkrc-2.0                   →   ~/.gtkrc-2.0
desktop/niri/.config/niri/config.kdl        →   ~/.config/niri/config.kdl
```

## Usage

```sh
./bootstrap.sh --list        # available profiles
./bootstrap.sh niri -n       # dry run — prints every link, changes nothing
./bootstrap.sh niri          # apply
./bootstrap.sh --unstow      # remove every symlink this repo owns
```

The profile is the single source of truth. For the single-choice tiers
(`theme`, `desktop`) `bootstrap.sh` unstows every package the profile does not
name before stowing the one it does, so applying a profile is idempotent and
switching desktops is a single command.

## On a fresh machine

```sh
sudo pacman -S stow
git clone git@github.com:AbhigyaKrishna/dotfiles.git ~/Projects/dotfiles
cd ~/Projects/dotfiles && ./bootstrap.sh niri
grep -v '^#' meta/systemd-user-units.txt | xargs -r systemctl --user enable --now
fisher update     # restores fish plugins listed in fish_plugins
```

Stow refuses to overwrite a real file. If a fresh install has already written a
config, move it aside and re-run.

## Adding a desktop environment

```sh
mkdir -p desktop/hyprland/.config/hypr
cp -r ~/.config/hypr/. desktop/hyprland/.config/hypr/
sed 's/^desktop:.*/desktop: hyprland/' profiles/niri.conf > profiles/hyprland.conf
./bootstrap.sh hyprland
```

No change to `bootstrap.sh` is needed. The same pattern adds a theme under
`theme/`.

If a package turns out to be shared between desktops — `noctalia` supports both
niri and Hyprland, for example — promote it to `common/` and drop it from the
desktop packages.

## What is not tracked

| Path | Why |
| --- | --- |
| `.config/gh/hosts.yml` | live OAuth token |
| `.config/noctalia/plugins/` | 3 MB of third-party code; `plugins.json` records which |
| `.config/micro/syntax/` | 146 syntax files shipped by micro, not authored here |
| `.config/polychromatic/devices/`, `states/`, `backends/` | device-capability cache, runtime lighting state, per-device persistence |
| `.config/htop/htop_history` | search history, not settings; `htoprc` is tracked |
| `.config/OpenRGB/` | contains only log files — no configuration to track |
| `.config/systemd/user/` | generated enable-symlinks; see `meta/systemd-user-units.txt` |
| `.config/vesktop/`, `.config/zen/` | 4 GB of browser and app profile data |
| `.config/mpv/` | empty |

For `gh`, `noctalia`, `micro` and `polychromatic`, the directory in `~/.config` is intentionally left as a real
directory. Stow only folds a directory into a single symlink when the target
does not exist, so keeping it real makes stow link the tracked files
individually and leave the untracked ones alone.

## Monitors

Monitor layout is managed with [Monique](https://github.com/ToRvaLDz/monique),
which writes `~/.config/niri/monitors.kdl` from the profiles in
`.config/monique/profiles/`. Both are tracked, so a saved arrangement comes back
with the repo — but they describe *this machine's* displays by make, model and
serial. On a second machine, re-detect in Monique rather than reusing these.

## Known wrinkle

`~/.config/gtk-3.0/settings.ini` sets `gtk-theme-name=cachyos-nord`, while
`.profile` exports `GTK_THEME=adw-gtk3-dark`. The environment variable wins, so
the effective theme is `adw-gtk3-dark`. Recorded as-is rather than silently
reconciled.
