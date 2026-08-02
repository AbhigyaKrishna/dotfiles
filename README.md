# dotfiles

Linux dotfiles for CachyOS, managed with [GNU Stow](https://www.gnu.org/software/stow/).

Built so that desktop-agnostic configuration survives a change of desktop
environment. Shell, terminals, CLI tools and hardware settings live in one tier;
the compositor and its shell live in another; theming in a third. Switching
desktops means swapping one tier, not rebuilding the setup.

## Layout

```
common/     always stowed — shell, terminals, CLI tools, env
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
sudo pacman -S --needed git stow
git clone git@github.com:AbhigyaKrishna/dotfiles.git ~/Projects/dotfiles
cd ~/Projects/dotfiles
./install-packages.sh          # -n first to see what it would do
./bootstrap.sh niri
cp meta/fish_variables.seed ~/.config/fish/fish_variables   # see below
grep -v '^#' meta/systemd-user-units.txt | xargs -r systemctl --user enable --now
fisher update     # restores fish plugins listed in fish_plugins
```

Stow refuses to overwrite a real file. If a fresh install has already written a
config, move it aside and re-run.

## Packages

`meta/packages.txt` lists the packages the tracked configuration depends on,
grouped by the stow package they back. `install-packages.sh` reads it, installs
only what is missing, and bootstraps paru first when absent — one entry
(`monique`) exists only in the AUR, and CachyOS ships paru in its own repo, so
on a fresh CachyOS install that is a single `pacman -S`.

```sh
./install-packages.sh -n     # list what is missing, change nothing
./install-packages.sh        # install it
./install-packages.sh -y     # no confirmation prompts
```

The script reports what remains uninstalled and exits non-zero rather than
claiming success, since paru can skip a package.

Adding to the list is just a new line in `meta/packages.txt`; the script needs
no change. The list deliberately covers only what the tracked configs need — it
is not a full record of installed packages, which `pacman -Qqe` already gives.

## Default applications

Defaults live in `common/misc/.config/mimeapps.list`, tracked like any other
config, so they travel with the repo instead of being re-clicked on every
install. Zen is the default browser, covering http, https, html, pdf and
mailto; sxiv handles images, mpv audio and video, Nautilus directories, kitty
the `terminal` scheme.

`xdgctl` is installed for editing them — a TUI that writes this same file, so
changes made in it show up as a normal diff:

```sh
xdgctl              # interactive; then check what changed
git -C ~/Projects/dotfiles diff common/misc/.config/mimeapps.list
```

To verify what a handler actually resolves to, ask the resolver applications
use rather than trusting the file:

```sh
xdg-mime query default x-scheme-handler/http    # -> zen.desktop
gio mime x-scheme-handler/http
```

`xdg-settings get default-web-browser` reports something different here — a
JetBrains entry, left over from Toolbox registering itself. It is inaccurate:
`xdg-mime` and `gio` both resolve to Zen, and those are what applications
consult. Not worth chasing unless something actually opens in the wrong place.

`.profile` also exports `BROWSER=zen-browser`, for the terminal programs that
read that variable instead of going through XDG.

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
| `.config/noisetorch/`, `.config/openrazer/`, `.config/polychromatic/` | written by their own daemons and tied to this machine's devices |
| `.config/fish/fish_variables` | see below — seeded from `meta/fish_variables.seed` |

### fish_variables

fish owns its universal-variable file and rewrites it whenever a `set -U` runs,
so it cannot be a symlink into the repo — stow will not even place it while a
fish session is live. It is kept out of the packages and stored as
`meta/fish_variables.seed`, copied into place by hand on a new machine.

It still holds real configuration (`fish_user_paths`, the `pure_*` prompt
settings, the fisher plugin registry), so refresh the seed after changing any of
them:

```sh
cp ~/.config/fish/fish_variables meta/fish_variables.seed
```

For `gh`, `noctalia`, `micro` and `polychromatic`, the directory in `~/.config` is intentionally left as a real
directory. Stow only folds a directory into a single symlink when the target
does not exist, so keeping it real makes stow link the tracked files
individually and leave the untracked ones alone.

## Provenance

Much of this starts life as the `cachyos-niri-noctalia` default, which CachyOS
installs from `/etc/skel/.config/`. That directory is the upstream baseline, so
what is genuinely customized can always be recovered with a diff:

```sh
diff -r desktop/niri/.config/niri /etc/skel/.config/niri
```

As of the initial import:

| File | State |
| --- | --- |
| `niri/cfg/rules.kdl` | 18 lines changed |
| `niri/cfg/keybinds.kdl` | 16 lines changed |
| `niri/cfg/misc.kdl` | 9 lines changed |
| `niri/cfg/input.kdl` | 7 lines changed |
| `niri/config.kdl` | 4 lines changed |
| `niri/cfg/autostart.kdl` | 3 lines changed |
| `niri/cfg/animation.kdl`, `display.kdl`, `layout.kdl` | unchanged from skel |
| `niri/monitors.kdl` | generated by Monique, no skel counterpart |
| `noctalia/settings.json`, `colors.json`, `colorschemes/` | not in skel |
| `fish/config.fish`, `alacritty.toml`, `gtk-3.0/settings.ini` | changed from skel |
| `fish/functions/`, `conf.d/`, `completions/`, `fish_plugins` | not in skel |
| `micro/settings.json`, `micro/colorschemes/` | unchanged from skel |

Defaults are tracked anyway. They cost almost nothing, and having them in the
repo means a diff against a future `/etc/skel` shows what upstream changed.

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
