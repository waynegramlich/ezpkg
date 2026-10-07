# 6.9 `.pth` files: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.9 of `LOGBOOK.md` on 2026-10-04.

* Step 6.9: `.pth` files, which is `I.pfaibne`.  `install` uses
  `sys.path.insert`, which never executes a `.pth` file, so a package
  relying on one is quietly half installed.  `site.addsitedir` is the
  experiment.

  Moved up sharply on 2026-09-27, because it stopped being tidiness.
  Step 6.3 took the unpacking of wheels away from `pip` and on to us,
  and 6.3.12 named `.pth` as part of the specification we had knowingly
  not implemented.

  The example this step used to give was wrong, and Step 6.17.1 found it
  out by looking: **`coverage` ships no `.pth` file at all.**  Measured
  2026-09-27 on `coverage==7.6.1`, whose wheel holds 62 entries and not
  one of them ends in `.pth`; `a1_coverage.pth` is a file coverage's
  documentation tells a person to write by hand.  The claim had been sat
  here since the step was written and it motivated moving the step up.

  Two packages that really do ship one, also measured: `setuptools`
  carries `distutils-precedence.pth`, which is on very nearly every
  machine, and `pytest-cov` carries `pytest-cov.pth`, which is how *it*
  reaches subprocesses.  Both are code executed at path setup, so the
  gap is real and the step stands; only the example changes.
  * 6.9.2 - Done 2026-09-28, and it needed **both** calls rather than a
    choice between them.  Measured: `site.addsitedir` appends to the
    back of `sys.path`, where this cache is supposed to come first; and
    it skips a directory already listed while still processing that
    directory's `.pth` files.  So `provide` inserts the tree at the
    front as before and then calls `addsitedir` on it, which runs the
    `.pth` files without costing the cache its precedence.  A third test
    pins that ordering, because a future tidy-up that dropped the insert
    would look harmless and quietly demote every cached package.

    Both halves of what a `.pth` can do are exercised by a `pathy`
    package in the test index: an `import` line, which now runs, and a
    directory line, which now lands on `sys.path`.  Running `.pth` files
    twice in one process would run their import lines twice, so the
    existing `if str(tree) not in sys.path` guard is now load bearing
    and says so.

  * 6.9.1 - This changes what Step 6.10.2 has to say, so decide it
    before that section is written.  A `.pth` line beginning with
    `import` is **executed** when the path is set up, which is how
    `coverage` reaches subprocesses.  Step 6.6's claim survives intact --
    the gate refuses before anything is unpacked, so only an approved
    wheel ever gets that far -- but "a wheel is an inert zip" stops being
    the whole story once an installed package can run code at import
    time, and the `README.md` should say so rather than leave a stranger
    to discover it.
