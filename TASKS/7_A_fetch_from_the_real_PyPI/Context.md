# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-22: State (condensed)

* `Details.md` holds the release procedure; it works end to end on
  test.pypi.org.  Newest upload `0.0.1.dev202610222321` (from
  `b116d02`): `release_check` passed, `check.yml` 39871377247 25/25,
  `email_check.yml` 39871177436 13/13.
* Rehearsal, as Claude runs it in the background (about 6 minutes):
  `git push github main`; `gh workflow run release.yml -f
  target=testpypi`; approve via `gh api -X POST
  repos/waynegramlich/ezpkg/actions/runs/R/pending_deployments -F
  "environment_ids[]=E" -f state=approved -f comment=...` (GitHub
  refuses it without a `comment` since 2026-10-24; E from a GET of the same
  URL, `.[0].environment.id`); `gh run watch R --exit-status`;
  `./release_check.py testpypi` (its last line names the version);
  `gh workflow run check.yml -f target=testpypi -f version=V`; watch.
* Claude starts and approves `testpypi` runs; a `pypi` run needs Wayne.
* `v0.N.M` versions are disposable: a bad one is followed by the next
  number, never repaired.  The tag comes after the test.pypi.org
  rehearsal, since a pushed tag should never move.
* Open children: `T.rsbr` (Wayne's README sweep, 2026-10-23), then
  `T.utpat`, the last task.  Closed 2026-10-22: `T.wrw`, `T.towam`,
  `T.fwrm`, `T.abfd`, `T.ept`, `T.ee`; and every issue (`I.wmau`,
  `I.ffspo`, `I.htdwcp`).  No issue is open.
* For `T.utpat`, carried from `T.wrw`: Wayne sets up the `pypi`
  environment (tags `v*` only), the `v*` tag ruleset and the pypi.org
  pending publisher; Claude makes `release.yml` call `check.yml` after
  `publish`, and the Quick Start's `ezpkg>=0.0.1.dev0,<0.1` entry fits
  the real version.  The `pypi` path of `release.yml` has never run.
* `PyPI_Via_GitHub.md` (top level, git-ignored) is the reusable
  write-up; bring it up to date when the `pypi` half works.
* Commits carry `Assisted-by: Claude Code:claude-opus-5-5` from
  `git_hooks/`; update the model there when it changes.

## 2026-10-23

* The bootstrap changed (`2026-10-23`, its fingerprint in `BOOTSTRAPS`),
  so the test.pypi.org upload `0.0.1.dev202610222321` is stale: the next
  rehearsal must upload a fresh build before `release_check` passes.
* The cache's `remove.py`, `list.py` and `quick_start.py` are now
  executable on Linux and macOS (`refresh(..., executable=True)`, which
  also mends an existing cache).
* The quick suite is `./ezpkg_test.py` (`FAST`): it must run the latest
  bootstrap's case.  `EZPKG_TEST=NONE` is only the coverage baseline.

## 2026-10-24

* `T.rsbr` (README sweep) closed; `T.utpat` is the only open child.
* Code changed today, so the next test.pypi.org rehearsal must upload
  a fresh build (bootstrap `2026-10-23`, `too_new` moves a developer's
  date, `bootstrap.py` has one case).  `email_check.py` was broken by
  the 2026-10-23 template (`version`, not `release = "1.0.0"`) and is
  fixed; `email_check.yml` has not run since.
* Next (Wayne, 2026-10-24): after his commit, a couple of coverage runs
  (`./ezpkg_test_all.py DIR`, or `./ezpkg_coverage.py --children DIR`)
  with tests added for missed lines; then the rehearsal and `T.utpat`.
* Later the same day, while Wayne was out: `ux/drive.py` steps 2.10
  and 2.14 used the old setting names (`upgrade`, `exports`) and failed;
  fixed and passing (2.10 now only checks that `update-frequency =
  "daily"` runs).  Coverage work: 8 new tests and 6 extended in
  `ezpkg_test.py` (one, `test_reconcile_when_a_fetch_or_an_edit_fails`,
  had a truthy `too_new` mock that hid the no-retry path); `ezpkg.py`
  went from 69 unrun lines to 29.  All uncommitted, for Wayne's review.
* S4 decisions (Wayne, same evening): S4.1 the four unreachable guards
  marked `# pragma: no cover`; S4.2 the Part 1 editing code deleted
  (`EDIT_PROGRAM`, `restart`, `first_run_note`, `edit_part1`,
  `edit_for`, the `mypy` comments, 19 `@editing` tests), with
  end-user tests now getting approvals from a real `email` copy
  (`run_as_developer`, S4.2.1); S4.3 left; S4.4 kept (live code).
  After: 342 tests, `ezpkg.py` 17 unrun lines; `ux/drive.py` 29/29.
  Uncommitted, for Wayne's review.
* Rehearsal of `bee374f` (Wayne's commit after S4.2): release run
  40142778665 uploaded `0.0.1.dev202610242327`; `release_check.py
  testpypi` passed; `check.yml` 40143578538 25/25 and
  `email_check.yml` 40143580763 13/13.  S4.5 (an end user's copy whose entry asks for
  another version than its approval: its own "conflict" line) is
  made after that commit; with it the quick suite passed (342 tests,
  4 skipped), and Wayne commits it.
* Next: rehearse Wayne's S4.5 commit on test.pypi.org (a fresh dev
  build; `release_check`, `check.yml`, `email_check.yml`), then
  `T.utpat`: Wayne's `pypi` environment, `v*` ruleset and pending
  publisher; Claude's `release.yml` calling `check.yml`; the tag; the
  approved `pypi` run; `./release_check.py pypi`.
* Rehearsal of `c124b71` (S4.5 committed): release run 40145136428
  uploaded `0.0.1.dev202610250003`; `release_check.py testpypi`
  passed; `check.yml` 40145216400 25/25; `email_check.yml`
  40145218708 13/13.
* `T.utpat` setup, 2026-10-25 UTC: Wayne added the pypi.org pending
  publisher (`ezpkg`, `waynegramlich/ezpkg`, `release.yml`, `pypi`).
  Claude, by `gh api` (Wayne: do as much as possible through `gh`):
  the `pypi` environment now has Wayne as required reviewer and a
  `v*` **tag** rule (it had a `v*` branch rule and no reviewer); the
  tag ruleset `release tags` (id 25802525) forbids creating, moving or
  deleting `v*` tags except for the repository admin.
* `release.yml` now ends with a `check` job calling `check.yml`
  (which gained a `workflow_call` trigger) with the version `build`
  read from the wheel's name.  Committed by Wayne as `95dd84a`;
  rehearsed: release run 40147083384 27/27 (build, publish and the 25
  `check` jobs) for `0.0.1.dev202610250032`, `release_check.py
  testpypi` passed, `email_check.yml` 40147238981 13/13.
* **Released 2026-10-25: `ezpkg` 0.0.1 on pypi.org.**  Claude tagged
  `95dd84a` as `v0.0.1` (annotated, pushed; Wayne: "All I own is
  `git commit`"), started release run 40147698445 (`--ref v0.0.1 -f
  target=pypi`; Claude Code's permission check refused the first
  try until Wayne said go) and approved its `pypi` deployment:
  27/27, `ezpkg-0.0.1-py3-none-any.whl` on pypi.org, and
  `./release_check.py pypi 0.0.1` passed.  `T.utpat` closed.
