# Top Level Context

<!-- --------------------------- 79 characters ---------------------------- -->

`CLAUDE.md` holds only `@` imports; project facts that every session
needs live here instead.

## The Files

* `ezpkg.py`: The `ezpkg` package itself (the `EZPkg` class).
* `quick_start.py`: The Quick Start program, and the authority for the
  bootstrap text.
* `bootstrap.py`: Every bootstrap this project has tried, one function
  per case (`nopip1` ... `nopip8`); `nopip8` is the one that ships
  (2026-10-20): it fetches only `ezpkg`'s wheel, keeps it as
  `~/.ezpkg/ezpkg.whl` and imports from it; `EZPkg.own_pip` fetches
  `pip`.  pypi.org has no `ezpkg` yet, so `ux/drive.py` and
  `release_check.py testpypi` put the wheel there themselves.
* `ezpkg_test.py`: The test suite.
* `ezpkg_coverage.py`: Coverage with the standard library `trace`
  (`trace_hook/` carries it into child processes).
* `README.md`: The user documentation, rewritten by Wayne since
  2026-10-19; Wayne leads it.  `README.md.old` is the README before the
  redesign, from which lost text was restored (2026-10-20).
* `release.py`: Builds the wheel to publish (`./release.py
  testpypi|pypi DIR`), using `release_wheel` from `ezpkg_test.py`.
* `.github/workflows/release.yml`: Publishes it with Trusted
  Publishing, after Wayne approves on GitHub (`T.wrw`).
* `release_check.py`: Runs the Quick Start as a new user against a
  published `ezpkg` (`./release_check.py [--python PY] [--console]
  testpypi|pypi [VERSION]`).  `--console` gives it a real terminal
  (a pseudoterminal, or ConPTY via `pywinpty` on Windows) and answers
  the download prompt.
* `.github/workflows/check.yml`: Runs `release_check.py` on GitHub's
  Linux, Windows, Apple Silicon and Intel macOS runners, Python 3.11
  to 3.15, plus python.org's macOS Python without certificates and a
  `--console` job per system: `gh workflow run check.yml -f
  target=testpypi -f version=V` (25 jobs, about 3 minutes; Claude
  starts it).  Started by hand, not yet by `release.yml` (`T.gar`).
* `email_check.py build DIR` / `friend DIR OUT` and
  `.github/workflows/email_check.yml`: `email` and `zipapp` releases
  (`T.ee`) built on every runner kind (Linux and Windows x86_64/ARM,
  macOS ARM/Intel, Alpine in Docker), each fetching `uv` itself
  (`EZPKG_UV=fetch`), then Linux's run as a friend's on Windows, macOS
  and Linux (`gh workflow run email_check.yml`, 13 jobs; Claude
  starts it).
* `ux/drive.py [--keep] [--until STEP | --only STEP...] [--ux-dir
  DIR]`: Runs the scripted UX steps (end user 1.1-1.12, developer
  2.1-2.17, whose program is the Quick Start without Part 1) on a
  pseudoterminal in a temporary copy of the Quick
  Start, as a stranger's real first run: a fresh home, the bootstrap
  fetching `pip` from pypi.org and installing a wheel of the project's
  `ezpkg.py` (`PIP_FIND_LINKS`), everything else from real pypi.org.
  Each step declares the program's mode (`end-user`, `developer`, or
  `gone` when `~/.ezpkg` must be removed) and is checked against it.
  Claude runs it (about 7 minutes, in the background).  The transcript,
  with framed steps, is `ux/drive_output.txt` (ignored); each step is
  also written unframed to `ux/uxNN_NAME.txt` (`NN` is the step's
  position, not its number), which Wayne edits into the agreed output
  and commits, so `git diff ux/` after a rerun shows what is left to
  build (`T.abfd`'s `Context.md`).  A rerun overwrites them; while
  Wayne may be editing them, run with `--ux-dir` into the scratchpad
  and copy back.  Each step also leaves `uxNN_prog.py` (as it ran),
  named on the `.txt`'s third line, so Wayne can `diff` the
  transitions; a step fails if `ezpkg` edits `prog.py`.
  `--only 1.4` runs one step from the snapshot the step before left
  in `ux/.snapshots/` (ignored; dropped when the code changes), or
  after running the earlier steps as unrecorded setup.
  A step can set more environment, such as `EZPKG_ANSWER_SECONDS=3`
  for the no-answer step.  The `ux/uxNN_prog*.py` snapshots are excluded from `ruff` and `mypy`.
* `git_hooks/`: `prepare-commit-msg` adds `Assisted-by: Claude
  Code:claude-opus-5-5` to Wayne's commit messages (deletable in the
  editor), and `commit-msg` refuses a message that is only that
  trailer.  On per clone with `git config core.hooksPath git_hooks`.
  Update the trailer when the model changes.

