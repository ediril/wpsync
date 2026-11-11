from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from wordpress_fake import SITE, FakeWordPress, Terminal, add_profile, invoke

from wpsync.documents import Document, body_checksum, fields_checksum, write_document
from wpsync.posts import ContentFormat, Post, PostStatus
from wpsync.state import PostRecord, write_state
from wpsync.wordpress.client import fingerprint

API_ROOT = f"{SITE}/wp-json/"


def synced(root, wordpress, post_id, name):
    """Write a post file and record it as synchronized with the fake blog."""
    remote = wordpress.post(post_id)
    post = Post(
        title=remote["title"]["raw"],
        slug=remote["slug"],
        status=PostStatus.PUBLIC,
        body="Body",
    )
    path = Path("content") / name
    write_document(root / path, Document(str(post_id), post))
    with write_state(root, API_ROOT) as state:
        state.save(
            PostRecord(
                str(post_id),
                PurePosixPath(path),
                body_checksum(post),
                fields_checksum(post),
                fingerprint(remote),
                ContentFormat.HTML,
                remote["link"],
                (),
            )
        )
    return root / path


def edit(path, old, new):
    path.write_text(path.read_text().replace(old, new))


def new_post(root, name, **fields):
    fields.setdefault("status", PostStatus.PUBLIC)
    write_document(root / "content" / name, Document(None, Post(**fields)))


def test_diff_in_an_empty_folder_says_there_are_no_posts(tmp_path, store):
    add_profile(store, "myblog", tmp_path)

    status, output, _ = invoke(["myblog", "diff"], store, password=None)

    assert (status, output) == (
        0,
        "No posts here yet. Run wpsync pull, or add Markdown files under content/.\n",
    )


def test_diff_without_local_changes_never_contacts_the_blog(tmp_path, store):
    wordpress = FakeWordPress()
    add_profile(store, "myblog", tmp_path)
    synced(tmp_path, wordpress, 1, "one.md")
    synced(tmp_path, wordpress, 2, "two.md")

    status, output, errors = invoke(
        ["myblog", "diff"], store, wordpress=wordpress, password=None
    )

    assert status == 0
    assert output == "No local changes.\n"
    assert wordpress.requests == []


def test_diff_shows_local_changes_and_fetches_only_those_posts(tmp_path, store):
    wordpress = FakeWordPress(post_count=7)
    wordpress.post(3)["content"]["raw"] = (
        "<!-- wp:paragraph --><p>x</p><!-- /wp:paragraph -->"
    )
    add_profile(store, "myblog", tmp_path)
    edit(synced(tmp_path, wordpress, 1, "content.md"), "Body", "New body")
    edit(
        synced(tmp_path, wordpress, 2, "details.md"), "title: Post 2", "title: Renamed"
    )
    edit(synced(tmp_path, wordpress, 3, "blocks.md"), "Body", "New body")
    edit(synced(tmp_path, wordpress, 4, "both.md"), "Body", "New body")
    wordpress.post(4)["title"]["raw"] = "Edited on WordPress"
    synced(tmp_path, wordpress, 5, "deleted.md").unlink()
    synced(tmp_path, wordpress, 6, "unchanged.md")
    edit(
        synced(tmp_path, wordpress, 7, "unpublish.md"),
        "status: public",
        "status: private",
    )
    new_post(tmp_path, "note.md", title="Note", status=PostStatus.PRIVATE)

    status, output, _ = invoke(["myblog", "diff"], store, wordpress=wordpress)

    assert status == 0
    assert output.splitlines() == [
        "~    blocks.md",
        "?    both.md",
        "~    content.md",
        "~    details.md",
        "~    unpublish.md",
        "Not shown: 1 private (try using -x), 1 remote-only (try using -a)",
    ]
    fetched = [r.url.params.get("include") for r in wordpress.requests]
    assert fetched == ["1,2,3,4,7"]


def test_diff_marks_a_new_file_whose_slug_is_taken_as_a_conflict(tmp_path, store):
    wordpress = FakeWordPress(post_count=3)
    add_profile(store, "myblog", tmp_path)
    new_post(tmp_path, "a.md", title="Different", slug="post-1")
    new_post(tmp_path, "d.md", title="Fresh")

    status, output, _ = invoke(["myblog", "diff"], store, wordpress=wordpress)

    assert (status, output.splitlines()) == (
        0,
        ["?  l a.md", "+  l d.md"],
    )


