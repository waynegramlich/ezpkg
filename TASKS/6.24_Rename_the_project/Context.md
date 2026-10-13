# LLM Agent Context Log

## 2026-10-12: Decisions

* Wayne chose `EZPkg`: module `ezpkg`, class `EZPkg`, cache `~/.ezpkg`,
  `EZPKG_*` variables, `.ezpkg` approvals suffix, `ezpkg:` messages.
  `ezpkg`, `ez-pkg`, `ez_pkg` returned 404 on pypi.org and
  test.pypi.org on 2026-10-12.
* Claude renames inside files; Wayne renames the directory and any git
  remote last.  Done together with `T.rd` (bootstrap anatomy, `nopip5`
  with `stdout=2`).

## 2026-10-12: Rename done inside the files; waiting on Wayne

* `git mv` to `ezpkg.py`, `ezpkg_test.py`, `ezpkg_coverage.py`; every
  spelling replaced (`ALT_VENV`, `AltVEnv`, `alt_venv`, `altvenv`).  The
  test `DISTRIBUTION` is `ezpkg`, not `ez-pkg`: unlike `alt-venv` and
  `alt_venv`, those two are different PyPI names.
* `nopip5` = `nopip4` + `stdout=2` (still 35 pasted lines); shipped in
  `quick_start.py`, both README copies, `QUICK_START`, `BOOTSTRAPS`
  (`4512ebb4...`), `SHIPPING`, `FAST_CASES`.  Measured beside `nopip4`:
  3.53 s / 0.16 s against 3.75 s / 0.15 s.  All old cases now use
  `~/.ezpkg` too.
* Quick suite: 254 run, OK, 18 skipped.  The extra skip,
  `test_the_date_keeps_to_older_releases`, borrows a `pip` from the real
  `~/.ezpkg`, which on Wayne's machine is still `~/.alt_venv`.
* README proposals in HTML comments: title/intro, Download Prompt
  stderr, "step 4 never catches it", `stdout=2` bullet.
* Left for Wayne (#5): the directory, the GitHub repository (the test
  wheel's Homepage already says `github.com/waynegramlich/ezpkg`), and
  the `aic`/`ai_contexts` symlinks.  Then close `T.rp`.

## 2026-10-12: Closed

* Wayne accepted all four README proposals; #1 is for now, since he
  will redo the intro.  #3 now says step 4 lists an import your own
  Python happens to have, and releasing refuses it again.
