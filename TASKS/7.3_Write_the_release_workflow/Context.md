# LLM Agent Context Log

Earlier entries are in `History.md`.

## 2026-10-19: State (condensed)

* `release.py` and `.github/workflows/release.yml` work (first run
  38787209885; many rehearsals since).  `release.py` builds in a
  temporary directory and copies only the wheel out; `dist/` is
  git-ignored.  The build job runs `ruff` 0.17.0 and `mypy` 1.9.0.
* The `testpypi` environment (reviewer `waynegramlich`, branch `main`)
  and the test.pypi.org pending publisher are set up.
* Left for `T.utpat`: the `pypi` environment (tags `v*` only), the
  `v*` tag ruleset, the pypi.org pending publisher.  Wayne keeps this
  task open until then.
