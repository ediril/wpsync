from wordpress_fake import FakeWordPress, add_profile, invoke

UPLOADS = "https://blog.test/wp-content/uploads/2026/01"


def image_block(media_id, name):
    return (
        f'<!-- wp:image {{"id":{media_id},"sizeSlug":"large"}} -->\n'
        f'<figure class="wp-block-image size-large"><img src="{UPLOADS}/{name}" '
        f'alt="" class="wp-image-{media_id}"/></figure>\n<!-- /wp:image -->'
    )


def run(store, wordpress, *arguments):
    return invoke(["myblog", *arguments], store, wordpress=wordpress)


def test_delete_keeps_the_post_and_its_own_images_in_trash_until_restored(
    tmp_path, store
):
    wordpress = FakeWordPress(post_count=2)
    wordpress.post(1)["content"]["raw"] = "\n\n".join(
        [image_block(42, "sunset-1024x768.jpg"), image_block(43, "shared.jpg")]
    )
    wordpress.pages = [{"id": 50, "content": {"raw": image_block(43, "shared.jpg")}}]
    add_profile(store, "myblog", tmp_path)
    run(store, wordpress, "pull")
    post = (tmp_path / "content/post-1.md").read_text()

    status, output, _ = run(store, wordpress, "delete", "post-1", "-y")

    assert (status, output) == (
        0,
        "Deleted #1 from WordPress, with 1 image; "
        "moved content/post-1.md to .trash/content/post-1.md.\n",
    )
    assert wordpress.deleted == [("posts", 1), ("media", 42)]
    assert (tmp_path / ".trash/content/post-1.md").read_text() == post
    assert sorted(
        p.name for p in (tmp_path / ".trash/content/images/2026/01").iterdir()
    ) == [
        "shared.jpg",
        "sunset-1024x768.jpg",
    ]
    _, output, _ = run(store, wordpress, "trash")
    assert output == "ID  Title (restores to)\n 1  Post 1 (content/post-1.md)\n"

    status, output, _ = run(store, wordpress, "restore", "post-1")
    assert (status, output) == (
        0,
        "Restored content/post-1.md; push puts it back on the blog.\n",
    )
    assert not (tmp_path / ".trash/content/post-1.md").exists()
    assert (tmp_path / "content/images/2026/01/sunset-1024x768.jpg").exists()

    _, output, _ = run(store, wordpress, "push")
    assert output.splitlines()[-2:] == [
        "+  3  content/post-1.md  1 image; https://blog.test/post-1/",
        "Pushed 1 post (1 new), 1 image.",
    ]
    assert len(wordpress.uploads) == 1
    assert "wp-image-43" in wordpress.post(3)["content"]["raw"]


def test_push_prune_deletes_posts_whose_files_were_deleted_keeping_a_copy(
    tmp_path, store
):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)
    run(store, wordpress, "pull")
    (tmp_path / "content/post-1.md").unlink()
    (tmp_path / "content/post-2.md").unlink()
    wordpress.post(2)["title"]["raw"] = "Edited on WordPress"
    both = (
        "content/post-2.md  deleted locally; changed on WordPress since the last sync"
    )

    _, output, _ = run(store, wordpress, "push")
    assert output == "Nothing to push.\n"
    _, output, _ = run(store, wordpress, "diff", "-p")
    assert output.splitlines() == [
        "- l  1  content/post-1.md  deletes on push",
        f"?    2  {both}",
    ]

    _, output, _ = run(store, wordpress, "push", "-p")
    assert output.splitlines() == [
        "-  1  content/post-1.md  deleted; kept in .trash/",
        f"?  2  {both}",
        "Pushed 1 post (1 deleted); 1 skipped. "
        "Rerun with --yes to accept the skipped changes.",
    ]
    assert wordpress.deleted == [("posts", 1)]
    assert "id: 1\n" in (tmp_path / ".trash/content/post-1.md").read_text()

    _, output, _ = run(store, wordpress, "push", "-p", "-y")
    assert output.splitlines()[-1] == "Pushed 1 post (1 deleted)."
    copy = (tmp_path / ".trash/content/post-2.md").read_text()
    assert "title: Edited on WordPress\n" in copy
    _, output, _ = run(store, wordpress, "pull")
    assert output.splitlines()[-1] == "Nothing to pull."
