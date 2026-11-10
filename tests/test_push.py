import re

from wordpress_fake import FakeWordPress, add_profile, invoke

IMAGE = "https://blog.test/wp-content/uploads/2026/01/sunset-1024x768.jpg"


def run(store, wordpress, *arguments):
    return invoke(["myblog", *arguments], store, wordpress=wordpress)


def write_post(root, name, header, body="Text."):
    path = root / "content" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{header}---\n\n{body}\n")
    return path


def pulled_blog(tmp_path, store):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)
    run(store, wordpress, "pull")
    wordpress.requests.clear()
    return wordpress, tmp_path / "content/post-1.md"


def test_an_untitled_post_publishes_and_keeps_its_id_through_a_rename_and_title(
    tmp_path, store
):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)

    status, output, _ = invoke(
        ["myblog", "create"], store, wordpress=wordpress, password=None
    )
    assert status == 0
    [path] = (tmp_path / "content").glob("*.md")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{4}\.md", path.name)
    assert output == (
        f"Created content/{path.name} (private; set status: public to publish it).\n"
    )
    assert path.read_text() == (
        "---\ntitle: ''\nstatus: private\ncategories: []\ntags: []\n---\n"
    )

    _, output, _ = invoke(["myblog", "push"], store, wordpress=wordpress, password=None)
    assert output == "Nothing to push.\n"
    assert wordpress.requests == []

    path.write_text(path.read_text().replace("private", "public") + "\nFirst *post*.\n")
    status, output, errors = run(store, wordpress, "push")

    assert (status, errors) == (0, "")
    assert output.splitlines()[1:] == [
        f"+  3  content/{path.name}  https://blog.test/3/",
        "Pushed 1 post (1 new).",
    ]
    assert wordpress.saved == [
        {
            "content": "<p>First <em>post</em>.</p>",
            "title": "",
            "status": "publish",
            "categories": [],
            "tags": [],
        }
    ]
    assert path.read_text() == (
        "---\n"
        "id: 3\n"
        "title: ''\n"
        "slug: '3'\n"
        "date: 2026-02-01T13:00:00+03:00\n"
        "status: public\n"
        "categories:\n"
        "- News\n"
        "tags: []\n"
        "---\n"
        "\n"
        "First *post*.\n"
    )

    renamed = path.with_name("first.md")
    path.rename(renamed)
    renamed.write_text(renamed.read_text().replace("title: ''", "title: First"))
    _, output, _ = run(store, wordpress, "push")
    assert output == "~  3  content/first.md\nPushed 1 post (1 updated).\n"
    assert wordpress.post(3)["title"]["raw"] == "First"
    assert len(wordpress.posts) == 3

    wordpress.requests.clear()
    _, output, _ = run(store, wordpress, "diff")
    assert output.startswith("No local changes.")
    assert wordpress.requests == []


def test_a_renamed_file_keeps_its_post_when_a_new_file_takes_its_old_name(
    tmp_path, store
):
    wordpress, first = pulled_blog(tmp_path, store)
    first.rename(first.with_name("renamed.md"))
    write_post(tmp_path, "post-1.md", "title: New one\nstatus: public\n")

    _, output, _ = run(store, wordpress, "push")
    assert output.splitlines()[-1] == "Pushed 1 post (1 new)."

    _, output, _ = run(store, wordpress, "diff", "-a")
    assert output.splitlines() == [
        "=    3  content/post-1.md",
        "=    2  content/post-2.md",
        "=    1  content/renamed.md",
    ]


def test_create_takes_a_title_and_slug_and_never_overwrites(tmp_path, store):
    add_profile(store, "myblog", tmp_path)

    status, output, _ = invoke(
        ["myblog", "create", "notes/a", "-t", "Long title", "-s", "short"],
        store,
        password=None,
    )
    assert status == 0
    text = (tmp_path / "content/notes/a.md").read_text()
    assert "title: Long title\nslug: short\n" in text

    for arguments, message in (
        (["other", "-s", "short"], "slug 'short' is used by content/notes/a.md"),
        (["notes/a.md"], "content/notes/a.md already exists"),
        (["../a"], "'../a' does not make a file name"),
        (["!!!"], "'!!!' does not make a file name"),
    ):
        status, _, errors = invoke(
            ["myblog", "create", *arguments], store, password=None
        )
        assert status == 1
        assert message in errors


