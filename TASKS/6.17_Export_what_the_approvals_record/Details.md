# 6.17 Export what the approvals record

Turn a working `AltVEnv` program into other forms, using what
`AltVEnv` already knows about it.  After `ALT_VENV_APPROVE=write`, the
approvals file beside the program (`prog.altvenv`) names every wheel
the program uses, with its exact version and SHA-256, and the wheels
are in the cache: in effect a lock file.  Each export is a view of it,
chosen with one variable, `ALT_VENV_EXPORT`, and written instead of
running the program:

* `pins`: prints Part 1's `dependencies` with every package pinned to
  an exact `==` version, ready to paste back in (a "freeze").
  Removed 2026-10-12: the `exclude-newer` date that `write` puts in
  Part 1 does its job for a `.py` sent on its own (`T.srdisb`).
* `zipapp`: writes `prog.pyz`, the program and its packages in one
  file that runs with `python3 prog.pyz`, with no network and no
  `~/.alt_venv`.  Pure-Python packages only, for now.
* `uv`: writes `prog-uv.py` and its lock file, for people who use
  `uv run` instead.

Also done as part of this: the bootstrap (`nopip4`) and `AltVEnv` skip
fetching what is already importable, which a `zipapp` and `uv run`
need.  All four steps are done; the only leftover is measuring
`nopip4`'s row (cold and warm start, size) in `bootstrap.py`.
