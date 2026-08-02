# dotfiles

Linux dotfiles for CachyOS, managed with [GNU Stow](https://www.gnu.org/software/stow/).

Built so that desktop-agnostic configuration survives a change of desktop
environment. Shell, terminals, CLI tools and hardware settings live in one tier;
the compositor and its shell live in another; theming in a third. Switching
desktops means swapping one tier, not rebuilding the setup.

## Layout

```
common/     always stowed — shell, terminals, CLI tools, env, scripts
theme/      GTK/Qt look — exactly one active
desktop/    compositor / DE — exactly one active
profiles/   which packages each profile turns on
meta/       things that cannot be symlinked (root-owned config, unit lists)
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
grep -v '^#' meta/systemd-system-units.txt | xargs -r sudo systemctl enable --now
fisher update     # restores fish plugins listed in fish_plugins
```

The root-owned pieces are not covered by any of this; install them by hand from
`meta/system/` as described below.

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

**TLP as the power manager.** TLP handles power here, not
`power-profiles-daemon`. On this laptop there is no ACPI `platform_profile`, so
PPD had nothing but the `amd_pstate` knob and reported `PlatformDriver:
placeholder` for two of its three profiles; TLP tunes disk APM, PCIe ASPM, wifi
power save and USB besides, and switches on AC/battery by itself.

The bar keeps working across the swap. `tlp-pd` declares
`provides=power-profiles-daemon`, satisfying noctalia's optdepend, and ships
both the `org.freedesktop.UPower.PowerProfiles` and `net.hadess.PowerProfiles`
D-Bus interfaces — the former is what noctalia's `PowerProfileService.qml`
reaches through `Quickshell.Services.UPower`.

```sh
paru -S tlp-pd                                    # replaces power-profiles-daemon
sudo install -Dm644 meta/system/tlp.d/10-local.conf /etc/tlp.d/10-local.conf
sudo systemctl enable --now tlp.service tlp-pd.service
tlp-stat -s                                       # expect no conflict warning
```

Swapping in place, rather than installing fresh, needs one extra step first.
Removing the `power-profiles-daemon` package does not stop its running daemon,
and that process keeps ownership of both bus names. `tlp-pd.service` is
`Type=dbus`, so it waits for names it can never get and systemd kills it at the
15s timeout, on a restart loop — while `tlp-pd`'s own log looks perfectly
healthy right up to "Initial profile". Stop the orphan before starting tlp-pd:

```sh
sudo systemctl stop power-profiles-daemon.service || sudo pkill -f power-profiles-daemon
busctl --system list | grep PowerProfiles   # should name tlp-pd, not power-profiles-
```

The unit file is gone by then, so systemd reports it `LoadState=not-found` while
still `ActiveState=active`; `stop` may refuse it and the `pkill` fallback is
what does the work. A reboot achieves the same thing.

The drop-in holds the only three settings this machine changes from TLP's
defaults: `SOUND_POWER_SAVE_ON_AC=0` stops the HDA codec sleeping on AC and
popping at the start of playback, `USB_AUTOSUSPEND=0` stops USB devices being
suspended out from under you (USB Bluetooth radios included), and
`WIFI_PWR_ON_BAT=off` stops wifi power saving on battery, which TLP enables by
default and which adds latency and stalls long-lived connections — see the lock
section below for why that matters here. TLP sets no `DEVICES_TO_DISABLE_*`
rules, so wifi and Bluetooth are never rfkill'd out from under the session.
It is a drop-in rather than an edit to
`/etc/tlp.conf` because tlp.conf is a pacman backup file and editing it earns a
`.pacnew` on every update; `/etc/tlp.d/README` names this as the intended path.
`tlpui` is installed for editing it. Note tlp.conf overrides the directory, so
the settings must not be set in both.

The CLI is `tlpctl`. `powerprofilesctl` does not exist under this setup —
anything scripted against it needs changing. To go back, `paru -S
power-profiles-daemon` removes `tlp-pd` by conflict; disable `tlp.service`
afterwards or the two will fight over the governor.

**logind lid handling.** Lid events belong to niri here, not logind, so every
`HandleLidSwitch*` is set to `ignore`. The reasoning is in the lock section
below.

```sh
sudo install -Dm644 meta/system/logind.conf.d/10-lid.conf \
  /etc/systemd/logind.conf.d/10-lid.conf
sudo systemctl restart systemd-logind    # ends the graphical session
```

Restarting logind kills the session, so a reboot or a logout/login is the
gentler way to pick it up. Drop-ins override the same keys in
`/etc/systemd/logind.conf` and survive updates that rewrite it.

**OOM protection and hibernation.** Two more drop-ins, covered in the memory
and sleep sections below.

```sh
sudo install -Dm644 meta/system/oomd.conf.d/10-pressure.conf \
  /etc/systemd/oomd.conf.d/10-pressure.conf
sudo install -Dm644 meta/system/sleep.conf.d/10-hibernate.conf \
  /etc/systemd/sleep.conf.d/10-hibernate.conf
sudo systemctl restart systemd-oomd
```

**Enabled systemd units.** Recorded in `meta/systemd-user-units.txt` and
`meta/systemd-system-units.txt`; see the fresh-machine steps above. The system
list is deliberately not a full inventory — around thirty units are enabled on
this machine and only the ones something tracked here depends on are listed.

There are no custom systemd unit *files*. `~/.config/systemd/user/` holds the
enable-symlinks `systemctl --user enable` creates plus one drop-in,
`app.slice.d/10-oomd.conf` from the `systemd` package in `common/`; everything
in `/etc/systemd/system/` is package-owned apart from the drop-in above.

That drop-in is the reason `bootstrap.sh` pre-creates `*.d` directories under
`.config/systemd` before stowing. systemd ignores a drop-in directory that is
a symlink, and stow folds a directory the target does not have yet into a
single link — so the file would be linked correctly, load never, and give no
error. Check with `systemctl --user show app.slice -p DropInPaths`: an empty
value means it folded.

## Lock, lid and idle

Locking and suspending are deliberately separate here. Closing the lid or
walking away locks the screen and nothing else — builds, downloads, music, SSH
sessions and containers all keep running. The machine only truly suspends when
staying awake would flatten a battery.

| Trigger | On mains | On battery |
| --- | --- | --- |
| Lid closed | lock, stay running | lock, then sleep after 10 min |
| Lid closed, battery ≤ 20% | — | lock and sleep immediately |
| Lid closed, external display | nothing — keep working | nothing — keep working |
| Idle 10 min | screens off | screens off |
| Idle 11 min | lock | lock |
| Idle 30 min | stay running | lock and sleep |

"Sleep" means `suspend-then-hibernate`: suspend to RAM, then hibernate ninety
minutes later if it is still asleep, so a bag overnight does not come out flat.
`meta/system/sleep.conf.d/10-hibernate.conf` sets the delay and stops a machine
on mains hibernating on its own. The script falls back to a plain suspend if
hibernation is unavailable, so this degrades rather than breaks. Hibernation
needs no extra setup here — `resume=UUID=...` is already on the kernel cmdline
against a 20G swap partition, and logind reports `CanSuspendThenHibernate=yes`
— but it is worth trying `systemctl hibernate` by hand once, since zram runs
near full on this machine and its pages go into the image too.

Three pieces cooperate:

**`meta/system/logind.conf.d/10-lid.conf`** takes logind out of the picture.
The obvious `HandleLidSwitch=lock` does not work: noctalia has no logind
integration at all — nothing in the shell listens for
`org.freedesktop.login1`'s `Lock` signal — so logind would blank the display
and leave the session unlocked behind it. Every `HandleLidSwitch*` is therefore
`ignore`.

**`desktop/niri/.config/niri/cfg/lid.kdl`** handles the lid instead, through
niri's `switch-events`. `lid-close` and `lid-open` both call the script below;
reopening the lid cancels a pending suspend.

**`common/bin/.local/bin/niri-power-action`** decides what a lid close or an
idle timeout should actually do, since that depends on power state. Its two
tunables sit at the top of the file: `CRITICAL_PCT=20` and `LID_GRACE=600`.
The scheduled suspend re-checks both the lid and the power state when it fires,
so a missed `lid-open` event cannot suspend a machine that is open and in use.

### Multiple monitors

Locking is safe across outputs by construction: `WlSessionLock` puts a surface
on every output and the protocol will not accept input until each one has one,
so a second screen cannot be left showing the desktop. `lockScreenMonitors` is
empty, which gives every screen the full lock UI; naming monitors there gives
the unlisted ones a black screen instead. Screen-off and screen-on go through
niri and cover every output too.

Closing the lid with an external display attached does nothing at all — no
lock, no suspend — so the laptop can sit shut on a desk driving an external
screen. niri turns the laptop panel itself off, and knows the lid is shut from
logind's `LidClosed` property, which `HandleLidSwitch=ignore` does not affect:
`ignore` suppresses logind's *action*, not the property. Detection reads DRM
sysfs (`/sys/class/drm/*/status`, skipping `eDP`/`LVDS`/`DSI`) rather than
`niri msg`, so it needs no JSON parser and holds up if the compositor is busy.

Walking away while docked is still covered — the idle stages lock at eleven
minutes whatever the lid is doing. The one gap worth knowing: undocking while
the lid is already shut leaves the session unlocked, because the lid-close that
would have locked it was suppressed as clamshell. The idle stages catch it
eleven minutes later.

The idle stages come from noctalia's own idle service, configured under `idle`
in `desktop/niri/.config/noctalia/settings.json`. Note `suspendTimeout` is `0`,
which disables the built-in suspend stage on purpose: noctalia's suspend stage
always calls `lockAndSuspend()` and its `suspendCommand` runs *in addition to*
that rather than instead of it, so it cannot be made conditional. The 30-minute
suspend is expressed as an `idle.customCommands` entry instead, which runs a
bare command with no built-in action attached.

Because the session now stays up with the lid shut, power saving that was
harmless when the machine suspended is not any more — hence `WIFI_PWR_ON_BAT`
and `USB_AUTOSUSPEND` being switched off in the TLP drop-in above. Wifi and
Bluetooth stay fully connected while locked.

The lock screen itself is noctalia's, tuned for as little friction as possible:
`autoStartAuth` so the password field is live the moment it appears and there is
nothing to click first, `lockScreenAnimations` for a fade rather than a hard
cut, `lockScreenBlur` and `lockScreenTint` for a blurred and dimmed wallpaper,
and `enableLockScreenMediaControls` so what is playing stays controllable.
`allowPasswordWithFprintd` is left off — no fingerprint reader on this machine.
`Mod+Alt+L` locks on demand.

## Memory pressure

14G of RAM with zram on top is not much for this workload, and the machine runs
close to the edge: `/proc/pressure/memory` sits around `full avg300=7%`, meaning
roughly seven percent of any five minutes *every* task is stalled waiting on
memory. Without a userspace OOM killer the next spike is a hard freeze — the
kernel's own OOM killer only acts once an allocation actually fails, long after
the desktop has stopped responding.

`systemd-oomd` handles it, driven by `common/systemd`'s drop-in on `app.slice`.
The scoping is what makes this safe. niri runs in `session.slice` while the
user manager gives every app it launches its own scope under `app.slice`
(`app-niri-kitty-2970.scope`), so oomd can only ever choose an application —
it structurally cannot kill the compositor or log the session out. The same
per-app scoping is why oomd suits this setup better than `earlyoom`, which
picks a single process by score: oomd takes out one whole app cleanly.

The trigger is memory pressure, never swap usage. Swap-based killing is the
other common recipe and would be actively wrong here, because zram is meant to
sit near 100% — a swap threshold would fire constantly during normal use.

```sh
systemctl --user show app.slice -p DropInPaths -p ManagedOOMMemoryPressure
journalctl -u systemd-oomd            # what it killed, and why
```

## Gaming

The machine is hybrid — an AMD Vega iGPU and an RTX 3050 — and **Vulkan
enumerates the iGPU first**. Anything launched without PRIME offload therefore
renders on the Vega, silently and slowly. That is the problem
`common/bin/.local/bin/gamerun` exists to remove:

```
Steam launch options:   gamerun %command%
with gamescope:         gamerun gamescope -f -W 1920 -H 1080 --force-grab-cursor -- %command%
```

It composes `prime-run`, `gamemoderun` and `mangohud`, skipping any that are
not installed, and each can be dropped for a single launch with
`GAMERUN_PRIME=0`, `GAMERUN_GAMEMODE=0` or `GAMERUN_HUD=0`. The point is that
the environment lives in one place instead of being retyped per game and
drifting apart — which is exactly what had happened: of four games with launch
options set, only one carried PRIME offload.

Confirm it worked from the overlay. `gpu_name` is in the MangoHud config for
precisely this reason: if the corner says NVIDIA GeForce RTX 3050, the game is
on the right card. From a shell:

```sh
gamerun vulkaninfo --summary | grep -m1 deviceName   # expect NVIDIA
```

`common/env/.config/environment.d/path.conf` is what lets Steam find `gamerun`
by name. Shell rc files are no help — nothing launched from the compositor
sources them — and a missing `~/.local/bin` on the session PATH means the game
simply does not start.

### Steam launch options

Steam keeps these in `localconfig.vdf`, which it rewrites constantly and fills
with unrelated state, so it is not tracked here. Recorded instead, to be put
back by hand after a reinstall. **Steam must be closed while editing that file
or it overwrites the change on exit.**

| Game | Launch options |
| --- | --- |
| THE FINALS | `VKD3D_CONFIG=no_upload_hvv gamescope -w 1920 -h 1080 -W 1920 -H 1080 -f -s 1.8 --force-grab-cursor --backend=wayland -- gamerun %command%` |
| War Robots | `DXVK_ASYNC=1 SDL_MOUSE_RELATIVE_SPEED_SCALE=1.0 gamescope -f -w 1920 -h 1080 -W 1920 -H 1080 --force-grab-cursor -- gamerun %command%` |
| anything else | `gamerun %command%` |

Note where `gamerun` sits relative to gamescope: **inside** it, after the `--`.
That leaves gamescope on the iGPU, which is what drives the display, and
offloads only the game to the RTX 3050 — the ordinary PRIME arrangement.
Wrapping gamescope itself works too and is the form `gamerun --help` describes,
but it makes gamescope render on NVIDIA and then present across to the iGPU,
which is the slower and more fragile path. Worth trying the other way round
only if a game misbehaves.

`gamemode` matters more here than on a desktop because TLP is the power manager
and is deliberately conservative; gamemode raises the governor for the session
and restores it after. Its one wrinkle is that TLP re-applies on a power-source
change, so plugging in mid-game resets the governor underneath it.

### VRR, and why it is not on-demand

The Acer is a 180Hz FreeSync panel and the laptop panel reports
`vrr_supported=false`, so VRR is set on the Acer only — in the **Monique
profile**, not in niri's config. Two findings forced that:

- niri does not merge two `output` blocks for the same display; the later one
  replaces the earlier wholesale. An output block in `cfg/display.kdl` carrying
  only a VRR line moved the laptop panel from Monique's `x=2409 y=-84` to
  `x=0 y=0`. Since Monique owns `monitors.kdl` and it is included last, any
  per-output setting has to go through Monique or be destroyed by it.
- Monique models on-demand VRR (`VRR.FULLSCREEN = 2`) but its niri backend
  emits a bare `variable-refresh-rate` for any non-off value
  (`models.py:339`), so **the Acer runs VRR full time**, not only for games.

Always-on VRR makes some panels flicker in brightness at idle. If that shows
up, set `vrr` back to `0` in the profile. The `variable-refresh-rate` window
rule for games in `cfg/rules.kdl` is inert until Monique emits on-demand, and
is there so this starts behaving correctly when it does.

### Dual monitor

Games open on the Acer via `open-on-output` in `cfg/rules.kdl`, matching both
`steam_app_*` and gamescope windows; niri falls back to the focused output when
it is not connected, so it is safe undocked.

`focus-follows-mouse` is capped with `max-scroll-amount="0%"`. Without the cap,
nudging the pointer toward the second screen can pull focus off a game that has
not grabbed the cursor, taking keyboard input with it. gamescope's
`--force-grab-cursor` already covers wrapped launches; the cap is for the rest.

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
