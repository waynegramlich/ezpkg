# 20 A uv export drops an ezpkg the program imports

A program normally never imports `ezpkg` itself; the bootstrap does,
with `importlib.import_module`.  But one that does (`import ezpkg`, to
use its API) loses it when exported with `EZPKG_EXPORT=uv`: the export
strips the bootstrap, nothing in Part 1 declares `ezpkg` (the bootstrap
supplies it, so `T.kdaiis` never adds it to `dependencies`), and the
export's import check (`check_imports`, `T.cibe`) exempts `ezpkg`.  So
`uv run YOUR_PROG-uv.py` fails at `import ezpkg`.  The `zipapp` export
probably has the same gap.  Untested.

Possible answers: have the export add `ezpkg` to the exported Part 1
when the program imports it, or refuse the export and say why.

Various thoughts:
* Claude (2026-10-15): Found while Wayne dogfooded `T.kdaiis` with
  `import ezpkg`, which is correctly left out of `dependencies` (and
  now gets the author's `mypy` comment).  Rare enough to wait.
