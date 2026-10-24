# Summary of `T.rsbr` README sweep before the release
Done 2026-10-24, after Wayne's full re-read.  Claude fixed spelling and
grammar, synced the table of contents (Troubleshooting, Project
Information) and checked the text against the code; Wayne decided each
mismatch (S1.1-S1.10, S2.1-S2.4, S3.1-S3.2).  Notable outcomes: the
`uv` release is `PROG_NAME-VERSION-uv.py` plus its `.lock`; the cache
purge is 30 days unless `purge-unused-after`; a new import newer than a
developer's frozen date now moves that program's date to today with a
notice (`too_new`, code and test changed) rather than stopping, while a
date written into Part 1 still stops the run; a paragraph credits `uv`
for locking releases for every computer; Project Information says
`EZPkg` was built with Claude Code (Claude Opus 5.5) and that most of
the work is testing, and links to the guide at the top of
`ezpkg_test.py`.  The "Missing Stuff" section, the Claude notes and the
inaccurate "locally installed packages" bullet were deleted; README has
no HTML comments left.  Same day, outside the README: `bootstrap.py`
reduced to the one shipping bootstrap (`2026-10-23`), `email_check.py`
fixed for the `version` setting, `ezpkg_test.py` begins with the steps
before a pull request and "How To Test `EZPkg`", and
`ezpkg_test_all.py` runs every local test in one command.  Related:
`T.ffrp`, `T.utpat`, `T.rd`.
