# 7.8 EZPkg updates itself

The bootstrap installs `ezpkg` into `~/.ezpkg` only when none is there,
and nothing ever upgrades it.  So once a program carries a newer
bootstrap than the cached `ezpkg` knows, that `ezpkg` either rejects
the bootstrap's new arguments or, since `T.reb`, refuses the bootstrap
as edited.  After the pypi.org release every bootstrap change would
break every machine that ran an older one.  Must be done before `T.abfd`,
which changes the bootstrap, and `T.utpat`.

## The Design (Wayne, 2026-10-16)

1. **`ezpkg` is in Part 1's `dependencies`,** with a range like any
   other package (`"ezpkg>=0.1,<0.2"`), so each program runs the `ezpkg`
   its author chose, pinned by the approvals and the resolution date.
   A program never changes because another one needed a newer `ezpkg`.
2. **The copy in `~/.ezpkg` is a launcher.**  When the running `ezpkg`
   does not satisfy the program's entry, it fetches one that does into
   `~/.ezpkg/versions/`, as for any package, and runs the program again
   with that one first on the path.  Wherever the running `ezpkg` came
   from (`~/.ezpkg`, a virtual environment, `PYTHONPATH`), that is how
   it is dealt with.
3. **Order:** the switch comes before `T.reb`'s check, so the right
   `ezpkg` judges the bootstrap.
4. **No network, or no `ezpkg` that satisfies the entry:** stop with
   one line saying which `ezpkg` the program needs, and that the
   network could not be reached.
5. **Asking:** downloading silently is fine; running downloaded code
   without asking is not.  The bootstrap is exempt, since the author put
   it there; the `ezpkg` the author's Part 1 asks for is the author's
   choice too.
6. **No updating now and then:** the person running a program does not
   expect it to change from the first time they ran it.
7. **Reuse the existing structure** (versioned trees, approvals,
   request records) wherever possible.

## Consequences

* The bootstrap needs no `version=`, provided the first pypi.org
  release has the launcher, so every launcher in the wild can switch.
* `T.kdaiis` stops leaving `ezpkg` out of `dependencies`: a program
  with a bootstrap needs an `ezpkg` entry, offered with a range.
* The Quick Start's Part 1 gains the entry, and README says why.
* `I.uedepi` goes away: a `uv` export keeps `ezpkg`, and `uv run`
  provides it.

## Building It

* A standard-library version comparison that orders `0.0.1.devN`
  before `0.0.1`, for test.pypi.org rehearsals.
* Running the program again: `os.execv`, except on Windows, which runs
  it as a child and exits with its status.  At most once, marked by an
  environment variable, so a failed switch stops rather than loops.
* A lock, from 6.4's concurrent installs, so two programs switching at
  once do not collide.
* Tests: every published bootstrap (`OLD_BOOTSTRAP_TEXTS`) still works
  with the newest `ezpkg`; the Quick Start's entry is satisfied by
  `ezpkg.__version__`.
