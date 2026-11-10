from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import TextIO

import httpx

from wpsync import __version__
from wpsync.config import (
    Configuration,
    ConfigurationError,
    ConfigurationStore,
    Profile,
    canonical_local_root,
    default_password_env,
    validate_environment_name,
    validate_profile_name,
)
from wpsync.documents import (
    CONTENT_DIR,
    TRASH_DIR,
    Document,
    DocumentError,
    LocalDocument,
    scan_documents,
    scan_trash,
    write_document,
)
from wpsync.editors import Editor, EditorError, editor_command, launch
from wpsync.posts import Post, PostStatus, PostSummary, RemoteState
from wpsync.pull import Puller
from wpsync.push import Pusher
from wpsync.state import (
    PostRecord,
    StateError,
    follow_moves,
    read_media,
    read_records,
)
from wpsync.sync import Action, DiffEntry, SelectionError, compare, select
from wpsync.trash import TrashError, delete_post, restore_post
from wpsync.wordpress.client import WordPressClient, WordPressError, discover_api_root
from wpsync.wordpress.remote import WordPressRemote

COMMANDS = (
    "init",
    "map",
    "remove",
    "root",
    "profile",
    "profiles",
    "editor",
    "create",
    "ls",
    "show",
    "open",
    "diff",
    "pull",
    "push",
    "delete",
    "trash",
    "restore",
)
PROFILE_AWARE_COMMANDS = frozenset(
    {
        "map",
        "remove",
        "root",
        "profile",
        "create",
        "ls",
        "show",
        "open",
        "diff",
        "pull",
        "push",
        "delete",
        "trash",
        "restore",
    }
)
TIMESTAMP_FORMAT = "%Y-%m-%d-%H%M"
TIMESTAMP_NAME = re.compile(r"(\d{4}-\d{2}-\d{2}-\d{4})(?:-(\d+))?\.md")
JUST_CREATED = timedelta(minutes=10)
"""How long after create a plain wpsync open still opens the new post."""
NO_POSTS = "No posts here yet. Run wpsync pull, or add Markdown files under content/."
RESET = "\033[0m"
MARKER_COLORS = {
    "+": "\033[38;5;82m",
    "~": "\033[33m",
    "-": "\033[31m",
    "?": "\033[35m",
    "x": "\033[90m",
    "l": "\033[38;5;51m",
    "r": "\033[38;5;30m",
}
LEGEND = (
    ("+ l", "new local post; push creates it"),
    ("~ l", "changed locally; push updates the post"),
    ("- l", "deleted locally; push -p deletes it from WordPress"),
    ("?  ", "conflict or ambiguous match; push stops and asks"),
    ("=  ", "unchanged (shown with -a)"),
    ("x l", "private; push never sends it (shown with -a)"),
)
LS_LEGEND = (
    ("*", "Public: push publishes it (blank means private)"),
    ("*Jan 1, 2029", "Public: scheduled; the blog shows it from that date"),
)


class _Session:
    """The process context a command runs in."""

    def __init__(
        self,
        store: ConfigurationStore,
        stdin: TextIO,
        stdout: TextIO,
        environ: Mapping[str, str],
        transport: httpx.BaseTransport | None,
        launch: Callable[[list[str]], None],
    ) -> None:
        self.store = store
        self.stdin = stdin
        self.stdout = stdout
        self.environ = environ
        self.transport = transport
        self.launch = launch

    def ask(self, prompt: str) -> str:
        print(prompt, end="", file=self.stdout, flush=True)
        return self.stdin.readline().strip()

    def confirm(self, prompt: str, *, default: bool) -> bool:
        """Ask a yes/no question. End of input counts as No."""
        while True:
            print(prompt, end="", file=self.stdout, flush=True)
            answer = self.stdin.readline()
            if answer == "":
                print(file=self.stdout)
                return False
            normalized = answer.strip().lower()
            if normalized in {"y", "yes"}:
                return True
            if normalized in {"n", "no"}:
                return False
            if normalized == "":
                return default
            print("Please answer yes or no.", file=self.stdout)

    def password(self, profile: Profile) -> str:
        password = self.environ.get(profile.password_env)
        if not password:
            raise ConfigurationError(f"{profile.password_env} is not set")
        return password


def _resolve_command(value: str) -> str:
    if value in COMMANDS:
        return value
    matches = [command for command in COMMANDS if command.startswith(value)]
    if not matches:
        raise ConfigurationError(f"unknown command '{value}'")
    if len(matches) > 1:
        raise ConfigurationError(f"ambiguous command '{value}': {', '.join(matches)}")
    return matches[0]


def _could_be_command(value: str) -> bool:
    return any(command.startswith(value) for command in COMMANDS)


def _resolve_invocation(arguments: list[str]) -> tuple[list[str], str | None]:
    """Expand command prefixes and split off a leading profile override."""
    if not arguments or arguments[0].startswith("-"):
        return arguments, None
    first = arguments[0]
    if (
        first not in COMMANDS
        and len(arguments) > 1
        and not arguments[1].startswith("-")
        and _could_be_command(arguments[1])
    ):
        command = _resolve_command(arguments[1])
        if command not in PROFILE_AWARE_COMMANDS:
            raise ConfigurationError(
                f"profile prefix '{first}' cannot be used with '{command}'"
            )
        return [command, *arguments[2:]], validate_profile_name(first)
    return [_resolve_command(first), *arguments[1:]], None


