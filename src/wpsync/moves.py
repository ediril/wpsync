"""Following post files that moved: their records and their image paths.

A post is its ID; its record's path is only where its file was last seen. A
moved file's relative image paths are rewritten to name the same images from
its new place before the move is recorded, since the previous place is known
only until then.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from wpsync.documents import LocalDocument, body_checksum, write_document
from wpsync.markup.markdown import replace_image_sources
from wpsync.media import moved_sources
from wpsync.state import PostRecord, write_state


@dataclass(frozen=True)
class Move:
    """A post file found somewhere other than where it was."""

    path: PurePosixPath
    previous: PurePosixPath
    images: int
    """How many image sources were rewritten."""
    problem: str = ""
    """Why the image sources could not be rewritten."""


@dataclass(frozen=True)
class Followed:
    documents: list[LocalDocument]
    """The post files, with rewritten image sources."""
    records: dict[str, PostRecord]
    """The records, each at its file's current path."""
    moves: list[Move]
    """The moves recorded or made, with their image sources rewritten."""


def follow_moves(
    root: Path,
    api_root: str,
    documents: list[LocalDocument],
    records: dict[str, PostRecord],
    *,
    scope: set[str] | None = None,
    previous: Mapping[PurePosixPath, PurePosixPath] | None = None,
    save: bool = True,
) -> Followed:
    """Record the moved files of the posts in scope, all when None.

    The image sources of each are rewritten first. A record whose file was
    unedited apart from the move keeps it unedited, so the rewrite is not
    taken for a change. Posts out of scope follow their files only in the
    returned records, keeping their previous place for a later command.
    previous gives where files moved by the caller were, posts with no record
    included. Without save, nothing is written: the result previews it.
    """
    previous = previous or {}
    records = dict(records)
    followed, moves, saved = [], [], []
    for item in documents:
        path = PurePosixPath(item.path)
        post_id = item.document.post_id
        record = records.get(post_id) if post_id else None
        # Where the file was: moved by the caller, or last recorded, or both.
        before = [
            place
            for place in (previous.get(path), record.path if record else None)
            if place is not None and place != path
        ]
        if not before:
            followed.append(item)
            continue
        if path not in previous and scope is not None and post_id not in scope:
            records[post_id] = replace(record, path=path)  # type: ignore[arg-type,index]
            followed.append(item)
            continue
        moved, move = _rebase(root, item, before, save)
        followed.append(moved)
        moves.append(move)
        if record is not None:
            unedited = record.body_checksum == body_checksum(item.document.post)
            checksum = body_checksum(moved.document.post)
            records[post_id] = replace(  # type: ignore[index]
                record,
                path=path,
                body_checksum=checksum if unedited else record.body_checksum,
            )
            saved.append(records[post_id])  # type: ignore[index]
    if saved and save:
        with write_state(root, api_root) as state:
            for record in saved:
                state.save(record)
    return Followed(followed, records, moves)


def _rebase(
    root: Path, item: LocalDocument, previous: list[PurePosixPath], save: bool
) -> tuple[LocalDocument, Move]:
    path = PurePosixPath(item.path)
    post = item.document.post
    sources = moved_sources(root, previous, path, post.body)
    if not sources:
        return item, Move(path, previous[0], 0)
    body = replace_image_sources(post.body, sources)
    if body is None:
        problem = "its image paths could not be updated for the move; fix them by hand"
        return item, Move(path, previous[0], 0, problem)
    document = replace(item.document, post=replace(post, body=body))
    if save:
        write_document(root / item.path, document)
    return LocalDocument(item.path, document), Move(path, previous[0], len(sources))
