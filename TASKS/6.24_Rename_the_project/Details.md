# 6.24 Rename the project

Rename the project, at the very end, just before publishing to
test.pypi.org (`T.ffrp`).  The focus has moved from avoiding virtual
environments to making package management easier, so `AltVEnv` no
longer describes it; Wayne is considering `EZPkg` (`ezpkg`, `ez-pkg`
and `ez_pkg`, one name to PyPI, were free on 2026-10-12; `easypkg` is
taken).  Check the name is still free on PyPI and test.pypi.org first.

What carries the old name:

* The module `alt_venv.py` and its class `AltVEnv`, and every
  `import alt_venv`.
* The bootstrap: the import, `~/.alt_venv`, `pip install alt_venv` and
  the directory check.  So the rename is a new bootstrap, `nopip5`,
  which should also carry `stdout=2` on its `pip install` (`T.m`), and
  `quick_start.py`, both README copies and `bootstrap.py` follow it.
  With `stdout=2`, the README's first-run sample under "Download
  Prompt" should say `pip`'s lines are on standard error.
* The failed-fetch message can then point to the README, whose URL
  depends on the repository name (`T.m`): a shared URL constant keeps
  the `raise` on one source line.
* `test_the_enabling_copy_is_current` (`T.trcb`) finds the README's
  "Enabling `AltVEnv` for Your Program" heading by its exact text, so
  renaming that heading means updating the test.
* The cache directory `~/.alt_venv`, the `ALT_VENV_*` environment
  variables, and the `.altvenv` approvals suffix.
* `alt_venv_test.py`, `alt_venv_coverage.py`, `bootstrap.py`'s
  `PACKAGE` and messages that begin `alt_venv:`.
* `README.md`, `ABOUT.md`, `LICENSE`, `mypy.ini`, `ruff.toml`, and the
  repository and directory names.

Task and issue files are history and keep the old name.
