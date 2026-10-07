# 11 The venv executable directory is hard-coded

(CLOSED 2026-10-01)  Cases 4 and 11 reach into `root / "bin"` at
`bootstrap.py:296`, `400` and `407`.  On Windows a virtual environment puts its
executables in `Scripts`, so the pip reclaim would silently delete nothing and
case 11's subprocess would not find an interpreter at all.  The inconsistency
is inside a single case body: the same code checks `os.name != "nt"` when
choosing symlinks, and asks `sysconfig` for the platform's site-packages, then
hard-codes `bin`.  Nothing breaks on Linux, which is the whole of the current
scope.

Various thoughts:
* Claude (2026-10-01): Closed with Wayne's agreement.  The hard-coded
  `bin` is only in `venv3` and `venv4`, which will not ship.
