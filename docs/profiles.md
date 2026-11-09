# Profiles and credentials

[← WPSync README](../README.md)

## Credentials

WPSync signs in with a WordPress Application Password, which you create in the
WordPress dashboard under **Users > Profile > Application Passwords**.
Application Passwords require the site to use HTTPS.

WPSync reads the password from an environment variable and never stores it. The
variable name comes from the profile name: profile `myblog` reads
`MYBLOG_WP_PASSWORD`. Choose a different variable with `--password-env` when
creating the profile.

## Profiles

A profile maps one local folder to one blog. Profiles are stored in
`~/.wpsync/config.json`. Folders may not overlap between profiles.

From the folder you want to use for the blog:

```console
wpsync init myblog --site https://example.com --username emrah
export MYBLOG_WP_PASSWORD='abcd efgh ijkl mnop qrst uvwx'
wpsync pull
```

`init` checks that the address is a WordPress site and saves the profile
without signing in. It offers the current directory as the profile's folder;
press Enter to accept it, or decline to name another. Use `--local-root PATH`
to name it directly, and omit `-u`/`--username` to be prompted. The username is
your WordPress login name or email address. A blog installed in a subfolder,
such as `https://example.com/blog`, works like any other.

The first `pull` downloads every post and its images (see
[Pulling posts](push-and-pull.md#pulling-posts)). It also says which account
signed in and notes any limits: an account that can edit only its own posts,
such as an Author, does not see other authors' posts.

Commands run inside a profile's folder, or any folder below it, use that
profile automatically. Elsewhere, put the profile name before the command:

```console
wpsync pull              # bring changes from the blog
wpsync myblog pull       # the same, from any directory
wpsync profiles          # list profiles; * marks the current one
wpsync profile --details # show the current profile's settings
wpsync root myblog       # print the profile's folder
wpsync map --local-root /new/folder   # move the profile to another folder
wpsync remove myblog     # remove the profile only
```

`map` asks for confirmation and only changes the local folder. A different
blog needs its own profile, because synchronization state belongs to one blog.
`remove` deletes only the profile; local files and the blog stay unchanged.
