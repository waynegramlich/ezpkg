# Embedded Virtual Environment Log Book

<!-- ----------------------------79 characters----------------------------- -->

This file contains the running record of this project.  It has some similarity
to `CLAUDE.md`, but `CLAUDE.md` is maintained by Claude at Wayne's
direction, whereas this file is primarily maintained by Wayne, with some
suggestions by Claude.

## Rules of Engagement

Both `mercurial` and `git` are installed in this directory.  Claude uses
`mercurial` and Wayne uses `git`.  Period.  `mercurial` is updated more
frequently by Claude, so it provides a mechanism to undo mistakes at a
finer granularity.  `CLAUDE.md` holds the detailed working agreement and
is the authority when the two disagree; it is also the copy Claude loads
at the start of every session.

## Problem Statement

The number of Python packages that are present when `python3` is installed
onto a computer tends to be focused on the more popular and/or "necessary"
ones.  The less popular ones have to be dealt with by the end user.

The dividing line between the two is not as simple as it first appears.
There are really three categories, and only the first is guaranteed:

* **Compiled into the interpreter.**  Modules such as `math` are built
  directly into the `python3` binary.  They have no `__file__` attribute
  at all, and nothing can remove them short of rebuilding Python.  These
  are present wherever Python is.
* **Standard library shipped as files.**  Modules such as `venv` and
  `importlib` are equally part of the Python standard library, but they
  arrive as ordinary `.py` files in a directory.  That makes them
  *separable*, and distributions do separate them.
* **Third party, from the Python Package Index.**  Packages such as
  `coverage` are never present unless somebody installs them.  This is
  the category the project is nominally about.

In the shell code immediately below, `math` is in the first category,
`venv` is in the second, and `coverage` is in the third.

Do some initial tests to see which of the three are actually present:
```bash
$ which python3
/usr/bin/python3
$ python3 --version
Python 3.12.3
$ python3 -c "import math"
$ python3 -c "import venv"  # Works here; ships separately as python3-venv.
$ python3 -c "import coverage"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'coverage'
```

With a Python virtual environment, the `coverage` module can be installed:
```bash
$ # Create a test virtual environment in `/tmp/venv_test`.
$ cd /tmp
$ mkdir venv_test
$ cd venv_test
$ python3 -m venv .venv  # Virtual environment is now in `.venv` directory.
```
Next, activate the `.venv` virtual environment and install `coverage`:
```bash
$ source .venv/bin/activate  # Activate virtual environment. Prompt changes.
$ python3 -m pip install coverage
$ python3 -c "import coverage"  # `coverage` module is installed and available.
```

Finally, delete the entire `venv_test` directory to clean up:
```bash
$ deactivate  # Leave the virtual environment first.
$ cd /tmp
$ rm -rf /tmp/venv_test  # Delete the entire `venv_test` directory.
```

That walkthrough quietly assumes one thing: that `python3 -m venv` works
at all.  It does not always, and the reason is the gnarly part.

There is absolutely **NO** official set of packages that every Python
distribution must provide.  CPython defines a standard library, but nothing
obliges a redistributor to ship all of it.  The fundamental takeaway is
that the various distributions are free to ship whatever subset of the
standard library they choose; the resources listed below go into the
specifics.

The consequences for this project are direct:

1. **A virtual environment is not a tool that can be assumed.**  The
   obvious workaround for a missing package -- "just make a venv" -- may
   itself be the missing package.
2. **`pip` is not a tool that can be assumed either.**  Any bootstrap
   that shells out to `pip` has to cope with `pip` not being there.
3. **The floor is lower than expected, which widens the niche.**  If the
   guaranteed baseline is only "an interpreter plus the standard library
   as that distribution chose to ship it," then a solution that needs
   nothing but the interpreter is worth more than it first appeared.
4. **The baseline must be measured, not assumed.**  One machine is one
   data point.  Establishing what is actually guaranteed across the
   distributions worth supporting is now a Phase 2 task, not a detail.

Various trade-offs need to be made, and a complete solution that always
works may simply not be possible.

### The escape hatch: ship the interpreter too

