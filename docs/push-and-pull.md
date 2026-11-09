# Pull and push

[← WPSync README](../README.md)

## Pulling posts

`pull` brings the blog's posts into the profile folder: each post becomes
`content/<slug>.md`, and images from the site's media library are downloaded into
`content/images/` and referenced from the Markdown. The copy of an image that the post
displays is downloaded, usually WordPress's resized `large` copy.

If an image's file is gone from the server, or the server answers with something
other than an image, pull lists it as `missing:` on the post's line and carries on. The
Markdown refers to the image's local path as usual, and later pulls add the file if the
server has it again. Any other download failure, such as a server error, stops
the pull; rerun it to continue.

Blank paragraphs and repeated line breaks, which only force vertical space in
WordPress, are left out of the Markdown. The post keeps that spacing on the blog
until you edit and push it.

```console
wpsync pull          # every post
wpsync pull 123      # one post, by ID
wpsync pull hello    # one post, by slug, including one not pulled yet
wpsync pull -y       # answer yes to every question
```

```text
+  123  content/hello-world.md  2 images
~  145  content/release-notes.md
?  150  content/about.md  changed on both sides; your file is unchanged
+  160  content/gallery-tour.md  kept as HTML: core/gallery
Pulled 3 posts (2 new, 1 updated), 2 images; 1 skipped. Rerun pull with --yes to accept the skipped changes.
```

Pull never loses local work:

- A file you edited is replaced only after you confirm, and only when the post
  also changed on WordPress. Without a terminal, or when you answer no, the
  file is skipped.
- A WordPress post with the same slug as a local file that has no `id` yet is
  linked to that file, so pull does not create a duplicate. If WordPress's
  version would change the file's title, content, or status, or a date,
  category, or tag the file sets, pull asks first. A shared title alone does
  not link them, because titles need not be unique.
- A file you deleted is not restored, and a post deleted on WordPress keeps its
  local file.
- Header entries WPSync does not sync, such as `layout:`, are kept when a file
  is updated.

Dates are written in the blog's time zone. Images placed inside a line of text,
rather than on their own, keep their WordPress address and are not downloaded.

## Pushing posts

`push` sends changed local files to the blog. Run `diff` first to see what it
will do; both come from the same plan.

```console
wpsync push          # every post
wpsync push 123      # one post, by ID
wpsync push hello    # one post, by slug, title, or file
wpsync push -p       # also trash posts whose files you deleted
wpsync push -y       # answer yes to every question
```

```text
+  170  content/hello-world.md  1 image; https://example.com/hello-world/
~  145  content/release-notes.md
?  150  content/about.md  content; also changed on WordPress since the last sync
Pushed 2 posts (1 new, 1 updated), 1 image; 1 skipped. Rerun with --yes to accept the skipped changes.
```

- A public file without an `id` creates a post. Push then writes the post's `id`,
  slug, date, categories, and tags into the file, including anything WordPress
  chose, such as a default category.
- A changed file updates only the side that changed: editing the header never
  replaces the post's content.
- A private file is never sent, except that a published post made private becomes
  a draft. Its ID, comments, and address are kept, and edits made in the meantime
  are sent when it is made public again.
- Local images are uploaded to the media library once and sent as WordPress image
  markup. An image file you replace is uploaded again. See
  [Images](post-files.md#images) for where image files can live.
- A post without a title is skipped.
- Push deletes nothing on the blog unless you pass `-p` / `--prune`. With it,
  each post whose file you deleted moves to the WordPress trash, where it stays
  for 30 days and can be restored from the dashboard. WPSync stops tracking
  the post. Preview this with `wpsync diff -p`. To choose one deleted file's
  post, use its ID: `wpsync push -p 123`.

Push asks first, defaulting to no, before it would:

- replace a post that has the same slug as a new file, or one this folder never
  synced. Declining creates nothing, since WordPress would change the slug.
- create a second post with the same title.
- replace a post that also changed on WordPress.
- trash a post that changed on WordPress since the last sync.
- turn a block-editor post into plain HTML.
- create categories or tags the blog does not have.

Without a terminal, every question counts as no. If WordPress stores different
content than it was sent, usually because the account lacks `unfiltered_html`, the
post's line says so.

## Deleting posts

`delete` removes one post from the blog and from your folder:

```console
wpsync delete hello      # by slug, ID, file name, or title
wpsync delete hello -y   # without asking
```

It asks first, and says so if the post changed on WordPress since the last
sync. On yes, the post moves to the WordPress trash, where it stays for 30 days
and can be restored from the dashboard. The file moves into `.trash/` in the
profile folder, keeping its path, so `content/2019/hello.md` becomes
`.trash/content/2019/hello.md`, with `-2` added if that name is taken. WPSync
stops tracking the post. Images stay where they are, since other posts may
show them, and `.trash/` is never emptied for you.

A file without an `id` was never on the blog, so `delete` only moves it to
`.trash/`. To undo a delete, restore the post from the WordPress trash and move
the file back into `content/`. WordPress restores the post as a draft, so the
next pull asks before linking it to the file.

Deleting a file yourself instead leaves the post on the blog until you run
`wpsync push -p`.
