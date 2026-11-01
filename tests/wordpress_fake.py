"""A fake WordPress REST API and CLI helpers shared by the tests."""

import base64
import io
import json
import re

import httpx

from wpsync.cli import run
from wpsync.config import Profile

SITE = "https://blog.test"
PASSWORD = "abcd efgh ijkl mnop"


class FakeWordPress:
    """Serves the REST API responses wpsync reads, as WordPress shapes them."""

    def __init__(
        self,
        post_count=3,
        rest_route=False,
        can_edit=True,
        can_edit_others=True,
        advertises_api=True,
    ):
        self.rest_route = rest_route
        self.can_edit_others = can_edit_others
        self.advertises_api = advertises_api
        self.can_edit = can_edit
        self.requests = []
        self.broken_uploads = {}
        self.saved = []
        """The JSON body of each post create or update, in order."""
        self.uploads = []
        self.rewrite_content = lambda content: content
        """Stands in for filters such as kses, which change what WordPress stores."""
        self.posts = [
            {
                "id": number,
                "title": {"raw": f"Post {number}"},
                "content": {"raw": f"<p>Body {number}</p>"},
                "slug": f"post-{number}",
                "link": f"https://blog.test/post-{number}/",
                "status": "publish" if number % 2 else "draft",
                "date_gmt": f"2026-01-{number % 28 + 1:02d}T10:00:00",
                "categories": [1],
                "tags": [],
            }
            for number in range(1, post_count + 1)
        ]

    categories = {1: "News", 2: "Travel"}
    tags = {5: "python"}

    def post(self, post_id):
        return next(post for post in self.posts if post["id"] == int(post_id))

    @property
    def api_root(self):
        return f"{SITE}/?rest_route=/" if self.rest_route else f"{SITE}/wp-json/"

    def route(self, request):
        if self.rest_route:
            return request.url.params.get("rest_route")
        prefix = "/wp-json"
        path = request.url.path
        return path[len(prefix) :] if path.startswith(prefix + "/") else None

    def write(self, route, request):
        if route == "/wp/v2/media":
            self.uploads.append(request.headers["Content-Disposition"])
            media_id = 900 + len(self.uploads)
            base = "https://blog.test/wp-content/uploads/uploaded"
            return httpx.Response(
                201,
                json={
                    "id": media_id,
                    "source_url": f"{base}-{media_id}.png",
                    "media_details": {
                        "sizes": {
                            "large": {"source_url": f"{base}-{media_id}-1024x768.png"}
                        }
                    },
                },
            )
        if route in ("/wp/v2/categories", "/wp/v2/tags"):
            terms = self.categories if route.endswith("categories") else self.tags
            term_id = max(terms, default=0) + 10
            terms[term_id] = json.loads(request.content)["name"]
            return httpx.Response(201, json={"id": term_id})
        body = json.loads(request.content)
        self.saved.append(body)
        if route == "/wp/v2/posts":
            post = {
                "id": max((p["id"] for p in self.posts), default=0) + 1,
                "title": {"raw": ""},
                "content": {"raw": ""},
                "slug": "",
                "status": "draft",
                "date_gmt": "2026-02-01T10:00:00",
                "categories": [1],
                "tags": [],
            }
            self.posts.append(post)
        else:
            post = self.post(route.rsplit("/", 1)[1])
        for key, value in body.items():
            if key in ("title", "content"):
                post[key] = {"raw": value}
            elif key in ("categories", "tags"):
                post[key] = value or post[key]
            else:
                post[key] = value
        post["content"]["raw"] = self.rewrite_content(post["content"]["raw"])
        slug = post["slug"] or re.sub(r"\W+", "-", post["title"]["raw"].lower()).strip(
            "-"
        )
        taken = {p["slug"] for p in self.posts if p is not post}
        post["slug"] = f"{slug}-2" if slug in taken else slug
        post["link"] = f"https://blog.test/{post['slug']}/"
        return httpx.Response(200, json=post)

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path.startswith("/wp-content/uploads/"):
            if request.url.path in self.broken_uploads:
                return httpx.Response(
                    self.broken_uploads[request.url.path],
                    headers={"Content-Type": "text/html"},
                    text="<html></html>",
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "image/jpeg"},
                content=b"image:" + request.url.path.encode(),
            )
        route = self.route(request)
        if request.method == "POST":
            return self.write(route, request)
        if route is None or not self.advertises_api:
            link = f'<{self.api_root}>; rel="https://api.w.org/"'
            headers = {"Link": link} if self.advertises_api else {}
            return httpx.Response(200, headers=headers, text="<html></html>")
        expected = "Basic " + base64.b64encode(f"emrah:{PASSWORD}".encode()).decode()
        if request.headers.get("Authorization") != expected:
            return httpx.Response(
                401,
                json={
                    "code": "incorrect_password",
                    "message": (
                        "The provided password is an invalid application password."
                    ),
                },
            )
        if route == "/wp/v2/users/me":
            return httpx.Response(
                200,
                json={
                    "roles": ["administrator"],
                    "capabilities": {
                        "edit_posts": self.can_edit,
                        "edit_others_posts": self.can_edit_others,
                        "unfiltered_html": True,
                    },
                },
            )
        if route == "/":
            return httpx.Response(
                200, json={"timezone_string": "Europe/Istanbul", "gmt_offset": 3}
            )
        if route in ("/wp/v2/categories", "/wp/v2/tags"):
            terms = self.categories if route.endswith("categories") else self.tags
            return httpx.Response(
                200,
                json=[{"id": i, "name": n} for i, n in terms.items()],
                headers={"X-WP-TotalPages": "1"},
            )
        if route == "/wp/v2/posts":
            per_page = int(request.url.params["per_page"])
            page = int(request.url.params["page"])
            posts = self.posts
            if "include" in request.url.params:
                wanted = {int(i) for i in request.url.params["include"].split(",")}
                posts = [post for post in posts if post["id"] in wanted]
            if "slug" in request.url.params:
                posts = [p for p in posts if p["slug"] == request.url.params["slug"]]
            pages = max(1, -(-len(posts) // per_page))
            chunk = posts[(page - 1) * per_page : page * per_page]
            return httpx.Response(
                200, json=chunk, headers={"X-WP-TotalPages": str(pages)}
            )
        return httpx.Response(
            404, json={"code": "rest_no_route", "message": "No route"}
        )


class Terminal(io.StringIO):
    def isatty(self):
        return True


def invoke(
    arguments, store, *, stdin="", wordpress=None, password=PASSWORD, stdout=None
):
    stdout, stderr = stdout or io.StringIO(), io.StringIO()
    status = run(
        arguments,
        store=store,
        stdin=stdin if hasattr(stdin, "readline") else io.StringIO(stdin),
        stdout=stdout,
        stderr=stderr,
        environ={"MYBLOG_WP_PASSWORD": password} if password else {},
        transport=httpx.MockTransport(wordpress or FakeWordPress()),
    )
    return status, stdout.getvalue(), stderr.getvalue()


def add_profile(store, name, root):
    configuration = store.load()
    configuration.add(
        name,
        Profile(
            SITE, f"{SITE}/wp-json/", "emrah", "MYBLOG_WP_PASSWORD", root.resolve()
        ),
    )
    store.save(configuration)