def _profile_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "profile_name",
        nargs="?",
        metavar="PROFILE",
        help="profile; inferred from the current directory when omitted",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wpsync",
        description=(
            "Manage WordPress posts as local Markdown files. Run commands inside "
            "a mapped profile folder, or prefix a command with a profile name. "
            "Commands may be shortened to any unique prefix."
        ),
    )
    parser.add_argument("-v", "--version", action="version", version=__version__)
    parser.add_argument(
        "--legend", action="store_true", help="show diff and ls symbols and exit"
    )
    subparsers = parser.add_subparsers(dest="command")

    init = subparsers.add_parser(
        "init",
        help="create a profile that maps a local folder to a blog",
        description=(
            "Create a profile for a WordPress site without signing in. Without "
            "--local-root, offer the current directory. Pull next."
        ),
    )
    init.add_argument("profile_name", metavar="PROFILE", help="new profile name")
    init.add_argument(
        "--site", required=True, help="blog address, such as https://example.com"
    )
    init.add_argument(
        "-u", "--username", help="WordPress username; prompted when omitted"
    )
    init.add_argument(
        "--password-env",
        metavar="NAME",
        help="password environment variable (default: PROFILE_WP_PASSWORD)",
    )
    init.add_argument("--local-root", metavar="PATH", help="local folder for this blog")

    map_parser = subparsers.add_parser(
        "map",
        help="move a profile's local folder",
        usage="wpsync map [PROFILE] [--local-root PATH]\n       wpsync PROFILE map",
        description=(
            "Point a profile at a different local folder after a [y/N] "
            "confirmation. A different blog needs its own profile."
        ),
    )
    _profile_argument(map_parser)
    map_parser.add_argument(
        "--local-root",
        metavar="PATH",
        help="new local folder; defaults to the current directory",
    )

    remove = subparsers.add_parser(
        "remove",
        help="remove a profile",
        usage="wpsync remove [PROFILE]\n       wpsync PROFILE remove",
        description="Remove the profile only; local files and the blog stay unchanged.",
    )
    _profile_argument(remove)

    root = subparsers.add_parser(
        "root",
        help="print a profile's local folder",
        usage="wpsync root [PROFILE]\n       wpsync PROFILE root",
        description=(
            'Print only the local folder, suitable for cd "$(wpsync root PROFILE)".'
        ),
    )
    _profile_argument(root)

    profile = subparsers.add_parser(
        "profile",
        help="show the current or named profile",
        usage=(
            "wpsync profile [PROFILE] [--details]\n"
            "       wpsync PROFILE profile [--details]"
        ),
    )
    _profile_argument(profile)
    profile.add_argument(
        "--details",
        action="store_true",
        help="show the site, account, and local folder",
    )

    subparsers.add_parser(
        "profiles",
        help="list profiles",
        description="List profiles; * marks the one containing this directory.",
    )

    editor = subparsers.add_parser(
        "editor",
        help="choose the editor that open uses",
        usage="wpsync editor [obsidian|vscode]",
        description=(
            "Choose the Markdown editor that open uses, saved in "
            "~/.wpsync/config.json. Asks when no editor is named."
        ),
    )
    editor.add_argument(
        "name",
        nargs="?",
        choices=list(Editor),
        metavar="obsidian|vscode",
        help="the editor",
    )

    create = subparsers.add_parser(
        "create",
        help="start a new post file",
        usage=(
            "wpsync create [FILE] [-t TITLE] [-s SLUG] [-o]\n"
            "       wpsync PROFILE create [FILE] [-t TITLE] [-s SLUG] [-o]"
        ),
        description=(
            "Start a private post under content/. Set its status to public when push "
            "should publish it. A post may stay untitled."
        ),
    )
    create.add_argument(
        "file",
        nargs="?",
        metavar="FILE",
        help="file name under content/; the date and time when omitted",
    )
    create.add_argument("-t", "--title", default="", help="the post's title")
    create.add_argument(
        "-o", "--open", action="store_true", help="open the new file in your editor"
    )
    create.add_argument(
        "-s", "--slug", help="the post's address; WordPress assigns one when omitted"
    )

    ls = subparsers.add_parser(
        "ls",
        help="list local posts and how many issues each has",
        usage="wpsync ls [-l]\n       wpsync PROFILE ls [-l]",
        description=(
            "List the post files in this profile without contacting the blog. On a "
            "terminal, lines are cut to fit instead of wrapping."
        ),
    )
    ls.add_argument(
        "-l",
        "--long",
        action="store_true",
        help="show each post's file and URL on their own lines",
    )

    show = subparsers.add_parser(
        "show",
        help="show one post's details and issues",
        usage="wpsync show ID|SLUG\n       wpsync PROFILE show ID|SLUG",
        description=(
            "Show a post's details and what is wrong with it, without contacting "
            "the blog. A title or file also selects a post."
        ),
    )
    show.add_argument("post", metavar="ID|SLUG", help="the post")

    open_parser = subparsers.add_parser(
        "open",
        help="open a post file in your editor",
        usage="wpsync open [ID|SLUG]\n       wpsync PROFILE open [ID|SLUG]",
        description=(
            "Open a post's file in the editor chosen with wpsync editor, asking "
            "first if none is chosen. A title or file also selects the post."
        ),
    )
    open_parser.add_argument(
        "post",
        nargs="?",
        metavar="ID|SLUG",
        help="the post; the one wpsync create just made when omitted",
    )

    diff = subparsers.add_parser(
        "diff",
        help="show what push would change",
        usage=(
            "wpsync diff [ID|SLUG] [-a] [-p]\n"
            "       wpsync PROFILE diff [ID|SLUG] [-a] [-p]"
        ),
        description=(
            "Show local changes and anything that would stop a push. Contacts the "
            "blog only for changed, new, or, with -p, deleted posts. A title or file "
            "also selects a post."
        ),
    )
    diff.add_argument(
        "post", nargs="?", metavar="ID|SLUG", help="one post; all when omitted"
    )
    diff.add_argument(
        "-a", "--all", action="store_true", help="also show unchanged posts"
    )
    diff.add_argument(
        "-p",
        "--prune",
        action="store_true",
        help="show what push -p would delete from the blog",
    )

    push = subparsers.add_parser(
        "push",
        help="send local posts to the blog",
        usage=(
            "wpsync push [ID|SLUG] [-p] [-y]\n"
            "       wpsync PROFILE push [ID|SLUG] [-p] [-y]"
        ),
        description=(
            "Create and update posts on the blog from changed local files. Publishes "
            "public posts and never sends private ones, except to turn a published "
            "post that became private into a draft. Deletes nothing unless -p is "
            "given. A title or file also selects a post; select a deleted file's "
            "post by its ID."
        ),
    )
    push.add_argument(
        "post", nargs="?", metavar="ID|SLUG", help="one post; all when omitted"
    )
    push.add_argument(
        "-p",
        "--prune",
        action="store_true",
        help="delete posts whose files were deleted, keeping them in .trash/",
    )
    push.add_argument(
        "-y", "--yes", action="store_true", help="answer yes to every question"
    )

    delete = subparsers.add_parser(
        "delete",
        help="delete a post from the blog, keeping it in .trash/",
        usage="wpsync delete ID|SLUG [-y]\n       wpsync PROFILE delete ID|SLUG [-y]",
        description=(
            "Delete a post from the blog for good, with the library images no other "
            "post or page uses, and move its file and images into the profile "
            "folder's .trash/, keeping their paths. Asks first. A title or file "
            "also selects the post."
        ),
    )
    delete.add_argument("post", metavar="ID|SLUG", help="the post")
    delete.add_argument(
        "-y", "--yes", action="store_true", help="delete without asking"
    )

    subparsers.add_parser(
        "trash",
        help="list the posts in .trash/",
        usage="wpsync trash\n       wpsync PROFILE trash",
        description="List deleted posts kept in .trash/, without contacting the blog.",
    )

    restore = subparsers.add_parser(
        "restore",
        help="bring a post back from .trash/",
        usage="wpsync restore ID|SLUG\n       wpsync PROFILE restore ID|SLUG",
        description=(
            "Move a post and its images from .trash/ back where they were, as a new "
            "post: the next push creates it on the blog. A title or file also "
            "selects the post."
        ),
    )
    restore.add_argument("post", metavar="ID|SLUG", help="the post")

    pull = subparsers.add_parser(
        "pull",
        help="bring posts from the blog into local files",
        usage="wpsync pull [ID|SLUG] [-y]\n       wpsync PROFILE pull [ID|SLUG] [-y]",
        description=(
            "Create and update local post files from the blog and download their "
            "images. Local edits are never overwritten without asking. A file also "
            "selects a post."
        ),
    )
    pull.add_argument(
        "post", nargs="?", metavar="ID|SLUG", help="one post; all when omitted"
    )
    pull.add_argument(
        "-y", "--yes", action="store_true", help="answer yes to every question"
    )
    return parser


