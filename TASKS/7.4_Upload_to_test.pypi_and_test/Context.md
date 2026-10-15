# LLM Agent Context Log

## 2026-10-12 end of session: where to pick up

* 7.1 is closed: https://github.com/waynegramlich/ezpkg is public, and
  `git push` works over HTTPS through `gh`.  Task 6 is closed.
* Start here: Wayne makes a test.pypi.org account (with 2FA) and an API
  token.  Claude checks what packaging needs: a `pyproject.toml`,
  version `0.0.1`, a wheel holding only `ezpkg.py`, and the Homepage
  `https://github.com/waynegramlich/ezpkg`.

## 2026-10-13: Opened; a dry run passes

* Tasks 7 and 7.2 opened (Wayne: 7 holds information shared by 7.1-7.3).
* No `pyproject.toml` is needed: `ezpkg_test.release_wheel` already
  builds the published wheel by hand (`History.md` in task 7, 6.17.2).
  `release_wheel(dir, distribution="ezpkg", version=dev_version())`
  made `ezpkg-0.0.1.dev202610131741-py3-none-any.whl` (55 KB: `ezpkg.py`
  plus `METADATA`, `WHEEL`, `RECORD`); `uvx twine check --strict`
  passes.  `README.md` has no relative links to break on the PyPI page.
* Plan: upload as `ezpkg` (not a trial name), since the bootstrap
  hard-codes `ezpkg`, with a `.dev` version so `0.0.1` stays clean.
  test.pypi names are separate from pypi.org's.  Wayne holds the token
  and runs the upload (`uv publish` is already installed; `twine` via
  `uvx`).  Then fetch back as a stranger: `quick_start.py` with no
  `~/.ezpkg`, `PIP_INDEX_URL=https://test.pypi.org/simple/` and
  `PIP_EXTRA_INDEX_URL=https://pypi.org/simple/` (for `cowsay`).
* Noticed: `ezpkg.py`'s docstring still says "This file is a
  placeholder.  `EZPkg` is deliberately empty", which ships in the wheel.
* Fixed: Wayne shortened `ezpkg.py`'s header comment and docstring to
  pointers at `README.md` (and its PyPI page); license untouched.
* test.pypi and pypi.org accounts share nothing (users, 2FA, tokens).
  First token must be account-wide; after the first upload, swap it for
  one scoped to `ezpkg`.  Trusted Publishing is an option for 7.3.
* `release_wheel` now writes the wheel's version into the packaged
  module's `__version__` (test `test_the_module_states_the_wheel_version`);
  `__version__` moved up to just after the imports in `ezpkg.py`.
* Every "Step N.M[.K]" in the code became a tag: `T.xyz` for an item,
  "N.M.K of `T.xyz`" for a sub-step in that item's `History.md`.  Old
  6.17.x sub-steps live in `T.ffrp`'s `History.md`, not `T.ewar`.
* The wheel's `Summary` is now the first line of `ezpkg.py`'s docstring
  (`SUMMARY` in `ezpkg_test.py`), so it is written once.  Wayne chose
  "Automatic Package Fetching for One-File Programs" ("Python" is
  redundant on PyPI).

## 2026-10-13: Back to Pending

* The token plan above is superseded: the upload goes through the
  release workflow (`T.wrw`) after hardware 2FA (`T.suh2`), so that it
  rehearses the pypi.org upload (`T.utpat`).  The dry run and the
  fetch-back plan still stand.

## 2026-10-15: The Quick Start works from test.pypi.org

* `ezpkg 0.0.1.dev202610151838` was uploaded by `T.wrw`'s workflow.
* test.pypi.org has a `cowsay` 6.1.2 by an unknown author, newer than
  pypi.org's real 6.1, so `PIP_EXTRA_INDEX_URL=https://test.pypi.org/simple/`
  would fetch a stranger's code.  Never mix the two indexes.
* Instead: the `ezpkg` wheel was fetched from test.pypi.org's JSON API
  (SHA-256 checked) into a directory, and `quick_start.py` was run from
  a copy outside the project with a fresh `HOME`, no `PYTHONPATH` and
  `PIP_FIND_LINKS` naming that directory, everything else from
  pypi.org.  It fetched `pip`, installed `ezpkg` from the wheel, fetched
  `cowsay 6.1` and printed the cow; exit 0.
* The existing suite tests the project's own `ezpkg.py` against its
  local index, so running it says nothing about the published wheel.
  Proposed to Wayne: a release check that does the run above, for
  `testpypi` or `pypi`.
* Wayne: "make it really easy".  `./release_check.py testpypi|pypi
  [VERSION]` does the run above in a temporary directory, pins `ezpkg`
  with `PIP_CONSTRAINT` (so a newer pypi.org release cannot win), and
  passes on exit 0, the cow, and the right `ezpkg-*.dist-info`.
  Passed for `testpypi` 0.0.1.dev202610151838; `pypi` says "no ezpkg
  on pypi" until `T.utpat`.  On failure it leaves the directory.
