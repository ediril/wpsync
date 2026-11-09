"""Sending local posts to the platform."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import cached_property
from pathlib import Path, PurePosixPath
from typing import Protocol

from wpsync.documents import (
    Document,
    LocalDocument,
    body_checksum,
    fields_checksum,
    parse_document,
    serialize_document,
    write_document,
)
from wpsync.markup.markdown import image_sources
from wpsync.media import Media, MediaImage, MediaLibrary, PostMedia, image_path
from wpsync.posts import ContentFormat, Conversion, FetchedPost, Post
from wpsync.state import MediaRecord, PostRecord, write_state
from wpsync.sync import Action, DeleteStep, DiffEntry, PushStep, Remote
from wpsync.trash import DeleteRemote, delete_post


class PushRemote(Remote, DeleteRemote, Protocol):
    def fetch_posts(self, ids: list[str]) -> list[FetchedPost]: ...

    def convert(self, post: FetchedPost, media: Media) -> Conversion: ...

    def render(self, markdown: str, media: Media) -> str: ...

    def upload(self, name: str, data: bytes) -> MediaImage: ...

    def missing_terms(self, post: Post) -> list[str]:
        """Descriptions of the post's categories and tags the platform lacks."""
        ...

    def save(
        self,
        post_id: str | None,
        post: Post,
        content: str | None,
        fields: bool,
        unpublish: bool,
    ) -> FetchedPost: ...

    def keeps_display(self, sent: str, stored: str) -> bool:
        """Whether the platform stored content that displays as it was sent."""
        ...


class _CannotSend(Exception):
    """A post that cannot be sent as it stands, which does not stop the others."""


@dataclass
class PushResult:
    new: int = 0
    updated: int = 0
    deleted: int = 0
    images: int = 0
    skipped: int = 0
    declined: int = 0
    """Skipped posts that answering yes would have sent."""

    def summary(self) -> str:
        pushed = self.new + self.updated + self.deleted
        if not pushed:
            skipped = f"; {self.skipped} skipped" if self.skipped else ""
            return f"Nothing to push{skipped}."
        counts = (
            (self.new, "new"),
            (self.updated, "updated"),
            (self.deleted, "deleted"),
        )
        parts = [f"{count} {label}" for count, label in counts if count]
        line = f"Pushed {pushed} post{'s' * (pushed != 1)}"
        line += f" ({', '.join(parts)})" if parts else ""
        if self.images:
            line += f", {self.images} image{'s' * (self.images != 1)}"
        if self.skipped:
            line += f"; {self.skipped} skipped"
        return line + "."


