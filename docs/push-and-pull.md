# Pull and push

[← WPSync README](../README.md)

## Pulling posts

`pull` brings the blog's posts into the profile folder: each post becomes
`content/<slug>.md`, and images from the site's media library are downloaded into
`content/images/` and referenced from the Markdown. The copy of an image that the post
displays is downloaded, usually WordPress's resized `large` copy.

If an image's file is gone from the server, or the server answers with something
other than an image, pull counts it as missing from the blog and carries on; `ls`
and `show` list it as an issue of the post. The
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

Pull prints each file it writes, as HLSync does: `+` for a new post or image,
`~` for an updated post, and `?` for a post it skipped after a question.

```text
  + images/2025/11/photo.jpg
  + hello-world.md
  ~ release-notes.md
  ? about.md
Pull complete: 3 changes; 1 skipped. Rerun with --yes to accept the skipped changes.
Deleted on WordPress, local files kept:
  old.md
```

A post that cannot be pulled at all shows as `failed`, with the reason, and
the posts deleted on one side are listed after the summary.

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
wpsync push -p       # also delete posts whose files you deleted
wpsync push -y       # answer yes to every question
```

```text
  + images/photo.png
  + hello-world.md
  ~ release-notes.md
  ? about.md
  failed  draft.md: image not found: images/missing.png
Push complete: 3 changes; 2 skipped. Rerun with --yes to accept the skipped changes.
Note: hello-world.md: WordPress set the slug to hello-world-2
```

Push prints each file it changes on the blog, as HLSync does: `+` for a new
post or uploaded image, `~` for an updated post, `-` for a deleted one, and `?`
for a post it skipped after a question. A post it cannot send at all shows as
`failed`, with the reason. Notes after the summary report what WordPress did
differently from what was sent.

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
- Push deletes nothing on the blog unless you pass `-p` / `--prune`. With it,
  each post whose file you deleted is deleted from the blog, as `delete` does
  (see [Deleting posts](#deleting-posts)). Its current version is saved in
  `.trash/` first, at the path the file had. Preview this with
  `wpsync diff -p`. To choose one deleted file's post, use its ID:
  `wpsync push -p 123`.

Push asks first, defaulting to no, before it would:

- replace a post that has the same slug as a new file, or one this folder never
  synced. Declining creates nothing, since WordPress would change the slug.
- create a second post with the same title.
- replace a post that also changed on WordPress.
- delete a post that changed on WordPress since the last sync.
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
sync. On yes:

- The post is deleted from the blog for good, with its comments. Not every
  blogging platform has a trash, so WPSync keeps its own.
- Its images are deleted from the media library, except an image that another
  post or page on the blog, or another local post, shows. WPSync looks for the
  image in the text of posts and pages and among their featured images; it does
  not check themes, widgets, or other post types.
- The file moves into `.trash/` in the profile folder, keeping its path, so
  `content/2019/hello.md` becomes `.trash/content/2019/hello.md`, with `-2`
  added if that name is taken. The images only it shows move there too, so the
  copy still shows them in your editor.
- WPSync stops tracking the post.

A file without an `id` was never on the blog, so `delete` only moves it to
`.trash/`. Deleting a file yourself instead leaves the post on the blog until
you run `wpsync push -p`.

`trash` lists the posts in `.trash/`, and `restore` brings one back:

```console
$ wpsync trash
ID  Title (restores to)
67  Hello (content/2019/hello.md)
$ wpsync restore hello
Restored content/2019/hello.md; push puts it back on the blog.
```

Restore moves the file and its images back where they were and removes its
`id`, since the deleted post is gone. The next push creates it again as a new
post with the same title, slug, and date, and uploads its images again. Its
comments do not come back. `.trash/` is never emptied for you; delete files
from it when you no longer need them.