## The Bootstrap Has Three Copies

`quick_start.py` is the authority, and the test suite fails until these
match it:

* The Quick Start copy in `README.md`.  Its "Enabling `EZPkg` for a
  Program" says to copy Part 2, the bootstrap from `# Begin` to `# End`
  (its imports included), from `quick_start.py`, so it has no copy of
  its own (Wayne, 2026-10-22).  A developer writes no Part 1.
* `QUICK_START` in `ezpkg.py`.
* The `nopip8` function in `bootstrap.py` (which spells the package name
  as `PACKAGE` and the index as `JSON_API`).

A changed bootstrap is a new one, comments and spaces included
(`T.reb`: `EZPkg` refuses any bootstrap that is not, line for line once
trimmed, a published one).  It needs a new `nopipN` name, its
fingerprint added to the end of `BOOTSTRAPS` in `ezpkg.py`, and the
previous text kept in `OLD_BOOTSTRAP_TEXTS`.  `bootstrap.py`'s copies
spell things as variables, so its harness sets
`EZPKG_BOOTSTRAP=unchecked`.

Part 1 of every released program lists `ezpkg` first (the Quick
Start's is `ezpkg>=0.0.1.dev0,<0.1` until the real release), and that
entry chooses which `ezpkg` runs it (`T.eui`).  A release writes Part 1
into its copy when the program has none (`with_script_block`), with a
`requires-python` worked out from the syntax and the packages
(`python_range`), or the setting.

`SETTINGS_TEMPLATE` in `ezpkg.py` is the authority for what an empty
`prog.py.toml` is filled with, and `README.md`'s "`prog.py.toml`
Settings" shows it verbatim (Claude copies it after every change; a
test fails otherwise, or on a line over 79 columns).  It names no
program: `PROG_NAME` is the README's word (Wayne, 2026-10-22).

## The Two Modes (`T.abfd`, 2026-10-19)

