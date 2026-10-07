# 18 The cache check tests for a directory

(CLOSED 2026-09-25)  Every one of the twelve cases guards its install with `if
not (target / PACKAGE).is_dir()`.  A distribution that installs as a single
module puts a `.py` file there, not a directory, so the guard is false on every
run and the install is repeated forever. `alt_venv` is exactly such a
distribution, so the defect applies to the package this project ships.

Two things follow.  Every case re-downloads on every run, which the
Task 5 chart shows as warm times that match cold times.  And case 11
does not merely repeat work, it fails: it installs with the venv's
own `pip`, deletes that `pip`, and then on the second run tries to
install with it again, exiting non-zero three times out of three.
The Task 2 chart missed all of this because `coverage` installs as a
directory, which made the guard behave correctly by accident.

A possible solution is to ask whether the package imports rather
than whether a path exists, which is also what `I.apiia` asks for; a
narrower one is to test for the module file as well as the
directory.  The two issues are distinct.  `I.apiia` is about skipping
an install that is not needed, and this one is about a cache hit
that is never detected at all.

Various thoughts:
* Claude (2026-09-25): Fixed the same day, by Wayne's approach: the
  second stage repairs the layout rather than twelve pasted case
  bodies being edited, so no case gained a line and the `paste`
  column did not move.  `AltVEnv.repair_module_layout` rewrites
  the module it was imported from as `<name>/__init__.py`, but only
  when that file lies under the cache root, so a checkout is never
  touched.  The cost is one extra fetch, on the first run only.
* Claude (2026-09-25): Two things were not obvious.  Half the cases
  install into `~/.alt_venv` and half into a `site-packages`
  directory inside it, so the repair has to look anywhere under the
  root rather than at the root itself; and `bootstrap.py` never
  constructed an `AltVEnv`, so its epilogue now does what a real
  program does next.  The repair also has to decline to run once the
  module is a package, since `__init__.py` has the stem `__init__`
  and an earlier version buried it one directory deeper on the second
  run.  `test_every_case_bootstraps_repeatedly` runs three times for
  that reason.
