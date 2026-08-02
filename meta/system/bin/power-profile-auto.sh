#!/usr/bin/env bash
#
# Set the power profile to match the charger state. Invoked by
# meta/system/udev/99-power-profile.rules on every AC adapter change.
#
# NOT PORTABLE AS WRITTEN. The adapter is hardcoded to ACAD, which is what
# this laptop calls it. Other machines use AC, AC0 or ADP1, and a desktop has
# no adapter at all. Elsewhere the [[ -f ]] test simply fails and the script
# does nothing — it does not misbehave, it just never fires. Check with
# `ls /sys/class/power_supply/` and change AC_PATH to match.
#
# Not installable by stow: it belongs to root under /usr/local/bin. See the
# README.
#
#   sudo install -Dm755 meta/system/bin/power-profile-auto.sh \
#     /usr/local/bin/power-profile-auto.sh

AC_PATH="/sys/class/power_supply/ACAD/online"

if [[ -f "$AC_PATH" ]]; then
    if [[ $(cat "$AC_PATH") == "1" ]]; then
        powerprofilesctl set performance
    else
        powerprofilesctl set power-saver
    fi
fi
