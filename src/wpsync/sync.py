"""Comparing local post files with their last synchronized state."""

from __future__ import annotations

import difflib
from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Generic, Protocol, TypeVar

from wpsync.documents import (
    CONTENT_DIR,
    FIELDS,
    LocalDocument,
    body_checksum,
    fields_checksum,
)
from wpsync.posts import ContentFormat, Post, PostStatus, PostSummary, RemoteState
from wpsync.state import PostRecord

C = TypeVar("C", bound="Candidate")


class SelectionError(ValueError):
    """Raised when a post selector matches no post or several."""


class Remote(Protocol):
    def post_states(self, ids: list[str]) -> dict[str, RemoteState]: ...

    def post_summaries(self) -> list[PostSummary]: ...


@dataclass(frozen=True)
class Selection:
    documents: list[LocalDocument]
    records: dict[str, PostRecord]


def select(
    selector: str | None,
    documents: list[LocalDocument],
    records: dict[str, PostRecord],
    *,
    root: Path,
    base: Path,
) -> Selection:
    """Narrow to one post chosen by post ID, file, slug, or title.

    A file name without a folder is looked for under the current directory
    first, then in every folder under content/.
    """
    if selector is None:
        return Selection(documents, records)
    if selector.isdigit():
        chosen = [item for item in documents if item.document.post_id == selector]
        if chosen or selector in records:
            record = {selector: records[selector]} if selector in records else {}
            return Selection(chosen, record)
        raise SelectionError(f"no local post has id {selector}")
    if "/" in selector:
        chosen = _at_path(selector, documents, root, base)
        if not chosen:
            raise SelectionError(f"{selector} is not a post file under {CONTENT_DIR}/")
    elif selector.endswith(".md"):
        chosen = _at_path(selector, documents, root, base) or [
            item for item in documents if PurePosixPath(item.path).name == selector
        ]
        if not chosen:
            raise SelectionError(f"no post file is named {selector}")
    else:
        title = selector.casefold()
        chosen = (
            [item for item in documents if item.document.post.slug == selector]
            or [item for item in documents if PurePosixPath(item.path).stem == selector]
            or [
                item
                for item in documents
                if item.document.post.title.casefold() == title
            ]
        )
        if not chosen:
            raise SelectionError(
                f"no local post has slug, file name, or title '{selector}'"
            )
    if len(chosen) > 1:
        paths = ", ".join(str(item.path) for item in chosen)
        raise SelectionError(f"'{selector}' matches {paths}")
    post_id = chosen[0].document.post_id
    record = {post_id: records[post_id]} if post_id in records else {}
    return Selection(chosen, record)


def _at_path(
    selector: str, documents: list[LocalDocument], root: Path, base: Path
) -> list[LocalDocument]:
    path = (base / selector).resolve()
    try:
        relative = PurePosixPath(path.relative_to(root).as_posix())
    except ValueError as error:
        raise SelectionError(f"{selector} is outside the profile folder") from error
    return [item for item in documents if PurePosixPath(item.path) == relative]