class Pusher:
    def __init__(
        self,
        root: Path,
        api_root: str,
        connect: Callable[[], PushRemote],
        records: dict[str, PostRecord],
        media: list[MediaRecord],
        confirm: Callable[[str], bool],
        report: Callable[[DiffEntry], None],
    ) -> None:
        self.root = root
        self.api_root = api_root
        self.connect = connect
        self.records = records
        self.library = MediaLibrary(root, media)
        self.confirm = confirm
        self.report = report
        self.result = PushResult()

    @cached_property
    def remote(self) -> PushRemote:
        return self.connect()

    def push(self, entries: list[DiffEntry]) -> PushResult:
        for entry in entries:
            if isinstance(entry.step, DeleteStep):
                self._delete(entry, entry.step)
            elif entry.step is not None:
                self._send(entry, entry.step)
            elif entry.action is Action.CONFLICT:
                self._skip(entry, entry.detail)
        return self.result

    def _send(self, entry: DiffEntry, step: PushStep) -> None:
        document = step.document
        post = document.document.post
        path = PurePosixPath(document.path)
        if step.question and not self.confirm(step.question):
            self._decline(entry, entry.detail)
            return
        if step.target and step.content and self._is_block_post(step.target):
            question = (
                f"{entry.path} updates a block post, which becomes plain HTML. "
                "Continue?"
            )
            if not self.confirm(question):
                self._decline(entry, "block post would become plain HTML")
                return
        missing = self.remote.missing_terms(post) if step.fields else []
        if missing and not self.confirm(
            f"{entry.path} needs {', '.join(missing)}. Create on WordPress?"
        ):
            self._decline(entry, "needs " + ", ".join(missing))
            return
        try:
            uploaded = self._upload_images(path, post.body) if step.content else 0
        except _CannotSend as error:
            self._skip(entry, str(error))
            return
        media = PostMedia(self.library, path)
        content = self.remote.render(post.body, media) if step.content else None
        saved = self.remote.save(
            step.target, post, content, step.fields, step.unpublish
        )
        self._record(step, document, saved, content)
        self.result.images += uploaded
        self._report_sent(entry, step, saved, content, uploaded)

    def _delete(self, entry: DiffEntry, step: DeleteStep) -> None:
        if step.question and not self.confirm(step.question):
            self._decline(entry, entry.detail)
            return
        self.records.pop(step.target, None)
        fetched = [] if step.gone else self.remote.fetch_posts([step.target])
        if not fetched:
            with write_state(self.root, self.api_root) as state:
                state.forget(step.target)
            self.result.deleted += 1
            self.report(
                DiffEntry(
                    Action.DELETED,
                    "",
                    step.target,
                    entry.path,
                    "already gone from WordPress",
                )
            )
            return
        post = fetched[0]
        # The trash keeps the blog's version, since the local file is gone.
        conversion = self.remote.convert(post, PostMedia(self.library, entry.path))
        for download in self.library.take_pending():
            self.library.release(download)
        copy = Document(
            post.id, replace(post.post, body=conversion.markdown.strip("\n"))
        )
        deleted = delete_post(
            self.root,
            self.api_root,
            self.remote,
            post.id,
            entry.path,
            copy,
            on_disk=False,
        )
        self.result.deleted += 1
        detail = "deleted; kept in .trash/"
        if deleted.media:
            detail += f"; {deleted.media} image{'s' * (deleted.media != 1)} deleted"
        self.report(DiffEntry(Action.DELETED, "", post.id, entry.path, detail))

    def _is_block_post(self, post_id: str) -> bool:
        state = self.remote.post_states([post_id]).get(post_id)
        return state is not None and state.format is ContentFormat.BLOCKS

    def _upload_images(self, post: PurePosixPath, body: str) -> int:
        """Upload the local images a body shows that the media table lacks."""
        uploaded = 0
        for source in sorted(image_sources(body)):
            path = image_path(post, source)
            if path is None:
                continue
            if path.is_absolute() or ".." in path.parts:
                raise _CannotSend(f"image {source} is outside the profile folder")
            known = self.library.by_path.get(path)
            file = self.root / path
            if not file.is_file():
                # A media row without a file is an image missing from the blog
                # too: its library markup is all there is to send.
                if known is not None:
                    continue
                raise _CannotSend(f"image not found: {source}")
            data = file.read_bytes()
            checksum = hashlib.sha256(data).hexdigest()
            if known is not None and known.checksum in ("", checksum):
                continue
            image = self.remote.upload(path.name, data)
            record = MediaRecord(path, checksum, image.id, image.url, image.size)
            self.library.add(record)
            # Saved at once, so a failure below cannot upload it twice.
            with write_state(self.root, self.api_root) as state:
                state.save_media(record)
            uploaded += 1
        return uploaded

    def _record(
        self,
        step: PushStep,
        document: LocalDocument,
        saved: FetchedPost,
        content: str | None,
    ) -> None:
        current = document.document
        post = current.post
        if step.fields:
            # What the platform decided becomes the file's, as a pull would write.
            post = replace(
                post,
                slug=saved.post.slug or post.slug,
                date=post.date or saved.post.date,
                categories=saved.post.categories,
                tags=saved.post.tags,
            )
        written = Document(saved.id, post, current.extra)
        if written != current:
            write_document(self.root / document.path, written)
        reread = parse_document(serialize_document(written)).post
        previous = self.records.get(saved.id)
        # A body push did not send must still count as unsent next time.
        body = body_checksum(reread)
        if previous is not None and content is None:
            body = previous.body_checksum
        missing = previous.missing_files if previous else ()
        if content is not None:
            missing = tuple(url for url in missing if url in content)
        record = PostRecord(
            saved.id,
            PurePosixPath(document.path),
            body,
            fields_checksum(reread),
            saved.state.fingerprint,
            saved.state.format,
            saved.url,
            missing,
        )
        self.records[saved.id] = record
        with write_state(self.root, self.api_root) as state:
            state.save(record)

    def _report_sent(
        self,
        entry: DiffEntry,
        step: PushStep,
        saved: FetchedPost,
        content: str | None,
        uploaded: int,
    ) -> None:
        details = []
        if uploaded:
            details.append(f"{uploaded} image{'s' * (uploaded != 1)}")
        wanted = step.document.document.post.slug
        if step.fields and wanted and saved.post.slug != wanted:
            details.append(f"WordPress set the slug to {saved.post.slug}")
        if content is not None and not self.remote.keeps_display(
            content, saved.content
        ):
            details.append("WordPress changed the content; check the post")
        if step.unpublish:
            details.append("now a draft on WordPress")
        if step.target is None:
            self.result.new += 1
            details.append(saved.url)
            action = Action.NEW
        else:
            self.result.updated += 1
            action = Action.CHANGED
        self.report(DiffEntry(action, "", saved.id, entry.path, "; ".join(details)))

    def _decline(self, entry: DiffEntry, detail: str) -> None:
        self.result.declined += 1
        self._skip(entry, detail)

    def _skip(self, entry: DiffEntry, detail: str) -> None:
        self.result.skipped += 1
        self.report(DiffEntry(Action.CONFLICT, "", entry.post_id, entry.path, detail))
