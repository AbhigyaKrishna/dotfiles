# Desktop themes

Open Noctalia's launcher and type **`/profile`**, or select **Desktop Profiles**
from its provider list. **Super+Shift+T** and `desktop-theme` open that same
native provider. A profile owns the complete desktop experience: Niri keybindings,
window layout/rules and animations, the entire Noctalia shell, desktop widgets,
fonts, icons, colors and application styling. Light/dark mode is a separate
choice inside the active theme.

```sh
desktop-theme             # Noctalia /profile provider
desktop-theme glyph       # apply Glyph, or resume its saved settings
desktop-theme original    # return to the desktop saved before the first switch
desktop-theme status
```

`common/appearance` is installed by the `niri` profile. To install just the new
package into an existing setup:

```sh
stow -d common -t "$HOME" appearance
fc-cache -f "$HOME/.local/share/fonts"
systemctl --user restart noctalia.service  # refresh the shell's font cache
```

Python runs the profile backend; the selection UI is a native Noctalia launcher
provider. Noctalia's Settings window
provides settings for its appearance, bar, panels, launcher, dock, wallpaper,
desktop widgets, notifications, OSD, security, power, plugins and app templates.
Use `nwg-look` for GTK fonts, icons and cursors, and `qt5ct` / `kvantummanager`
for Qt appearance. Monitor layout remains shared between themes.

Edit the active theme's Niri bindings with
`xdg-open ~/.config/niri/cfg/keybinds.kdl`. Noctalia's **Settings → Keybinds**
controls shell keyboard navigation. Switching profiles switches both sets.
`Super+Shift+T` opens `/profile` in both bundled themes, and `Super+Shift+Escape` shows the active Niri
shortcut overlay.

## Glyph

