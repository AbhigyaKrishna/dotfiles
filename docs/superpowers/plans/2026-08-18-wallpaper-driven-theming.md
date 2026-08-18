# Wallpaper-Driven Theming Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make kitty, alacritty, btop, GTK (3+4), VSCode Insiders, and zen-browser recolour from the current wallpaper via Noctalia's built-in template engine, while keeping the repo clean and `adw-dark` as the base theme.

**Architecture:** Two layers. `adw-dark` stays the static structural base (GTK/Qt theme selection, fonts, cursor). Noctalia renders per-app colour files from the wallpaper palette on every change and live-reloads each app. kitty and GTK self-wire through post-hooks; alacritty and btop need one config line each; VSCode needs an extension + symlink bridge; zen needs one pref flip and auto-wires the rest. Generated files that land in stow-folded repo dirs are gitignored.

**Tech Stack:** Noctalia-shell (Quickshell) template engine, GNU Stow, git, kitty/alacritty/btop configs, VSCode Insiders, zen-browser userChrome.

**Design source:** `docs/superpowers/specs/2026-08-18-wallpaper-driven-theming-design.md`

---

## Testing note (this is a config repo, not an app)

There are no unit tests. Each task's "test" is a **verification command with expected output** — a grep of the resulting config state, a check that a generated file appeared, or `git status` staying clean. The observable colour change is confirmed visually by the user at the end (Task 8). "Fails first" is shown by running the verification *before* the change and seeing the old/absent state.

Throughout, this IPC forces a regeneration without waiting for a wallpaper change:

```bash
qs -c noctalia-shell ipc call theme generate 2>/dev/null \
  || qs -c noctalia-shell ipc call colorScheme generate 2>/dev/null \
  || echo "IPC name differs — toggle any template in Settings→ColorScheme→Templates to force AppThemeService.generate()"
```

> The exact IPC verb may differ by Noctalia version. If both calls fail, the Settings UI toggle in Task 4 already triggers `AppThemeService.generate()`, so generation can always be forced that way.

---

## File Structure

**Tracked edits (in stow packages):**
- `.gitignore` — new section ignoring generated theme outputs
- `common/terminals/.config/alacritty/alacritty.toml` — add `import`
- `common/cli/.config/btop/btop.conf` — change `color_theme`
- `desktop/niri/.config/noctalia/settings.json` — `enableUserTheming` + `activeTemplates`
- `README.md` — theming section: document the two-layer model and caveats

**Untracked (git rm --cached), then gitignored:**
- `common/terminals/.config/kitty/current-theme.conf`
- `common/terminals/.config/kitty/themes/noctalia.conf`

**Manual / non-stow (documented, per-machine):**
- VSCode Insiders: extension install + symlink bridge + `workbench.colorTheme`
- zen: `toolkit.legacyUserProfileCustomizations.stylesheets = true`

---

## Task 1: Gitignore generated outputs and untrack the kitty files

