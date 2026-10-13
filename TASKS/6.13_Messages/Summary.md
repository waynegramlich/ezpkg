# Summary of `T.m` Messages

Messages go to standard error, never standard output, with one
exception found by the 2026-10-01 survey: the bootstrap's `pip install`
progress on a first run.  Wayne decided it gets `stdout=2` in `nopip5`,
made with the rename (`T.rp`).  The download prompt's wording is
Wayne's and is documented in README, including the `Really never ask
again?` confirmation after `a`.  A failing `install()` inside the
bootstrap ends in one `alt_venv: ... failed:` line, not a traceback.
Deferred to `T.rp`, since the URL depends on the repository name: a
README link in the failed-fetch message.  Related: `T.rp`, `T.rd`.