class Candidate(Protocol):
    @property
    def id(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def slug(self) -> str: ...


@dataclass(frozen=True)
class Match(Generic[C]):
    """How a post relates to the posts on the other side.

    Only a shared slug identifies the same post. A shared title is reported so
    the user can avoid a duplicate, but titles need not be unique.
    """

    post: C | None
    """The one post with the same slug."""
    candidates: tuple[C, ...] = ()
    """Several posts with the same slug; none is chosen."""
    same_title: tuple[C, ...] = ()
    """Other posts with the same title."""


def match_post(post: Post, candidates: Sequence[C]) -> Match[C]:
    by_slug = tuple(c for c in candidates if post.slug and c.slug == post.slug)
    title = post.title.strip()
    same_title = tuple(
        c for c in candidates if title and c.title.strip() == title and c not in by_slug
    )
    if len(by_slug) > 1:
        return Match(None, by_slug, same_title)
    return Match(by_slug[0] if by_slug else None, (), same_title)


class Action(StrEnum):
    NEW = "+"
    CHANGED = "~"
    DELETED = "-"
    CONFLICT = "?"
    UNCHANGED = "="
    PRIVATE = "x"


@dataclass(frozen=True)
class PushStep:
    """What a push does for one post."""

    document: LocalDocument
    target: str | None = None
    """The post to update; a new post is created when None."""
    content: bool = True
    fields: bool = True
    unpublish: bool = False
    question: str | None = None
    """What to ask first, for anything that could overwrite or duplicate a post."""


@dataclass(frozen=True)
class TrashStep:
    """What a pruning push does for a post whose file was deleted."""

    target: str
    gone: bool = False
    """The post is already off WordPress, so only its record is dropped."""
    question: str | None = None


@dataclass(frozen=True)
class DiffEntry:
    action: Action
    side: str
    """'l' when the difference is local, 'r' when remote, blank for both."""
    post_id: str | None
    path: PurePosixPath
    detail: str = ""
    step: PushStep | TrashStep | None = None
    """None when a push leaves the post alone."""


@dataclass(frozen=True)
class Diff:
    entries: list[DiffEntry]
    notes: list[str]


def _local_changes(document: LocalDocument, record: PostRecord) -> list[str]:
    post = document.document.post
    changes = []
    if body_checksum(post) != record.body_checksum:
        changes.append("content")
    if fields_checksum(post) != record.fields_checksum:
        changes.append("details")
    return changes


def _typo_notes(document: LocalDocument) -> list[str]:
    notes = []
    for key in document.document.extra_keys:
        close = difflib.get_close_matches(key, FIELDS, n=1, cutoff=0.75)
        if close:
            notes.append(
                f"{document.path}: '{key}' is not synced; did you mean '{close[0]}'?"
            )
    return notes


def compare(selection: Selection, remote: Remote, prune: bool = False) -> Diff:
    """Classify the selected posts, contacting the remote only when needed.

    With prune, a post whose file was deleted is moved to the trash.
    """
    entries: list[DiffEntry] = []
    changed: dict[str, tuple[LocalDocument, list[str]]] = {}
    unlinked: list[LocalDocument] = []
    new: list[LocalDocument] = []
    notes: list[str] = []
    present = set()
    for document in selection.documents:
        notes.extend(_typo_notes(document))
        post_id = document.document.post_id
        path = PurePosixPath(document.path)
        private = document.document.post.status is PostStatus.PRIVATE
        if post_id is not None:
            present.add(post_id)
        record = selection.records.get(post_id) if post_id else None
        if private and record is None:
            entries.append(DiffEntry(Action.PRIVATE, "l", post_id, path, "private"))
            continue
        if post_id is None:
            new.append(document)
            continue
        if record is None:
            unlinked.append(document)
            continue
        changes = _local_changes(document, record)
        if changes:
            changed[post_id] = (document, changes)
        else:
            entries.append(DiffEntry(Action.UNCHANGED, "", post_id, path))
    deleted = [
        record
        for post_id, record in selection.records.items()
        if post_id not in present
    ]
    if not prune:
        entries.extend(
            DiffEntry(
                Action.DELETED,
                "l",
                record.post_id,
                record.path,
                "deleted locally; WordPress keeps the post",
            )
            for record in deleted
        )
        deleted = []

    ids = sorted(
        {
            *changed,
            *(d.document.post_id for d in unlinked),
            *(record.post_id for record in deleted),
        },
        key=int,
    )
    states = remote.post_states(ids) if ids else {}  # type: ignore[arg-type]
    entries.extend(
        _trash_entry(record, states.get(record.post_id)) for record in deleted
    )
    for post_id, (document, changes) in changed.items():
        record = selection.records[post_id]
        state = states.get(post_id)
        path = PurePosixPath(document.path)
        detail = ", ".join(changes)
        unpublish = document.document.post.status is PostStatus.PRIVATE
        if unpublish:
            # Push sends nothing for a private post except unpublishing it.
            if state is None or not state.published:
                entries.append(
                    DiffEntry(Action.PRIVATE, "l", post_id, path, f"{detail}; private")
                )
                continue
            detail = "unpublish; becomes a draft on WordPress"
        if state is None:
            entries.append(
                DiffEntry(
                    Action.CONFLICT,
                    "",
                    post_id,
                    path,
                    f"{detail}; deleted on WordPress",
                )
            )
        elif state.fingerprint != record.remote_fingerprint:
            step = _update_step(document, post_id, changes, unpublish)
            question = (
                f"#{post_id} {path} changed locally and on WordPress. "
                "Replace WordPress's version with your file?"
            )
            entries.append(
                DiffEntry(
                    Action.CONFLICT,
                    "",
                    post_id,
                    path,
                    f"{detail}; also changed on WordPress since the last sync",
                    replace(step, question=question),
                )
            )
        else:
            if (
                "content" in changes
                and not unpublish
                and state.format is ContentFormat.BLOCKS
            ):
                detail += "; block post becomes plain HTML on push"
            step = _update_step(document, post_id, changes, unpublish)
            entries.append(DiffEntry(Action.CHANGED, "l", post_id, path, detail, step))
    for document in unlinked:
        post_id = document.document.post_id
        exists = post_id in states
        detail = (
            "linked to a post that was never synced here"
            if exists
            else "linked to a post that is not on WordPress"
        )
        path = PurePosixPath(document.path)
        step = None
        if exists:
            question = (
                f"{path} has id {post_id} but was never synced here. "
                "Replace that post with your file?"
            )
            step = PushStep(document, target=post_id, question=question)
        entries.append(DiffEntry(Action.CONFLICT, "", post_id, path, detail, step))
    if new:
        summaries = remote.post_summaries()
        for document in new:
            entries.append(_new_entry(document, summaries))
    entries = [_require_title(entry) for entry in entries]
    entries.sort(key=lambda entry: str(entry.path))
    return Diff(entries, notes)


def _trash_entry(record: PostRecord, state: RemoteState | None) -> DiffEntry:
    post_id, path = record.post_id, record.path
    if state is None:
        return DiffEntry(
            Action.DELETED,
            "l",
            post_id,
            path,
            "deleted locally and on WordPress",
            TrashStep(post_id, gone=True),
        )
    if state.fingerprint != record.remote_fingerprint:
        question = (
            f"#{post_id} {path} was deleted locally but changed on WordPress. "
            "Move the post to the trash anyway?"
        )
        return DiffEntry(
            Action.CONFLICT,
            "",
            post_id,
            path,
            "deleted locally; changed on WordPress since the last sync",
            TrashStep(post_id, question=question),
        )
    return DiffEntry(
        Action.DELETED,
        "l",
        post_id,
        path,
        "deleted locally; push -p moves the post to the trash",
        TrashStep(post_id),
    )


def _require_title(entry: DiffEntry) -> DiffEntry:
    """A post push would publish or update cannot go without a title."""
    step = entry.step
    if (
        not isinstance(step, PushStep)
        or step.unpublish
        or step.document.document.post.title.strip()
    ):
        return entry
    return replace(
        entry, action=Action.CONFLICT, detail="no title; push needs one", step=None
    )


def _update_step(
    document: LocalDocument, post_id: str, changes: list[str], unpublish: bool
) -> PushStep:
    if unpublish:
        return PushStep(
            document, target=post_id, content=False, fields=False, unpublish=True
        )
    return PushStep(
        document,
        target=post_id,
        content="content" in changes,
        fields="details" in changes,
    )


def _new_entry(document: LocalDocument, summaries: Sequence[PostSummary]) -> DiffEntry:
    path = PurePosixPath(document.path)
    match = match_post(document.document.post, summaries)
    if match.candidates:
        listed = ", ".join(f"#{post.id} {post.title!r}" for post in match.candidates)
        return DiffEntry(
            Action.CONFLICT, "l", None, path, f"same slug as several posts: {listed}"
        )
    if match.post is not None:
        detail = f"same slug as #{match.post.id} {match.post.title!r}"
        question = (
            f"{path} has the same slug as #{match.post.id} {match.post.title!r}. "
            "Replace that post with your file?"
        )
        step = PushStep(document, target=match.post.id, question=question)
        return DiffEntry(Action.CONFLICT, "l", None, path, detail, step)
    detail = "new post"
    question = None
    if match.same_title:
        listed = ", ".join(f"#{p.id}" for p in match.same_title)
        detail += f"; same title as {listed}"
        question = f"{path} has the same title as {listed}. Create another post?"
    step = PushStep(document, question=question)
    return DiffEntry(Action.NEW, "l", None, path, detail, step)
