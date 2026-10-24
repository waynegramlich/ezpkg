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
  "environment_ids[]=E" -f state=approved` (E from a GET of the same
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
* A Quick Start run outside the project fails with `ezpkg: download
  ezpkg failed: <HTTPError 404>` until `ezpkg` is on pypi.org: the
  bootstrap asks pypi.org only.  Before then, run it with
  `PYTHONPATH="$HOME/public_html/projects/ezpkg"`.
* The cache's `remove.py`, `list.py` and `quick_start.py` are now
  executable on Linux and macOS (`refresh(..., executable=True)`, which
  also mends an existing cache).
* The quick suite is `./ezpkg_test.py` (`FAST`): it must run the latest
  bootstrap's case.  `EZPKG_TEST=NONE` is only the coverage baseline.