def _resolve_profile(
    arguments: argparse.Namespace, configuration: Configuration
) -> tuple[str, Profile]:
    prefix = arguments.profile_prefix
    positional = getattr(arguments, "profile_name", None)
    if prefix is not None and positional is not None:
        raise ConfigurationError(
            "profile was specified both before the command and as an argument"
        )
    name = prefix or positional
    if name is None:
        active = configuration.profile_for_path(Path.cwd().resolve())
        if active is None:
            raise ConfigurationError(
                "current directory is not inside a mapped profile; prefix the "
                "command with a profile (wpsync PROFILE COMMAND)"
            )
        return active
    name = validate_profile_name(name)
    if name not in configuration.profiles:
        raise ConfigurationError(f"profile '{name}' does not exist")
    return name, configuration.profiles[name]


def _normalize_site(site: str) -> str:
    site = site.strip()
    if "://" not in site:
        site = f"https://{site}"
    url = httpx.URL(site)
    if url.scheme not in {"http", "https"} or not url.host:
        raise ConfigurationError(f"'{site}' is not an http or https address")
    return site


def _sign_in(client: WordPressClient, profile: Profile) -> list[str]:
    """Check the account can sync, and describe what limits it."""
    user = client.current_user()
    capabilities = user.get("capabilities", {})
    if not capabilities.get("edit_posts"):
        raise WordPressError(
            f"'{profile.username}' cannot edit posts on {profile.site}"
        )
    roles = ", ".join(user.get("roles", [])) or "no role"
    lines = [f"Signed in to {profile.site} as '{profile.username}' ({roles})."]
    if not capabilities.get("edit_others_posts"):
        lines.append(
            "Note: this account can edit only its own posts, so posts by other "
            "authors are not pulled."
        )
    if not capabilities.get("unfiltered_html"):
        lines.append(
            "Note: this account lacks unfiltered_html, so WordPress removes "
            "markup such as iframes and scripts from saved posts."
        )
    return lines


