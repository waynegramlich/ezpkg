# Summary of `T.foec` Flesh out the `EZPkg` class

Closed for now on 2026-10-12, with all 24 child tasks (6.1-6.24) closed.
`EZPkg` now fetches a program's Part 1 packages into a versioned cache
in `~/.ezpkg`, asks before downloading, records and replays approvals
as a lock, scans imports on ordinary runs and before exporting, flags
imports above the bootstrap, stamps a resolution date, culls stale
entries, and exports to `zipapp` and `uv`.  The shipping bootstrap is
`nopip5`, which needs no preinstalled `pip`.  New features get new
tasks; publishing is task 7.
