# LLM Agent Context Log

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
