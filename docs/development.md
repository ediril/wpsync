# Development and maintenance

[← WPSync README](../README.md)

Install the development environment, then run the tests and lint:

```console
uv sync
uv run pytest
uv run ruff check src tests
```

## Running the checkout's `wpsync`

`uv sync` installs `wpsync` into the project's `.venv` as an editable install.
With that environment activated, `wpsync` runs the checkout's code as it is on
disk, including uncommitted edits, without reinstalling.

`wpsync --version` is fixed when the environment is built, so after a commit it
shows the previous version until you run `uv sync` or any `uv run` command,
which rebuilds it. Run `uv sync` after adding a dependency, too.

## Switching the installed `wpsync`

To use the checkout's code from any terminal, without activating `.venv`,
switch your installed `wpsync` command to the checkout instead. You need only
one of the two. Run this from the repository root:

```console
uv tool install --force --editable .
```

The command then runs the checkout's code, so edits take effect without
reinstalling. `wpsync --version` is computed from Git history when you install;
rerun the command after committing to refresh it. Use `wpsync --legend` for a
quick display check, or run `wpsync diff` from a profile folder to preview its
differences. Pull and diff are read-only; push changes the blog.

To switch back to the published release from PyPI:

```console
uv tool install --force --refresh wpsync
```

`--refresh` makes uv check PyPI again instead of reusing its cached package
index. Without it, uv may reinstall an older release right after you publish.

## Project layout

The PyPI distribution, installed command, and Python package are all `wpsync`.
See [`TODO.md`](../TODO.md) for the ordered work queue and
[`CHANGELOG.md`](../CHANGELOG.md) for completed changes.
[`decisions/`](../decisions/) holds substantial architectural choices and their
rationale, and [`plans/`](../plans/) holds future work. CLI conventions and
current usage are documented in the README; smaller changes are explained in
commit messages.

WordPress-specific code lives in `src/wpsync/wordpress/`. The sync engine, the
post file format, and project state stay platform-neutral so other blogging
platforms can be added later.

## Releasing to PyPI

Releases use `<major>.<work-day>.<increment>` without leading zeroes. Versions
advance from a starting version using Git history, not the build date:

- [`version.json`](../version.json) gives the version of the history's root
  commit, `1.0.1`.
- Each later date with commits advances the work-day number by one, regardless
  of how many idle days pass.
- On the root commit's date, the increment advances from its starting value for
  each later commit. On later work days, it starts at `1` and counts commits on
  that date.
- Dates use each commit's recorded committer date and timezone. Only the
  first-parent history of the current checkout counts; a merge counts once.
  All commits count, including documentation and maintenance changes.

The root commit is `1.0.1`. Another commit on the same date is `1.0.2`. The
next date with a commit produces `1.1.1`, even after a week without changes.

Builds reject backwards-moving commit dates. Wheels and source archives keep
the computed version; installed commands do not use Git. `uv sync` and
`uv run` rebuild the development environment when `version.json`,
`build_backend/versioning.py`, or the current commit changes. A copy installed
with `uv tool install` keeps its version until it is reinstalled. To start a
new major, use `<major>.0.1` as the starting version.

Use an existing PyPI account with two-factor authentication and an API token.
Twine uses credentials from `~/.pypirc` or `TWINE_USERNAME`/`TWINE_PASSWORD`,
and prompts if needed. Do not store the token in the repository.

1. Commit the changes to release. Preparation refuses a working tree with
   uncommitted changes, because the version describes the last commit.
2. Update [`CHANGELOG.md`](../CHANGELOG.md) when useful. Release notes and dated
   headings are optional and do not block publishing.
3. Commit any release-note changes. From that clean checkout, with development
   dependencies installed, run:

   ```console
   ./scripts/publish.sh
   ```

   The script uses the repository's `.venv/bin/python` when available,
   otherwise `python3`; set `PYTHON` to select another interpreter. Through the
   helpers in `scripts/helpers/`, it checks the release identity, runs lint and
   tests, builds the wheel and source archive with `uv build`, checks their
   metadata with Twine, installs the wheel into a clean environment to confirm
   `wpsync --version`, and uploads both artifacts. If `dist/wpsync/<version>/`
   already exists, it reuses those prepared artifacts. New commits advance the
   version; existing artifacts are not rebuilt automatically.

   To prepare and validate artifacts without publishing, run
   `./scripts/publish.sh --prepare`.

4. A Git tag is not required by PyPI. It is strongly recommended for source
   provenance: tag the release commit as `v<version>`, push that tag, and create
   a corresponding GitHub Release.
5. Install the published version in a clean environment and run
   `wpsync --version` before announcing it.

PyPI does not allow a published version to be replaced. If publication fails
after accepting either artifact, create another commit (an empty release-retry
commit is sufficient) and build a new release; do not reuse the failed version.
Publish from one release history: separate branches can compute the same
version and are not separate publication streams.
