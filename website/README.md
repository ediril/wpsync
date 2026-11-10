# WPSync website

This directory is the complete shared-hosting document root. It requires PHP
8.3 and Apache; there is no build step or package installation.

To check it locally, serve it with PHP's built-in server at
http://localhost:8000 (pass another port as the argument):

```console
./scripts/run_server.sh
```

Deploy the contents of `website/`, including `.htaccess`, directly into the
site's remote document root. The page uses Google Fonts for Space Mono and IBM
Plex Mono; the content security policy in `.htaccess` permits only those font
resources in addition to same-origin assets.

The page derives its canonical URL from the validated request host and exposes
Open Graph and Twitter large-image metadata for `assets/social-preview.jpg`. It
also provides search-engine directives, SoftwareApplication JSON-LD, and a
`rel="describedby"` link to the root `llms.txt` project summary. The page mark
is provided as an SVG favicon, a 32-pixel PNG, a multi-size root `favicon.ico`,
and a 180-pixel Apple touch icon.

The style follows HLSync's site, with a violet accent in place of HLSync's
green so the two read as related but distinct.

The terminal session on the page and in the social preview uses WPSync's real
output formats; keep it in step when those change.

The licensing and pricing section at `#pricing` matches HLSync's: use at no
charge under PolyForm Strict 1.0.0 and commercial licensing by inquiry. The
repository `LICENSE` governs; summaries grant no additional permissions. The
footer notes that WordPress is a trademark of the WordPress Foundation and that
WPSync is not affiliated with it.