def _init(arguments: argparse.Namespace, session: _Session) -> str:
    name = validate_profile_name(arguments.profile_name)
    configuration = session.store.load()
    if name in configuration.profiles:
        raise ConfigurationError(f"profile '{name}' already exists")
    site = _normalize_site(arguments.site)
    api_root = discover_api_root(site, session.transport)
    password_env = (
        validate_environment_name(arguments.password_env)
        if arguments.password_env
        else default_password_env(name)
    )
    username = arguments.username or session.ask("WordPress username: ")
    if not username:
        raise ConfigurationError("a WordPress username is required")
    if arguments.local_root is not None:
        local_root = canonical_local_root(arguments.local_root)
    else:
        current = canonical_local_root(Path.cwd())
        if session.confirm(
            f"Map current directory '{current}' to {site}? [Y/n] ", default=True
        ):
            local_root = current
        else:
            supplied = session.ask("What local folder should be mapped instead? ")
            if not supplied:
                raise ConfigurationError("a local folder is required; use --local-root")
            local_root = canonical_local_root(supplied)
    configuration.check_root(name, local_root)
    configuration.add(name, Profile(site, api_root, username, password_env, local_root))
    session.store.save(configuration)
    step = "run wpsync pull"
    if not session.environ.get(password_env):
        step = f"set {password_env} to an Application Password, then {step}"
    return f"Created profile '{name}': '{local_root}' maps to {site}.\nNext: {step}."


def _map(arguments: argparse.Namespace, session: _Session) -> str:
    configuration = session.store.load()
    name, profile = _resolve_profile(arguments, configuration)
    local_root = canonical_local_root(arguments.local_root or Path.cwd())
    if local_root == profile.local_root:
        return f"Profile '{name}' already uses '{local_root}'."
    configuration.remap(name, local_root)
    prompt = (
        f"Change profile '{name}' local folder from '{profile.local_root}' "
        f"to '{local_root}'? [y/N] "
    )
    if not session.confirm(prompt, default=False):
        return f"Profile '{name}' is unchanged."
    session.store.save(configuration)
    return f"Mapped '{local_root}' to {profile.site}."


def _remove(arguments: argparse.Namespace, session: _Session) -> str:
    configuration = session.store.load()
    name, _ = _resolve_profile(arguments, configuration)
    del configuration.profiles[name]
    session.store.save(configuration)
    return f"Removed profile '{name}'. Local files and the blog are unchanged."


def _root(arguments: argparse.Namespace, session: _Session) -> str:
    _, profile = _resolve_profile(arguments, session.store.load())
    return os.fspath(profile.local_root)


def _profile(arguments: argparse.Namespace, session: _Session) -> str:
    configuration = session.store.load()
    if arguments.profile_prefix is None and arguments.profile_name is None:
        active = configuration.profile_for_path(Path.cwd().resolve())
        if active is None:
            return "No active profile. Use wpsync PROFILE COMMAND."
        name, profile = active
    else:
        name, profile = _resolve_profile(arguments, configuration)
    if not arguments.details:
        return name
    return "\n".join(
        (
            f"Profile '{name}':",
            f"  Site: {profile.site}",
            f"  REST API: {profile.api_root}",
            f"  Username: {profile.username}",
            f"  Password env: {profile.password_env}",
            f"  Local root: {profile.local_root}",
        )
    )


def _profiles(arguments: argparse.Namespace, session: _Session) -> str:
    configuration = session.store.load()
    if not configuration.profiles:
        return "No profiles configured."
    active = configuration.profile_for_path(Path.cwd().resolve())
    active_name = active[0] if active else None
    return "\n".join(
        f"{'*' if name == active_name else ' '} {name}"
        for name in sorted(configuration.profiles)
    )


def _use_color(stream: TextIO, environ: Mapping[str, str]) -> bool:
    if "NO_COLOR" in environ:
        return False
    is_terminal = getattr(stream, "isatty", None)
    return bool(is_terminal and is_terminal())


def _paint(text: str, color: bool) -> str:
    if not color:
        return text
    return "".join(
        f"{MARKER_COLORS[char]}{char}{RESET}" if char in MARKER_COLORS else char
        for char in text
    )


