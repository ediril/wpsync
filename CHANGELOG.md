# Changelog

## Unreleased

### Added

- Profiles map one local folder to one blog, following HLSync: `init`,
  `map`, `remove`, `root`, `profile`, and `profiles`, stored in
  `~/.wpsync/config.json`, with current-directory inference, a profile-prefix
  override, and an Application Password read from an environment variable.
  `init` checks that the address is a WordPress site without signing in.
- Read and write post files: Markdown under `content/` with a YAML header.
  WPSync rewrites its own fields canonically, keeps other header entries and
  their comments byte for byte, and reports every invalid file and every post
  ID shared by two files at once.
- Convert post content between WordPress and Markdown. Push renders plain HTML
  that WordPress displays as written. Pull reads stored block and classic
  content, uses Pandoc-style attributes and fenced divs only where a post has
  styling plain Markdown cannot express, and checks every conversion against a
  model of what WordPress displays. Anything that would display differently is
  kept as its exact original source, as plain HTML or in a ```` ```{=html} ````
  fence.
  Blank paragraphs and repeated line breaks, used only to force vertical space,
  are left out.
- Post `status` is `public` or `private`, and new files are private. Push
  will publish public posts and never send private ones, except to turn a
  published post that became private into a draft. Pull writes published posts
  as public and drafts, scheduled, pending, and WordPress-private posts as
  private.
- `diff [ID|SLUG]` shows what push would do in HLSync's layout: folders
  before files with posts indented, and status slots for the action, `x` for a
  private post push skips, and whether the post exists only locally (`l`), only
  on WordPress (`r`), or on both. `-a` shows unchanged posts and `-x` private
  ones. It contacts the blog only for changed or new posts, and a new file
  whose slug belongs to a post is a conflict. `ls` lists local posts by ID,
  title, file, and number of issues, fitting the terminal; `ls -l` puts each post's
  file and address on the blog on their own lines. `show ID|SLUG` gives one post's details and lists its
  issues, finding the post by ID, slug, file, or title.
- `pull [ID|SLUG]` brings posts into `content/<slug>.md` and downloads the
  images they display into `content/images/`, in the same year and month
  folders as WordPress's uploads, referred to relative to each post
  file so Markdown editors preview them. Edited files are replaced, and unlinked
  files are linked with WordPress's changes, only after confirmation or
  `--yes`. A file that WordPress's version would only fill in is linked without
  asking. Pull never restores or deletes local files. Titles are written as
  readers see them, so `&amp;` in a stored title becomes `&`.
  An image whose file is gone from the server, or that comes back as something
  other than an image, is reported, and the post still converts. Later pulls
  add the file if the server has it again.
  Iframes showing uploaded files are checked too.
- `create [FILE] [-t TITLE] [-s SLUG]` starts a private post file under
  `content/`, named after the date and time when no file is given. A post may
  stay untitled; WordPress then uses its ID as its address.
- `open [ID|SLUG]` opens a post's file in Obsidian or VS Code, or without a
  name the post edited last; `create -o` opens the new file at once. The
  editor is chosen with `editor [obsidian|vscode]` and saved in
  `~/.wpsync/config.json`; both ask when no editor is chosen.
- `push [ID|SLUG]` creates and updates posts from changed files, sending only the
  content or the header fields that changed. It writes what WordPress assigned
  back into new files, uploads local images, turns a published post made private
  into a draft, and asks before replacing a matched or remotely changed post,
  duplicating a title, converting a block post, or creating terms. It skips a
  post without a title.
- `scripts/publish.sh [--prepare]` builds, checks, and publishes releases to
  PyPI.
- `delete ID|SLUG` deletes a post from the blog, with the library images no
  other post or page uses, after asking, and keeps its file and images in the
  profile folder's `.trash/`. `trash` lists what is there and `restore` brings
  a post back, so the next push creates it again.
- `push -p` / `--prune` deletes posts whose files you deleted the same way,
  saving each post's current version in `.trash/` first, and asks first for a
  post that changed on WordPress since the last sync; `diff -p` previews it.
  Without `-p`, push still deletes nothing.

### Changed

- `diff` lists the images push would upload, new (`+  l`) or replaced (`~`). A
  replaced image counts as a change to every post that shows it, so push
  uploads it again and updates those posts even if their files did not change.
- `push` and `pull` print each file they change as HLSync does, `  + path`,
  `  ~ path`, or `  - path`, uploaded and downloaded images included, with
  `?` for a skipped post and `failed` with the reason for one that cannot be
  sent, and end with `Push complete: N changes.` or `Pull complete: N changes.`
  Pull lists posts deleted on either side after the summary, and push's notes
  report what WordPress changed from what was sent.
- License WPSync under PolyForm Strict 1.0.0.
- `show`, `open`, `diff`, and `push` find a post by its file name without a
  folder, such as `vibing` or `vibing.md`, in any folder under `content/`;
  `pull` does so for a name ending in `.md`.
- Derive versions from Git history like HLSync: `<major>.<work-day>.<increment>`
  starting from `version.json`. The history starts at 1.0.1, so
  releases begin at 1.1 and follow the 1.0.x releases a previous `wpsync`
  project published on PyPI.

### Fixed

- Push shows an uploaded GIF at its original size, since the resized copies
  WordPress makes keep only the first frame of an animation.
- Pull downloads the images a post shows when it links a local file that
  already matches the post, instead of leaving them missing unreported.