There is one way to make this entire problem disappear, and it is worth
naming explicitly so that it is a conscious choice rather than an
oversight.  If the program is shipped as a **Snap**, **Flatpak**, or
**Docker image**, the Python interpreter and every package it needs are
bundled into the artifact.  The baseline stops being "whatever this
machine's distribution chose to ship" and becomes "exactly what was put
in the image."  Nothing above applies any more.

The cost is that somebody has to do the bundling:

* It is a **build step**, so the program is no longer a file that can be
  handed to somebody.  This is the same objection already raised against
  `shiv` and `pex` under Prior Art below -- those bundle the packages,
  these also bundle the interpreter.
* The artifact is **large**: tens or hundreds of megabytes for what may
  be a few hundred lines of Python.
* It has to be built and published **per format**, and the user needs the
  corresponding runtime (`snapd`, Docker) installed -- which is itself a
  preinstalled dependency, just a bigger one than `pip-run`.

So containerization is a real answer, and for a program of any size it is
probably the *right* answer.  This project is aimed at the case it serves
badly: a single script, handed to somebody, that should just run.

Here are some additional resources that discuss the issue further:

* [PEP 534 -- Improved Errors for Missing Standard Library
  Modules](https://peps.python.org/pep-0534/) states the practice
  outright: "Many Linux and other distributions are already separating
  out parts of the standard library to standalone packages."  It
  contrasts Debian, which catches the import failure and tells the user
  which package to install, with Fedora, which omits the module silently.
  Note the PEP's status is *Withdrawn* -- its proposed fix was dropped,
  but its description of what redistributors do stands.
* [Negative Python user
  experience](https://gist.github.com/tiran/2dec9e03c6f901814f6d1e8dad09528e)
  on Debian/Ubuntu, by Christian Heimes, a CPython core developer, is the
  `.deb` versus `.rpm` comparison in detail: `ensurepip` absent, `venv`
  present but unusable without `python3-venv`, `distutils` stripped, and
  `pip` missing.  He contrasts this with Fedora and RHEL, which keep an
  internal `platform-python` so that the user-facing `python3` stays
  complete.  It is a well-credentialed opinion piece, not a
  specification.
* [Why does `pip` seem to be missing or
  broken?](https://software.codidact.com/posts/291787) is the same
  question asked from the user's side.

## Goal

The goal of this project is to make it possible to write a single-file
Python program that can access other Python packages that may not be
preinstalled.  The initial focus is to be able to import most packages
available at the [Python Package Index](https://pypi.org).  Later on, it
might make sense to be able to grab Python code from places like
[GitHub](https://github.com/) or other online code sources.

The word "most" is deliberate.  This is a goal, not a guarantee.  Some
packages will turn out to be trivial to support and others too hard to be
worth the trouble, and which is which is not knowable in advance.  The
boundary gets drawn as the code is written, by joint judgement; deciding
that a hard case is not worth supporting is a legitimate outcome rather
than a failure.

## Prior Art

Somebody has already solved most of this problem.  What follows is every
approach found, and what each one still asks of the user.

* [PEP 723](https://peps.python.org/pep-0723/) is final, and its
  canonical text is now maintained by the PyPA as the [inline script
  metadata
  spec](https://packaging.python.org/specifications/inline-script-metadata/).
  Dependencies are declared in a `# /// script` comment block at the top
  of a single file.  It is a *format*, not a runner: something has to
  read that block, and that something is `uv` or `pipx`, so the program
  still cannot simply be run.
* [uv](https://docs.astral.sh/uv/)
  ([source](https://github.com/astral-sh/uv)) is a fast Rust
  implementation of the Python packaging tools.  `uv run script.py`
  reads a PEP 723 block and builds an isolated environment.
* [pipx](https://pipx.pypa.io/stable/)
  ([source](https://github.com/pypa/pipx)) is the PyPA tool for running
  and installing Python applications in isolation.  `pipx run
  script.py` reads the same block.
* [pip-run](https://pypi.org/project/pip-run/)
  ([source](https://github.com/jaraco/pip-run)) is the closest prior art
  by far, and it already does what this project set out to do.  Its own
  description of the mechanism is `pip install -t $TMPDIR`, then
  `PYTHONPATH=$TMPDIR python`, then cleanup -- no venv at all.  It reads
  dependencies from either a `__requires__` variable or a PEP 723 block,
  and with a `#!/usr/bin/env pip-run` shebang the user really does just
  run `./script.py`.  `PIP_RUN_RETENTION_STRATEGY=persist` caches the
  installed tree in the user cache directory, keyed per requirement set,
  with optional max age eviction.  It is maintained (16.1.0, May 2025).
* The [scriptstrap](https://pypi.org/project/scriptstrap/) package
  ([source](https://github.com/postlund/scriptstrap)) is closer in
  spirit: importing it creates a venv, pip installs the dependencies,
  and re-executes the script inside the venv.  It is not a real
  alternative though -- it is a single 0.0.1 release from January 2018,
  abandoned after three days and never updated.  Read it for the
  technique, not as a maintained solution.
* [shiv](https://pypi.org/project/shiv/) and
  [pex](https://pypi.org/project/pex/) solve a different shape of the
  problem: a build step bundles the program and all its dependencies
  into a single `.pyz` or `.pex` file, which unpacks to a cache
  directory at run time.  The user runs one file and needs nothing but
  Python, but somebody has to build that file per platform, which does
  not help a script you simply want to hand somebody.
* Many hand written bootstrap scripts do the same thing as scriptstrap.

The common thread is that **every one of these must itself be installed
before the user can run the program.**  That single remaining
requirement is what the rest of this log book is about.

<!-- FENCE:
tThe material above this fence is basically settled.  Editing it is
discouraged, though exceptions can be made.  Leaving it alone is what
keeps decisions that have already been made from being revisited over and
over.

Date: Mon Sep 21, 2026
-->

## Strategy

Work progresses in the following stages.

## Phase 1: Initial exploration (2026-09-20)

1. **Decide whether to use `git`, `mercurial`, or both**:

   The decision was to use `mercurial` for undo and redo, and `git` for
   coarser-grained changes of the code.  `CLAUDE.md` records the resulting
   working agreement.  Only Wayne uses `git` and only Claude uses `mercurial`.

2. **Experiment 1**: Create the bootstrap code.
  
   This experiment assumes that eventually there will be a pip installable
   package on [PyPI](https:/pypi.org) (i.e. the Python Package Index web site)
   that contains a package that an `EmbeddedVenv` class.  The package name
   is to be decided.

   The bootstrap code will live in every program that needs to bootstrap this
   code into their program.  This bootstrap code will assume that Python3
   distribution being used has a small number packages like `venv`, `pip`,
   and `importlib` preinstalled.

   The code will create a `~/.embedded_venv` directory` and initialize it
   using the `venv` package.  The bootstrap is to be a pure Python program
   that does not cheat by directly executing `python3 -m pip install XXX`.
   Only `venv` and other "standard" Python libraries are to be used.  Finally,
   the `coverage` package will imported using the `importlib` package.

   In general, the bootstrap program should be optimized to be a relatively
   small number of lines.  Do not do this optimization just yet.

   **Status: done.**  The code is `bootstrap.py`.  Both install
   mechanisms from the open design question below are implemented: pip
   driven in process when `pip` imports, and a pure-stdlib wheel fetch
   when it does not.  Neither spawns a subprocess.  `coverage` is
   imported through `importlib.import_module`.

   All three mechanisms live in one `bootstrap.py`, inline in `main()`,
   selected by a single command-line argument fed to a single `match`
   statement.  Run it as `python3 bootstrap.py <1|2|3> [dir]`.  The
   numbering matches the "Open design question" below: 1 is pip in
   process, 2 is pip as a subprocess, 3 is no pip at all.

   Deliberately un-Pythonic: every `import` not needed by all three
   sits inside its own `case` clause, so each case is self-contained
   and the cost of each mechanism can be read off directly.  Only
   `importlib`, `pathlib`, `sys` and `sysconfig` are shared, at module
   level.  `main()` has no blank lines in it.

   | | imports | lines | cold | warm | size |
   |---|---|---|---|---|---|
   | 1, pip in process | 3 | 15 | 5.5 s | 0.14 s | 17 MB |
   | 2, pip subprocess | 3 | 15 | 5.6 s | 0.14 s | 17 MB |
   | 3, no pip at all | 4 | 39 | 1.2 s | 0.15 s | 1.7 MB |

   "imports" and "lines" count only what is inside that `case` clause.
   Shared on top of any of them: 4 imports and 10 lines of scaffolding,
   and `main()` is 81 lines all told.

   **The table now states the trade in one row each, and it is a real
   trade.**  Mechanism 3 is 4.6x faster and 10x smaller *on disk*, and
   it is the only one that survives a machine with no pip -- but it
   costs 39 lines against 15, and those lines have to be pasted by hand
   into the end user's program.  Mechanisms 1 and 2 buy their brevity
   by making pip do the work, which is exactly the dependency the
   project is trying to escape.

   The disk figures come from mechanism 3 skipping the venv entirely; 1
   and 2 must build one, and the venv's own copy of pip is 16 MB of
   their 17.  An earlier version of this table had all three at ~5 s and
   17 MB, indistinguishable, because every mechanism built a venv before
   deciding whether it wanted one.  That was finding 7, and writing the
   difference out as an explicit per-case decision is what exposed it.
   This is Phase 1's "the venv is not actually needed" conclusion
   arriving a second time, from the other direction, now measured
   rather than argued.

   Measured earlier, isolating the install step from venv creation:

   | | cold | warm | size |
   |---|---|---|---|
   | in-process pip | 5.5 s | 0.15 s | 18 MB |
   | stdlib wheel fetch | 1.0 s | 0.15 s | 972 KB |

   The 18 MB is almost entirely the venv's own copy of pip; the 972 KB
   is `coverage` alone, and grows to 1.7 MB once `__pycache__` is
   written.  The stdlib timing is the fetch by itself, on a warm DNS
   cache, and excludes venv creation.

   Findings:

   1. **`venv.EnvBuilder` does not default to symlinks; the command line
      does.**  `python3 -m venv` passes `symlinks=True` on POSIX, but
      `EnvBuilder()`'s own default is `symlinks=False`.  Three bare
      venvs, built three ways on the same box:

      | how built | files | size | symlinks |
      |---|---|---|---|
      | `EnvBuilder(symlinks=False)` | 1013 | 35.7 MB | 1 |
      | `EnvBuilder(symlinks=True)` | 1013 | 12.7 MB | 4 |
      | `python3 -m venv` | 1013 | 12.7 MB | 4 |

      All three produce the **identical list of 1013 files**; the only
      difference is that `symlinks=False` writes `bin/python`,
      `bin/python3` and `bin/python3.12` as three separate 7.7 MB copies
      of the interpreter where the other two write symlinks.  3 x 7.7 MB
      is the entire 23 MB gap.

      `EnvBuilder(symlinks=True)` and the command line are otherwise the
      same thing: a recursive diff finds nothing but the venv's own path
      embedded in `bin/activate` and `pyvenv.cfg`.  (`pyvenv.cfg` claims
      `command = /usr/bin/python3 -m venv <dir>` even when no command
      line was involved -- `EnvBuilder` synthesizes that line.)

      Creation time is ~3.1 s either way, so copying 23 MB costs nothing
      measurable; the cost is purely disk.  Phase 1 never saw any of
      this because Phase 1 used the command line.  Any code driving
      `venv` programmatically has to pass `symlinks=True` explicitly.

   2. **Both paths chose the same wheel**, including the compiled
      `tracer.cpython-312-x86_64-linux-gnu.so`.  The 40-line tag matcher
      in `compatible_wheel_tags()` agreed with pip on this package.
      That is one package on one platform and should not be read as more
      than it is; musl versus glibc is not distinguished at all.

   3. **The pip being driven in process was the venv's, not the
      system's.**  `sys.path.insert` happens before `import pip`, so the
      venv's pip 24.0 shadowed `/usr/lib/python3/dist-packages/pip`.
      This is accidental but convenient: it means the in-process path
      would work on a system with no pip, *if* the venv could be built.

   4. **That "if" is the whole question, and the answer looks like no.**
      On Debian and Ubuntu, `ensurepip` ships inside `python3-venv`.  So
      either both `venv` and `ensurepip` are present -- in which case the
      venv can be built and it brings its own pip -- or neither is, in
      which case step 1 fails before any of this matters.  The venv's
      16 MB of pip therefore never earns itself: whenever it is
      reachable, the system's pip was reachable too.  The stdlib fetch
      path is the only one that survives the case the project exists
      for.  (This still rests on unverified assumption 1 below.)

   5. **What the stdlib path skips**: dependency resolution, `RECORD`,
      and console-script generation.  `coverage` has no runtime
      dependencies, so the only loss here is the `coverage` command,
      which this experiment does not need.  A package with dependencies
      would need real work.

   6. **`.pth` files are inert under `sys.path.insert`.**  Both paths
      install `a1_coverage.pth`, coverage's hook for measuring
      subprocesses, but `.pth` files are only executed by
      `site.addsitedir()`, which a bare `sys.path.insert` does not call.
      Any package that relies on a `.pth` is quietly half-installed by
      option C.  Using `site.addsitedir()` instead of `sys.path.insert`
      would fix it and is worth trying.

   7. **The code has a structural flaw worth keeping in view.**
      `bootstrap()` creates the venv *before* deciding how to install,
      so on the machine finding 4 describes -- no `venv`, no
      `ensurepip`, no `pip` -- it fails at step 1 and never reaches the
      one path that would have worked.  The venv is load-bearing in the
      code and not in the argument.  Left as written because Experiment
      1 asked for a venv, but the ordering is backwards for option C.

Claude: I am currently ignoring the rest of this document...  Feel free to
mention some of the stuff below to me, so don't delete anything. Yet.

3. **Experiment 2**: 

   `python3 -m venv /tmp/evenv` is the whole of it.  It needs no
   privileges and takes a second or two.  The entire state of the
   environment lives in one small `pyvenv.cfg` file naming the Python
   that created it:

       home = /usr/bin
       include-system-site-packages = false
       version = 3.12.3
       executable = /usr/bin/python3.12
       command = /usr/bin/python3 -m venv /tmp/evenv

   Everything else in the tree is either a symlink back to that Python or
   a copy of `pip`.  Activation is *not* required to use it: running
   `/tmp/evenv/bin/python3` directly is enough, since `activate` only
   edits `PATH` and the shell prompt.

3. **Record the entire venv directory structure.**

   A fresh venv is 1140 files and 15 MB, and nearly all of that is `pip`
   itself:

       evenv/
           pyvenv.cfg
           bin/
               activate  activate.csh  activate.fish  Activate.ps1
               pip  pip3  pip3.12         # scripts w/ absolute shebangs
               python -> python3
               python3 -> /usr/bin/python3
               python3.12 -> python3
           include/python3.12/            # empty
           lib64 -> lib
           lib/python3.12/site-packages/
               pip/  pip-24.0.dist-info/

   Python 3.12 no longer installs `setuptools` into a new venv.

4. **Install a package into that environment.**

   `/tmp/evenv/bin/python3 -m pip install requests` installed `requests`
   plus its four dependencies (`certifi`, `charset_normalizer`, `idna`,
   `urllib3`), taking the tree from 1140 to 1379 files and 15 MB to
   19 MB.

5. **Repeat step 3 and diff the files to see what changed.**

   The diff is confined to exactly two places:

   1. `lib/python3.12/site-packages/` gains one directory and one
      `*.dist-info/` directory per installed package, plus `__pycache__`
      directories.
   2. `bin/` gains one small wrapper script per console entry point, here
      `idna` and `normalizer`; packages without entry points add nothing
      there.

   Nothing else changes at all: `pyvenv.cfg`, `include/`, `lib64` and the
   activate scripts are all untouched by installation.

6. **Figure out Phase 2.**  See the two sections below.

### Experiments beyond the plan

These were not in the plan, but they decide the shape of Phase 2.

**Activation is not required.**  Running `/tmp/evenv/bin/python3
script.py` directly gives `sys.prefix = /tmp/evenv` and imports from the
venv.  `activate` is a convenience, not a mechanism.

**Activation is not even needed to reach the packages.**  A package
installed only in the venv (`cowsay`, deliberately absent system-wide)
imports fine under the *system* interpreter given either

    PYTHONPATH=/tmp/evenv/lib/python3.12/site-packages python3 script.py

or, with no environment variables and no wrapper at all, from inside the
script itself:

    sys.path.insert(0, "/tmp/evenv/lib/python3.12/site-packages")
    import cowsay        # works

**`pip install --target` skips the venv entirely.**

    python3 -m pip install --target /tmp/etarget cowsay

produces a plain directory of 32 files / 220 KB that `sys.path.insert`
consumes identically -- versus 15 MB of `pip` for an empty venv.  The
console scripts are still generated, so entry points are not lost.

**A venv is relocatable, mostly.**  Moving `/tmp/evenv` to a new path and
running `bin/python3` still works, because `bin/python3` is a symlink to
`/usr/bin/python3` and `sys.prefix` is derived from the directory found
at run time.  The `bin/pip*` wrapper scripts do break, since their
shebangs hold the old absolute path.  Irrelevant if those wrappers are
never used.

Together these mean the venv is not actually needed; only a directory of
installed packages is.

## Where this leaves the project

This problem is largely solved, and the earlier claim that nobody avoids
the re-execution was wrong.  What every existing solution still requires
is exactly one thing preinstalled before the user can run the program:
`uv`, `pipx`, or `pip-run`, all described under Prior Art above.

The only remaining niche for this project is needing *nothing*
preinstalled beyond the standard Python that is already there: the
bootstrap travels inside the program itself.

**That niche rests on an assumption not yet tested.**  "Standard Python"
is not one thing.  On Debian and Ubuntu, `python3-pip` and `python3-venv`
are packaged separately from `python3`, so a machine can have a working
interpreter and no `pip` and no `venv`.  On the machine used for Phase 1,
`pip`, `ensurepip` and `venv` all import, but that is one box.  If `pip`
is commonly absent, the bootstrap has to carry more than a
`sys.path.insert`, and the niche is narrower than it looks.

`ensurepip` is the obvious escape hatch: it is stdlib, and it can place a
`pip` where there was none.  Whether Debian and Ubuntu actually ship it
with the base interpreter -- they have been known to strip it -- is part
of the same untested assumption.

**The decision criterion.**  Building this is worth the work only if the
program must run on a machine where the user cannot, or will not, install
anything at all.  If the user can run one `pip install pip-run`, then
`pip-run` is the answer and this project is an exercise.  Phase 2 should
be judged against that sentence.

## Phase 2: To Be Decided

The Phase 1 findings argue for the lightest of three possible designs:

* **A. Re-exec into a venv** -- what `scriptstrap` and the blog posts do.
  Costs 15 MB per environment, and the re-exec is visible to the user
  (doubled process, confused signal handling, `sys.argv[0]` surprises).
* **B. Vendor the packages into the repository** -- no network needed,
  but it bloats the repository and breaks on compiled extensions such as
  `charset_normalizer`'s `.so`.
* **C. Cache directory plus `sys.path.insert`** -- recommended.  A small
  module the program imports first.  It checks whether each required
  package is already importable; if not, it runs
  `pip install --target <cache-dir>` once, then prepends `<cache-dir>` to
  `sys.path`.  No venv, no activation, no re-exec, ~200 KB per package.

Option C is also, essentially, what `pip-run` already does -- the
difference is only that the module ships inside the program instead of
being installed alongside it.

Prototyping C should settle these questions:

1. Is `pip` reliably present?  This is the load-bearing question above,
   and it should be answered before any of the rest.
2. Where does the cache directory live?  `~/.cache/<program>/` per XDG,
   or next to the program?
3. How are required packages declared?  Reusing the PEP 723
   `# /// script` block would make the program compatible with `uv run`
   for free.
4. What identifies a cache as valid?  Python version, platform tag and
   package versions all belong in the cache directory name, because of
   compiled extensions like the `.so` above.
5. What happens with no network, and should it fall back to whatever the
   system already provides?
6. Should an already-active venv be honored rather than overridden?

## Open Loose Ends

Where things stand as of 2026-09-21, written down so that none of it
lives only in somebody's head.

### Unverified assumptions

These are believed true but were **not** measured.  Anything built on
them is built on sand until they are checked.

1. **`ensurepip` ships inside `python3-venv` on Debian and Ubuntu.**  If
   so, the standard library's own mechanism for installing `pip` is
   missing in exactly the situation where it would be needed.  This came
   from Christian Heimes' write-up (see Problem Statement), not from a
   measurement.
2. **What a minimal install actually provides.**  Everything measured in
   Phase 1 came from one Ubuntu 24.04 box on which `python3-venv` and
   `python3-pip` both happen to be installed.  What was confirmed there
   is only that the two are *separate apt packages* and that `pip`,
   `venv` and `ensurepip` all import.  Nothing was confirmed about a
   machine where they are absent.

Both are settled the same way: a stock container for each distribution
worth supporting, running `python3 -c "import venv, ensurepip, pip"` and
`python3 -m venv /tmp/x`, and recording what happens.  That is Phase 2
question 1, and it gates the rest.

### Document structure

Neither of these is urgent; both were noticed and deferred.

1. **`## Strategy` is an empty heading.**  It holds one sentence, and
   `## Phase 1` follows it as a *sibling* rather than a child, so the
   phases are not actually inside it.  The natural content is the A/B/C
   design comparison currently sitting under Phase 2 -- that comparison
   *is* the strategy.
2. **"Where this leaves the project" repeats the Problem Statement.**
   Its "That niche rests on an assumption not yet tested" paragraph
   re-derives the `python3-pip` / `python3-venv` split, which the Problem
   Statement now covers at greater length and with sources.  Two places
   for one fact is what produced the contradiction this log book was
   created to end; the paragraph should shrink to a pointer.

### Open design question: how does the bootstrap install a package?

Experiment 1 says the bootstrap "does not cheat by directly executing
`python3 -m pip install XXX`" and that "only `venv` and other 'standard'
Python libraries are to be used".  It also assumes `pip` is preinstalled.
Those two pull in different directions, and the reading chosen decides
what gets written.  Three candidate mechanisms, undecided as of
2026-09-21:

1. **Drive `pip` in-process.**  Create the environment with `venv`, then
   call pip from inside Python instead of spawning it.  Smallest code,
   but it depends on `pip._internal`, which is explicitly unsupported and
   changes between pip releases.
2. **Spawn `pip` as a subprocess** (`sys.executable -m pip install
   --target ...`).  Uses pip's supported CLI, is the most robust, and
   still means the *user* never types a pip command.  Whether that counts
   as "cheating" is the question.
3. **Use no pip at all.**  Query the PyPI JSON API with `urllib`,
   download the wheel, unpack it with `zipfile`, and put it on
   `sys.path`.  A wheel is a zip, so this needs only the standard
   library.  Much bigger, and dependency resolution becomes ours -- but
   it is the only option that survives `pip` being absent, which the
   Problem Statement says can happen.

Related tension worth settling at the same time: Experiment 1's premise
is that `venv`, `pip` and `importlib` are preinstalled, while the Problem
Statement argues that exactly `venv` and `pip` are the two that Debian
and Ubuntu split out.  Only `importlib` is safe.  Experiment 1 may
reasonably accept that limitation as a starting point -- but it should be
a deliberate choice rather than an oversight.

### Where work resumes

Phase 2, question 1 -- measure the baseline across distributions -- then
prototype option C.  The decision criterion in "Where this leaves the
project" is the thing to judge the result against: this is worth building
only if the program must run where the user cannot, or will not, install
anything at all.

## Journal

Dated entries that do not fit the phase structure.

* **2026-09-20** -- Phase 1 steps 1 through 6 carried out; findings
  above.  Initial prior-art research missed `pip-run` and concluded that
  nobody avoids the re-execution.  Corrected the same day.
* **2026-09-21** -- Learned that different Linux distributions ship
  different subsets of the Python standard library; `venv` and `pip` are
  separate apt packages on Debian and Ubuntu.  Until now they were
  assumed to be uniform.  Problem Statement rewritten around the three
  categories this implies.
* **2026-09-21** -- Prior art consolidated into its own section ahead of
  Strategy, and Phase 1 step 2 removed; the research had been split
  across two places and described `pip-run` twice.  Remaining Phase 1
  steps renumbered 2 through 6.
* **2026-09-21** -- `PLAN.md` replaced by this log book, and `PHASE1.md`
  folded in here and then deleted; it carried the uncorrected "nobody has
  solved this" claim, which contradicted the corrected text.  Both files
  remain recoverable from mercurial.

