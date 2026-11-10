# Post files

[← WPSync README](../README.md)

## Header and body

Each post is a Markdown file under the profile folder's `content/` directory, in
any subfolder. Everything else in the profile folder is yours: WPSync reads only
`.md` files under `content/`, and skips files and folders whose names start
with a dot. The file starts with a YAML header:

```markdown
---
id: 123
title: Hello world
slug: hello-world
date: 2026-10-01T09:30:00+02:00
status: public
categories:
- News
tags:
- python
---

The post body in Markdown.
```

- `id` links the file to a WordPress post. Leave it out for a new post.
- `title`, `slug`, and `date` are optional. A `date` needs a time zone offset
  or `Z`.
- `status` is `public` or `private`, and defaults to `private`. Push publishes
  a public post; a public post with a future `date` is scheduled. Push never
  sends a private post, except to turn a published post that became private
  into a WordPress draft, which keeps its ID, comments, and address for when it
  is made public again. Pull writes published posts as `public` and drafts,
  scheduled, pending, and WordPress-private posts as `private`.
- `categories` and `tags` are lists of names.

The body is Markdown. Styling that plain Markdown cannot express uses
Pandoc-style attributes, and only where a post has such styling:

```markdown
Some [red text]{style="color: #c00"} and [a link](https://example.com/){target=_blank}.

{.has-text-align-right}
A right-aligned paragraph.

![Sunset](images/sunset.jpg "Caption"){.aligncenter}

:::: {.wp-block-columns}
::: {.wp-block-column}
Left column.
:::
::::
```

A video or other embeddable URL alone in a paragraph is embedded by WordPress.
Content with no Markdown form, such as galleries, stays in the file as its
exact original HTML; WPSync never drops it. When plain HTML would not survive
Markdown unchanged, it is wrapped in a raw HTML fence, which is published
exactly as written:

````markdown
```{=html}
<!-- wp:gallery -->
<figure class="wp-block-gallery">…</figure>
<!-- /wp:gallery -->
```
````

Other header entries, such as `layout:` from another tool, stay in the file
exactly as written and are never sent to WordPress. When WPSync rewrites a file,
it writes its own fields in the order above, sorts category and tag names, and
leaves other entries and their comments unchanged. Two files with the same `id`
are an error.

## Images

An image's path is relative to the post file that shows it, as Markdown editors
such as VS Code and Obsidian read it, so their previews show the image. Pull
saves images in `content/images/`, in the same folders WordPress keeps them
in: an image uploaded to `wp-content/uploads/2025/11/photo.png` becomes
`content/images/2025/11/photo.png`. Two uploads with the same file name in
different months therefore never collide, and an image is saved at the same
path on every pull. A post in `content/` refers to
`images/2025/11/photo.png`, and one in `content/2019/` to
`../images/2025/11/photo.png`. An
image you add can be anywhere in the profile folder, so an editor that saves
pasted images next to the post works too. Moving a post into another folder
breaks its relative image paths, as it does in any Markdown editor.

In Obsidian, turn off **Use [[Wikilinks]]** and set **New link format** to
**Relative path to file** under Settings, Files and links. WPSync reads standard
Markdown images, `![alt](path)`, and sends `![[photo.png]]` as plain text.

## Starting a post

`create` starts a post file under `content/`. The file name, title, and slug
can all wait:

```console
wpsync create                                  # content/2026-11-10-1432.md, from the time
wpsync create idea                             # content/idea.md
wpsync create drafts/hello -t "Hello, World!"  # content/drafts/hello.md, with a title
wpsync create hello -s hello-again             # choose the slug
wpsync create -o                               # and open it in your editor
```

```markdown
---
title: ''
status: private
categories: []
tags: []
---
```

A new post is private, so nothing is published until you set `status: public`
and run `push`. A post can stay untitled, which suits short pieces: WordPress
shows it without a title, and its address uses its ID, such as
`https://example.com/203/`, unless you set a slug. Without a slug, WordPress
assigns one from the title when the post is created.

You can rename or move a post's file and change its title at any time. The
`id` in its header ties the file to its post, so push updates the same post
instead of creating a new one. Moving a file to another folder breaks its
relative image paths, as in any Markdown editor. `create` never overwrites a
file and only touches local files.

## Opening a post

`open` opens a post's file in your Markdown editor, chosen by ID, slug, title,
or file. Choose the editor with `editor`, which is saved in
`~/.wpsync/config.json` for every profile. Without a name it asks, and so does
`open` the first time if no editor is chosen:

```console
wpsync editor vscode     # or obsidian
wpsync open hello
wpsync open              # the post wpsync create just made
```

Without a name, `open` opens the newest post `create` named after the time,
such as `content/2026-11-10-1432.md`, if it was made in the last 10 minutes.
That helps when you forgot `-o`. Otherwise `open` fails and asks you to name
the post, so it never opens one you have forgotten about.

VS Code opens the file with the profile folder as its workspace, using the
`code` command; on macOS without that command, it opens the Visual Studio Code
app instead. Obsidian opens files only inside a vault, so open the profile
folder, or a folder above it, as a vault first. Other editors are not supported
yet.
