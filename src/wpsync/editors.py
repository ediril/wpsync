"""Opening post files in the user's Markdown editor."""

from __future__ import annotations

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
INSTALL_HINTS = {
    "code": "; in VS Code, run Shell Command: Install 'code' command in PATH"
}


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
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as error:
        hint = INSTALL_HINTS.get(command[0], "")
        raise EditorError(f"'{command[0]}' is not on your PATH{hint}") from error
    except subprocess.CalledProcessError as error:
        raise EditorError(
            f"'{command[0]}' failed with exit status {error.returncode}"
        ) from error
