"""Shell startup integration that lets 'wpsync cd' change directory."""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path

from wpsync.storage import write_text_atomic

BEGIN = "# >>> wpsync shell setup >>>"
END = "# <<< wpsync shell setup <<<"

# A program cannot change its parent shell's directory, so 'cd' is handled by
# this function; every other command passes through to the wpsync program.
BLOCK = f"""{BEGIN}
# Lets 'wpsync cd [PROFILE]' change to a profile's local folder.
wpsync() {{
  if [ "$1" = cd ]; then
    shift
    local dir
    dir="$(command wpsync root "$@")" && cd "$dir"
  else
    command wpsync "$@"
  fi
}}
{END}
"""

STARTUP_FILES = {"zsh": ".zshrc", "bash": ".bashrc"}


class ShellSetupError(RuntimeError):
    pass


def startup_file(environ: Mapping[str, str]) -> Path:
    """Return the interactive startup file of the user's login shell."""
    shell = Path(environ.get("SHELL", "")).name
    if shell not in STARTUP_FILES:
        named = shell or "unknown"
        raise ShellSetupError(f"setup supports zsh and bash, not '{named}'")
    home = Path(environ.get("HOME") or Path.home())
    directory = Path(environ.get("ZDOTDIR") or home) if shell == "zsh" else home
    return directory / STARTUP_FILES[shell]


def install_shell_function(path: Path) -> bool:
    """Write the shell function block; return True if it replaced an older one."""
    # Write through a symlink so dotfile managers keep their link.
    target = path.resolve() if path.is_symlink() else path
    try:
        existing = target.read_text(encoding="utf-8")
        mode = stat.S_IMODE(target.stat().st_mode)
    except FileNotFoundError:
        existing, mode = "", 0o644
    start, end = existing.find(BEGIN), existing.find(END)
    if start != -1 and end > start:
        rest = existing[end + len(END) :]
        updated = existing[:start] + BLOCK + rest.removeprefix("\n")
        replaced = True
    else:
        separator = "" if not existing else "\n" if existing.endswith("\n") else "\n\n"
        updated = existing + separator + BLOCK
        replaced = False
    write_text_atomic(target, updated, mode=mode)
    return replaced


def home_relative(path: Path, home: Path) -> str:
    """Show a startup file path with the home directory as '~'."""
    try:
        return f"~/{path.relative_to(home).as_posix()}"
    except ValueError:
        return os.fspath(path)
