"""WordPress posts in WPSync's platform-neutral form."""

from __future__ import annotations

import mimetypes
import re
from datetime import UTC, tzinfo
from typing import Any
from urllib.parse import quote, unquote, urlsplit

import httpx

from wpsync.media import Media, MediaImage, MissingImage
from wpsync.posts import (
    Conversion,
    FetchedPost,
    Post,
    PostStatus,
    PostSummary,
    RemoteState,
)
from wpsync.state import MediaRecord
from wpsync.wordpress.client import (
    FINGERPRINT_FIELDS,
    HEADERS,
    SYNCED_STATUSES,
    TIMEOUT,
    WordPressClient,
    WordPressError,
    display_title,
    local_status,
    parse_gmt,
    remote_state,
    request,
)
from wpsync.wordpress.content import render_html, same_display, to_markdown

PULL_FIELDS = FINGERPRINT_FIELDS + ",generated_slug,link"


class WordPressRemote:
    """Reads posts and media from one WordPress site."""

    def __init__(
        self, client: WordPressClient, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.client = client
        # Images are often served from another host, so this client never
        # carries the site's credentials.
        self.downloads = httpx.Client(
            headers=HEADERS, timeout=TIMEOUT, follow_redirects=True, transport=transport
        )
        self._timezone: tzinfo | None = None
        self._terms: dict[str, dict[int, str]] = {}
        self._featured: set[str] | None = None

    def close(self) -> None:
        self.downloads.close()

    def fetch_posts(
        self, ids: list[str] | None = None, slug: str | None = None
    ) -> list[FetchedPost]:
        return [
            self._fetched(post)
            for post in self.client.posts(PULL_FIELDS, ids=ids, slug=slug)
        ]

    def convert(self, post: FetchedPost, media: Media) -> Conversion:
        return to_markdown(post.content, media)

    def download(self, url: str) -> bytes:
        response = request(self.downloads, "GET", url)
        if response.status_code in (404, 410):
            raise MissingImage(url)
        if response.is_error:
            raise WordPressError(
                f"could not download {url} (HTTP {response.status_code})"
            )
        # Some servers answer a missing file with a web page and a 200.
        if not response.headers.get("content-type", "").startswith("image/"):
            raise MissingImage(url)
        return response.content

    def available(self, url: str) -> bool:
        response = request(self.downloads, "GET", url)
        if response.status_code in (404, 410):
            return False
        if response.is_error:
            raise WordPressError(f"could not check {url} (HTTP {response.status_code})")
        return True

    def post_states(self, ids: list[str]) -> dict[str, RemoteState]:
        return self.client.post_states(ids)

    def post_summaries(self) -> list[PostSummary]:
        return self.client.post_summaries()

    def render(self, markdown: str, media: Media) -> str:
        return render_html(markdown, media)

    def upload(self, name: str, data: bytes) -> MediaImage:
        media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
        headers = {
            "Content-Type": media_type,
            "Content-Disposition": f'attachment; filename="{quote(name)}"',
        }
        image = self.client.post("wp/v2/media", content=data, headers=headers).json()
        large = image.get("media_details", {}).get("sizes", {}).get("large")
        if large:
            return MediaImage(str(image["id"]), large["source_url"], "large")
        return MediaImage(str(image["id"]), image["source_url"], "full")

    def missing_terms(self, post: Post) -> list[str]:
        return [
            f"{label} '{name}'"
            for taxonomy, label, names in (
                ("categories", "category", post.categories),
                ("tags", "tag", post.tags),
            )
            for name in names
            if self._term_id(taxonomy, name) is None
        ]

    def save(
        self,
        post_id: str | None,
        post: Post,
        content: str | None,
        fields: bool,
        unpublish: bool,
    ) -> FetchedPost:
        body: dict[str, Any] = {}
        if content is not None:
            body["content"] = content
        if fields:
            body["title"] = post.title
            body["status"] = "publish" if post.status is PostStatus.PUBLIC else "draft"
            body["categories"] = self._term_ids("categories", post.categories)
            body["tags"] = self._term_ids("tags", post.tags)
            if post.slug:
                body["slug"] = post.slug
            if post.date:
                body["date_gmt"] = post.date.astimezone(UTC).strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
        if unpublish:
            body["status"] = "draft"
        route = "wp/v2/posts" + (f"/{post_id}" if post_id else "")
        params = {"context": "edit", "_fields": PULL_FIELDS}
        return self._fetched(self.client.post(route, params, json=body).json())

    def delete_post(self, post_id: str) -> None:
        # force skips WordPress's own trash: WPSync keeps the copy in .trash/.
        self.client.delete(f"wp/v2/posts/{post_id}", {"force": "true"})

    def delete_media(self, media_id: str) -> None:
        self.client.delete(f"wp/v2/media/{media_id}", {"force": "true"})

    def media_in_use(self, media: MediaRecord, post_id: str) -> bool:
        # WordPress marks an image it inserts with its library ID; images added
        # by hand are found by their file path, in any of the image's sizes.
        for term in (f"wp-image-{media.media_id}", _upload_stem(media.url)):
            for route in ("wp/v2/posts", "wp/v2/pages"):
                found = self.client.get_all(
                    route,
                    {
                        "search": term,
                        "status": SYNCED_STATUSES,
                        "context": "edit",
                        "_fields": "id",
                    },
                )
                if any(str(item["id"]) != post_id for item in found):
                    return True
        return media.media_id in self._featured_media()

    def _featured_media(self) -> set[str]:
        """The library images posts and pages show as their featured image."""
        if self._featured is None:
            self._featured = {
                str(item["featured_media"])
                for route in ("wp/v2/posts", "wp/v2/pages")
                for item in self.client.get_all(
                    route,
                    {
                        "status": SYNCED_STATUSES,
                        "context": "edit",
                        "_fields": "id,featured_media",
                    },
                )
                if item.get("featured_media")
            }
        return self._featured

    def keeps_display(self, sent: str, stored: str) -> bool:
        return same_display(sent, stored)

    def _term_id(self, taxonomy: str, name: str) -> int | None:
        wanted = name.casefold()
        for term_id, term_name in self._term_names(taxonomy).items():
            if term_name.casefold() == wanted:
                return term_id
        return None

    def _term_ids(self, taxonomy: str, names: tuple[str, ...]) -> list[int]:
        ids = []
        for name in names:
            term_id = self._term_id(taxonomy, name)
            if term_id is None:
                term_id = self.client.create_term(taxonomy, name)
                self._term_names(taxonomy)[term_id] = name
            ids.append(term_id)
        return ids

    def _fetched(self, post: dict[str, Any]) -> FetchedPost:
        if self._timezone is None:
            self._timezone = self.client.site_timezone()
        names = {
            taxonomy: self._term_names(taxonomy) for taxonomy in ("categories", "tags")
        }
        fields = Post(
            title=display_title(post),
            slug=unquote(post["slug"]),
            date=parse_gmt(post["date_gmt"]).astimezone(self._timezone),
            status=local_status(post["status"]),
            categories=tuple(
                sorted({names["categories"][i] for i in post["categories"]})
            ),
            tags=tuple(sorted({names["tags"][i] for i in post["tags"]})),
        )
        return FetchedPost(
            str(post["id"]),
            fields,
            post["content"]["raw"],
            remote_state(post),
            _file_stem(post),
            post["link"],
        )

    def _term_names(self, taxonomy: str) -> dict[int, str]:
        if taxonomy not in self._terms:
            self._terms[taxonomy] = self.client.term_names(taxonomy)
        return self._terms[taxonomy]


def _upload_stem(url: str) -> str:
    """An image's upload path without its size suffix, matching every size."""
    path = unquote(urlsplit(url).path)
    path = path.split("/uploads/", 1)[-1]
    return re.sub(r"(-\d+x\d+|-scaled)?\.\w+$", "", path)


def _file_stem(post: dict[str, Any]) -> str:
    slug = unquote(post["slug"] or post.get("generated_slug") or "")
    slug = re.sub(r"[/\\:\x00]", "-", slug).strip(".-")
    return slug or f"post-{post['id']}"
