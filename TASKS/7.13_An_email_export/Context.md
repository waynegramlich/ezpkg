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

## Open

1. `README.md`: edit together (next session).  To document: `upgrade`,
   `cull-days`, `release` + `exports`, `prog.py.releases`, `list.py`;
   the line after a yes now names `list.py`.
2. `T.ept`: template wording (Claude rewrote the release paragraph,
   added `upgrade` and `cull-days`).
3. `ux/drive.py` developer steps (2.x) are stale (edits, old trigger).
4. Coverage: the 72 lines above, when resumed.
5. Later: warn at release when a compiled package lacks a wheel for a
   computer `requires-python` admits; an `email` step in
   `ux/drive.py`; whether `email_check.yml` joins `check.yml`.
