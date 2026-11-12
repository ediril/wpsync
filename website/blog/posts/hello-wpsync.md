---
title: Hello from WPSync
date: 2026-11-11
description: WPSync keeps a WordPress blog as a folder of Markdown files. This blog will follow its progress.
---

WPSync is a command-line tool that keeps a WordPress blog as a folder of
Markdown files. You pull your posts, write in the editor you already use, see
what changed, and push it back.

```console
$ wpsync init myblog --site https://example.com
$ wpsync pull
$ wpsync create -o
$ wpsync diff
$ wpsync push
```

Each post is a plain file with a short header for its title, date, status, and
categories. Images live in the same folder, linked by relative paths, so Obsidian and
VS Code show them while you write. New posts stay private until you mark them
public, and nothing is deleted from the blog unless you ask.

WordPress is the first platform, and the tool is still early. This blog will
cover new releases, how to set up a writing workflow around WPSync, and the
problems we run into along the way.

To try it, install it with `uv tool install wpsync` and start with the
[README](https://github.com/ediril/wpsync#readme).