def _legend(session: _Session) -> str:
    color = _use_color(session.stdout, session.environ)
    lines = ["Diff legend:"]
    lines.extend(f"  {_paint(marker, color)}  {meaning}" for marker, meaning in LEGEND)
    lines.append("ls legend:")
    width = max(len(marker) for marker, _ in LS_LEGEND)
    lines.extend(f"  {marker:<{width}}  {meaning}" for marker, meaning in LS_LEGEND)
    return "\n".join(lines)


class _LazyRemote:
    """Connects to the blog only if a command turns out to need it."""

    def __init__(self, profile: Profile, session: _Session) -> None:
        self.profile = profile
        self.session = session
        self.client: WordPressClient | None = None

    def connect(self) -> WordPressClient:
        if self.client is None:
            self.client = WordPressClient(
                self.profile.api_root,
                self.profile.username,
                self.session.password(self.profile),
                self.session.transport,
            )
        return self.client

    def post_states(self, ids: list[str]) -> dict[str, RemoteState]:
        return self.connect().post_states(ids)

    def post_summaries(self) -> list[PostSummary]:
        return self.connect().post_summaries()

    def close(self) -> None:
        if self.client is not None:
            self.client.http.close()


def _profile_root(
    arguments: argparse.Namespace, session: _Session
) -> tuple[Profile, Path]:
    _, profile = _resolve_profile(arguments, session.store.load())
    base = profile.local_root if arguments.profile_prefix else Path.cwd().resolve()
    return profile, base


def _create(arguments: argparse.Namespace, session: _Session) -> str:
    profile, _ = _profile_root(arguments, session)
    root = profile.local_root
    slug = arguments.slug or ""
    if slug:
        users = [
            item.path
            for item in scan_documents(root)
            if item.document.post.slug == slug
        ]
        if users:
            raise SelectionError(f"slug '{slug}' is used by {users[0]}")
    if arguments.file is None:
        relative = _timestamp_file(root, datetime.now())
    else:
        relative = _new_file(arguments.file)
    path = root / relative
    if path.exists():
        raise SelectionError(f"{relative} already exists")
    write_document(path, Document(None, Post(title=arguments.title, slug=slug)))
    created = f"Created {relative} (private; set status: public to publish it)."
    if arguments.open:
        return f"{created}\n{_open_file(session, root, relative)}"
    return created


def _just_created(root: Path, now: datetime) -> PurePosixPath | None:
    """The newest post create named after the time, if made just now.

    The time in the file name is when create made it, so nothing is recorded;
    pulled posts and files renamed to a real name never match.
    """
    found = []
    for path in (root / CONTENT_DIR).glob("*.md"):
        match = TIMESTAMP_NAME.fullmatch(path.name)
        if match is None:
            continue
        made = datetime.strptime(match[1], TIMESTAMP_FORMAT)
        if timedelta(0) <= now - made <= JUST_CREATED:
            found.append((made, int(match[2] or 1), path.name))
    if not found:
        return None
    return PurePosixPath(CONTENT_DIR, max(found)[2])


def _timestamp_file(root: Path, now: datetime) -> PurePosixPath:
    """A free file name under the posts folder from the current time."""
    stem = now.strftime(TIMESTAMP_FORMAT)
    for name in (stem, *(f"{stem}-{n}" for n in range(2, 100))):
        relative = PurePosixPath(CONTENT_DIR, f"{name}.md")
        if not (root / relative).exists():
            return relative
    raise SelectionError(f"too many posts named {stem} in {CONTENT_DIR}/")


def _new_file(name: str) -> PurePosixPath:
    """A file under the posts folder from a chosen name."""
    stem = name.removesuffix(".md")
    if "/" not in stem:
        stem = re.sub(r"[^\w.-]+", "-", stem.casefold()).strip("-.")
    relative = PurePosixPath(CONTENT_DIR, f"{stem}.md")
    if not stem or ".." in relative.parts or PurePosixPath(stem).is_absolute():
        raise SelectionError(f"'{name}' does not make a file name")
    return relative


def _ls(arguments: argparse.Namespace, session: _Session) -> str:
    profile, _ = _profile_root(arguments, session)
    documents = scan_documents(profile.local_root)
    if not documents:
        return NO_POSTS

    def order(item):  # noqa: ANN001, ANN202
        post_id = item.document.post_id
        return (post_id is None, int(post_id) if post_id else 0, str(item.path))

    records = read_records(profile.local_root, profile.api_root)
    heading = "Title" if arguments.long else "Title (file)"
    now = datetime.now(UTC)
    rows = [("ID", "Public", "Issues", heading)]
    details: list[list[str]] = [[]]
    for item in sorted(documents, key=order):
        post = item.document.post
        post_id = item.document.post_id or "-"
        record = records.get(post_id)
        public = _public(post, now)
        title = post.title or "(no title)"
        missing = record.missing_files if record else ()
        issues = str(len(missing)) if missing else "-"
        if arguments.long:
            rows.append((post_id, public, issues, title))
            details.append([str(item.path), *([record.url] if record else [])])
        else:
            name = PurePosixPath(item.path).relative_to(CONTENT_DIR)
            rows.append((post_id, public, issues, f"{title} ({name})"))
            details.append([])
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    indent = " " * (sum(widths) + 6)
    lines = []
    for (post_id, public, issues, title), extra in zip(rows, details, strict=True):
        lines.append(
            f"{post_id:>{widths[0]}}  {public:<{widths[1]}}  "
            f"{issues:<{widths[2]}}  {title}"
        )
        lines.extend(indent + line for line in extra)
    is_terminal = getattr(session.stdout, "isatty", None)
    if is_terminal and is_terminal():
        columns = shutil.get_terminal_size().columns
        lines = [_fit(line, columns) for line in lines]
    return "\n".join(lines)


