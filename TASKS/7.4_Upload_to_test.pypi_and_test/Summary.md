# Summary of `T.uttat` Upload to test.pypi and test

Done 2026-10-15.  `T.wrw`'s workflow uploaded `ezpkg` to test.pypi.org
three times (0.0.1.dev202610151838, ...1925 from `3c25b3c`, ...1933
from `53b8b26`), each approved on GitHub (the first by Claude with
`gh api`, at Wayne's word); a run takes about two minutes.  `./release_check.py testpypi|pypi [VERSION]` is the
test: it runs a copy of `quick_start.py` as a new user (fresh `HOME`,
no `PYTHONPATH` or `PIP_*`), with only the `ezpkg` wheel from
test.pypi.org (SHA-256 checked) and `pip` and `cowsay` from pypi.org,
because test.pypi.org's `cowsay` 6.1.2 is a stranger's.  It pins
`ezpkg` with `PIP_CONSTRAINT`, and passes on exit 0, the cow and the
right `.dist-info`.  The index's newest version is cached for 15
minutes, so with no version it asks `gh` which version the newest
successful `release TARGET` run built (`run-name` in `release.yml`).
All three uploads passed.  The test suite is unchanged: it tests the
project's own `ezpkg.py` against its local index.  Next: `T.utpat`.
