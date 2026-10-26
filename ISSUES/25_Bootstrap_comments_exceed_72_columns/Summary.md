# Summary of `I.bce7c` Bootstrap comments exceed 72 columns
Fixed 2026-10-25 in `ezpkg` 0.0.4, on pypi.org (tag `v0.0.4`,
`ea695ee`).  `R.pcr` keeps comment lines to 72 columns, and the
bootstrap `2026-10-25` had four over.  The new bootstrap `2026-10-26`
keeps every comment line to 68 columns, so `bootstrap.py`'s copy,
indented 4 more, still fits ("Present?", "python.org Macs.", "Do not
edit try block!" moved to the `except` line, Part 1's comment
rewrapped).  It is in every copy and `BOOTSTRAPS`, with `2026-10-25`
kept in `OLD_BOOTSTRAP_TEXTS`.  Rehearsal run 40250369533 (28/28),
release run 40251281792 (28/28), and `release_check.py pypi 0.0.4`
passed.  Not part of this: the other 74 over-long comment lines in
the rest of the code, and 6 errors from local `mypy` 2.4.0 already at
HEAD (`release.yml` pins 1.9.0).  Related: `I.bfms`, `T.ffrp`.