def test_a_new_file_with_a_taken_slug_is_never_created_and_updates_only_on_yes(
    tmp_path, store
):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)
    path = write_post(
        tmp_path, "mine.md", "title: Mine\nslug: post-1\nstatus: public\n"
    )

    status, output, _ = run(store, wordpress, "push")

    assert status == 0
    assert output.splitlines()[-2:] == [
        "?  -  content/mine.md  same slug as #1 'Post 1'",
        "Nothing to push; 1 skipped. Rerun with --yes to accept the skipped changes.",
    ]
    assert wordpress.saved == []
    assert "id:" not in path.read_text()

    _, output, _ = run(store, wordpress, "push", "-y")

    assert "~  1  content/mine.md" in output
    assert len(wordpress.posts) == 2
    assert wordpress.post(1)["content"]["raw"] == "<p>Text.</p>"
    assert path.read_text().startswith("---\nid: 1\n")


def test_a_shared_title_needs_a_yes_before_creating_a_duplicate(tmp_path, store):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)
    write_post(tmp_path, "mine.md", "title: Post 1\nslug: other\nstatus: public\n")

    _, output, _ = run(store, wordpress, "push")
    assert "?  -  content/mine.md  new post; same title as #1" in output
    assert wordpress.saved == []

    _, output, _ = run(store, wordpress, "push", "--yes")
    assert "+  3  content/mine.md" in output


def test_a_slug_wordpress_changes_is_reported_and_written_back(tmp_path, store):
    wordpress = FakeWordPress(post_count=1)
    add_profile(store, "myblog", tmp_path)
    path = write_post(tmp_path, "mine.md", "title: Mine\nslug: mine\nstatus: public\n")
    original = wordpress.write

    def sanitize(route, request):
        response = original(route, request)
        wordpress.posts[-1]["slug"] = "mine-renamed"
        response._content = response.content.replace(b'"mine"', b'"mine-renamed"')
        return response

    wordpress.write = sanitize
    _, output, _ = run(store, wordpress, "push")

    assert "WordPress set the slug to mine-renamed" in output
    assert "slug: mine-renamed\n" in path.read_text()


def test_an_update_sends_only_the_side_of_the_file_that_changed(tmp_path, store):
    wordpress, path = pulled_blog(tmp_path, store)

    path.write_text(path.read_text().replace("title: Post 1", "title: Renamed"))
    _, output, _ = run(store, wordpress, "push")
    assert output.splitlines()[-2:] == [
        "~  1  content/post-1.md",
        "Pushed 1 post (1 updated).",
    ]
    assert "content" not in wordpress.saved[-1]
    assert wordpress.saved[-1]["title"] == "Renamed"

    path.write_text(path.read_text().replace("Body 1", "New body"))
    run(store, wordpress, "push")
    assert wordpress.saved[-1] == {"content": "<p>New body</p>"}

    wordpress.saved.clear()
    _, output, _ = run(store, wordpress, "push")
    assert output == "Nothing to push.\n"
    assert wordpress.saved == []


def test_a_change_on_both_sides_or_to_a_block_post_needs_a_yes(tmp_path, store):
    wordpress, path = pulled_blog(tmp_path, store)
    path.write_text(path.read_text().replace("Body 1", "Mine"))
    wordpress.post(1)["title"]["raw"] = "Changed there"

    _, output, _ = run(store, wordpress, "push")
    assert "also changed on WordPress since the last sync" in output
    assert wordpress.saved == []
    run(store, wordpress, "pull", "1", "--yes")

    wordpress.post(1)["content"]["raw"] = (
        "<!-- wp:paragraph -->\n<p>Block</p>\n<!-- /wp:paragraph -->"
    )
    run(store, wordpress, "pull", "1", "--yes")
    path.write_text(path.read_text().replace("Block", "Edited"))

    _, output, _ = run(store, wordpress, "push")
    assert "?  1  content/post-1.md  block post would become plain HTML" in output
    assert wordpress.saved == []

    _, output, _ = run(store, wordpress, "push", "-y")
    assert wordpress.saved == [{"content": "<p>Edited</p>"}]


def test_a_private_post_becomes_a_draft_and_later_republishes_with_unsent_edits(
    tmp_path, store
):
    wordpress, path = pulled_blog(tmp_path, store)
    path.write_text(
        path.read_text()
        .replace("status: public", "status: private")
        .replace("Body 1", "Edited while private")
    )

    _, output, _ = run(store, wordpress, "push")

    assert "~  1  content/post-1.md  now a draft on WordPress" in output
    assert wordpress.saved == [{"status": "draft"}]
    assert wordpress.post(1)["content"]["raw"] == "<p>Body 1</p>"

    wordpress.saved.clear()
    _, output, _ = run(store, wordpress, "push")
    assert output == "Nothing to push.\n"
    assert wordpress.saved == []

    path.write_text(path.read_text().replace("status: private", "status: public"))
    run(store, wordpress, "push")

    assert wordpress.post(1)["status"] == "publish"
    assert wordpress.post(1)["content"]["raw"] == "<p>Edited while private</p>"
    assert wordpress.post(1)["id"] == 1


