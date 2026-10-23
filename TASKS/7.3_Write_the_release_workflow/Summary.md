# Summary of `T.wrw` Write the release workflow
Done 2026-10-22.  `.github/workflows/release.yml` (started by hand,
`gh workflow run release.yml -f target=testpypi|pypi`) builds the wheel
with `./release.py TARGET dist/` (`release_wheel` from `ezpkg_test.py`;
`testpypi` is a disposable `dev_version()`, `pypi` is
`ezpkg.__version__` and only from its `v` tag), runs `ruff`, `mypy`
and `twine check --strict`, and publishes with Trusted Publishing
after Wayne approves the environment.  `testpypi` has run many times
since run 38787209885; its environment and pending publisher are set
up.  The `pypi` path is written but has never run.  Carried to
`T.utpat`: the `pypi` environment (tags `v*` only), the `v*` tag
ruleset, the pypi.org pending publisher, and `release.yml` calling
`check.yml` after `publish`.  Related: `T.uttat`, `T.utpat`, `T.gar`.
