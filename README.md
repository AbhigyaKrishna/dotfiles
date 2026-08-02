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

## Docker, rootless

The daemon runs as the user rather than as root, so containers have no path to
the host's root and the images live under `~/.local/share/docker` instead of
`/var/lib/docker`. Three tracked pieces make that work:

- `docker` and `docker-rootless-extras` in `meta/packages.txt`, plus
  `docker-compose` and `docker-buildx`. The extras package is AUR-only; it
  supplies `dockerd-rootless.sh`, `rootlesskit` and `slirp4netns`.
- The `docker.socket` **user** unit in `meta/systemd-user-units.txt`, which
  socket-activates the rootless `docker.service` on
  `$XDG_RUNTIME_DIR/docker.sock`.
- `DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock`, exported from `.zshrc`,
  `.bashrc` and `config.fish`. The CLI defaults to `/var/run/docker.sock`, so
  without this it talks to the wrong daemon — or to none. It is repeated per
  shell rather than set once in `environment.d`, because `environment.d` is
  only read by the systemd user manager and would miss ssh sessions.

The subuid/subgid ranges it also needs are under "Root-owned pieces" below.
Confirm the daemon the CLI reached is the rootless one:

```sh
docker info | grep -A1 Security   # expect `rootless` in the options
docker info --format '{{.DockerRootDir}}'
```

Two caveats about the current machine, neither of them tracked here on purpose:

- The **system** `docker.service` is also enabled, so a rootful daemon runs
  alongside on `/var/run/docker.sock`. Nothing in this repo enables it. On a
  rebuild it stays off unless you turn it on, and `DOCKER_HOST` keeps the CLI
  pointed at the rootless socket either way.
- Lingering is off (`loginctl show-user "$USER" -p Linger`), so the daemon and
  its containers stop with the last session. `sudo loginctl enable-linger
  "$USER"` changes that if you want containers to survive logout.

## Root-owned pieces

Some things this configuration depends on live outside `$HOME`, so stow cannot
place them. They are recorded under `meta/` and installed by hand.

**sddm keyring override.** systemd services default to `KeyringMode=private`,
giving sddm its own session keyring. `pam_kwallet` writes the wallet password
there at login, so under `private` the user session never inherits it and
kwallet cannot auto-unlock — which breaks `ksshaskpass`, and with it the
`SSH_ASKPASS` / `GIT_ASKPASS` flow that ssh and git rely on here.

```sh
sudo install -Dm644 meta/system/sddm.service.d/override.conf \
  /etc/systemd/system/sddm.service.d/override.conf
sudo systemctl daemon-reload
```

**subuid / subgid ranges for rootless docker.** The rootless daemon maps
container UIDs into a subordinate range owned by the user. Without an entry in
`/etc/subuid` and `/etc/subgid`, `dockerd-rootless.sh` refuses to start. There
is no file to install — the range is allocated per user:

```sh
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 "$USER"
grep "$USER" /etc/subuid /etc/subgid   # verify
```

`kernel.unprivileged_userns_clone` must also be `1`; it is the default on Arch.

**Power profile switching.** `power-profiles-daemon` comes in with the desktop
tier — it is an optdepend of `noctalia-shell`, and the bar's `PowerProfile`
widget reads and sets profiles through it. It exposes the profiles but does not
choose between them, so switching stays manual, from the widget. This udev rule
adds the automatic half: on every AC adapter change it runs a helper that sets
`performance` on the charger and `power-saver` on battery. The widget still
works without the rule; the rule needs the package the widget already pulls in.

```sh
sudo install -Dm755 meta/system/bin/power-profile-auto.sh \
  /usr/local/bin/power-profile-auto.sh
sudo install -Dm644 meta/system/udev/99-power-profile.rules \
  /etc/udev/rules.d/99-power-profile.rules
sudo udevadm control --reload
```

The helper hardcodes `ACAD` as the adapter, which is this laptop's name for it.
Other machines use `AC`, `AC0` or `ADP1`, and a desktop has none — there the
script's file test fails and it quietly does nothing rather than misfiring.
`ls /sys/class/power_supply/` shows the right name; the script has a comment
saying so.

**TLP, as device tweaks only.** TLP is installed but is *not* the power
manager — `power-profiles-daemon` is. The two are mutually exclusive as profile
managers, so `tlp.service` stays disabled; enabling it makes them fight over
the governor and the platform profile, and `tlp-stat -s` reports the clash.
What TLP contributes is two settings that are not profile settings and overlap
with nothing PPD touches: `SOUND_POWER_SAVE_ON_AC=0` stops the HDA codec
sleeping on AC and popping at the start of playback, and `USB_AUTOSUSPEND=0`
stops USB devices being suspended out from under you.

```sh
sudo install -Dm644 meta/system/tlp.d/10-local.conf /etc/tlp.d/10-local.conf
sudo tlp start
```

A drop-in rather than `/etc/tlp.conf`, because tlp.conf is a pacman backup file
and editing it earns a `.pacnew` on every update. `/etc/tlp.d/README` documents
this as the intended path. `tlpui` is installed for editing it.

**These two settings do not survive a reboot.** Applying them is what
`tlp.service` would do, and it is disabled, so they only take effect when TLP
is run by hand. If that matters, the way to make them stick without handing
power management back to TLP is to set them at the module level instead, which
takes effect at boot and does not involve TLP at all:

```sh
echo 'options snd_hda_intel power_save=0' | sudo tee /etc/modprobe.d/audio.conf
echo 'options usbcore autosuspend=-1'     | sudo tee /etc/modprobe.d/usb.conf
```

That is not what is deployed here; the drop-in above is. Recorded as the known
alternative rather than applied silently.

**Enabled systemd user units.** Recorded in `meta/systemd-user-units.txt`; see
the fresh-machine steps above.

There are no custom systemd unit files. `~/.config/systemd/user/` holds only
the enable-symlinks `systemctl --user enable` creates, and everything in
`/etc/systemd/system/` is package-owned apart from the drop-in above.

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

## Theme

`adw-gtk3-dark` throughout: `gtk-3.0/settings.ini`, `gtk-4.0/settings.ini`,
`.gtkrc-2.0`, `xsettingsd.conf`, and the `GTK_THEME` export in `.profile` all
name it.

They previously all said `cachyos-nord`, a theme that is not installed and is
not in any repo. GTK apps looked right only because `GTK_THEME` overrides the
settings files; unset it and everything fell back to unstyled Adwaita. The
files now state what is actually in effect.

Note that `.gtkrc-2.0` carries a "DO NOT EDIT, will be overwritten by nwg-look"
header. Running nwg-look may revert it — check `git diff` afterwards.

Qt goes through `QT_QPA_PLATFORMTHEME=qt5ct` → qt5ct `style=kvantum` → Kvantum
`theme=KvArcDark`. Both packages are in `meta/packages.txt`, and KvArcDark is
one Kvantum ships, so the chain needs nothing extra. It was previously set to
`Nordic-Darker-Solid`, which was never installed — Kvantum falls back silently
rather than warning, so it looked fine while doing nothing.

`xsettingsd` is spawned from `niri/cfg/autostart.kdl`. It serves the same theme
and font settings over XSETTINGS to X11 and XWayland apps, which do not read
`gtk-3.0/settings.ini`. Native Wayland GTK apps ignore it.