def test_a_local_image_uploads_once_and_is_sent_as_library_markup(tmp_path, store):
    wordpress = FakeWordPress(post_count=1)
    add_profile(store, "myblog", tmp_path)
    (tmp_path / "content/images").mkdir(parents=True)
    (tmp_path / "content/images/cat.png").write_bytes(b"cat")
    path = write_post(
        tmp_path,
        "2026/mine.md",
        "title: Mine\nstatus: public\n",
        "![A cat](../images/cat.png)",
    )

    _, output, _ = run(store, wordpress, "push")

    assert "+  2  content/2026/mine.md  1 image;" in output
    assert "Pushed 1 post (1 new), 1 image." in output
    assert wordpress.uploads == ['attachment; filename="cat.png"']
    url = "https://blog.test/wp-content/uploads/uploaded-901-1024x768.png"
    assert wordpress.saved[-1]["content"] == (
        '<figure class="wp-block-image size-large">'
        f'<img src="{url}" alt="A cat" class="wp-image-901" /></figure>'
    )
    assert "../images/cat.png" in path.read_text()

    path.write_text(path.read_text() + "\nMore.\n")
    write_post(
        tmp_path, "top.md", "title: Top\nstatus: public\n", "![](images/cat.png)"
    )
    run(store, wordpress, "push")
    assert len(wordpress.uploads) == 1
    assert 'class="wp-image-901"' in wordpress.saved[-1]["content"]

    (tmp_path / "content/images/cat.png").write_bytes(b"a better cat")
    path.write_text(path.read_text() + "\nEven more.\n")
    run(store, wordpress, "push")
    assert len(wordpress.uploads) == 2


def test_a_missing_image_is_not_uploaded_and_a_lost_one_stops_only_its_post(
    tmp_path, store
):
    wordpress = FakeWordPress(post_count=1)
    wordpress.post(1)["content"]["raw"] = (
        '<!-- wp:image {"id":42,"sizeSlug":"large"} -->\n'
        f'<figure class="wp-block-image size-large"><img src="{IMAGE}" alt="" '
        'class="wp-image-42"/></figure>\n<!-- /wp:image -->'
    )
    wordpress.broken_uploads["/wp-content/uploads/2026/01/sunset-1024x768.jpg"] = 404
    add_profile(store, "myblog", tmp_path)
    run(store, wordpress, "pull")
    pulled = tmp_path / "content/post-1.md"
    pulled.write_text(pulled.read_text() + "\nMore.\n")
    write_post(
        tmp_path, "lost.md", "title: Lost\nstatus: public\n", "![](images/nope.png)"
    )
    write_post(tmp_path, "fine.md", "title: Fine\nstatus: public\n")

    _, output, _ = run(store, wordpress, "push", "-y")

    assert wordpress.uploads == []
    assert 'class="wp-image-42"' in wordpress.post(1)["content"]["raw"]
    assert "?  -  content/lost.md  image not found: images/nope.png" in output
    assert "+  2  content/fine.md" in output
    assert "1 skipped." in output


def test_missing_terms_are_created_only_after_a_yes(tmp_path, store):
    wordpress = FakeWordPress(post_count=1)
    add_profile(store, "myblog", tmp_path)
    path = write_post(
        tmp_path,
        "mine.md",
        "title: Mine\nstatus: public\ncategories: [news, Fresh]\ntags: [new-tag]\n",
    )

    _, output, _ = run(store, wordpress, "push")
    assert "needs category 'Fresh', tag 'new-tag'" in output
    assert wordpress.saved == []

    run(store, wordpress, "push", "-y")

    assert sorted(wordpress.categories.values()) == ["Fresh", "News", "Travel"]
    assert "- Fresh\n- News\n" in path.read_text()
    assert "- new-tag\n" in path.read_text()


def test_content_wordpress_changes_when_saving_is_reported(tmp_path, store):
    wordpress = FakeWordPress(post_count=1)
    wordpress.rewrite_content = lambda content: "<p>Filtered</p>"
    add_profile(store, "myblog", tmp_path)
    write_post(tmp_path, "mine.md", "title: Mine\nstatus: public\n")

    _, output, _ = run(store, wordpress, "push")

    assert "WordPress changed the content; check the post" in output
