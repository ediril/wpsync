# Listing posts and diff

[← WPSync README](../README.md)

## Listing posts

Local files are the source of truth. `ls` lists the posts in the profile folder
without contacting the blog. On a terminal, it cuts lines to fit instead of
letting them wrap:

```console
$ wpsync ls
ID  Public        Issues  Title (file)
67  *             2       Hurt (hurt.md)
 -                -       Idea (idea.md)
 -  *Jan 1, 2029  -       Later (later.md)
```

`wpsync ls -l` puts each post's file and its address on the blog, as of the last
pull, on their own lines. If a line is cut, widen the terminal or pipe the output,
which is never cut:

```console
$ wpsync ls -l
ID  Public  Issues  Title
67  *       2       Hurt
                    content/hurt.md
                    https://blog.test/hurt/
```

`Public` marks a public post with `*`, before its date if the post is scheduled
and readers cannot see it yet; a private post has no mark. `Issues` counts what
is wrong with a post; `show` says what, for one post chosen by ID, slug, file,
or title:

```console
$ wpsync show hurt
ID:         67
Title:      Hurt
Slug:       hurt
Status:     public
Date:       2025-11-04T10:00:00-05:00
Categories: Notes
Tags:       -
File:       content/hurt.md
URL:        https://blog.test/hurt/
Issues:     2
  missing file: https://blog.test/wp-content/uploads/2025/11/photo.png
  missing file: https://blog.test/wp-content/uploads/2025/11/discussion.html
```

An issue is an image or embedded page that a pull found missing from the server.
Pull tries missing files again each time. It checks the images it downloads and
iframes showing uploaded files, when it pulls a post. It does not check images
inside kept HTML, in a line of text, or on other sites, or uploads a post only
links to.

## Diff

`diff` shows what a push would change and anything that would stop it:

```console
wpsync diff          # every post
wpsync diff 123      # one post, by ID
wpsync diff hello    # one post, by slug
wpsync diff "Hello World"   # one post, by title
wpsync diff content/new-idea.md   # one post, by file
wpsync diff -a       # also list unchanged posts
wpsync --legend      # explain the diff and ls symbols
```

```text
~ l  123  content/hello-world.md  content; block post becomes plain HTML on push
~ l  145  content/release-notes.md  details
?    150  content/about.md  content; also changed on WordPress since the last sync
- l  160  content/old.md  deleted locally; WordPress keeps the post
+ l    -  content/new-idea.md  new post
~ l  170  content/old-news.md  unpublish; becomes a draft on WordPress
Not shown: 12 unchanged, 3 private (-a to show)
```

`content` means the body changed and `details` means a header field changed.
Private posts (`x l`) are listed with `-a`; their edits stay local.
`diff` never changes anything. It contacts the blog only for posts that changed
locally, to check whether they also changed on WordPress since the last sync,
and for new files, to check their slugs and titles against existing posts. A
taken slug is a conflict (`?`); a shared title is noted, since push asks before
creating a second post with the same title.
With no local changes it works offline. Posts created or edited on WordPress
appear only through `pull`.
