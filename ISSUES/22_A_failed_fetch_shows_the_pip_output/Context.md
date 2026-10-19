# LLM Agent Context Log

## 2026-10-17: Filed

* Filed and opened at Wayne's word, priority 1, from the `run` dogfood
  (`~/ezpkg_dogfood/output`).  Not started; Wayne: "punted for now".
* Related code: `EZPkg.download`/`provide` raise
  `RuntimeError("could not fetch ...: <stderr>")`; `failure_reason`
  (from `T.kdaiis`) already picks `pip`'s `ERROR:` line, but only
  `reconcile` uses it.  `T.eui` Details item 4 wants one line naming
  the `ezpkg` a program needs when none can be had.
* Case 5 (no private `pip`) added at Wayne's word; found when
  `~/ezpkg_dogfood/run` (project on `PYTHONPATH`) used the system's
  `pip` 24.0.  The harness now gives its home a `pip.whl`.
* Control-C at any `ezpkg` question, or during a download, printed a
  `KeyboardInterrupt` traceback (found by `~/ezpkg_dogfood/drive`).
  Fixed the same day in `install()` (see `T.kdaiis`'s `Context.md`):
  one line, `ezpkg: interrupted, so prog.py stops here.`  Leftover
  downloads in `pending/` are left for `cull`.

## 2026-10-19: Built (Wayne: "you do the work and summarize")

* `EZPkg.end_user_failure`, from `install_declared` when the program
  is not its developer's: one line, never `pip`'s text, which goes to
  `~/.ezpkg/last_failure.txt` (date, program, `ezpkg`, Python,
  platform, then `pip`'s output); the line names that file for the
  author, except in the no-network case.
  1. No network (`NO_NETWORK` patterns): "`prog.py` needs software
     packages from the internet, but the internet could not be
     reached, so `prog.py` did not run.  Connect, then run it again."
     Checked end to end with a dead `PIP_INDEX_URL`.
  2. A pinned version gone (`unavailable`, using `index_files`):
     "`prog.py` needs cowsay 6.1, which PyPI no longer offers ...  Its
     author can send a newer `prog.py`."
  3. No wheel here: "... which has no version for this computer
     (Python 3.12 on Linux x86_64) ...".
  4. Noise: never shown; anything else is "`prog.py` could not get its
     software packages, so it did not run: ERROR: ..." (`pip`'s
     `ERROR:` line).
  5. No private `pip`: `EZPkg.own_pip` fetches `pip.whl` as the
     bootstrap does (`fetch_url`: `urllib`, then `curl`), only for the
     real `~/.ezpkg` (a named cache keeps the interpreter's `pip`);
     never fatal.  Called at the start of `download`.
* Tests: `test_an_end_users_failed_fetch_is_one_plain_line` (cases
  1-4, `index_files` mocked), `test_only_the_real_cache_fetches_its_own_pip`.
  Cases 2, 3 and 5 are not yet seen end to end.