def test_one_post_is_selected_by_id_slug_file_name_or_path(
    tmp_path, store, monkeypatch
):
    wordpress = FakeWordPress(post_count=2)
    add_profile(store, "myblog", tmp_path)
    (tmp_path / "content/2019").mkdir(parents=True)
    edit(synced(tmp_path, wordpress, 1, "one.md"), "Body", "New body")
    edit(synced(tmp_path, wordpress, 2, "2019/two.md"), "Body", "New body")
    (tmp_path / "content/drafts").mkdir()
    new_post(tmp_path, "drafts/one.md", title="Draft", status=PostStatus.PRIVATE)
    monkeypatch.chdir(tmp_path)

    for selector in ("2", "post-2", "two", "two.md", "content/2019/two.md"):
        status, output, _ = invoke(["diff", selector], store, wordpress=wordpress)
        assert (status, output) == (
            0,
            "     2019/\n~      two.md\n",
        ), selector

    status, _, errors = invoke(["diff", "one.md"], store, wordpress=wordpress)
    assert (status, errors) == (
        1,
        "wpsync: error: 'one.md' matches content/drafts/one.md, content/one.md\n",
    )
    monkeypatch.chdir(tmp_path / "content")
    status, output, _ = invoke(["diff", "one.md"], store, wordpress=wordpress)
    assert (status, output) == (0, "~    one.md\n")

    status, _, errors = invoke(["diff", "post-9"], store, wordpress=wordpress)
    assert status == 1
    assert "no local post has slug, file name, or title 'post-9'" in errors


def test_ls_lists_local_posts_without_contacting_the_blog(tmp_path, store, monkeypatch):
    wordpress = FakeWordPress(post_count=12)
    add_profile(store, "myblog", tmp_path)
    synced(tmp_path, wordpress, 12, "twelve.md")
    synced(tmp_path, wordpress, 3, "three.md")
    new_post(tmp_path, "idea.md", title="Idea", status=PostStatus.PRIVATE)
    new_post(tmp_path, "later.md", title="Later", date=datetime(2099, 1, 2, tzinfo=UTC))

    def ls(*arguments, stdout=None):
        return invoke(
            ["myblog", "ls", *arguments],
            store,
            wordpress=wordpress,
            password=None,
            stdout=stdout,
        )[1].splitlines()

    assert ls() == [
        "ID  Public        Issues  Title (file)",
        " 3  *             -       Post 3 (three.md)",
        "12  *             -       Post 12 (twelve.md)",
        " -                -       Idea (idea.md)",
        " -  *Jan 2, 2099  -       Later (later.md)",
    ]
    assert ls("-l")[:4] == [
        "ID  Public        Issues  Title",
        " 3  *             -       Post 3",
        "                          content/three.md",
        "                          https://blog.test/post-3/",
    ]
    assert wordpress.requests == []

    monkeypatch.setenv("COLUMNS", "32")
    assert ls(stdout=Terminal())[:2] == [
        "ID  Public        Issues  Title…",
        " 3  *             -       Post …",
    ]
    assert ls("-l", stdout=Terminal())[2] == "                          conte…"


def test_show_finds_a_post_by_id_slug_file_or_title(tmp_path, store):
    wordpress = FakeWordPress(post_count=3)
    add_profile(store, "myblog", tmp_path)
    synced(tmp_path, wordpress, 3, "three.md")

    for selector in ("3", "post-3", "content/three.md", "post 3"):
        status, output, errors = invoke(
            ["myblog", "show", selector], store, wordpress=wordpress, password=None
        )
        assert (status, errors) == (0, "")
        assert output.splitlines()[0] == "ID:         3"
    assert "URL:        https://blog.test/post-3/" in output.splitlines()
    assert wordpress.requests == []


def test_state_from_another_blog_is_refused(tmp_path, store):
    add_profile(store, "myblog", tmp_path)
    with write_state(tmp_path, "https://other.test/wp-json/"):
        pass

    status, _, errors = invoke(["myblog", "diff"], store)

    assert status == 1
    assert "synchronized with a different blog" in errors
