# WPSync website

This directory is the complete document root for
[wpsync.dev](https://wpsync.dev). It requires PHP 8.3 or later, served by
nginx with PHP-FPM. [`nginx.conf`](nginx.conf) is the site's configuration.

Install the PHP dependencies once, and again whenever `composer.lock` changes:

```console
composer install --no-dev -d website
```

To check the site locally, serve it with PHP's built-in server at
http://localhost:8000 (pass another port as the argument):

```console
./scripts/run_server.sh
```

Deploy the contents of `website/`, including `vendor/`, into the site's
remote document root, `/var/www/wpsync`. `nginx.conf` is the complete site
configuration: HTTPS with the Let's Encrypt certificate for wpsync.dev, the
redirect from HTTP, routing of blog addresses to `blog/index.php`, and hiding
`vendor/` and the Composer files.

## Pages

- `index.php` is the homepage.
- `site.php` holds the parts every page shares: the `<head>` metadata, the
  header and navigation, and the footer.
- `blog/index.php` serves the post list at `/blog/` and each post at
  `/blog/<slug>`. The `/blog/` location in `nginx.conf` routes those addresses
  to it; PHP's built-in server does the same locally without configuration.

## Blog posts

Each post is a Markdown file in `blog/posts/`. Its file name is its address:
`blog/posts/hello-wpsync.md` is served at `/blog/hello-wpsync`. Use lowercase
letters, digits, and hyphens.

The file starts with a YAML header:

```markdown
---
title: Hello from WPSync
date: 2026-11-11
description: One or two sentences for the post list and search results.
---

The post, in GitHub-flavored Markdown.
```

All three fields are required. The list shows the newest post first. A post
appears as soon as its file is deployed.
