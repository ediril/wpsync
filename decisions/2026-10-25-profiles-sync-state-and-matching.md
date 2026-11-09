# Profiles, sync state, and matching

Date: 2026-10-25

## Decision

### Profiles

A profile maps one local folder to one blog, following HLSync's profile model.
Profiles live in `~/.wpsync/config.json` and hold the site URL, the discovered
REST API root, the username, the password environment-variable name, and one
canonical local root. Local roots may not equal, contain, or be contained by
another profile's root. `wpsync init NAME --site URL` creates a profile and
proposes the current directory as its root. Commands run inside a mapped root
use that profile; elsewhere the profile is named before the command
(`wpsync myblog pull`). No profile selection persists between commands.

Credentials are WordPress Application Passwords read from an environment
variable. The variable name defaults to one derived from the profile name, such
as `MYBLOG_WP_PASSWORD`, and can be overridden when the profile is created.
Credential values are never stored.

`init` only checks that the site advertises a WordPress REST API and saves
the profile; it needs no credentials. `pull` signs in and checks that the
account can edit posts. Until something has been pulled, it also reports
limits that would make a pull look incomplete, such as an account that can edit
only its own posts. No setup step separates `init` from the first `pull` or
`push`: the first command that synchronizes a post creates the sync state, and
push matching (below) keeps a push without a prior pull safe.

### Sync state

Local files are the source of truth; WordPress is where they are published.
WPSync assumes the blog is not normally edited independently and checks the
WordPress side only to avoid overwriting a change made there by accident.

Each local root holds `.wpsync/state.db`, a SQLite database that stores no
post content. A `site` row records which blog the folder belongs to, and WPSync
refuses to use the database with a different blog. For every linked post the
`posts` table stores the post ID, the local path, two checksums of the file as
of the last sync (one of the body, one of the synchronized header fields
together), a fingerprint of the WordPress post as of the last sync (its title,
content, slug, status, date, and category and tag IDs), its content format
(block or plain HTML), its address on the blog, and the images pull found
missing. The media table arrives with pull. One pull or push of a
post updates its rows in a single transaction.

A post changed locally when either checksum differs. Push sends the content
only when the body checksum differs, and the header fields only when the header
checksum differs, so editing only a post's header never replaces block content.

WPSync contacts WordPress only when a command needs it:

- `diff` and `push` fetch, by ID, the posts that changed locally, and warn when
  one also changed on WordPress since the last sync.
- `diff` and `push` fetch the lightweight post list only when a new local file
  needs matching.
- `pull` fetches every post with its content.

Posts created or changed on WordPress therefore appear only through `pull`.

`diff`, `pull`, and `push` act on every post or on one post, selected by post
ID, slug, or file path.

### Matching

Only a shared slug identifies the same post; titles need not be unique.

Creating a post through the REST API never overwrites one: WordPress gives a
new post with a taken slug a different slug (`hello-world-2`). Only an update,
which names a post ID, changes an existing post. A file without a post ID is
checked against remote posts at push time:

- Its slug belongs to a post: ask whether to update that post, naming it.
  Declining stops; push does not create a post whose slug WordPress would
  change.
- Only its title matches one or more posts: ask whether to create another post
  with the same title. Titles need not be unique.
- Nothing matches: create a new post.

A confirmed match writes the post ID into the file's frontmatter. When push sends
a post's header fields, what WordPress decided (the ID, slug, date when the file
has none, categories, and tags) is written into the file and the sync state, so
the file reads as a pull would have written it. A file whose post ID this folder
has never synchronized, such as one copied from elsewhere, is a conflict: push
asks before updating that post. A first pull is therefore not required before
push.

`diff` and `push` share one plan: comparing a post produces both the line `diff`
shows and the step `push` performs, including any question to ask. A push that
stops between saving a post and recording it is safe to repeat, because the next
push finds the post by its slug or title and asks. A body that push did not send,
as when unpublishing, keeps its old checksum, so it is sent when the post is next
made public.

Pull applies the same rule in the other direction: a WordPress post with the
same slug as a local file without a post ID, or one whose ID a never-synced
file already carries, is linked to that file, and a shared title alone does
not link them. Pull asks first unless WordPress's version only fills in what
the file leaves empty: the slug, date, categories, and tags. The title and
content never count as empty, because a blank file that shares a slug is more
likely meant as a new post, and linking it would let the next push replace the
existing one. Linking a file that the pull would not change loses nothing, so
asking would only be noise.

### Prompts

WPSync asks before it updates a matched post, overwrites a conflict, creates
missing categories or tags, or converts a block-format post to plain HTML.
Every prompt defaults to No. `-y` / `--yes` answers yes to every prompt within
the selected files. When no terminal can answer, a prompt counts as No and the
message names `--yes`.

Push deletes nothing on the blog unless `-p` / `--prune` is given, as in
HLSync. `delete` removes one post; `push -p` removes each post whose file was
deleted, after saving the blog's version of it. Either way the post is deleted
from the blog for good, its records are dropped, and its file is kept in the
profile folder's `.trash/` at its original path. Images that no other post or
page uses, on the blog or locally, go with it: deleted from the media library
and moved into `.trash/`. A post that changed on the blog since the last sync
asks first. `restore` moves a post back without its `id`, so the next push
creates it again. Pull never deletes local files.

The trash is WPSync's own, not WordPress's, because other blogging platforms
may have none; the Markdown copy is also easier to read than a post in a
dashboard trash. The cost is that a restored post is a new post: its ID,
comments, and anything else only the blog held are gone.

## Rationale

The profile model matches HLSync so the two tools behave alike. Checksums and a
fingerprint recorded at each sync tell WPSync which side changed without
comparing clocks, which HLSync needs only because FTP cannot read remote
content cheaply. Storing checksums instead of copies keeps the database small;
a text diff of pending changes compares the file with the current WordPress
post, and Git covers history. Contacting WordPress only for locally changed
posts keeps everyday commands fast and offline-capable, at the cost of not
noticing WordPress-side edits to posts the user has not touched. SQLite gives
atomic multi-row updates for a post and its media without hand-written
journaling.

Titles repeat across posts, while WordPress keeps published slugs unique, so
matching requires agreement or a single candidate and never picks among several.
A single `--yes` flag covers every prompt because every case is a question WPSync
would otherwise ask.

## Risks

- The WordPress REST API has no conditional update. A remote edit made between
  WPSync's conflict check and its save is not detected.
- The media table exists only in the local root. If it is lost, WPSync cannot
  recognize uploaded images and the next push uploads duplicates.
- Git can store `state.db` as a backup but cannot diff or merge it.

## Intentionally excluded

- Storing credentials or using the OS keychain for the MVP.
- Contacting the blog with credentials during `init`.
- Detecting WordPress-side changes to posts that are unchanged locally,
  except through `pull`.
- Selecting several posts in one command; a command acts on one post or all.
- Linking posts by title, or by slug without confirmation when the pull
  would change what the file says.
