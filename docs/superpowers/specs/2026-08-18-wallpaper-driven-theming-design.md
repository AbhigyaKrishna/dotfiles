# Wallpaper-driven theming via Noctalia templates — design

**Date:** 2026-08-18
**Status:** Approved, pending implementation plan
**Scope:** Make kitty, alacritty, btop, GTK (3 + 4), VSCode Insiders, and
zen-browser recolor from the current wallpaper, driven by Noctalia's built-in
template engine. The static `adw-dark` base theme is retained, not replaced.

---

## Problem

Noctalia already generates a colour palette from the wallpaper
(`colorSchemes.useWallpaperColors: true`, `generationMethod: "content"`) and
uses it for its own bar and panels. But `templates.enableUserTheming` is
`false` and `templates.activeTemplates` is empty, so nothing outside the shell
follows the wallpaper. Terminals, editor, browser and GTK apps stay on the
static `theme/adw-dark` look regardless of what is on screen.

The result is a desktop that is only half-themed: the shell shifts with the
wallpaper, everything the user actually works in does not.

## Goal

Turn on Noctalia's template engine for the full app stack on this machine so a
wallpaper change propagates to every surface, while keeping the change
reproducible and low-churn in a public dotfiles repo.

Non-goals:
- Replacing `adw-dark`. It stays as the structural GTK/Qt base.
- Introducing `matugen` or any external colour generator. Noctalia has its own
  `TemplateProcessor` and needs nothing added.
- Theming apps not in daily use here (foot, ghostty, wezterm, helix, emacs,
  etc.), even though Noctalia ships templates for them.

---

## Architecture: two layers

**Static base (unchanged).** `theme/adw-dark` continues to own the structural
theme: `gtk-3.0/settings.ini` and `gtk-4.0/settings.ini` select
`adw-gtk3-dark` and set the font and cursor; `qt5ct`, `Kvantum`, `xsettingsd`,
`nwg-look` are untouched. None of these files are edited by this work.

**Dynamic tint (new).** Noctalia renders each active template against the
wallpaper-derived palette and writes a per-app colour file to that app's config
tree, then runs a post-hook that live-reloads the app. For GTK this is a
`gtk.css` full of libadwaita `@define-color` overrides
(`accent_color`, `window_bg_color`, `headerbar_bg_color`, …) that **tint the
adw-gtk3-dark base** rather than replace it. The two layers compose: `adw-dark`
provides structure, Noctalia provides colour.

**Data flow:**

```
wallpaper change
  → Noctalia colour generation (content method; already enabled)
  → TemplateProcessor renders each active template with the palette
  → writes <app colour file> to the app's config dir
  → postHook (Assets/Scripts/bash/template-apply.sh <app>) live-reloads the app
```

---

## Components

### 1. Noctalia configuration (tracked)

File: `desktop/niri/.config/noctalia/settings.json` (stowed, so tracked).

- `templates.enableUserTheming`: `false` → `true`
- `templates.activeTemplates`: `[]` → six target objects of the shape
  `{"id": "<id>", "enabled": true}`, one per id:
  `kitty`, `alacritty`, `btop`, `gtk`, `code`, `zenBrowser`.
  (GTK is a single `gtk` template that emits both GTK3 and GTK4 outputs — not
  two ids. Confirmed against `TemplateRegistry.qml` and the array shape used by
  `TemplatesSubTab.qml`/`TemplateProcessor.qml`.)

`colorSchemes.useWallpaperColors` and `generationMethod: "content"` are already
set and need no change.

> Implementation note: `activeTemplates` entries must match the `id` values in
> `/etc/xdg/quickshell/noctalia-shell/Services/Theming/TemplateRegistry.qml`.
> The ids for VSCode and zen are `code` and `zenBrowser` (camelCase) — confirm
> each id against the registry before writing, since a typo silently drops the
> target rather than erroring.

### 2. App wiring (tracked, in stow)

Each app must be told to consume the file Noctalia will write. These edits are
dotfiles and belong in their stow packages.

Registry inspection changed two of these from what was first assumed — kitty
and GTK are self-wiring through their post-hooks and need **no** config edit;
their cost is instead untracking generated files (see §3).

| App | File / action | Edit |
|---|---|---|
| kitty | none (self-wiring) | The `kitty` post-hook does `ln -sf themes/noctalia.conf ~/.config/kitty/current-theme.conf`, and `kitty.conf` already has `include current-theme.conf`. No edit. But `current-theme.conf` and `themes/noctalia.conf` are **currently tracked** and must be untracked + gitignored (§3). |
| alacritty | `common/terminals/.config/alacritty/alacritty.toml` | Under the existing `[general]` (has `live_config_reload = true`), add `import = ["~/.config/alacritty/themes/noctalia.toml"]`. Live reload is already on, so it retints without restart. |
| btop | `common/cli/.config/btop/btop.conf` | `color_theme = "Default"` → `color_theme = "noctalia"` (the btop output is `~/.config/btop/themes/noctalia.theme`; btop names themes by filename stem). |
| gtk | none (self-wiring) | The `gtk` template writes `~/.config/gtk-{3,4}.0/noctalia.css`; its post-hook `gtk-refresh.py` auto-creates `gtk.css` with `@import url("noctalia.css")` and syncs the gsettings colour-scheme. No edit — but the created `gtk.css` and `noctalia.css` land in the stow-folded repo dirs and must be gitignored (§3). `settings.ini` still selects the adw-gtk3-dark base. |
| VSCode Insiders | extension + symlink bridge | The `code` template writes to `~/.vscode/extensions/noctalia.noctaliatheme-0.0.5/…`, but Insiders reads `~/.vscode-insiders/extensions/`. Install the extension in Insiders, symlink `~/.vscode/extensions/noctalia.noctaliatheme-0.0.5` → the Insiders copy so noctalia's write resolves, and set `workbench.colorTheme: "NoctaliaTheme"` in Insiders settings. |
| zen | one pref (rest is automatic) | The `zenBrowser` post-hook **auto-injects** the `@import` lines into every `~/.zen/*/chrome/userChrome.css` and writes the CSS under `~/.cache/noctalia/` (outside the repo). The only manual step is enabling `toolkit.legacyUserProfileCustomizations.stylesheets = true` in the profile. |

