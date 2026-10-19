# History

Earlier `Context.md` entries, moved here on 2026-10-19 to keep startup
context small.  Not loaded at startup.

## 2026-10-14: Trusted Publishing checked against docs.pypi.org

* Publisher fields: owner, repository, workflow filename; environment
  optional but "strongly" recommended (required reviewers).
* `id-token: write` is mandatory and belongs on the job, not the
  workflow.  Action `pypa/gh-action-pypi-publish@release/v1`; TestPyPI
  via `repository-url: https://test.pypi.org/legacy/`.
* Build in a separate job and hand the files over as an artifact; use
  tag protection for `v*`.
* A pending publisher does not reserve the name until its first
  upload, and is invalidated if someone else registers the name first.
* `release_wheel` (`ezpkg_test.py`) defaults to `ezpkg_trial`;
  `dev_version()` makes `X.Y.Z.devYYYYMMDDHHMM`.

## 2026-10-14: Where this stopped

* `Details.md` holds the plan, rewritten twice today: one manual
  workflow with input `target` (`testpypi` uploads a `dev_version()`,
  `pypi` the tagged `X.Y.Z`), because deleting on test.pypi.org never
  frees a filename.  Wayne agreed that going live should be a flag.
* Still open: `ezpkg` rather than `ezpkg_trial` on test.pypi.org
  (Claude recommends `ezpkg`), and whether the build job runs only
  `ruff` and `mypy`.
* Next: ask Wayne those two, then write `release.py` and
  `.github/workflows/release.yml`.  Nothing is written yet, and
  nothing is set up on GitHub, test.pypi.org or pypi.org.

## 2026-10-15: Written

* Wayne settled both questions: `ezpkg` on both indexes (`release.py`
  passes `distribution="ezpkg"`; `RELEASE_DISTRIBUTION` in the tests
  stays `ezpkg_trial`), and the build job runs only `ruff` (0.17.0) and
  `mypy` (1.9.0), pinned to Wayne's versions.
* `release.py` and `.github/workflows/release.yml` written.  Locally:
  `ruff`, `mypy` pass; `./release.py testpypi DIR` builds
  `ezpkg-0.0.1.devN-py3-none-any.whl`, which `twine check --strict`
  passes; `pypi` refuses an untagged HEAD.  `dist/` is git-ignored.
* `release_wheel` writes a module copy beside the wheel, so `release.py`
  builds in a temporary directory and copies only the wheel out.
* The reordered procedure (`T.ffrp`) means `testpypi` runs from untagged
  commits, so its environment allows branch `main`, not tags `v*`.  The
  `pypi` environment is limited to `v*` tags.
* Next: Wayne commits and pushes, sets up the `testpypi` environment and
  the test.pypi.org pending publisher, and runs it (`T.uttat`).

## 2026-10-15: The first run worked

* Wayne set up the `testpypi` environment (reviewer `waynegramlich`,
  branch `main`; checked with `gh api`) and the test.pypi.org pending
  publisher.  `gh auth refresh -s workflow` was needed before a push
  could add `.github/workflows/`.
* Run 38787209885 (`gh workflow run release.yml -f target=testpypi`):
  build passed, Claude approved the deployment with `gh api ...
  pending_deployments` at Wayne's word, publish passed.
  `ezpkg 0.0.1.dev202610151838` is on test.pypi.org; `pip install` from
  there into a scratch venv imports it with that `__version__`.
* Left for `T.utpat`: the `pypi` environment (tags `v*` only), the
  `v*` tag ruleset and the pypi.org pending publisher.