def _public(post: Post, now: datetime) -> str:
    """The Public column: a mark, before the date for a post not yet shown."""
    if post.status is not PostStatus.PUBLIC:
        return ""
    if post.date is None or post.date <= now:
        return "*"
    return f"*{post.date:%b} {post.date.day}, {post.date.year}"


def _cells(character: str) -> int:
    """How many terminal columns a character takes."""
    if unicodedata.category(character) in ("Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1


def _fit(line: str, columns: int) -> str:
    """Cut a line to the terminal's width, so that it does not wrap."""
    if sum(map(_cells, line)) <= columns:
        return line
    kept, used = [], 0
    for character in line:
        used += _cells(character)
        if used > columns - 1:
            break
        kept.append(character)
    return "".join(kept) + "…"


def _one_post(
    arguments: argparse.Namespace, session: _Session
) -> tuple[Profile, LocalDocument, dict[str, PostRecord]]:
    """The profile, the file of the post a command names, and the records."""
    profile, base = _profile_root(arguments, session)
    root = profile.local_root
    records = read_records(root, profile.api_root)
    selection = select(
        arguments.post, scan_documents(root), records, root=root, base=base
    )
    if not selection.documents:
        raise SelectionError(f"post {arguments.post} has no local file")
    return profile, selection.documents[0], records


def _show(arguments: argparse.Namespace, session: _Session) -> str:
    _, item, records = _one_post(arguments, session)
    post = item.document.post
    post_id = item.document.post_id
    record = records.get(post_id) if post_id else None
    missing = record.missing_files if record else ()
    fields = (
        ("ID", post_id or "-"),
        ("Title", post.title or "(no title)"),
        ("Slug", post.slug or "-"),
        ("Status", post.status.value),
        ("Date", post.date.isoformat() if post.date else "-"),
        ("Categories", ", ".join(post.categories) or "-"),
        ("Tags", ", ".join(post.tags) or "-"),
        ("File", str(item.path)),
        ("URL", record.url if record else "-"),
        ("Issues", str(len(missing)) if missing else "-"),
    )
    lines = [f"{name + ':':<12}{value}" for name, value in fields]
    lines.extend(f"  missing file: {url}" for url in missing)
    return "\n".join(lines)


def _diff(arguments: argparse.Namespace, session: _Session) -> str:
    profile, base = _profile_root(arguments, session)
    root = profile.local_root
    selection = select(
        arguments.post,
        scan_documents(root),
        read_records(root, profile.api_root),
        root=root,
        base=base,
    )
    remote = _LazyRemote(profile, session)
    try:
        result = compare(selection, remote, arguments.prune)
    finally:
        remote.close()
    if not result.entries:
        return NO_POSTS
    color = _use_color(session.stdout, session.environ)
    quiet = (Action.UNCHANGED, Action.PRIVATE)
    shown = [e for e in result.entries if arguments.all or e.action not in quiet]
    hidden = Counter(e.action for e in result.entries if e not in shown)
    width = max((len(e.post_id or "-") for e in shown), default=1)
    lines = [_entry_line(entry, color, width) for entry in shown]
    if not shown:
        lines.append("No local changes.")
    if hidden:
        counts = [
            f"{hidden[action]} {action.name.lower()}"
            for action in quiet
            if hidden[action]
        ]
        lines.append(f"Not shown: {', '.join(counts)} (-a to show)")
    lines.extend(f"Note: {note}" for note in result.notes)
    return "\n".join(lines)


def _entry_line(
    entry: DiffEntry, color: bool, width: int = 1, sides: bool = True
) -> str:
    marker = f"{entry.action} {entry.side or ' '}" if sides else entry.action.value
    marker = _paint(marker, color)
    detail = f"  {entry.detail}" if entry.detail else ""
    return f"{marker}  {entry.post_id or '-':>{width}}  {entry.path}{detail}"


def _pull_target(
    selector: str | None, documents: list[LocalDocument], root: Path, base: Path
) -> tuple[list[str] | None, str | None]:
    """The post IDs or slug a pull selector names; a slug may be remote only."""
    if selector is None:
        return None, None
    if selector.isdigit():
        return [selector], None
    if "/" in selector or selector.endswith(".md"):
        chosen = select(selector, documents, {}, root=root, base=base).documents
        post_id = chosen[0].document.post_id
        if post_id is None:
            raise SelectionError(
                f"{selector} is not linked to a post yet; push it first"
            )
        return [post_id], None
    local = [d for d in documents if d.document.post.slug == selector]
    if local and local[0].document.post_id:
        return [local[0].document.post_id], None
    return None, selector


def _open(arguments: argparse.Namespace, session: _Session) -> str:
    if arguments.post is not None:
        profile, item, _ = _one_post(arguments, session)
        return _open_file(session, profile.local_root, PurePosixPath(item.path))
    profile, _ = _profile_root(arguments, session)
    recent = _just_created(profile.local_root, datetime.now())
    if recent is None:
        minutes = int(JUST_CREATED.total_seconds() // 60)
        raise SelectionError(
            f"no post created in the last {minutes} minutes; "
            "name one: wpsync open ID|SLUG"
        )
    return _open_file(session, profile.local_root, recent)


def _open_file(session: _Session, root: Path, relative: PurePosixPath) -> str:
    configuration = session.store.load()
    editor = configuration.editor
    if editor is None:
        editor = _ask_editor(session)
        configuration.editor = editor
        session.store.save(configuration)
    session.launch(editor_command(editor, root, root / relative))
    return f"Opened {relative} in {editor.label}."


def _delete(arguments: argparse.Namespace, session: _Session) -> str:
    profile, item, records = _one_post(arguments, session)
    root = profile.local_root
    path = PurePosixPath(item.path)
    post_id = item.document.post_id
    record = records.get(post_id) if post_id else None
    if post_id is not None and record is None:
        raise SelectionError(
            f"{path} has id {post_id} but was never synced here; pull it first"
        )
    confirm = _confirmer(session, arguments.yes)
    declined = "Nothing deleted." + (
        "" if arguments.yes else " Rerun with --yes to delete it."
    )
    if record is None:
        if not confirm(f"{path} is not on WordPress. Move it to {TRASH_DIR}/?"):
            return declined
        deleted = delete_post(
            root, profile.api_root, None, None, path, item.document, on_disk=True
        )
        return f"Moved {path} to {deleted.trashed}."
    post_id = record.post_id
    lazy = _LazyRemote(profile, session)
    remote: WordPressRemote | None = None
    try:
        state = lazy.post_states([post_id]).get(post_id)
        title = item.document.post.title
        question = (
            f"Delete #{post_id} {title!r} from WordPress for good, with its "
            f"comments? The file moves to {TRASH_DIR}/."
        )
        if state is None:
            question = (
                f"#{post_id} is already gone from WordPress. "
                f"Move {path} to {TRASH_DIR}/?"
            )
        elif state.fingerprint != record.remote_fingerprint:
            question = (
                f"#{post_id} changed on WordPress since the last sync. {question}"
            )
        if not confirm(question):
            return declined
        if state is not None:
            remote = WordPressRemote(lazy.connect(), session.transport)
        deleted = delete_post(
            root, profile.api_root, remote, post_id, path, item.document, on_disk=True
        )
    finally:
        if remote is not None:
            remote.close()
        lazy.close()
    moved = f"moved {path} to {deleted.trashed}"
    if remote is None:
        return f"#{post_id} was already gone from WordPress; {moved}."
    images = ""
    if deleted.media:
        images = f", with {deleted.media} image{'s' * (deleted.media != 1)}"
    return f"Deleted #{post_id} from WordPress{images}; {moved}."


def _trash(arguments: argparse.Namespace, session: _Session) -> str:
    profile, _ = _profile_root(arguments, session)
    items = scan_trash(profile.local_root)
    if not items:
        return "The trash is empty."
    width = max(len("ID"), *(len(item.document.post_id or "-") for item in items))
    lines = [f"{'ID':>{width}}  Title (restores to)"]
    for item in items:
        post = item.document.post
        original = PurePosixPath(item.path).relative_to(TRASH_DIR)
        lines.append(
            f"{item.document.post_id or '-':>{width}}  "
            f"{post.title or '(no title)'} ({original})"
        )
    return "\n".join(lines)


def _restore(arguments: argparse.Namespace, session: _Session) -> str:
    profile, base = _profile_root(arguments, session)
    root = profile.local_root
    selection = select(arguments.post, scan_trash(root), {}, root=root, base=base)
    if not selection.documents:
        raise SelectionError(f"post {arguments.post} is not in the trash")
    item = selection.documents[0]
    original = restore_post(root, item)
    if item.document.post_id and item.document.post.status is PostStatus.PUBLIC:
        return f"Restored {original}; push puts it back on the blog."
    return f"Restored {original}."


def _editor(arguments: argparse.Namespace, session: _Session) -> str:
    editor = Editor(arguments.name) if arguments.name else _ask_editor(session)
    configuration = session.store.load()
    configuration.editor = editor
    session.store.save(configuration)
    return f"wpsync open now uses {editor.label}."


def _ask_editor(session: _Session) -> Editor:
    if not getattr(session.stdin, "isatty", lambda: False)():
        raise EditorError("no editor chosen; run wpsync editor obsidian|vscode")
    editors = list(Editor)
    print("Open posts with:", file=session.stdout)
    for number, editor in enumerate(editors, 1):
        print(f"  {number}) {editor.label}", file=session.stdout)
    other = len(editors) + 1
    print(f"  {other}) Other", file=session.stdout)
    while True:
        answer = session.ask(f"Choose 1-{other}: ")
        if not answer:
            raise EditorError("no editor chosen")
        if answer == str(other):
            raise EditorError("only Obsidian and VS Code are supported for now")
        if answer.isdigit() and 1 <= int(answer) < other:
            return editors[int(answer) - 1]


def _confirmer(session: _Session, yes: bool) -> Callable[[str], bool]:
    def confirm(question: str) -> bool:
        # Without a terminal nobody can answer, so the question counts as No.
        if yes:
            return True
        interactive = getattr(session.stdin, "isatty", lambda: False)()
        return interactive and session.confirm(f"{question} [y/N] ", default=False)

    return confirm


def _reporter(session: _Session) -> Callable[[DiffEntry], None]:
    color = _use_color(session.stdout, session.environ)

    def report(entry: DiffEntry) -> None:
        print(_entry_line(entry, color, sides=False), file=session.stdout, flush=True)

    return report


def _pull(arguments: argparse.Namespace, session: _Session) -> str:
    profile, base = _profile_root(arguments, session)
    root = profile.local_root
    yes = arguments.yes
    documents = scan_documents(root)
    ids, slug = _pull_target(arguments.post, documents, root, base)
    records = _follow_files(profile, documents)

    client = WordPressClient(
        profile.api_root, profile.username, session.password(profile), session.transport
    )
    remote = WordPressRemote(client, session.transport)
    try:
        account = _sign_in(client, profile)
        # Until something is pulled, say who signed in and what limits the account.
        if not records:
            print("\n".join(account), file=session.stdout, flush=True)
        puller = Puller(
            root,
            profile.api_root,
            remote,
            documents,
            records,
            read_media(root, profile.api_root),
            _confirmer(session, yes),
            _reporter(session),
        )
        result = puller.pull(ids=ids, slug=slug)
    finally:
        remote.close()
        client.http.close()
    summary = result.summary()
    if result.skipped and not yes:
        summary += " Rerun with --yes to accept the skipped changes."
    return summary


def _follow_files(
    profile: Profile, documents: list[LocalDocument]
) -> dict[str, PostRecord]:
    """The post records, with each path following its file if it moved."""
    root = profile.local_root
    paths = {
        item.document.post_id: PurePosixPath(item.path)
        for item in documents
        if item.document.post_id is not None
    }
    return follow_moves(
        root, profile.api_root, read_records(root, profile.api_root), paths
    )


def _push(arguments: argparse.Namespace, session: _Session) -> str:
    profile, base = _profile_root(arguments, session)
    root = profile.local_root
    documents = scan_documents(root)
    records = _follow_files(profile, documents)
    selection = select(arguments.post, documents, records, root=root, base=base)
    lazy = _LazyRemote(profile, session)
    opened: list[WordPressRemote] = []

    def connect() -> WordPressRemote:
        client = lazy.connect()
        account = _sign_in(client, profile)
        # Until something is synced, say who signed in and what limits the account.
        if not records:
            print("\n".join(account), file=session.stdout, flush=True)
        opened.append(WordPressRemote(client, session.transport))
        return opened[0]

    try:
        plan = compare(selection, lazy, arguments.prune)
        for note in plan.notes:
            print(f"Note: {note}", file=session.stdout, flush=True)
        pusher = Pusher(
            root,
            profile.api_root,
            connect,
            records,
            read_media(root, profile.api_root),
            _confirmer(session, arguments.yes),
            _reporter(session),
        )
        result = pusher.push(plan.entries)
    finally:
        for remote in opened:
            remote.close()
        lazy.close()
    summary = result.summary()
    if result.declined and not arguments.yes:
        summary += " Rerun with --yes to accept the skipped changes."
    return summary


HANDLERS = {
    "init": _init,
    "map": _map,
    "remove": _remove,
    "root": _root,
    "profile": _profile,
    "profiles": _profiles,
    "editor": _editor,
    "create": _create,
    "ls": _ls,
    "show": _show,
    "open": _open,
    "diff": _diff,
    "pull": _pull,
    "push": _push,
    "delete": _delete,
    "trash": _trash,
    "restore": _restore,
}


def run(
    argv: Sequence[str] | None = None,
    *,
    store: ConfigurationStore | None = None,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
    environ: Mapping[str, str] = os.environ,
    transport: httpx.BaseTransport | None = None,
    launch: Callable[[list[str]], None] = launch,
) -> int:
    parser = build_parser()
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        raw_arguments, profile_prefix = _resolve_invocation(raw_arguments)
    except ConfigurationError as error:
        parser.error(str(error))
    arguments = parser.parse_args(raw_arguments)
    arguments.profile_prefix = profile_prefix
    session = _Session(
        store or ConfigurationStore(), stdin, stdout, environ, transport, launch
    )
    if arguments.legend:
        if arguments.command is not None:
            parser.error("--legend cannot be combined with a command")
        print(_legend(session), file=stdout)
        return 0
    if arguments.command is None:
        parser.error("a command is required")
    try:
        message = HANDLERS[arguments.command](arguments, session)
    except (
        ConfigurationError,
        DocumentError,
        EditorError,
        SelectionError,
        StateError,
        TrashError,
        WordPressError,
    ) as error:
        print(f"wpsync: error: {error}", file=stderr)
        return 1
    print(message, file=stdout)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return run(argv)
