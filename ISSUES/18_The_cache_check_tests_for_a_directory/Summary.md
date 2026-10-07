# Summary of `I.cctfd` The cache check tests for a directory

Every one of the twelve cases guards its install with `if not (target /
PACKAGE).is_dir()`.  A distribution that installs as a single module puts a
`.py` file there, not a directory, so the guard is false on every run and the
install is repeated forever. `alt_venv` is exactly such a distribution, so the
defect applies to the package this project ships.

Last thought: Claude (2026-09-25): Two things were not obvious. Half the cases
install into `~/.alt_venv` and half into a `site-packages` directory inside it,
so the repair has to look anywhere under the root rather than at the root
itself; and `bootstrap.py` never constructed an `AltVEnv`, so its epilogue now
does what a real program does next. The repair also has to decline to run once
the module is a package, since `__init__.py` has the stem `__init__` and an
earlier version buried it one directory deeper on the second run.
`test_every_case_bootstraps_repeatedly` runs three times for that reason.
