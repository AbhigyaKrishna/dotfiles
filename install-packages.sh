#!/usr/bin/env bash
#
# install-packages.sh — install the packages backing this configuration.
#
#   ./install-packages.sh          install what is missing
#   ./install-packages.sh -n       list what would be installed, change nothing
#   ./install-packages.sh -y       do not prompt for confirmation
#
# Reads meta/packages.txt. Bootstraps paru first if it is absent, since one
# package (monique) only exists in the AUR. Separate from bootstrap.sh on
# purpose: this touches the system, bootstrap.sh only makes symlinks.

set -euo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
LIST="$REPO/meta/packages.txt"
DRY=0
NOCONFIRM=()

die()  { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarn:\033[0m %s\n' "$*" >&2; }

while (($#)); do
  case "$1" in
    -n|--dry-run) DRY=1 ;;
    -y|--noconfirm) NOCONFIRM=(--noconfirm) ;;
    -h|--help) sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \?//'; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

command -v pacman >/dev/null || die "not an Arch-based system (no pacman)"
[[ -f $LIST ]] || die "package list not found: $LIST"

# Strip comments and blanks.
mapfile -t PKGS < <(sed -e 's/#.*//' -e 's/[[:space:]]*$//' "$LIST" | grep -v '^$')
((${#PKGS[@]})) || die "no packages listed in $LIST"

# Which are actually missing?
missing=()
for p in "${PKGS[@]}"; do
  pacman -Qq "$p" >/dev/null 2>&1 || missing+=("$p")
done

if ((!${#missing[@]})); then
  info "all ${#PKGS[@]} packages already installed"
  exit 0
fi

info "${#missing[@]} of ${#PKGS[@]} packages missing:"
printf '  %s\n' "${missing[@]}"

if ((DRY)); then
  info "dry run — nothing installed"
  exit 0
fi

# paru is needed for the AUR entries. CachyOS ships it; elsewhere, build it.
if ! command -v paru >/dev/null; then
  info "paru not found — installing it first"
  if pacman -Si paru >/dev/null 2>&1; then
    sudo pacman -S --needed "${NOCONFIRM[@]}" paru
  else
    warn "paru is not in the configured repos; building from the AUR"
    command -v makepkg >/dev/null || sudo pacman -S --needed "${NOCONFIRM[@]}" base-devel
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    git clone --depth 1 https://aur.archlinux.org/paru-bin.git "$tmp/paru-bin"
    (cd "$tmp/paru-bin" && makepkg -si "${NOCONFIRM[@]}")
  fi
fi

info "installing"
paru -S --needed "${NOCONFIRM[@]}" "${missing[@]}"

# Report rather than assume success — paru may skip a package.
still=()
for p in "${missing[@]}"; do
  pacman -Qq "$p" >/dev/null 2>&1 || still+=("$p")
done
if ((${#still[@]})); then
  warn "still not installed: ${still[*]}"
  exit 1
fi
info "done — all ${#PKGS[@]} packages present"