A `prog.py.toml` beside `prog.py` makes it its developer's: no
questions, the packages kept in step with the imports silently, and
the versions frozen.  There is no `auto-dependencies` any more (Wayne,
2026-10-22): `dependencies` in `prog.py.toml` names what the imports
cannot (extras, exact versions), and Part 1's or its entries are never
removed.  A platform-guarded import gets a marker (`import_markers`);
an uncaught `ModuleNotFoundError` adds its package to the stash and
asks for another run (`add_missing`).  Dropped entries are noted in
the stash (`noted`; a guessed name is proved, so not noted), and the
next release lists them, with its own warnings (`warn`), under `warnings` in its
`prog.py.releases` entry; its one "Released" line counts them.  Since 2026-10-22 the developer's `prog.py` is not
edited (`EDIT_PROGRAM` off; whether it is never edited is undecided, so
the editing code and its `@editing` tests stay, switched on by
`EZPKG_EDIT_PROGRAM=on`, tests only).  What `ezpkg` works out (entries
for imports Part 1 lacks, `checksums`, `exclude-newer`, `released`)
is the program's stash in its `~/.ezpkg/develop/` record
(`EZPkg.stash`), seeded from Part 1 or the newest `email` build; Part
1's own entries and a hand-written date are read, never changed;
`upgrade = true` in `prog.py.toml` takes the newest versions; a
release merges the stash into a staged copy (`staged`) that its forms
are built from.  Releases are off until `exports` in
`prog.py.toml` names a form and `release` names a version (the
template leaves `exports = [` open with each form's line commented
out, and `release` commented out).  Then a developer's run where
`release` differs from the newest entry of `prog.py.releases` builds
that release (the forms `exports` names, in `EXPORT_FORMS` order:
`email`, `zipapp`, `uv`) beside `prog.py` as `prog-X.Y.Z.py`,
`.pyz`, `-uv.py` and its lock (`release_files`), removes the last
release's files, appends a `[[release]]` entry (version, date, commit,
`exclude-newer`, `dependencies`; `release_entry`) to
`prog.py.releases`, and then runs the program (Wayne, 2026-10-22: one
file for version control, no folder).  A lost stash is seeded from the
newest entry.  `cull` uses one number, 30 days (`CULL_DAYS`, or a
program's `cull-days`), and keeps a `develop/` record while its
program exists; `~/.ezpkg/list.py` lists what the cache holds.  An entry nothing imports goes once the latest recorded run
declared it and none of the last 10 loaded it (`unused_lately`,
`note_loaded`); a comment keeps it.  Without one, `prog.py` is an end user's: one question per
program, ever, and the program is never edited.  `prog.ezpkg`,
`EZPKG_APPROVE`, `EZPKG_EXPORT` and `EZPKG_BOOTSTRAP=check` are gone.

## Testing and Linting

* Quick tests, during development (about 2 minutes):
  `EZPKG_TEST=NONE ./ezpkg_test.py`.  A single class or method can be
  named after it.
* The full suite (`./ezpkg_test.py`, or `EZPKG_TEST=COMPLETE` for every
  `bootstrap.py` case) runs only when Wayne asks.  Its default
  (`FAST_CASES`) is `nopip8` alone (Wayne, 2026-10-22).
* Coverage: `./ezpkg_coverage.py --children DIR` (about 23 minutes,
  in the background, scratch `HOME`) annotates into `DIR` and lists the
  unrun lines not marked `# pragma: no cover` in `DIR/missing.txt`.
  Keep pragmas few (Wayne).  `ezpkg.py` was 97% on 2026-10-22.
* Tests of the old Part 1 editing are marked `@editing`
  (`EZPKG_EDIT_PROGRAM=on`); `run_as_developer` edits too, so end-user
  tests find approvals in Part 1.
* The date tests need a `pip` 26 or newer in `~/.ezpkg`, and skip
  without one.  This machine has no `~/.ezpkg`, so run the suite with
  `HOME` set to a scratch home whose `.ezpkg/pip.whl` is a current
  `pip` (`pip download pip --no-deps`).
* `ruff check .` and `mypy .`; both check against the Python 3.11 floor,
  and both must pass (`release.yml` runs `ruff`; the bootstrap's
  imports need their blank line before `try:`).

## Working With Wayne

* `README.md` rewrites are proposed in HTML comments beside the old
  text, with the line ranges of both (recheck them, since they shift);
  when Wayne says delete, delete.  Never nest HTML comments: an inner
  `-->` ends the outer one.  Wayne answers with `<!-- Claude: ... -->`
  notes, and open items are `<!-- Issue: ... -->` comments.  Re-read
  the file before editing, since Wayne edits it between turns.
* Wayne does his own end-to-end reads of `README.md`.
* Wayne prefers discussing in chat to notes in `Details.md` files.
* Startup context must stay under 150k characters.  Near the end of a
  major session, move superseded `Context.md` entries into the item's
  `History.md` (not loaded at startup), leaving `Context.md` as the
  current state, decisions still in force, open questions and next
  steps.
* Claude may push to GitHub, and start and approve `testpypi` release
  runs, but never commits; Wayne commits staged changes.
* `ezpkg` is on test.pypi.org (`T.uttat`) but not yet on pypi.org
  (`T.utpat`), so the Quick Start does not yet work for a new user;
  `ux/drive.py` installs a wheel of the project's `ezpkg.py`, and
  `release_check.py` checks what was published.
