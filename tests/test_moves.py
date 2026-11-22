from wordpress_fake import FakeWordPress, add_profile, invoke

IMAGE = "images/2026/01/sunset-1024x768.jpg"


def pulled_blog(tmp_path, store):
    """A blog whose first post shows an image, pulled into content/imported/."""
    wordpress = FakeWordPress(post_count=2)
    wordpress.post(1)["content"]["raw"] = (
        '<!-- wp:image {"id":42,"sizeSlug":"large"} -->\n'
        '<figure class="wp-block-image size-large"><img src="https://blog.test/'
        'wp-content/uploads/2026/01/sunset-1024x768.jpg" alt="Sunset" '
        'class="wp-image-42"/></figure>\n<!-- /wp:image -->'
    )
    add_profile(store, "myblog", tmp_path)
    run(store, wordpress, "pull")
    wordpress.requests.clear()
    return wordpress, tmp_path / "content/imported/post-1.md"


def run(store, wordpress, *arguments):
    return invoke(["myblog", *arguments], store, wordpress=wordpress)


def test_a_post_moved_by_hand_keeps_its_images_and_is_not_taken_for_an_edit(
    tmp_path, store
):
    wordpress, post = pulled_blog(tmp_path, store)
    assert f"![Sunset](../{IMAGE})" in post.read_text()
    moved = tmp_path / "content/post-1.md"
    post.rename(moved)

    _, output, _ = run(store, wordpress, "diff")
    assert output.splitlines() == [
        "No local changes.",
        "Note: post-1.md: push will update 1 image path after its move from "
        "imported/post-1.md",
    ]
    assert f"../{IMAGE}" in moved.read_text()

    status, output, errors = run(store, wordpress, "push")
    assert (status, output) == (0, "  Nothing to push.\n")
    assert (
        "Note: post-1.md: updated 1 image path after its move from imported/post-1.md"
        in errors.splitlines()
    )
    assert f"![Sunset]({IMAGE})" in moved.read_text()
    assert wordpress.saved == []

    wordpress.post(1)["title"]["raw"] = "Retitled"
    status, _, errors = run(store, wordpress, "pull")
    assert status == 0
    assert "  ~ post-1.md" in errors.splitlines()
    assert "title: Retitled\n" in moved.read_text()
    assert not post.exists()


def test_pushing_one_post_leaves_other_moved_files_for_validate(tmp_path, store):
    wordpress, post = pulled_blog(tmp_path, store)
    moved = tmp_path / "content/post-1.md"
    post.rename(moved)

    run(store, wordpress, "push", "post-2")
    assert f"../{IMAGE}" in moved.read_text()

    status, output, _ = run(store, wordpress, "validate")
    assert status == 0
    assert output.splitlines() == [
        "  ~ post-1.md: updated 1 image path after its move from imported/post-1.md",
        "Checked 2 posts: 1 updated.",
    ]
    assert f"![Sunset]({IMAGE})" in moved.read_text()


def test_move_keeps_image_paths_and_never_replaces_a_file(tmp_path, store):
    wordpress, post = pulled_blog(tmp_path, store)
    content = tmp_path / "content"

    status, output, _ = run(
        store, wordpress, "move", "content/imported/post-1.md", "content"
    )
    assert status == 0
    assert output.splitlines() == [
        "Moved imported/post-1.md to post-1.md.",
        "Note: post-1.md: updated 1 image path after its move from imported/post-1.md",
    ]
    assert f"![Sunset]({IMAGE})" in (content / "post-1.md").read_text()
    assert run(store, wordpress, "push")[1] == "  Nothing to push.\n"

    (content / "post-2.md").write_text("---\ntitle: Mine\n---\n")
    status, _, errors = run(
        store, wordpress, "move", "content/imported/post-2.md", "content"
    )
    assert status == 1
    assert errors == "wpsync: error: content/post-2.md already exists\n"
    assert (content / "imported/post-2.md").exists()
    status, _, errors = run(
        store, wordpress, "move", "content/imported/post-2.md", "content/.old"
    )
    assert (status, errors) == (
        1,
        "wpsync: error: content/.old is hidden; WPSync skips it\n",
    )

    status, output, _ = run(
        store, wordpress, "move", "content/imported", "content/2026"
    )
    assert (status, output) == (0, "Moved imported/ to 2026/ (1 post).\n")
    assert (content / "2026/post-2.md").exists()


def test_validate_reports_what_push_cannot_send_and_exits_1(tmp_path, store):
    wordpress, _ = pulled_blog(tmp_path, store)
    lost = tmp_path / "content/lost.md"
    lost.write_text("---\ntitel: Lost\n---\n\n![](images/nope.png)\n")

    status, output, _ = run(store, wordpress, "validate")

    assert status == 1
    lines = output.splitlines()
    assert "  ? lost.md: image not found: images/nope.png" in lines
    assert any("'titel' is not synced; did you mean 'title'?" in line for line in lines)
    assert lines[-1] == "Checked 3 posts: 2 issues."


def test_move_after_an_unrecorded_move_still_finds_the_images(tmp_path, store):
    wordpress, post = pulled_blog(tmp_path, store)
    by_hand = tmp_path / "content/post-1.md"
    post.rename(by_hand)

    status, _, _ = run(store, wordpress, "move", "content/post-1.md", "content/a/b")

    assert status == 0
    assert (
        f"![Sunset](../../{IMAGE})" in (tmp_path / "content/a/b/post-1.md").read_text()
    )
