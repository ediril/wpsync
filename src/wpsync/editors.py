"""Opening post files in the user's Markdown editor."""

from __future__ import annotations

import shutil
import subprocess
import sys
from enum import StrEnum
from pathlib import Path
from urllib.parse import quote


class EditorError(Exception):
    """No editor is chosen, or the chosen one cannot open the file."""


class Editor(StrEnum):
    OBSIDIAN = "obsidian"
    VSCODE = "vscode"

    @property
    def label(self) -> str:
        return {Editor.OBSIDIAN: "Obsidian", Editor.VSCODE: "VS Code"}[self]


URL_OPENER = {"darwin": ["open"], "win32": ["cmd", "/c", "start", ""]}.get(
    sys.platform, ["xdg-open"]
)
# macOS apps that open the same arguments when their command is not installed.
MAC_APPS = {"code": "Visual Studio Code"}


def editor_command(editor: Editor, root: Path, file: Path) -> list[str]:
    """The command that opens a post file of the profile folder in an editor."""
    if editor is Editor.VSCODE:
        # With the folder as its workspace, VS Code reuses one window per blog.
        return ["code", str(root), str(file)]
    if not any((folder / ".obsidian").is_dir() for folder in file.parents):
        raise EditorError(
            f"{file} is not in an Obsidian vault; open {root} as a vault in "
            "Obsidian first"
        )
    return [*URL_OPENER, "obsidian://open?path=" + quote(str(file), safe="")]


def launch(command: list[str]) -> None:
    program, *arguments = command
    # which() also finds Windows .cmd files, such as VS Code's code.cmd.
    executable = shutil.which(program)
    if executable is not None:
        _run([executable, *arguments], f"'{program}'")
    elif sys.platform == "darwin" and program in MAC_APPS:
        app = MAC_APPS[program]
        _run(
            ["open", "-a", app, *arguments],
            f"'{program}' is not on your PATH, and opening {app}",
        )
    else:
        raise EditorError(f"'{program}' is not on your PATH")


def _run(command: list[str], name: str) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise EditorError(
            f"{name} failed with exit status {error.returncode}"
        ) from error
