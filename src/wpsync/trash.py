"""WPSync's trash: deleted posts and their images, kept in the profile folder.

Deleting a post on the blog is permanent, since not every platform has a trash
of its own. The copy in `.trash/` keeps its path, so it still shows its images,
and restoring it brings it back as a new post that the next push creates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from wpsync.documents import (
    TRASH_DIR,
    Document,
    LocalDocument,
    scan_documents,
    write_document,
)
from wpsync.media import post_images
from wpsync.state import MediaRecord, read_media, write_state


class TrashError(Exception):
    """A post cannot be moved into or out of the trash."""


class DeleteRemote(Protocol):
    def delete_post(self, post_id: str) -> None:
        """Delete a post for good."""
        ...

    def delete_media(self, media_id: str) -> None:
        """Delete a library image for good."""
        ...

    def media_in_use(self, media: MediaRecord, post_id: str) -> bool:
        """Whether a post or page other than post_id shows the library image."""
        ...


@dataclass(frozen=True)
class Deleted:
    trashed: PurePosixPath
    """Where the post's file is now."""
    media: list[PurePosixPath]
    """Library images deleted from the blog."""


def delete_post(
    root: Path,
    api_root: str,
    remote: DeleteRemote | None,
    post_id: str | None,
    path: PurePosixPath,
    document: Document,
    on_disk: bool,
) -> Deleted:
    """Delete a post and the images only it shows, keeping both in the trash.

    The post and its library images are deleted from the blog when a remote is
    given; an image another post or page uses stays. A file already deleted
    locally is written to the trash from the document first.
    """
    shown_elsewhere = {
        image
        for item in scan_documents(root)
        if PurePosixPath(item.path) != path
        for image in post_images(PurePosixPath(item.path), item.document.post.body)
    }
    own = sorted(post_images(path, document.post.body) - shown_elsewhere)
    trashed = _free_path(root, PurePosixPath(TRASH_DIR) / path)
    if not on_disk:
        # Written before the blog loses the post, so a failure keeps a copy.
        (root / trashed).parent.mkdir(parents=True, exist_ok=True)
        write_document(root / trashed, document)
    deleted: list[MediaRecord] = []
    if remote is not None and post_id is not None:
        remote.delete_post(post_id)
        library = {record.path: record for record in read_media(root, api_root)}
        for image in own:
            record = library.get(image)
            if record is not None and not remote.media_in_use(record, post_id):
                remote.delete_media(record.media_id)
                deleted.append(record)
    if on_disk:
        _move(root, path, trashed)
    for image in own:
        target = PurePosixPath(TRASH_DIR) / image
        if (root / image).is_file() and not (root / target).exists():
            _move(root, image, target)
    if post_id is not None:
        with write_state(root, api_root) as state:
            state.forget(post_id)
            for record in deleted:
                state.forget_media(record.path)
    return Deleted(trashed, [record.path for record in deleted])


def restore_post(root: Path, item: LocalDocument) -> PurePosixPath:
    """Move a trashed post and its images back, as a post not on the blog yet."""
    trashed = PurePosixPath(item.path)
    original = trashed.relative_to(TRASH_DIR)
    if (root / original).exists():
        raise TrashError(f"{original} already exists; move it before restoring")
    document = item.document
    for image in post_images(trashed, document.post.body):
        if image.parts[0] != TRASH_DIR:
            continue
        target = image.relative_to(TRASH_DIR)
        if (root / image).is_file() and not (root / target).exists():
            _move(root, image, target)
    # The deleted post is gone for good, so push creates it again.
    (root / original).parent.mkdir(parents=True, exist_ok=True)
    write_document(root / original, Document(None, document.post, document.extra))
    (root / trashed).unlink()
    return original


def _free_path(root: Path, path: PurePosixPath) -> PurePosixPath:
    candidate = path
    number = 2
    while (root / candidate).exists():
        candidate = path.with_name(f"{path.stem}-{number}{path.suffix}")
        number += 1
    return candidate


def _move(root: Path, source: PurePosixPath, target: PurePosixPath) -> None:
    (root / target).parent.mkdir(parents=True, exist_ok=True)
    (root / source).rename(root / target)
