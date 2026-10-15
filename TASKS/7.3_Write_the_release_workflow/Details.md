# 7.3 Write the release workflow

Here are some references:
* [Configuring OpenID Connect in PyPI](
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-pypi)
* [PyPI publish GitHub Action](
  https://github.com/marketplace/actions/pypi-publish)

A GitHub Actions workflow that publishes with Trusted Publishing, the
same for test.pypi.org (`T.uttat`) and pypi.org (`T.utpat`) except for the
target and the environment.

## The Plan

One workflow, `.github/workflows/release.yml`, started by hand
(`workflow_dispatch`, from the Actions tab or `gh workflow run
release.yml -f target=testpypi`).  Its one input, `target`, is
`testpypi` or `pypi`; going live is changing that flag.  Two jobs,
the second waiting for the first:

1. **build** (no special permissions):
   * Checks out the chosen ref and sets up Python 3.12.
   * Runs `./release.py TARGET dist/`, which calls `release_wheel` with
     `distribution="ezpkg"`.  No `pyproject.toml`, no sdist.
     * `testpypi`: the version is `dev_version()`, so every rehearsal
       is new.
     * `pypi`: the version is `ezpkg.__version__`, and the run is
       refused unless it was started on the tag `v` + that version.
   * Runs `twine check --strict` on the wheel, which is the same check
     `ezpkg_test.py` already makes.
   * Saves `dist/` as an artifact.
2. **publish** (environment `TARGET`, `id-token: write`):
   * Downloads `dist/` and runs `pypa/gh-action-pypi-publish@release/v1`,
     with `repository-url: https://test.pypi.org/legacy/` for
     `testpypi` only.

Each environment has Wayne as its required reviewer, so nothing is
uploaded until he approves it on GitHub.

`release.py` is a small new script in the project.  It imports
`release_wheel` from `ezpkg_test.py`, so the tests and the release
build the same wheel.

## What Wayne Sets Up By Hand

* On GitHub (repository Settings):
  * Environments `testpypi` and `pypi`, each with Wayne as a required
    reviewer and deployments limited to tags matching `v*`.
  * A tag ruleset so that only Wayne can create `v*` tags.
* On test.pypi.org and pypi.org (account, "Publishing", "Add a new
  pending publisher"):
  * Project `ezpkg`, owner `waynegramlich`, repository `ezpkg`,
    workflow `release.yml`, environment `testpypi` or `pypi`.
  * A pending publisher does not reserve the name until the first
    upload, so the first upload should not wait long.

## Rehearsing on test.pypi.org

Checked 2026-10-14 (pypi.org/help, discuss.python.org):

* An owner can delete a file, a release or the whole project, on
  test.pypi.org as on pypi.org, and deletion is permanent.
* A deleted filename can never be uploaded again, "even once a project
  has been deleted and recreated", so deleting does not let a version
  be retried.
* Deleting the project releases the name to anyone, and one person who
  deleted a test.pypi.org project in March 2026 could not take the
  name back ("too similar to an existing project").  So never delete
  the `ezpkg` project; deleting a bad release is safe, but only tidies.
* Nothing found says test.pypi.org is wiped on a schedule.

So rehearsals use versions that can be thrown away:

* Target `testpypi` uploads `ezpkg` as `dev_version()`, such as
  `0.0.1.dev202610150300`, as often as needed to get the workflow
  right.
* Target `pypi` uploads the tagged `X.Y.Z` itself.  Everything else
  is the same steps.

Watching it install: the bootstrap fetches `pip` from pypi.org and then
runs it, and `pip` obeys `PIP_INDEX_URL`, so the Quick Start can
probably be tried against test.pypi.org with
`PIP_INDEX_URL=https://test.pypi.org/simple/` and
`PIP_EXTRA_INDEX_URL=https://pypi.org/simple/` (for `cowsay`).  Not yet
tried.  Against pypi.org it needs no flags at all.

## Open Questions

* **Which name goes to test.pypi.org?**  `release_wheel` defaults to
  the rehearsal name `ezpkg_trial`.  Claude recommends `ezpkg` on both
  indexes: they are separate, and the rehearsal should publish exactly
  what the real upload will.
* **Should the build job run the tests?**  `ruff check .` and `mypy .`
  are cheap.  The quick suite reaches the real PyPI and takes about two
  minutes; Claude would leave it to Wayne's machine.
