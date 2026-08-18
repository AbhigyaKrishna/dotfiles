# Capture tools + named workspaces — design

**Date:** 2026-08-18
**Status:** Approved, implementing directly (small, mechanical — no separate bite-sized plan)
**Scope:** Four independent desktop additions on niri + noctalia:
1. Region-screenshot annotation (satty)
2. Region OCR to clipboard (tesseract)
3. Screen colour picker / eyedropper (hyprpicker)
4. Named, auto-assigning workspaces (web / code / chat)

Screen recording was explicitly dropped: noctalia already ships a recorder
(gpu-screen-recorder backend, already installed) and the user uses it.

## Packages (meta/packages.txt, new "capture & desktop tools" section)

`grim slurp satty tesseract tesseract-data-eng hyprpicker wl-clipboard libnotify`

All in the official repos (verified). `wl-copy` (wl-clipboard) and `notify-send`
(libnotify) were already present but untracked; the new scripts call both by
name, so they are tracked for a clean rebuild.

## Scripts (common/bin/.local/bin/, stowed to ~/.local/bin — the niri-power-action pattern)

- **niri-ocr** — `grim -g "$(slurp)"` a region to a temp PNG, `tesseract` it to
  text, `wl-copy` the text, `notify-send` the character count. Temp file cleaned
  on exit.
- **niri-annotate** — `grim -g "$(slurp)" -` piped into `satty --filename -`,
  saving to `~/Pictures/Screenshots/` and copying the annotated image to the
  clipboard (`--copy-command wl-copy --early-exit`).
- **niri-color-pick** — `hyprpicker -f hex -r` (print to stdout, no autocopy),
  `wl-copy` the hex, `notify-send` it. Silent no-op if the pick is cancelled.

Rationale for scripts over inline `spawn-sh`: keeps KDL free of nested-quote
command substitution, and matches how niri-power-action already centralises
multi-step shell logic.

## Keybinds (niri/cfg/keybinds.kdl, new "Capture & Tools" section)

| Key | Spawns | Notes |
|---|---|---|
| `Mod+Shift+S` | `niri-annotate` | region → satty. S = snip/annotate |
| `Mod+Shift+O` | `niri-ocr` | region → OCR → clipboard. Mod+O is overview; Shift is free |
| `Mod+Shift+C` | `niri-color-pick` | eyedropper. Mod+C is center-column; Shift is free |

All three keys verified free in keybinds.kdl. Each carries a
`hotkey-overlay-title` like the existing binds.

## Named workspaces (niri/cfg/workspaces.kdl — new file, included from config.kdl)

Three persistent named workspaces, declared in order so they occupy indices 1–3
(so `Mod+1/2/3` focus them); dynamic workspaces continue after, unchanged, for
terminals and everything else.

```kdl
workspace "web"
workspace "code"
workspace "chat"
```

## Window rules (niri/cfg/rules.kdl — appended)

`open-on-workspace` rules, matching on app-id (confirmed: `zen`,
`jetbrains-goland`; forgiving regexes for the two not running at design time):

- `zen` → `web`
- `jetbrains-goland` OR `code-insiders`/`Code - Insiders` → `code`
- `beeper`/`Beeper` → `chat`

> app-id caveat: `zen` and `jetbrains-goland` are confirmed from live windows.
> beeper and VSCode Insiders were not open; the rules use case-tolerant regexes.
> If auto-assign misses either, check the real app-id with `niri msg windows`
> while the app is open and tighten the regex. This is the one implementation
> uncertainty, and it fails safe (window just opens on the current workspace).

## Verification

- `niri validate` passes on the new config.
- Each keybind spawns its script; scripts are `bash -n` clean and executable.
- Opening zen / goland / beeper lands them on their named workspace.
- `git status` clean after (no unrelated files, scripts tracked).

## Out of scope / not done

- Screen recording (noctalia already provides it).
- OCR languages beyond English (add `tesseract-data-*` later if needed).
