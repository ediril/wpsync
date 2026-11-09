import subprocess
import sys
from urllib.parse import quote

import pytest
from wordpress_fake import Terminal, add_profile, invoke

from wpsync import editors
from wpsync.documents import Document, write_document
from wpsync.editors import URL_OPENER, Editor, EditorError
from wpsync.posts import Post


def with_post(tmp_path, store):
    add_profile(store, "myblog", tmp_path)
    path = tmp_path / "content/notes/idea.md"
    write_document(path, Document(None, Post(title="Idea")))
    return path


def test_open_asks_once_for_an_editor_and_remembers_it(tmp_path, store):
    path = with_post(tmp_path, store)
    launched = []

    status, output, _ = invoke(
        ["myblog", "open", "Idea"],
        store,
        stdin=Terminal("2\n"),
        launch=launched.append,
        password=None,
    )

    assert status == 0
    assert "  3) Other" in output
    assert output.endswith("Opened content/notes/idea.md in VS Code.\n")
    assert launched == [["code", str(tmp_path.resolve()), str(path.resolve())]]
    assert store.load().editor is Editor.VSCODE

    status, output, _ = invoke(
        ["myblog", "open", "content/notes/idea.md"],
        store,
        launch=launched.append,
        password=None,
    )
    assert (status, output) == (0, "Opened content/notes/idea.md in VS Code.\n")
    assert len(launched) == 2


def test_an_editor_that_cannot_be_used_is_never_saved_or_started(tmp_path, store):
    with_post(tmp_path, store)

    for stdin, message in (
        ("", "no editor chosen; run wpsync editor obsidian|vscode"),
        (Terminal("3\n"), "only Obsidian and VS Code are supported for now"),
    ):
        status, _, errors = invoke(
            ["myblog", "open", "Idea"], store, stdin=stdin, password=None
        )
        assert (status, errors) == (1, f"wpsync: error: {message}\n")
    assert store.load().editor is None

    invoke(["editor", "obsidian"], store)
    status, _, errors = invoke(["myblog", "open", "Idea"], store, password=None)
    assert status == 1
    assert "is not in an Obsidian vault" in errors


def test_obsidian_opens_a_file_in_a_vault_by_its_path(tmp_path, store):
    path = with_post(tmp_path, store)
    (tmp_path / ".obsidian").mkdir()
    invoke(["editor"], store, stdin=Terminal("1\n"))
    launched = []

    invoke(["myblog", "open", "Idea"], store, launch=launched.append, password=None)

    url = "obsidian://open?path=" + quote(str(path.resolve()), safe="")
    assert launched == [[*URL_OPENER, url]]


def test_launch_finds_the_program_on_path_or_vs_code_as_a_mac_app(monkeypatch):
    found = {"code": "/opt/bin/code.cmd"}
    ran = []
    monkeypatch.setattr(editors.shutil, "which", found.get)
    monkeypatch.setattr(subprocess, "run", lambda command, check: ran.append(command))

    editors.launch(["code", "/blog", "/blog/a.md"])
    found.clear()
    monkeypatch.setattr(sys, "platform", "darwin")
    editors.launch(["code", "/blog", "/blog/a.md"])
    with pytest.raises(EditorError, match="'xdg-open' is not on your PATH"):
        editors.launch(["xdg-open", "obsidian://open"])

    assert ran == [
        ["/opt/bin/code.cmd", "/blog", "/blog/a.md"],
        ["open", "-a", "Visual Studio Code", "/blog", "/blog/a.md"],
    ]
