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