Glyph adapts [Nebelung-cloud/glyph-rice](https://github.com/Nebelung-cloud/glyph-rice)
to the existing **Niri + native Noctalia v5** desktop. It has monochrome surfaces,
white focus accents, red activity/error accents, and a dot-grid wallpaper.
The shell and GTK/Qt interface use **Glyph UI**, a mixed font family: regular
and medium text use **Space Grotesk**, while semibold and bold headings and
labels use **Glyph Dots**. This gives Noctalia's headers the dot-matrix look
without making descriptions and editable text dotted. Large desktop clock,
date and weather text, short bar labels and the power menu use **Glyph Dots**
directly. Media titles and active-window titles retain **Space Grotesk**;
terminals use **Space Mono**.
Native desktop widgets show the
date, weather, active media and CPU activity/temperature. First-use placement
uses each connected output's logical dimensions; use **Noctalia Settings →
Desktop → Toggle Editor** to move/resize widgets and add them to new monitors.

Its shell is independent of the outgoing theme: a vertical left sidebar with
its own widgets, a list launcher, floating quick settings, compact window
previews, no bottom dock, larger rounded panels, ten-pixel window gaps and
short eased animations. The original theme restores its own shell arrangement,
shortcuts, sixteen-pixel gaps and spring animations.

Glyph starts with the original profile's complete keybinding file and shell
keyboard controls. Its session-menu shortcut and physical power button open
Glyph Power; the other bindings retain Original's behavior. Each profile owns
its copy so its shortcuts can be customized independently later.

Glyph also copies Original's complete power-action menu and numeric shortcuts:
**1** Lock, **2** Lock and Suspend, **3** Hibernate, **4** Reboot, **5** Logout,
**6** Shutdown, and **7** Reboot to UEFI. Lock is immediate; the other actions
retain Original's ten-second countdowns. Edit them in **Noctalia Settings →
Shell → Session**; each profile saves its own actions.

**Glyph Power** (`dotfiles/glyph-power:menu`) is a native Noctalia plugin overlay
inspired by the upstream screenshot: a black surface, large dot-matrix action
names, a red selection dot and a dotted circle showing live uptime and the real
Niri window count. `Super+Shift+Q`, the physical power button and Glyph's bar
session button and the Control Center's **Power** tile open it. Arrow keys,
J/K or mouse hover select with the same
easing animation; Enter/Space or clicking confirms. Hover alone never runs an action;
the original numeric shortcuts still work. Actions stay in their imported order.
Selection eases over 240 ms: the new row and its text expand while the previous
row contracts, smoothly moving neighboring options to make space. Brightness
and the red selection dot fade with the same transition. Rapid navigation
retargets the animation from its current position, and frame ticks stop at rest.
During resizing, a tiny group-opacity variation forces a full repaint to work
around Noctalia's partial-redraw artifacts; full opacity is restored at rest.
Moving selection or closing the panel
cancels a countdown. Confirming a pending action again executes it immediately,
matching Noctalia's original behavior. Actions are read from the effective
`shell.session.actions` on every open, so GUI edits apply to both presentations.
The visual surface uses Noctalia v5.4's layer API (plugin API 36), spans the
whole focused output, and ignores reserved bar space. It has no frame, margins,
shadow or rounded corners. A Glyph-only Niri layer rule blurs the desktop behind
its translucent black background. Noctalia v5.4 layers do not deliver raw key
callbacks, so a one-pixel keyboard controller behind the visual layer keeps
Escape, arrows and numeric shortcuts working. Closing the controller tears down
the visual layer and cancels any pending countdown.
Noctalia hard-codes its Control Center header power icon to the built-in session
panel, so Glyph hides that icon and uses `dotfiles/glyph-power:power` in the
shortcut grid instead. It replaces the power-profile shortcut; profile selection
remains available in the **Power** tab. Noctalia's built-in session panel remains
available through its launcher button and explicit `panel-toggle session` IPC.

Glyph's sidebar launcher and `/profile` entry use a local Nothing-inspired
dot-matrix **N** with one red dot. Application, folder and toolkit icons use
**YAMIS**, a monochrome Linux icon theme by DIRN, selected for Noctalia, GTK 2/3/4
and Qt 5/6. The Android Nothing Icon Pack requires Nothing Launcher; YAMIS is the
Linux adaptation used here. Noctalia also desaturates and tints app icons live
using `shell.app_icon_colorize = true` and `shell.app_icon_color = "on_surface"`.
This covers launcher, dock, taskbar, active-window and tray app icons, including
fallback icons and newly installed apps. It follows light/dark palette changes
immediately. Toggle it in **Settings → Appearance → Interface**. Glyph saves
the setting independently of Original.

Live colorization affects Noctalia's icons. Inside other applications, YAMIS and
its inherited themes still apply; some applications cache those icons and need
reopening after a switch.

The unmodified YAMIS archive (including GPL-3.0 license) is bundled at
`presets/glyph/yamis.tar.gz` from
[googIyEYES/YAMIS](https://github.com/googIyEYES/YAMIS) commit
`24c02f6bb7bcd356e49df22f6942b078b66700fd`, SHA-256
`3413d300ce9ccfcc56805e2d44be702c00606fea1964abf5adbd12f7469d826b`.
The first Glyph setup installs it under `$XDG_DATA_HOME/icons/YAMIS` (default
`~/.local/share/icons/YAMIS`); switching profiles restores their saved icon
preferences. Existing installed YAMIS artwork is preserved. The `nothing.svg`
mark is drawn here, inspired by Nothing's typography; it is not an official logo.

| Action | Both profiles |
| --- | --- |
| App launcher | `Super+Space` |
| Window search | `Super+Shift+Tab` |
| Profile switcher | `Super+Shift+T` |
| Clipboard history | `Super+V` |
| Session menu | `Super+Shift+Q` |
| All active shortcuts | `Super+Shift+Escape` |

Dark and light palette variants include readable ANSI colors. Noctalia templates
apply the palette to GTK 3/4, Qt palettes, Niri focus/borders, Kitty, Alacritty and
Btop. GTK/XSETTINGS preferences and Qt's Fusion palette are synchronized. The
wallpaper is deliberately dark in both modes; change it in Noctalia Settings.
Use **Appearance → App Theming** / templates for additional supported apps.
Applications that implement their own theme systems still need their own
integration; this preset does not install browser, editor or website extensions.

The original Glyph is a custom Hyprland/Quickshell shell. Its edge-light OSD,
Nothing earbud controls and custom dashboard are not ported here; Noctalia's
native rendering and services remain in use. Each theme owns its shell settings,
plugin selection and keybindings. Glyph's sidebar uses built-in widgets;
the original restores its plugin widgets. Plugin content, notes and clipboard
history remain shared. The existing lock/idle policy is also declared in Glyph.

`dotfiles/desktop-profiles` is kept enabled in every profile so `/profile` stays
available after a switch, including when loading older saved profiles. The local
plugin lives under `common/appearance/.local/share/noctalia/plugins/desktop-profiles/`.
It lists actual backend profiles, marks the active one, and supports fuzzy search.
Selecting a row starts the switch outside the provider VM, so it survives shell
reloads; completion and failures are reported through Noctalia notifications.

The Glyph definition lives under
`common/appearance/.local/share/desktop-themes/presets/glyph/`:

- `theme.toml`: identity, revision and shortcut guide.
- `noctalia.toml`: complete shell definition, resolved against native defaults.
- `desktop.json`: widget types, settings and relative positions.
- `niri/cfg/`: keybindings, window layout/rules and animation profile.
- `Glyph.json`, `wallpaper.svg`, `kitty.conf`: palette and application assets.

Glyph never merges the outgoing theme's Noctalia configuration or GUI overrides.
The original theme is a private full capture of the desktop already installed.

The original font files are unmodified copies from Glyph at
`39a2a097300bd41e2927706e85bac0f9f8d57d8b`, distributed under the included
[SIL OFL](../common/appearance/.local/share/fonts/glyph/OFL.txt). `Glyph Dots` is
a renamed static Doto instance (`ROND=100`, `wght=700`) so Noctalia renders round
dots without variable-axis support. Rebuild it with
`python meta/fonts/build-glyph-dots.py` when fontTools is installed, then run
`python meta/fonts/build-glyph-ui.py` to rebuild the mixed family's four faces.
Its regular/medium faces retain Space Grotesk's outlines; its semibold/bold
faces retain Glyph Dots' outlines. Copyright and OFL metadata are preserved,
with the separate Space Grotesk OFL included next to the fonts. The preset,
wallpaper and switcher are implemented here; upstream's installer and shell
code are not used.

## Persistence and recovery

Snapshots live privately in `~/.local/state/desktop-themes/` (honoring
`XDG_STATE_HOME`). The first switch saves your original settings, generated
shell configuration files, Niri configuration/shortcuts, application appearance
files, their original Stow symlinks, and GNOME appearance preferences.
Every later switch saves the outgoing preset, so GUI edits survive a round trip.
Noctalia's complete declarative TOML layer and GUI-owned `settings.toml` are
part of each snapshot. GUI font and Qt-style changes are preserved across mode
changes too. Plugin data, notes,
calendar caches and clipboard history stay in their existing locations.

While Glyph is active, managed appearance files and folded Stow directories
are materialized locally before template hooks run. Tracked source files stay
untouched. Hardware output geometry, input/lid policy and startup services stay
shared. Return to **Your original** before running `bootstrap.sh` or Stow
again; that restores the original links and avoids conflicts with these local
working copies. Snapshots are machine-specific and should not be committed.

Switching validates both Noctalia and Niri, including the target keybindings,
and waits for Noctalia's `colors_changed` hook
to acknowledge completed template work. An error restores the outgoing snapshot
and reports the failure. Concurrent switches are rejected. If Noctalia is down,
the switcher reports that before changing appearance files. Start
`noctalia.service` and retry. If recovery itself fails, the error names the
retained backup; do not delete the snapshot directory.

Revision 2 upgrades the earlier appearance-only Glyph preset. Its old saved
settings are retained as `glyph-v1.json` before installing the full desktop
profile. Later GUI edits belong to revision 2 and survive theme switches.

The old `GTK_THEME=adw-gtk3-dark` export is removed so apps can follow light/dark
mode. An existing login session may still carry it: log out and back in once,
then reopen apps that cache toolkit settings. Most terminal/shell colors update
live; some GTK/Qt applications need reopening.

## Verification

```sh
python -m unittest discover -s tests -v
ruff check common/appearance
ruff format --check common/appearance
noctalia config validate
niri validate
noctalia plugins lint common/appearance/.local/share/noctalia/plugins/desktop-profiles
lua tests/test_profile_provider.lua common/appearance/.local/share/noctalia/plugins/desktop-profiles/profiles.luau
noctalia plugins lint common/appearance/.local/share/noctalia/plugins/glyph-power
lua tests/test_glyph_power.lua common/appearance/.local/share/noctalia/plugins/glyph-power
```

Regression checks run in temporary homes and cover symlink preservation,
generated-file cleanup, private backup permissions, failed-apply rollback,
unavailable shells, concurrency, template completion, full-shell and keybinding
isolation, legacy profile upgrades and per-theme GUI edits.
