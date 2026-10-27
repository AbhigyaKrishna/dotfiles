"""Profile operations behind Noctalia's native /profile launcher provider."""

import argparse
import json
import os
import sys
import tomllib

from manager import ThemeManager, run


def notify(summary, body, urgency):
    try:
        run(
            "notify-send",
            "--app-name=Desktop Profiles",
            f"--urgency={urgency}",
            "--",
            summary,
            body,
        )
    except (OSError, RuntimeError) as error:
        print(f"desktop-theme: notification failed: {error}", file=sys.stderr)


def open_provider(manager):
    manager.ensure_profile_provider()
    prefix = tomllib.loads(
        "prefix = "
        + run("noctalia", "msg", "config-get", "shell.launcher.provider_prefix")
    )["prefix"]
    run("noctalia", "msg", "panel-toggle", "launcher", prefix + "profile")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Desktop profiles for Noctalia")
    parser.add_argument(
        "command",
        nargs="?",
        default="menu",
        choices=(
            "menu",
            "list",
            "original",
            "glyph",
            "switch",
            "status",
            "sync",
            "ready",
        ),
    )
    parser.add_argument("profile", nargs="?", choices=("original", "glyph"))
    arguments = parser.parse_args(argv)
    if (arguments.command == "switch") != (arguments.profile is not None):
        parser.error(
            "switch requires a profile; other commands take no profile argument"
        )
    os.environ.pop("GTK_THEME", None)
    manager = ThemeManager()
    try:
        if arguments.command == "list":
            print(json.dumps(manager.profile_list()))
        elif arguments.command == "status":
            print(manager.current)
        elif arguments.command == "ready":
            manager.acknowledge_templates()
        elif arguments.command == "sync":
            with manager.locked():
                manager.sync_apps()
        elif arguments.command == "menu":
            open_provider(manager)
        else:
            name = (
                arguments.profile
                if arguments.command == "switch"
                else arguments.command
            )
            manager.apply(name)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"desktop-theme: {error}", file=sys.stderr)
        if arguments.command == "switch":
            notify("Could not switch desktop profile", str(error), "critical")
        return 1
    if arguments.command == "switch":
        notify(
            "Desktop profile",
            f"Using {manager.description(arguments.profile)['title']}",
            "normal",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
