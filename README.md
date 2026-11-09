# WPSync

WPSync (`wpsync`) is a command-line tool for managing blog posts as local
Markdown files: map a folder to a blog, pull its posts, edit them in any
editor, preview the differences, and push the changes back. WordPress is the
first supported platform.

WPSync is pre-alpha software. Profiles, pull, diff, and push work today;
commands and the post file format may change before a stable release.

## Who is it for?

WPSync is for people who would rather write blog posts in a Markdown editor,
such as VS Code or Obsidian, than in the WordPress editor.

Your files are the source of truth. Keep them in Git, edit them offline, and see
exactly what a push will change before anything reaches the blog.

## Installation

WPSync requires Python 3.11 or newer. Install it from PyPI with uv:

```console
uv tool install wpsync
```

Upgrade later with:

```console
uv tool upgrade wpsync
```

## Quick start

WPSync signs in with a WordPress Application Password, created in the WordPress
dashboard under **Users > Profile > Application Passwords**; the site must use
HTTPS. WPSync reads the password from an environment variable named after the
profile and never stores it.

From the folder you want to use for the blog:

```console
wpsync init myblog --site https://example.com --username emrah
export MYBLOG_WP_PASSWORD='abcd efgh ijkl mnop qrst uvwx'
wpsync pull              # download posts and images into content/
wpsync open hello-world  # edit a post in Obsidian or VS Code
wpsync diff              # see what push would change
wpsync push              # send the changes to the blog
```

`init` proposes the current directory as the profile's folder; pressing Enter
accepts it. Each post becomes a Markdown file under `content/` with a YAML
header, and its images go in `content/images/`.

## Everyday commands

```console
wpsync profiles                          # list profiles; * marks the current one
wpsync ls                                # local posts, without contacting the blog
wpsync show hello                        # one post's details and issues
wpsync create drafts/idea -t "An idea"   # start a new private post
wpsync open idea                         # open a post in your editor
wpsync pull                              # bring changes from the blog
wpsync diff                              # what push would change, read-only
wpsync push hello                        # send one post
```

A new post is private until you set `status: public` in its header. Pull asks
before replacing a file you edited, and push asks before replacing a post that
also changed on WordPress. Push never deletes anything on the blog.

## Documentation

- [Profiles and credentials](https://github.com/ediril/wpsync/blob/main/docs/profiles.md):
  Application Passwords, profiles, and running commands from anywhere.
- [Post files](https://github.com/ediril/wpsync/blob/main/docs/post-files.md):
  the header and body format, images, starting a post, and opening it in an
  editor.
- [Pull and push](https://github.com/ediril/wpsync/blob/main/docs/push-and-pull.md):
  what each changes, how they protect local and remote work, and when they ask.
- [Listing posts and diff](https://github.com/ediril/wpsync/blob/main/docs/listing-and-diff.md):
  `ls`, `show`, issues, and `diff`'s status markers.
- [Development and maintenance](https://github.com/ediril/wpsync/blob/main/docs/development.md):
  testing local changes, switching installs, and releasing.

## Command behavior

Commands accept any unique prefix, such as `wpsync di`. An ambiguous prefix
fails and lists the commands it could mean.

Use `wpsync -h` and `wpsync COMMAND -h` for built-in help, and `wpsync --legend`
for the diff and ls symbols. `wpsync -v` and `wpsync --version` print the
installed version.

## License

WPSync is source-available under the [PolyForm Strict License 1.0.0](https://github.com/ediril/wpsync/blob/main/LICENSE).
Use is free of charge for the purposes permitted by that license, including:

- Any noncommercial purpose.
- The personal uses listed in the license, such as personal study and hobby
  projects, without any anticipated commercial application.
- Use by charitable organizations, educational institutions, public research
  organizations, public safety or health organizations, environmental protection
  organizations, and government institutions, regardless of funding source or
  obligations resulting from funding.

This license grants no rights to modify or redistribute WPSync or create works
based on it. The full license governs; this summary does not grant additional
permissions.

Commercial use outside those permissions requires a separate paid license.
Contact [Emrah Diril](mailto:emrah@diril.org) for pricing and a commercial
agreement before beginning such use.

WPSync is source-available, not open source.
