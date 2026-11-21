import io
import os
import shutil
import subprocess
import sys

import pytest
from wordpress_fake import add_profile

from wpsync.cli import run
from wpsync.config import ConfigurationStore
from wpsync.shell import BEGIN, END


def setup(home, shell="/bin/zsh"):
    output, errors = io.StringIO(), io.StringIO()
    status = run(
        ["setup"],
        stdout=output,
        stderr=errors,
        environ={"HOME": str(home), "SHELL": shell},
    )
    return status, output.getvalue(), errors.getvalue()


def test_setup_adds_one_block_and_updates_it_in_place(tmp_path):
    dotfiles = tmp_path / "dotfiles"
    dotfiles.mkdir()
    target = dotfiles / "zshrc"
    target.write_text("export EDITOR=vim\n")
    target.chmod(0o640)
    (tmp_path / ".zshrc").symlink_to(target)

    status, output, _ = setup(tmp_path)
    assert status == 0
    assert output.startswith("Added the wpsync shell function in ~/.zshrc.\n")
    assert (tmp_path / ".zshrc").is_symlink()
    target.write_text(target.read_text() + "\nalias ll='ls -l'\n")

    assert setup(tmp_path)[1].startswith("Updated")
    text = target.read_text()
    assert text.count(BEGIN) == text.count(END) == 1
    assert text.startswith("export EDITOR=vim\n\n" + BEGIN)
    assert text.endswith(END + "\n\nalias ll='ls -l'\n")
    assert target.stat().st_mode & 0o777 == 0o640

    assert setup(tmp_path, shell="/usr/bin/fish") == (
        1,
        "",
        "wpsync: error: setup supports zsh and bash, not 'fish'\n",
    )


@pytest.mark.parametrize("shell", ["bash", "zsh"])
def test_setup_function_changes_directory_and_passes_other_commands(tmp_path, shell):
    executable = shutil.which(shell)
    if executable is None:
        pytest.skip(f"{shell} is not installed")
    blog = tmp_path / "my blog"
    blog.mkdir()
    store = ConfigurationStore(tmp_path / ".wpsync" / "config.json")
    add_profile(store, "myblog", blog)
    bin_directory = tmp_path / "bin"
    bin_directory.mkdir()
    program = bin_directory / "wpsync"
    program.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m wpsync "$@"\n')
    program.chmod(0o755)
    assert setup(tmp_path, shell=executable)[0] == 0
    startup = tmp_path / (".zshrc" if shell == "zsh" else ".bashrc")

    script = (
        f"source '{startup}'\n"
        "wpsync cd myblog && pwd\n"
        "cd / && wpsync cd nope; echo status=$? && pwd\n"
        "wpsync root myblog\n"
    )
    environment = {
        **os.environ,
        "HOME": str(tmp_path),
        "PATH": f"{bin_directory}:{os.environ['PATH']}",
    }
    result = subprocess.run(
        [executable, "-c", script],
        capture_output=True,
        text=True,
        env=environment,
        check=True,
    )
    assert result.stdout.splitlines() == [
        str(blog.resolve()),
        "status=1",
        "/",
        str(blog.resolve()),
    ]
    assert "profile 'nope'" in result.stderr


def test_cd_without_the_shell_function_explains_setup(store):
    errors = io.StringIO()
    status = run(["cd", "myblog"], store=store, stdout=io.StringIO(), stderr=errors)
    assert status == 1
    assert errors.getvalue() == (
        "wpsync: error: cd needs the shell function; run 'wpsync setup', "
        "then open a new terminal\n"
    )