Do this first: once templating is enabled, these files regenerate on every wallpaper change, and if they are tracked (kitty's two already are) they dirty the tree through stow-folded symlinks.

**Files:**
- Modify: `.gitignore`
- Untrack: `common/terminals/.config/kitty/current-theme.conf`, `common/terminals/.config/kitty/themes/noctalia.conf`

- [ ] **Step 1: Verify the current (dirty) state — kitty files are tracked**

Run:
```bash
git ls-files common/terminals/.config/kitty/ | grep -E 'current-theme|themes/noctalia'
```
Expected: BOTH files listed (this is the state we're removing):
```
common/terminals/.config/kitty/current-theme.conf
common/terminals/.config/kitty/themes/noctalia.conf
```

- [ ] **Step 2: Add the gitignore section**

Append to `.gitignore` (after the existing "Churn that stow folding can drag in" block is the natural home, but end-of-file is fine):
```gitignore
# ---------------------------------------------------------------------------
# Wallpaper-driven theme output (Noctalia template engine).
# These regenerate on every wallpaper change and are written THROUGH stow-folded
# symlinks into the repo (e.g. ~/.config/gtk-3.0 -> theme/adw-dark/.config/gtk-3.0).
# Derived state, not dotfiles — see docs/superpowers/specs/2026-08-18-wallpaper-driven-theming-design.md
# ---------------------------------------------------------------------------
**/kitty/themes/noctalia.conf
**/kitty/current-theme.conf
**/alacritty/themes/noctalia.toml
**/btop/themes/noctalia.theme
**/gtk-3.0/noctalia.css
**/gtk-3.0/gtk.css
**/gtk-4.0/noctalia.css
**/gtk-4.0/gtk.css
```

- [ ] **Step 3: Untrack the two kitty files (keep them on disk)**

Run:
```bash
git rm --cached common/terminals/.config/kitty/current-theme.conf \
                common/terminals/.config/kitty/themes/noctalia.conf
```
Expected: `rm 'common/terminals/.config/kitty/current-theme.conf'` and the themes one.

- [ ] **Step 4: Verify they are now ignored and no longer tracked**

Run:
```bash
git ls-files common/terminals/.config/kitty/ | grep -E 'current-theme|themes/noctalia' || echo "UNTRACKED-OK"
git check-ignore common/terminals/.config/kitty/current-theme.conf common/terminals/.config/kitty/themes/noctalia.conf
```
Expected: first line prints `UNTRACKED-OK`; second prints both paths (confirming they match an ignore rule).

- [ ] **Step 5: Commit**

```bash
git add .gitignore common/terminals/.config/kitty/current-theme.conf common/terminals/.config/kitty/themes/noctalia.conf
git commit -m "theme: gitignore noctalia-generated theme files; untrack kitty's"
```

---

## Task 2: Wire alacritty to import the generated theme

**Files:**
- Modify: `common/terminals/.config/alacritty/alacritty.toml` (the `[general]` section, currently around line 162)

- [ ] **Step 1: Verify no import exists yet**

Run:
```bash
grep -n 'import' common/terminals/.config/alacritty/alacritty.toml || echo "NO-IMPORT-YET"
```
Expected: `NO-IMPORT-YET`.

- [ ] **Step 2: Add the import under [general]**

The section currently reads:
```toml
[general]
live_config_reload = true
working_directory = "None"
```
Change it to:
```toml
[general]
live_config_reload = true
working_directory = "None"
# Wallpaper-driven colours from Noctalia (regenerated file, gitignored).
# live_config_reload above means a wallpaper change retints without a restart.
import = ["~/.config/alacritty/themes/noctalia.toml"]
```

- [ ] **Step 3: Verify the import is present and TOML still parses**

Run:
```bash
grep -n 'import = \["~/.config/alacritty/themes/noctalia.toml"\]' common/terminals/.config/alacritty/alacritty.toml
python3 -c "import tomllib; tomllib.load(open('common/terminals/.config/alacritty/alacritty.toml','rb')); print('TOML-OK')"
```
Expected: the grep prints the line; then `TOML-OK`.

- [ ] **Step 4: Commit**

```bash
git add common/terminals/.config/alacritty/alacritty.toml
git commit -m "theme: import noctalia wallpaper colours into alacritty"
```

---

## Task 3: Point btop at the generated theme

**Files:**
- Modify: `common/cli/.config/btop/btop.conf` (line 5)

- [ ] **Step 1: Verify the current value**

Run:
```bash
grep -n '^color_theme' common/cli/.config/btop/btop.conf
```
Expected: `5:color_theme = "Default"`.

- [ ] **Step 2: Change color_theme to the noctalia theme**

Replace the line `color_theme = "Default"` with:
```conf
color_theme = "noctalia"
```
(btop names themes by the filename stem of `~/.config/btop/themes/noctalia.theme`.)

- [ ] **Step 3: Verify**

Run:
```bash
grep -n '^color_theme = "noctalia"' common/cli/.config/btop/btop.conf
```
Expected: `5:color_theme = "noctalia"`.

- [ ] **Step 4: Commit**

```bash
git add common/cli/.config/btop/btop.conf
git commit -m "theme: point btop at noctalia wallpaper theme"
```

---

## Task 4: Enable Noctalia user theming for the five self/simple targets

Turns on `enableUserTheming` and activates `kitty`, `alacritty`, `btop`, `gtk`, plus prepares for `code`/`zenBrowser` (added in Tasks 5–6). Use the **Settings UI** — it writes the correct `{"id","enabled"}` object shape and calls `AppThemeService.generate()` immediately.

**Files:**
- Modify (indirectly, via UI): `desktop/niri/.config/noctalia/settings.json`

- [ ] **Step 1: Verify the current disabled state**

Run:
```bash
python3 -c "import json;d=json.load(open('desktop/niri/.config/noctalia/settings.json'));t=d['templates'];print('enableUserTheming=',t['enableUserTheming']);print('activeTemplates=',t['activeTemplates'])"
```
Expected: `enableUserTheming= False` and `activeTemplates= []`.

- [ ] **Step 2: Enable via the Settings UI**

Open Noctalia Settings → **Color Scheme → Templates** tab (open Settings with the control-centre / gear, or `qs -c noctalia-shell ipc call settings toggle`). Turn ON **"Enable user theming"**, then toggle ON: **Kitty, Alacritty, btop, GTK**. Leave VSCode and Zen for now (Tasks 5–6). Each toggle regenerates immediately.

> Fallback if the UI is unavailable: edit `desktop/niri/.config/noctalia/settings.json` so `templates.enableUserTheming` is `true` and `templates.activeTemplates` is:
> ```json
> [{"id":"kitty","enabled":true},{"id":"alacritty","enabled":true},{"id":"btop","enabled":true},{"id":"gtk","enabled":true}]
> ```
> then restart the shell: `qs -c noctalia-shell ipc call restart 2>/dev/null || (pkill -f 'qs -c noctalia-shell'; qs -c noctalia-shell &)`.

- [ ] **Step 3: Verify the settings persisted and the generated files appeared**

Run:
```bash
python3 -c "import json;d=json.load(open('desktop/niri/.config/noctalia/settings.json'));t=d['templates'];print('enabled=',t['enableUserTheming']);print('ids=',[x['id'] for x in t['activeTemplates']])"
ls -l ~/.config/kitty/themes/noctalia.conf ~/.config/alacritty/themes/noctalia.toml ~/.config/btop/themes/noctalia.theme ~/.config/gtk-3.0/noctalia.css ~/.config/gtk-4.0/noctalia.css
```
Expected: `enabled= True`; `ids=` includes `kitty alacritty btop gtk`; all five files exist. Also confirm kitty's symlink: `readlink ~/.config/kitty/current-theme.conf` → `themes/noctalia.conf`, and GTK auto-wiring: `grep noctalia.css ~/.config/gtk-3.0/gtk.css` prints the `@import`.

- [ ] **Step 4: Verify the working tree stayed clean (gitignore holds)**

Run:
```bash
git status --porcelain
```
Expected: ONLY `desktop/niri/.config/noctalia/settings.json` shows as modified. NO kitty/alacritty/btop/gtk generated files appear. If any generated file shows up, the Task 1 gitignore glob is wrong — fix it before continuing.

- [ ] **Step 5: Commit**

```bash
git add desktop/niri/.config/noctalia/settings.json
git commit -m "theme: enable noctalia user theming for kitty, alacritty, btop, gtk"
```

---

## Task 5: VSCode Insiders — extension + symlink bridge

Noctalia's `code` template writes to `~/.vscode/extensions/noctalia.noctaliatheme-0.0.5/…`, but Insiders reads `~/.vscode-insiders/extensions/`. This task installs the extension in Insiders and bridges the path. **This is the one target allowed to fail gracefully** — if the extension is unavailable, skip it and note so.

**Files:**
- Create (symlink): `~/.vscode/extensions/noctalia.noctaliatheme-0.0.5` → Insiders copy
- Modify: VSCode Insiders `settings.json` (`~/.config/Code - Insiders/User/settings.json`)
- Modify (Task 4 already made this easy): add `code` to `activeTemplates`

- [ ] **Step 1: Install the extension into Insiders**

Run:
```bash
code-insiders --install-extension noctalia.noctaliatheme 2>&1 | tail -3
ls -d ~/.vscode-insiders/extensions/noctalia.noctaliatheme-* 2>/dev/null
```
Expected: an installed-extension line, and the `ls` prints a versioned dir. **If the install fails** (not on the marketplace), STOP this task: leave `code` out of `activeTemplates`, note "VSCode target skipped — extension unavailable" in the Task 8 README caveats, and move to Task 6.

- [ ] **Step 2: Bridge the path Noctalia writes to**

Noctalia writes to the exact versioned path `noctalia.noctaliatheme-0.0.5`. Point that at whatever Insiders installed:
```bash
INSIDERS_DIR=$(ls -d ~/.vscode-insiders/extensions/noctalia.noctaliatheme-* | head -1)
mkdir -p ~/.vscode/extensions
ln -sfn "$INSIDERS_DIR" ~/.vscode/extensions/noctalia.noctaliatheme-0.0.5
readlink ~/.vscode/extensions/noctalia.noctaliatheme-0.0.5
```
Expected: `readlink` prints the Insiders extension dir.

- [ ] **Step 3: Select the theme in Insiders settings**

In `~/.config/Code - Insiders/User/settings.json`, set:
```json
"workbench.colorTheme": "NoctaliaTheme"
```
(Merge into the existing JSON object; don't overwrite the file.)

- [ ] **Step 4: Activate the `code` template**

In Settings → Color Scheme → Templates, toggle **VSCode** on (or add `{"id":"code","enabled":true}` to `activeTemplates` and restart the shell).

- [ ] **Step 5: Verify generation reaches the extension**

Run:
```bash
qs -c noctalia-shell ipc call theme generate 2>/dev/null; sleep 1
ls -l ~/.vscode/extensions/noctalia.noctaliatheme-0.0.5/themes/NoctaliaTheme-color-theme.json
```
Expected: the theme JSON exists (through the symlink). In a running Insiders window the colours update; if not, reload the window (`Ctrl+Shift+P` → "Reload Window").

- [ ] **Step 6: Commit the tracked change**

Only `settings.json` (activeTemplates now includes `code`) is tracked; the symlink and Insiders settings are per-machine.
```bash
git add desktop/niri/.config/noctalia/settings.json
git commit -m "theme: activate noctalia code (VSCode Insiders) template"
```

---

## Task 6: zen-browser — enable userChrome, let Noctalia auto-wire

The `zenBrowser` post-hook writes CSS to `~/.cache/noctalia/` and auto-injects `@import` lines into every `~/.zen/*/chrome/userChrome.css`. The only manual step is enabling legacy stylesheet loading. Best-effort (see spec Risks).

**Files:**
- Modify: zen profile prefs (`~/.zen/<profile>/user.js` or via about:config)
- Modify: `desktop/niri/.config/noctalia/settings.json` (add `zenBrowser`)

- [ ] **Step 1: Locate the zen profile**

Run:
```bash
find "$HOME/.zen" -maxdepth 2 -name prefs.js 2>/dev/null | head; ls -d "$HOME/.zen"/*/ 2>/dev/null
```
Expected: at least one profile dir. If `~/.zen` doesn't exist, launch zen once to create it, then retry. Note the profile path for the next step.

- [ ] **Step 2: Enable legacy userChrome stylesheets**

Add to that profile's `user.js` (create if absent):
```js
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
```
(Or set it in `about:config` in zen directly. `user.js` is more durable across restarts.)

- [ ] **Step 3: Activate the `zenBrowser` template**

Settings → Templates → toggle **Zen Browser** on (or add `{"id":"zenBrowser","enabled":true}` and restart the shell).

- [ ] **Step 4: Verify auto-wiring happened**

Run:
```bash
qs -c noctalia-shell ipc call theme generate 2>/dev/null; sleep 1
ls -l ~/.cache/noctalia/zen-browser/zen-userChrome.css
grep -rl 'zen-browser/zen-userChrome.css' "$HOME/.zen"/*/chrome/userChrome.css 2>/dev/null
```
Expected: the cache CSS exists, and the grep finds the injected `@import` in the profile's `userChrome.css`. Fully restart zen (not just reload) to see colours apply.

- [ ] **Step 5: Verify tree still clean, then commit**

Run:
```bash
git status --porcelain
```
Expected: only `settings.json` modified (zen writes nothing into the repo).
```bash
git add desktop/niri/.config/noctalia/settings.json
git commit -m "theme: activate noctalia zenBrowser template"
```

---

## Task 7: Document the two-layer model and caveats in the README

**Files:**
- Modify: `README.md` (its theming section)

- [ ] **Step 1: Find the theming section**

Run:
```bash
grep -n -iE '^#+.*(them|adw|gtk)' README.md | head
```
Expected: a heading for the theming/adw-dark discussion. Add the new subsection under it.

- [ ] **Step 2: Write the subsection**

Add prose covering exactly these points (match the README's existing voice — explain the *why*, not just the *what*):

```markdown
### Wallpaper-driven colours (Noctalia templates)

Two layers. `theme/adw-dark` is the static base — it selects adw-gtk3-dark and
sets fonts and cursor, and is unchanged by any of this. On top of it, Noctalia's
template engine recolours apps from the current wallpaper: enable it with
`templates.enableUserTheming` and the per-app toggles under Settings → Color
Scheme → Templates. Active here: kitty, alacritty, btop, GTK, VSCode, zen.

How each app is wired:
- **kitty / GTK** self-wire. kitty's hook symlinks `current-theme.conf` at the
  generated theme (kitty.conf already includes it); GTK's hook creates
  `gtk.css` with an `@import` of the generated `noctalia.css`. No config edit.
  Because `kitten themes` also owns `current-theme.conf`, don't run it — theme
  selection is Noctalia's job now.
- **alacritty / btop** take one line each (an `import`, and `color_theme`).
- **VSCode Insiders** needs the `noctalia.noctaliatheme` extension and a symlink
  from `~/.vscode/extensions/noctalia.noctaliatheme-0.0.5` to the Insiders copy,
  because the template writes to the stable-VSCode path, not the Insiders one.
- **zen** needs `toolkit.legacyUserProfileCustomizations.stylesheets = true`;
  the hook injects the `@import` into the profile automatically. Best-effort —
  a zen update can reset the pref or break userChrome.

The generated colour files are **not tracked**: they regenerate on every
wallpaper change and are written through stow-folded symlinks into the repo, so
they are gitignored (see the "Wallpaper-driven theme output" block in
`.gitignore`). A fresh machine has no colour files until the first login render;
apps fall back to their built-in defaults for those first seconds.

To turn the whole thing off, flip `enableUserTheming` back to false — every app
reverts to the static adw-dark look.
```

Adjust the "Active here" list if VSCode was skipped in Task 5.

- [ ] **Step 3: Verify it reads cleanly**

Run:
```bash
grep -n 'Wallpaper-driven colours' README.md
```
Expected: the new heading is found.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document wallpaper-driven theming (noctalia templates)"
```

---

## Task 8: End-to-end verification

- [ ] **Step 1: Force a real wallpaper change**

Change the wallpaper (Noctalia wallpaper panel, or `qs -c noctalia-shell ipc call wallpaper …`). This is the true trigger the whole feature exists for.

- [ ] **Step 2: Confirm every target retinted**

Visually confirm, in this order (easiest → fussiest):
- **btop**: open `btop` — palette follows the wallpaper.
- **kitty**: already-open window recolours live (USR1 reload).
- **alacritty**: already-open window recolours live (live_config_reload).
- **GTK app** (e.g. nautilus): accent/background follows; restart the app if it didn't pick up live.
- **VSCode Insiders**: editor theme shifts (reload window if needed). Skip if Task 5 was skipped.
- **zen**: restart zen; chrome recolours. Best-effort.

- [ ] **Step 3: Confirm the repo stayed clean through a wallpaper change**

Run:
```bash
git status --porcelain
```
Expected: EMPTY (all work committed; no generated file leaked in). This is the core repo-hygiene success criterion.

- [ ] **Step 4: Confirm clean revert path**

Toggle `enableUserTheming` off in Settings, change wallpaper, confirm apps fall back to adw-dark; toggle back on. (No commit — just proving the escape hatch works.)

---

## Self-review checklist (completed by plan author)

- **Spec coverage:** every spec component maps to a task — config (T4), alacritty/btop wiring (T2,T3), kitty/gtk self-wiring + untrack (T1,T4), VSCode (T5), zen (T6), gitignore (T1), docs+caveats (T7), fresh-machine/clean-tree criteria (T4,T6,T8). ✓
- **Placeholders:** none — every step has the exact command/edit. The one genuine unknown (VSCode extension availability) is handled as an explicit graceful-skip branch, not a TODO. ✓
- **Consistency:** template ids (`kitty`,`alacritty`,`btop`,`gtk`,`code`,`zenBrowser`), object shape `{"id","enabled":true}`, and output paths match across tasks and the corrected spec. ✓
