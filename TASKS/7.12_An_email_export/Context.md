# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-22: State (condensed)

* `email` export (with `zipapp` and `uv`): built, and proved on GitHub
  by `email_check.yml` run 39811077056 (13 jobs: builds on every
  runner kind, friends on Windows, macOS, Linux, Python 3.11/3.14).
  `ezpkg` fetches `uv` itself when none is installed (`EZPkg.uv`).
* A developer's `prog.py` is not edited (`EDIT_PROGRAM` off; whether
  never is undecided, so the editing code and its `@editing` tests
  stay; `EZPKG_EDIT_PROGRAM=on` for tests only).  The stash in
  `~/.ezpkg/develop/` holds the entries Part 1 lacks, `checksums`,
  `tags`, `exclude-newer`; seeded from Part 1, else the newest
  `prog.py.releases` entry.  Part 1's own entries and a hand-written
  date are read, never changed.  `upgrade = true` takes the newest
  versions.
* Releases: when `exports` names a form and `release` differs from the
  newest `[[release]]` in `prog.py.releases` (version, date, `commit`,
  `exclude-newer`, `dependencies`; no program copy, no checksums).
  Files to send beside `prog.py` (`prog-X.Y.Z.py`, `.pyz`, `-uv.py`,
  lock); the last release's are removed.  Built from a staged copy.
* `cull`: one number, `CULL_DAYS` 30 days, or a program's `cull-days`
  for what it holds; a `develop/` record stays while its program exists
  (the yes, the stash); `~/.ezpkg/list.py` lists what is held.
* Default suite runs only `nopip8`.

## 2026-10-22: Coverage pass (paused at Wayne's word)

* The traced suite (`./ezpkg_coverage.py --children DIR`, about 23
  minutes, scratch `HOME`) had two blind spots, fixed in
  `trace_hook/sitecustomize.py`: lines run from inside `ezpkg.whl` were
  dropped (`_read` now reads the zip member), and `os.execve` restarts
  lost the first run's counts (saved before `execve`; files named by
  pid and time).  `ezpkg_coverage.py` honours `# pragma: no cover`
  (line, or the block a marked line opens; `unmarked_misses`) and
  writes `missing.txt`.
* Dead code deleted: `stamp`, `summary`, `contains` (now the test
  helper `holds`).  About 15 tests added for edges (helpers on
  malformed blocks, stash/settings/release record, `reconcile`
  failures, import checks, builders, `uv` fetch, `commit_of`).
* Run 4 (all tests OK): `ezpkg.py` 97%, 72 lines unrun, none marked
  yet: Windows `answer_from` (pragma it), release/restart failure
  paths, `own_pip`, `end_user_failure`, `stale`, `too_new`,
  `commit_of`'s timeout, and apparently dead checks in
  `dependency_lines`/`dependency_comments`.  `bootstrap.py` stays at
  45% (old cases; Wayne will delete most).
* Python floor stays 3.11 (Claude's advice: 3.10 reaches end of life
  this month; only `tomllib` needs 3.11 in `ezpkg.py`).

## 2026-10-22 (afternoon): README, template, a Part 1 nobody writes

* Quick Start: Parts 2 and 3 merged into one pasted block, `# Begin the
  EZPkg bootstrap.` to `# End ...` (still `nopip8`: only the `try` is
  fingerprinted; a blank line before `try:` keeps `ruff`'s `I001`
  quiet, which `release.yml` enforces).  Parts now run 1-4.  README
  "Enabling" is three steps: paste Part 2, create `PROG_NAME.py.toml`,
  run.  A developer writes no Part 1.
* `SETTINGS_TEMPLATE` names no program (`PROG_NAME`), is plain text,
  and README shows it verbatim (`test_the_settings_template_is_current`,
  79 columns).  Wayne wrote its header; the stale README text after it
  is deleted.  `T.ept` is in effect done.
* `auto-dependencies` removed (Wayne).  New settings, under "Rarely
  needed": `dependencies` (joins Part 1's in `written`, never removed;
  `part1_entries` is Part 1 alone) and `requires-python` (else
  `python_range`: max of 3.11, `syntax_floor`, `package_floor`; no
  warning, Wayne: one on nearly every release trains people to ignore
  them; checking the standard library under an older Python declined).
* A release writes Part 1 into its copy when there is none
  (`with_script_block`, `with_requires_python` in `staged`).
  `lock_everywhere` keeps entries nothing here fetched, so the `email`
  copy approves `pywin32` for Windows.
* Platform markers from plain guards (`platform_marker`,
  `import_markers`, `marker_holds`, `holds_here`; single quotes inside
  TOML's double).  `MODULE_PACKAGES` gained `pywin32`'s modules and
  `socks`.  An uncaught `ModuleNotFoundError` in a developer's run adds
  its package to the stash, one line, run again (`catch_missing`,
  `add_missing`).
* Warnings: dropped entries are stash `notes` (`noted`; guessed names
  were noted too, until Wayne agreed they were routine noise: a guess
  is added only once `prove` passes); a release's own messages go through `warn`; both land under
  `warnings` in the `[[release]]` entry (`release_warnings`), once, and
  the "Released" line counts them.  A failed release says its warnings.
* Seen end to end in a scratch home; quick suite 349 OK.  GitHub
  `email_check.yml` passed on `d3a7c1e`; the first rehearsal failed on
  `I001` (fixed).  On `b116d02`: rehearsal `0.0.1.dev202610222321`
  (`release.yml` 39871174210), `release_check` passed, `check.yml`
  39871377247 25/25, `email_check.yml` 39871177436 13/13.

## Open

1. `ux/drive.py`: developer steps rewritten (2.1-2.17: no Part 1,
   stash checks, marker, `add_missing`, `dependencies`, a release with
   warnings, the email copy run as a friend's).  Wayne reads `ux/`.
2. Coverage: the 72 lines of the morning, plus today's code, when
   resumed.
3. Later: warn at release when a compiled package lacks a wheel for a
   computer `requires-python` admits; whether `email_check.yml` joins
   `check.yml`.
