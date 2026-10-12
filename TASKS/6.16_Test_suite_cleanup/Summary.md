# Summary of `T.tsc` Test suite cleanup

`alt_venv_coverage.py` measures the suite with the standard library's
`trace`, children and server threads included, and `--per-case` shows
what each `bootstrap.py` case adds beyond a no-case baseline, so cases
can be culled on evidence.  `FAST_CASES` ran `nopip1` to `nopip4`; the
other ten cases stay in `bootstrap.py` but do not run by default
(Wayne).  The last question, 6.16.4, was settled 2026-10-12:
`--per-case` now copies the project into `<directory>/project/` and
measures and compares there (`take_snapshot`), so edits made during the
quarter-hour run cannot spoil its report; `--compare` uses the same
copy.  A real run that day (baseline 743 s) found `nopip4` adds 140
lines, `nopip1` 29 more, and `nopip2` and `nopip3` nothing beyond them,
so Wayne dropped those two from `FAST_CASES`, leaving `nopip1` and
`nopip4`.
