# Summary of `I.srlfnp` The second run looks for a newer pip
Fixed 2026-10-25 in `ezpkg` 0.0.2, on pypi.org (tag `v0.0.2`,
`597bcdb`).  Wayne saw the second run of the Quick Start pause about
1.5 s: `own_pip` fetched a private `pip` on the first run without
writing the `last_pip` stamp, so the next run's `refresh_pip` ran
`pip download pip`.  `own_pip` now writes it; the test checks the next
`refresh_pip` starts no `pip`; and `release_check.py` fails when a
fresh `pip.whl` has no `last_pip`, so every `check.yml` runner tests
it (0.0.1 fails it; 0.0.2 passes, 27/27 in release run 40150840045,
whose first four `check` jobs failed because pypi.org's index served
only 0.0.1 for a minute after the upload, and passed when re-run).
Related: `T.utpat`, `I.spinu`.
