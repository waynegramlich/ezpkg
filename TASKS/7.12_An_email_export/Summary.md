# Summary of `T.ee` An email export

Done 2026-10-22.  A release's `email` form, `PROG_NAME-VERSION.py`, is
the program with a Part 1 approved for every computer and Python its
`requires-python` admits (`build_email`, `lock_everywhere`,
`everywhere_approvals`; `ezpkg` fetches `uv` itself), proved on GitHub
by `email_check.yml` (13/13).  The same day: a developer's `prog.py` is
never edited (the stash in `~/.ezpkg/develop/`); releases follow
`release` + `exports` and are recorded in `PROG_NAME.py.releases`; a
developer writes no Part 1, and a release writes one (with a worked-out
`requires-python`); platform markers from guards; a missing module
adds its package; `dependencies` and `requires-python` settings;
warnings in the release entry; messages name the `prog.py.toml` line
that caused them; `cull` uses 30 days and `list.py` lists the cache.
Coverage, end of day: `ezpkg.py` 97%, 80 lines unrun (none marked;
mostly Windows-only, timeout and `EDIT_PROGRAM` paths), 353 tests.
Left for later: warning at release when a
compiled package lacks a wheel for a computer `requires-python` admits.
Related: `T.abfd`, `T.ept`, `I.htdwcp`.
