#!/usr/bin/env bash
#
# bootstrap.sh — apply a dotfiles profile with GNU Stow.
#
#   ./bootstrap.sh niri          apply the 'niri' profile
#   ./bootstrap.sh niri -n       dry run, change nothing
#   ./bootstrap.sh --unstow      remove every symlink this repo owns
#   ./bootstrap.sh --list        show available profiles
#
# The profile is the single source of truth. For the single-choice tiers
# (theme, desktop) every package NOT named by the profile is unstowed first,
# so switching desktops is one command and re-running is idempotent.

set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$HOME"
TIERS=(common theme desktop)

STOW_FLAGS=()
PROFILE=""
MODE="apply"
DRY=0

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0; }

while (($#)); do
  case "$1" in
    -n|--simulate|--dry-run) STOW_FLAGS+=(--simulate --verbose); DRY=1 ;;
    -v|--verbose)            STOW_FLAGS+=(--verbose) ;;
    --unstow)                MODE="unstow" ;;
    --list)                  MODE="list" ;;
    -h|--help)               usage ;;
    -*)                      die "unknown flag: $1" ;;
    *)                       PROFILE="$1" ;;
  esac
  shift
done

command -v stow >/dev/null || die "GNU Stow is not installed (sudo pacman -S stow)"

if [[ $MODE == list ]]; then
  info "profiles in $REPO/profiles:"
  for f in "$REPO"/profiles/*.conf; do [[ -e $f ]] && basename "$f" .conf; done
  exit 0
fi

# ---------------------------------------------------------------------------
# unstow everything
# ---------------------------------------------------------------------------
if [[ $MODE == unstow ]]; then
  for tier in "${TIERS[@]}"; do
    [[ -d $REPO/$tier ]] || continue
    for pkg in "$REPO/$tier"/*/; do
      [[ -d $pkg ]] || continue
      stow "${STOW_FLAGS[@]}" -D -d "$REPO/$tier" -t "$TARGET" "$(basename "$pkg")" 2>/dev/null || true
    done
  done
  info "all packages unstowed"
  exit 0
fi

# ---------------------------------------------------------------------------
# apply a profile
# ---------------------------------------------------------------------------
[[ -n $PROFILE ]] || die "no profile given — try: $(basename "$0") --list"
CONF="$REPO/profiles/$PROFILE.conf"
[[ -f $CONF ]] || die "no such profile: $CONF"

# read "tier: pkg pkg" lines, ignoring blanks and comments
selected_for() {
  sed -e 's/#.*//' "$CONF" \
    | awk -F: -v t="$1" '$1 ~ "^[[:space:]]*"t"[[:space:]]*$" { $1=""; print }'
}

# systemd ignores a drop-in directory that is a symlink. Left to itself stow
# folds a directory the target does not have yet into one link, so an
# app.slice.d shipped by a package would silently never load. Creating the
# directory for real first makes stow link the .conf files inside it instead.
unfold_dropin_dirs() {
  local pkgdir="$1" d
  ((DRY)) && return 0
  while IFS= read -r -d '' d; do
    mkdir -p "$TARGET/${d#"$pkgdir/"}"
  done < <(find "$pkgdir" -type d -path '*/.config/systemd/*' -name '*.d' -print0 2>/dev/null)
}

# Same folding problem, different blast radius: on a machine where ~/.gnupg does
# not exist yet, stow would link the whole directory into the repo — leaving gpg
# with a 755 world-readable home it refuses to trust, and pointing the path that
# private keys get written to at a public git repo. Create it 700 for real first
# so stow only links the .conf files inside.
unfold_private_dirs() {
  local pkgdir="$1" d
  ((DRY)) && return 0
  while IFS= read -r -d '' d; do
    install -d -m 700 "$TARGET/${d#"$pkgdir/"}"
  done < <(find "$pkgdir" -type d -name '.gnupg' -print0 2>/dev/null)
}

info "applying profile '$PROFILE'"

for tier in "${TIERS[@]}"; do
  [[ -d $REPO/$tier ]] || continue
  read -ra want <<<"$(selected_for "$tier")"

  # drop packages in this tier that the profile does not ask for
  for pkg in "$REPO/$tier"/*/; do
    [[ -d $pkg ]] || continue
    name="$(basename "$pkg")"
    keep=0
    for w in ${want[@]+"${want[@]}"}; do [[ $w == "$name" ]] && keep=1; done
    if ((!keep)); then
      stow "${STOW_FLAGS[@]}" -D -d "$REPO/$tier" -t "$TARGET" "$name" 2>/dev/null || true
    fi
  done

  if ((${#want[@]})); then
    printf '  %-8s %s\n' "$tier" "${want[*]}"
    for w in "${want[@]}"; do
      unfold_dropin_dirs  "$REPO/$tier/$w"
      unfold_private_dirs "$REPO/$tier/$w"
    done
    stow "${STOW_FLAGS[@]}" -d "$REPO/$tier" -t "$TARGET" "${want[@]}"
  fi
done

info "done"

if [[ -f $REPO/meta/systemd-user-units.txt ]]; then
  printf '\nreminder: systemd user units are not stowed. To re-enable them:\n'
  printf '  grep -v "^#" %s | xargs -r systemctl --user enable --now\n' \
    "${REPO/#$HOME/\~}/meta/systemd-user-units.txt"
fi