### 3. Generated output (gitignored, NOT tracked)

Noctalia's output paths point *into* directories that stow has folded into repo
symlinks — e.g. `~/.config/kitty` → `common/terminals/.config/kitty`,
`~/.config/gtk-3.0` → `theme/adw-dark/.config/gtk-3.0`. A file written there
lands **inside the repo working tree**. This is the same mechanism the existing
`.gitignore` already handles for `gtk-3.0/bookmarks`, and it must be handled the
same way here or every wallpaper change dirties the tree.

Add a new `.gitignore` section covering the generated colour files, and
`git rm --cached` the two kitty files that are already committed:

- `**/kitty/themes/noctalia.conf` (currently tracked — untrack)
- `**/kitty/current-theme.conf` (currently tracked — untrack; the hook turns it
  into a symlink)
- `**/alacritty/themes/noctalia.toml`
- `**/btop/themes/noctalia.theme`
- `**/gtk-3.0/noctalia.css` and `**/gtk-3.0/gtk.css`
- `**/gtk-4.0/noctalia.css` and `**/gtk-4.0/gtk.css`

zen and VSCode need **no** gitignore entries: zen writes to `~/.cache/noctalia/`
and injects into the (untracked) zen profile, and VSCode writes into
`~/.vscode-insiders/extensions/` (also untracked). Only kitty, alacritty, btop
and gtk write through stow-folded symlinks into the repo.

Rationale: these are high-churn derived state regenerated on every wallpaper
change, exactly the category the `.gitignore` "Churn that stow folding can drag
in" section already excludes. `monitors.kdl` is tracked because it is
*low*-churn (changes only when monitors change); these are the opposite case.

### 4. Fresh-machine / fallback behaviour

No seed colour files are committed — committing them would reintroduce the
churn the gitignore is there to prevent, and they would be stale on any machine
with a different wallpaper. On a fresh machine, before Noctalia's first render:

- kitty: `include` of a missing file → warning, continues with built-in colours.
- alacritty: missing `import` → warning, continues.
- btop: unknown `color_theme` → falls back to a default theme.
- GTK: no `gtk.css` yet → adw-gtk3-dark shows untinted.

Noctalia applies templates on shell startup (the shell autostarts from
`niri/cfg/autostart.kdl`), so the gap is roughly the first couple of seconds of
the first login and then self-corrects. Acceptable; no seeding needed.

### 5. Reload

Each target's `postHook` runs `template-apply.sh <app>` for a live reload
(kitty via `kitten @ set-colors` / socket, etc.). GTK apps pick up colours on
next start or via the gsettings sync Noctalia already does
(`colorSchemes.syncGsettings: true`). No additional reload wiring is needed.

---

## Risks and documented caveats

These must be written into comments beside the relevant edits and/or the README
theming section, not just this spec.

1. **kitty `kitten themes` collision.** The `BEGIN_KITTY_THEME`/`END_KITTY_THEME`
   block is owned by kitty's theme kitten; running `kitten themes` again would
   overwrite our manual `include`. Document that theme selection is now
   Noctalia's job and `kitten themes` should not be used on this machine.
2. **zen userChrome fragility.** `userChrome.css` theming can break across zen
   updates and depends on a non-default pref. Treat as best-effort; document how
   to re-enable after a zen upgrade resets prefs.
3. **VSCode extension dependency.** The `code` target is inert without the
   Noctalia colour-theme extension installed and selected. If the extension is
   used, it should also be recorded (the extension id, and — if it is packaged —
   possibly `meta/packages.txt`), consistent with the repo's "record what the
   config depends on" rule.
4. **Stow-folding write-through.** Covered by the gitignore section above;
   called out here so it is not lost — the generated files write through folded
   symlinks into the repo, and the gitignore entries are what keep the tree
   clean.

## Open items to resolve during implementation (not assumptions)

Most of the original open items were resolved by registry inspection and are
now baked into the tables above (ids, btop path/name, gtk output filenames,
zen auto-wiring, the VSCode path mismatch). What remains genuinely unverified:

- Whether the `noctalia.noctaliatheme` extension installs cleanly into VSCode
  Insiders from the marketplace, or needs a manual VSIX. If neither works, the
  `code` target is dropped without affecting the other five — this is the one
  target allowed to fail gracefully.
- The exact zen profile directory on this machine (`~/.zen/<profile>/`) and that
  the pref flip survives a zen restart. zen remains best-effort per §Risks.

## Success criteria

- Changing the wallpaper visibly recolours kitty, alacritty, btop, GTK app
  windows, VSCode Insiders, and zen without any manual step.
- `git status` is clean after a wallpaper change (no generated files show up).
- A rebuild from this repo (`install-packages.sh` + `bootstrap.sh`) plus a first
  login produces the themed result with no missing-file breakage beyond the
  brief first-login gap.
- `adw-dark` still provides the base GTK/Qt theme; disabling `enableUserTheming`
  cleanly reverts every app to the static adw-dark look.
