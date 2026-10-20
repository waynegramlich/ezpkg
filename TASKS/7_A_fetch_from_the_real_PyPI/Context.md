# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-19: State (condensed)

* `Details.md` holds the release procedure; it works end to end on
  test.pypi.org.  Newest upload `0.0.1.dev202610192352` (`a4a2af7`:
  `I.ffspo`, the second-program wording, the reconcile fix; release
  run 39344213345), `release_check` and `check.yml` run 39344337125
  (25 jobs) passed.
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
* Before `T.utpat`: `I.wmau` and `I.ffspo` closed; Wayne sets up the
  `pypi` environment, the `v*` tag ruleset and the pypi.org pending
  publisher.  `release.yml` calling `check.yml` (from `T.gar`) is
  listed in `T.utpat`.
* Open children: `T.wrw`, `T.towam` (`T.fwrm`), `T.abfd`, `T.ept`;
  then `T.utpat`.  `T.kdaiis`, `T.reb`, `T.eui` closed 2026-10-19.
  README (tomorrow) gates the pypi.org setup (Wayne: a bad release
  would embarrass him).
* `PyPI_Via_GitHub.md` (top level, git-ignored) is the reusable
  write-up; bring it up to date when the `pypi` half works.
* Commits carry `Assisted-by: Claude Code:claude-opus-5-5` from
  `git_hooks/`; update the model there when it changes.
