# Summary of `I.bfms` The bootstrap fails mypy strict
Fixed 2026-10-25 in `ezpkg` 0.0.3, on pypi.org (tag `v0.0.3`,
`42a3505`).  Wayne's other Claude instance found that `mypy --strict`
(asked for by `R.pcr`) failed on the pasted bootstrap `2026-10-23`:
`def g(u)` was untyped and `req.URLError` is not exported by
`urllib.request`.  The new bootstrap `2026-10-25` types `g` (`u: str`,
`-> bytes`, wrapping `urlopen(...).read()` in `bytes()`) and imports
`urllib.error`; its comments were shortened to fit 79 columns.  It is
in every copy and `BOOTSTRAPS`, with `2026-10-23` kept in
`OLD_BOOTSTRAP_TEXTS`, so programs carrying it still run.  `mypy.ini`
now sets `strict = True`, and the tests patch standard modules
directly.  Release run 40166940783 passed 28/28 (its new `listed` job
waited 24 s for pypi.org to name 0.0.3), and `release_check.py pypi
0.0.3` passed.  Same day: a README Troubleshooting entry says
`__pycache__/`, `.mypy_cache/` and `.ruff_cache/` come from Python and
the tools, not from `EZPkg`.  Related: `I.srlfnp`, `T.reb`, `T.ffrp`.
