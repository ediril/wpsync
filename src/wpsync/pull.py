"""Bringing posts from the platform into local files."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import Protocol

from wpsync.documents import (
    CONTENT_DIR,
    Document,
    LocalDocument,
    body_checksum,
    display_path,
    fields_checksum,
    parse_document,
    serialize_document,
)
from wpsync.markup.markdown import image_sources
from wpsync.media import Media, MediaLibrary, MissingImage, PostMedia, image_path
from wpsync.posts import Conversion, FetchedPost, Post, UnrepresentableContent
from wpsync.state import MediaRecord, PostRecord, write_state
from wpsync.storage import write_atomic, write_text_atomic
from wpsync.sync import Action, Outcome, SelectionError, match_post


class PullRemote(Protocol):
    def fetch_posts(
        self, ids: list[str] | None = None, slug: str | None = None
    ) -> list[FetchedPost]: ...

    def convert(self, post: FetchedPost, media: Media) -> Conversion: ...

    def download(self, url: str) -> bytes: ...

    def available(self, url: str) -> bool: ...


@dataclass(frozen=True)
class _LocalCandidate:
    """A local file without a post ID, as a match candidate."""

    id: str
    title: str
    slug: str
    document: LocalDocument


@dataclass
class PullResult:
    changes: int = 0
    """Post files and images written."""
    missing_files: int = 0
    skipped: int = 0
    declined: int = 0
    """Skipped posts that answering yes would have pulled."""
    deleted_locally: list[str] = field(default_factory=list)
    deleted_remotely: list[str] = field(default_factory=list)

    def summary(self) -> str:
        tail = ""
        if self.missing_files:
            missing = self.missing_files
            tail += f"; {missing} file{'s' * (missing != 1)} missing from the blog"
        if self.skipped:
            tail += f"; {self.skipped} skipped"
        if self.changes:
            changes = f"{self.changes} change{'s' * (self.changes != 1)}"
            lines = [f"Pull complete: {changes}{tail}."]
        else:
            lines = [f"  Nothing to pull{tail}."]
        for heading, paths in (
            ("Deleted locally, not restored:", self.deleted_locally),
            ("Deleted on WordPress, local files kept:", self.deleted_remotely),
        ):
            if paths:
                lines.append(heading)
                lines.extend(f"  {display_path(path)}" for path in paths)
        return "\n".join(lines)


class Puller:
    def __init__(
        self,
        root: Path,
        api_root: str,
        remote: PullRemote,
        documents: list[LocalDocument],
        records: dict[str, PostRecord],
        media: list[MediaRecord],
        confirm: Callable[[str], bool],
        report: Callable[[Outcome], None],
        started: Callable[[int], None],
        advanced: Callable[[], None],
    ) -> None:
        self.root = root
        self.api_root = api_root
        self.remote = remote
        self.records = records
        self.confirm = confirm
        self.report = report
        self.started = started
        self.advanced = advanced
        self.library = MediaLibrary(root, media)
        self.documents = {
            d.document.post_id: d for d in documents if d.document.post_id
        }
        self.unlinked = [
            _LocalCandidate(str(d.path), d.document.post.title, d.document.post.slug, d)
            for d in documents
            if d.document.post_id is None
        ]
        self.taken = {PurePosixPath(d.path) for d in documents}
        self.result = PullResult()

    def pull(self, ids: list[str] | None = None, slug: str | None = None) -> PullResult:
        fetched = self.remote.fetch_posts(ids=ids, slug=slug)
        if not fetched and (ids or slug):
            named = f"slug '{slug}'" if slug else f"id {ids[0]}"  # type: ignore[index]
            raise SelectionError(f"WordPress has no post with {named}")
        self.started(len(fetched))
        for post in fetched:
            self._pull_post(post)
            self.advanced()
        if ids is None and slug is None:
            present = {post.id for post in fetched}
            for post_id, record in sorted(
                self.records.items(), key=lambda r: int(r[0])
            ):
                if post_id not in present and post_id in self.documents:
                    path = str(self.documents[post_id].path)
                    self.result.deleted_remotely.append(path)
        return self.result

    def _pull_post(self, post: FetchedPost) -> None:
        document = self.documents.get(post.id)
        record = self.records.get(post.id)
        if record is not None and document is None:
            self.result.deleted_locally.append(str(record.path))
            return
        if record is not None and document is not None:
            self._pull_tracked(post, document, record)
        elif document is not None:
            self._pull_unrecorded(post, document)
        else:
            self._pull_new(post)

    def _pull_tracked(
        self, post: FetchedPost, document: LocalDocument, record: PostRecord
    ) -> None:
        local = document.document.post
        changed_locally = (
            body_checksum(local) != record.body_checksum
            or fields_checksum(local) != record.fields_checksum
        )
        if post.state.fingerprint == record.remote_fingerprint:
            self._refresh(post, record)
            return
        path = PurePosixPath(document.path)
        if changed_locally and not self.confirm(
            f"#{post.id} {path} changed locally and on WordPress. "
            "Replace your file with WordPress's version?"
        ):
            self._decline(path)
            return
        self._write(post, path, document.document, Action.CHANGED)

    def _refresh(self, post: FetchedPost, record: PostRecord) -> None:
        """Bring an unchanged post's address and missing files up to date."""
        missing = tuple(url for url in record.missing_files if not self._is_back(url))
        self.result.missing_files += len(missing)
        current = replace(record, url=post.url, missing_files=missing)
        if current != record:
            with write_state(self.root, self.api_root) as state:
                state.save(current)

    def _is_back(self, url: str) -> bool:
        """Whether a missing file is on the server again, saving it if an image."""
        if url not in self.library.by_url:
            return self.remote.available(url)
        image = self.library.at_url(url)
        if image.checksum:
            return True
        try:
            data = self.remote.download(url)
        except MissingImage:
            return False
        # A file put there by hand since is the user's: it stays, and differs
        # from the checksum as any edited image does.
        if not (self.root / image.path).exists():
            write_atomic(self.root / image.path, data, mode=0o644)
        restored = replace(image, checksum=hashlib.sha256(data).hexdigest())
        self.library.add(restored)
        with write_state(self.root, self.api_root) as state:
            state.save_media(restored)
        self._report(Action.NEW, image.path)
        return True

    def _pull_unrecorded(self, post: FetchedPost, document: LocalDocument) -> None:
        path = PurePosixPath(document.path)
        question = (
            f"{path} has id {post.id} but was never synced here. "
            "Replace it with WordPress's version?"
        )
        self._link(post, path, document.document, Action.CHANGED, question)

    def _pull_new(self, post: FetchedPost) -> None:
        match = match_post(post.post, self.unlinked)
        if match.candidates:
            files = ", ".join(c.id for c in match.candidates)
            self._fail(f"#{post.id}", f"same slug as several local files: {files}")
            return
        if match.post is not None:
            candidate = match.post
            question = (
                f"WordPress post #{post.id} {post.post.title!r} has the same slug "
                f"as {candidate.id}. Link them and replace the file with "
                "WordPress's version?"
            )
            if self._link(
                post,
                PurePosixPath(candidate.id),
                candidate.document.document,
                Action.NEW,
                question,
            ):
                self.unlinked.remove(candidate)
            return
        path = self._new_path(post)
        self.taken.add(path)
        self._write(post, path, Document(post.id, post.post), Action.NEW)

    def _link(
        self,
        post: FetchedPost,
        path: PurePosixPath,
        document: Document,
        action: Action,
        question: str,
    ) -> bool:
        """Link a file to a post, asking only if WordPress's version changes it."""
        conversion = self._convert(post, path)
        if conversion is None:
            return False
        remote = replace(post.post, body=conversion.markdown.strip("\n"))
        if document.post_id == post.id and remote == document.post:
            # The file is untouched, but the images it shows may not be there yet.
            images, missing = self._save_media(path, conversion)
            self._record(post, path, document, images, missing)
            return True
        if not _only_fills_in(document.post, remote) and not self.confirm(question):
            for download in self.library.take_pending():
                self.library.release(download)
            self._decline(path)
            return False
        return self._write(post, path, document, action, conversion)

    def _new_path(self, post: FetchedPost) -> PurePosixPath:
        for name in (post.name, f"{post.name}-{post.id}"):
            path = PurePosixPath(CONTENT_DIR) / f"{name}.md"
            if path not in self.taken and not (self.root / path).exists():
                return path
        raise ValueError(f"no free file name for post {post.id}")

    def _write(
        self,
        post: FetchedPost,
        path: PurePosixPath,
        existing: Document,
        action: Action,
        conversion: Conversion | None = None,
    ) -> bool:
        if conversion is None:
            conversion = self._convert(post, path)
            if conversion is None:
                return False
        images, missing = self._save_media(path, conversion)
        written = Document(
            post.id,
            replace(post.post, body=conversion.markdown.strip("\n")),
            existing.extra,
        )
        write_text_atomic(self.root / path, serialize_document(written), mode=0o644)
        self._record(post, path, written, images, missing)
        self._report(action, path)
        return True

    def _save_media(
        self, path: PurePosixPath, conversion: Conversion
    ) -> tuple[list[MediaRecord], list[str]]:
        """Save the images a converted post shows, and report missing files."""
        used = {
            image
            for source in image_sources(conversion.markdown)
            if (image := image_path(path, source)) is not None
        }
        # Download first, so a failure leaves nothing of this post behind.
        files = []
        for download in self.library.take_pending():
            if download.path not in used:
                self.library.release(download)
                continue
            existing = self.root / download.path
            if existing.is_file():
                # A file at the image's own upload path is this image, saved
                # by an earlier pull whose record is gone.
                files.append((download, existing.read_bytes(), False))
                continue
            try:
                files.append((download, self.remote.download(download.url), True))
            except MissingImage:
                files.append((download, None, True))
        pages_gone = [
            url for url in conversion.embedded_pages if not self.remote.available(url)
        ]
        images = []
        for download, data, fresh in files:
            checksum = ""
            if data is not None:
                if fresh:
                    write_atomic(self.root / download.path, data, mode=0o644)
                    self._report(Action.NEW, download.path)
                checksum = hashlib.sha256(data).hexdigest()
            image = MediaRecord(
                download.path, checksum, download.media_id, download.url, download.size
            )
            self.library.add(image)
            images.append(image)
        shown = [self.library.by_path.get(image) for image in sorted(used)]
        missing = [
            record.url for record in shown if record and not record.checksum
        ] + pages_gone
        self.result.missing_files += len(missing)
        return images, missing

    def _convert(self, post: FetchedPost, path: PurePosixPath) -> Conversion | None:
        try:
            return self.remote.convert(post, PostMedia(self.library, path))
        except UnrepresentableContent as error:
            for download in self.library.take_pending():
                self.library.release(download)
            self._fail(str(path), str(error))
            return None

    def _record(
        self,
        post: FetchedPost,
        path: PurePosixPath,
        document: Document,
        images: list[MediaRecord],
        missing: list[str],
    ) -> None:
        # Checksums describe the file as it reads back, exactly as diff will see it.
        written = parse_document(serialize_document(document)).post
        with write_state(self.root, self.api_root) as state:
            for image in images:
                state.save_media(image)
            state.save(
                PostRecord(
                    post.id,
                    path,
                    body_checksum(written),
                    fields_checksum(written),
                    post.state.fingerprint,
                    post.state.format,
                    post.url,
                    tuple(missing),
                )
            )

    def _report(self, action: Action, path: PurePosixPath) -> None:
        self.result.changes += 1
        self.report(Outcome(action, str(path)))

    def _decline(self, path: PurePosixPath) -> None:
        self.result.skipped += 1
        self.result.declined += 1
        self.report(Outcome(Action.CONFLICT, str(path)))

    def _fail(self, label: str, reason: str) -> None:
        self.result.skipped += 1
        self.report(Outcome(Action.CONFLICT, label, reason))


def _only_fills_in(local: Post, remote: Post) -> bool:
    """Whether a post differs from a file only in fields the file leaves empty.

    The title and content never count as empty: an untitled or blank file
    sharing a slug with a post is more likely meant as a new post.
    """
    filled = replace(
        local,
        slug=local.slug or remote.slug,
        date=local.date or remote.date,
        categories=local.categories or remote.categories,
        tags=local.tags or remote.tags,
    )
    return filled == remote
