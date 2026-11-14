# Platforms and HLSync

Date: 2026-10-25

## Decision

WordPress is the first and, for the MVP, only supported platform. Everything
specific to it, such as REST API calls and WordPress's HTML conventions, lives
in `src/wpsync/wordpress/`. The sync engine, the local post file format, and
the project state stay platform-neutral.

WPSync follows HLSync's user experience and CLI conventions: profiles that map
a folder to a site, a profile inferred from the current directory, credentials
read from environment variables, and HLSync's diff and transfer output. It
shares no code or dependencies with HLSync.

## Rationale

Other blogging platforms are likely later. Keeping the platform behind one
package boundary lets a second platform arrive as a new adapter rather than a
rewrite of the engine, the file format, and existing users' state.

People who use both tools should find them behave alike, so a convention
HLSync already has is followed rather than redesigned. Sharing code would tie
the two release histories and licenses together for little gain, since the
overlap is in conventions, not in implementation: one synchronizes files over
FTP, the other posts through a blog's API.

## Boundaries

Where WPSync deliberately differs from HLSync, the difference is recorded with
the decision it belongs to, such as `init` in place of HLSync's `create` (see
the profiles decision).
