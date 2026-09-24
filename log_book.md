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

## Phase 1: Initial exploration (2026-09-20)

1. **Decide whether to use `git`, `mercurial`, or both**:

   The decision was to use `mercurial` for undo and redo, and `git` for
   coarser-grained changes of the code.  `CLAUDE.md` records the resulting
   working agreement.  Only Wayne uses `git` and only Claude uses `mercurial`.

2. **Experiment 1**: Create the bootstrap code.
  
   This experiment assumes that eventually there will be a pip installable
   package on [PyPI](https://pypi.org) (i.e. the Python Package Index web site)
   that contains a package that has an `EmbeddedVEnv` class.  The package is
   named `embedded-venv` on PyPI and imports as `embedded_venv`.

   The bootstrap code will live in every program that needs to bootstrap this
   code into their program.  This bootstrap code will assume that the
   Python3 distribution being used has a small number of packages like
   `venv`, `pip`, and `importlib` preinstalled.

   The code will create a `~/.embedded_venv` directory and initialize it
   using the `venv` package.  The bootstrap is to be a pure Python program
   that does not cheat by directly executing `python3 -m pip install XXX`.
   Only `venv` and other "standard" Python libraries are to be used.  Finally,
   the `coverage` package will be imported using the `importlib` package.

   In general, the bootstrap program should be optimized to be a relatively
   small number of lines.  Do not do this optimization just yet.

   The twelve mechanisms, measured by `bootstrap.py` itself.  What the
   columns mean is in its module docstring.

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 20    | 24    | 6.12 s | 0.16 s | 16981  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 20    | 24    | 6.68 s | 0.15 s | 16981  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 49    | 1.41 s | 0.15 s | 1682   |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 26    | 30    | 6.85 s | 0.16 s | 1790   |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 20    | 24    | 2.65 s | 0.15 s | 1790   |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 11    | 15    | 2.65 s | 0.14 s | 1762   |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 11    | 15    | 2.73 s | 0.14 s | 1762   |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 15    | 19    | 4.22 s | 0.15 s | 1762   |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 15    | 2.62 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 15    | 2.69 s | 0.14 s | 1698   |
|      | compile         |         |       |       |        |        |        |
| 11   | as 4 but        | 5       | 26    | 30    | 5.25 s | 0.15 s | 1790   |
|      | subprocess      |         |       |       |        |        |        |
| 12   | venv(no pip),   | 7       | 51    | 55    | 1.42 s | 0.16 s | 1714   |
|      | stdlib wheel    |         |       |       |        |        |        |
+------+-----------------+---------+-------+-------+--------+--------+--------+

   Findings:

   1. **`venv.EnvBuilder` does not default to symlinks; the command
      line does.**  `python3 -m venv` passes `symlinks=True` on POSIX,
      but `EnvBuilder()`'s own default is `symlinks=False`, which
      copies the 7.7 MB interpreter into `bin/python`, `bin/python3`
      and `bin/python3.12`.  That is 35.7 MB against 12.7 MB for an
      otherwise byte-identical tree of 1013 files; the 23 MB gap is
      exactly those three copies.  Creation takes ~3.1 s either way,
      so the cost is purely disk.  Phase 1 never saw this because
      Phase 1 used the command line.

   2. **`ensurepip` is essentially the entire cost of making a venv.**
      `EnvBuilder(with_pip=False)` builds one in 0.05 s and 28 KB,
      against 3.1 s and 12.7 MB with pip.  Nearly everything a venv
      costs is the pip it installs into itself.

   3. **The venv is never load-bearing.**  `pip install --target`
      needs no virtual environment at all.  Case 6 skips the venv and
      costs 15 pasted lines and 1762 KB; case 1 builds one and costs
      24 lines and 16981 KB, for identical observable behaviour.
      Phase 1 reached this conclusion by argument, from the venv
      side.  It is now measured from the bootstrap side and the
      numbers agree.

   4. **Running pip in process is not free of the user's program.**
      After one in-process install, `sys.modules` grows from 99
      entries to 740, 451 of them pip's, and pip leaves three
      `RichPipStreamHandler` objects on the *root* logger.  The same
      `log.warning("hello")` prints bare before the bootstrap runs and
      `WARNING: hello` through pip's handler afterwards, on a
      different stream.  Six of the twelve cases do this.  The subprocess
      cases cannot: that state dies with the child.  This is the
      strongest argument against the in-process mechanism, and it was
      not visible until it was measured.

   5. **pip can be imported straight out of its own wheel.**  A wheel
      is a zip and zips are importable, so
      `sys.path.insert(0, "<...>/pip-24.0-py3-none-any.whl")` makes
      pip importable without installing it anywhere -- no venv, no
      network, and nothing written to disk for pip itself.  Case 8
      does this in 15 lines.

   6. **Debian de-vendors `ensurepip`, and misnames the package that
      carries it.**  There is no `ensurepip/_bundled` directory on
      this machine; `_WHEEL_PKG_DIR` points at
      `/usr/share/python-wheels/`, which holds
      `pip-24.0-py3-none-any.whl` and `setuptools-68.1.2-...whl`.
      That confirms the de-vendoring the Problem Statement describes.

      The package layout is the surprise.  `python3.12-venv` contains
      `ensurepip` and nothing else -- three files.  The `venv` module
      itself lives in `libpython3.12-stdlib`, the base package.  So
      `import venv` succeeds on a machine that does not have
      `python3-venv` installed, while `python3 -m venv` fails there,
      because venv calls `ensurepip` to put pip inside the
      environment it builds.

      Whoever designs Experiment 2 should know that `import venv` is
      therefore not a valid probe for whether a virtual environment
      can be built; it answers yes on a machine where the answer is
      no.  The probes that discriminate are `import ensurepip` and
      `python3 -m venv` itself.  Measured with `dpkg -L` and
      `dpkg -S` on one Ubuntu 24.04 box.  Debian is believed to be
      laid out the same way, which is not verified here.

   7. **Reclaiming pip after the fact works.**  Deleting the venv's
      `pip`, its `pip-*.dist-info` and `bin/pip*` takes the tree from
      16981 KB to 1790 KB.  `coverage` still imports afterwards, a
      second package still installs by the pure-stdlib path, and
      `ensurepip` can put pip back if it is ever wanted again.  This
      is the right answer for a machine that has `venv` but no pip --
      and only for that machine, because `with_pip=False` reaches the
      same size for 6 fewer pasted lines wherever a system pip exists.
      Two cases do this reclaim and measure identically: case 4
      imports the manufactured pip, case 11 runs the venv's own
      interpreter as a child instead.  Case 11 is the one to ship,
      because it needs nothing from `pip._internal`.

   8. **`--no-compile` is worth almost nothing.**  60 KB, and 40
      `.pyc` files against 44, because the bootstrap imports the
      package two lines later and Python compiles what it imports
      anyway.  Rounding sizes to `1.7 MB` had made this look like a
      100 KB saving; reporting kilobytes killed the idea.

   9. **`.pth` files are inert under `sys.path.insert`.**  Every case
      installs coverage's `a1_coverage.pth`, its hook for measuring
      subprocesses, and no case executes it; only `site.addsitedir()`
      would.  Any package that relies on a `.pth` is quietly
      half-installed by every mechanism here.

   10. **Independence from pip costs 49 pasted lines against 15.**
       That is the whole trade, stated in one line.  The hand-rolled
       wheel-tag matcher agreed with pip's choice for one package on
       one platform, including the compiled
       `tracer.cpython-312-x86_64-linux-gnu.so`, and it cannot tell
       musl from glibc.  Case 3 also produces the smallest tree,
       1682 KB, because it never generates the three `coverage`
       console scripts that `pip --target` writes into `bin/`.

   **Where this departed from the instructions above.**  The
   instructions asked for four things: build `~/.embedded_venv` using
   `venv`, do not cheat by executing `python3 -m pip install`, use
   only `venv` and other standard libraries, and import through
   `importlib`.  Every case does the last of those.  No case does the
   other three at once.

   Cases 1, 4 and 5 build the venv and spawn nothing, but reach into
   `pip._internal`, which is not a standard library.  Case 3 uses
   nothing but standard libraries and spawns nothing, at the cost of
   building no venv at all.  Cases 2, 7, 10 and 11 spawn pip, which
   the instructions call cheating, and case 11 is the one finding 7
   recommends.

   Case 12 was then written to close that gap, and it is the only
   one of the twelve that does all four: a venv built with
   `with_pip=False`, filled by case 3's wheel fetcher.  It costs 55
   pasted lines against case 3's 49, and 1714 KB against 1682.  So
   the instructions were satisfiable after all, and the price of
   satisfying them is 6 lines and 32 KB spent on a virtual
   environment that nothing subsequently reads.  That is finding 3
   arriving from the other side: the venv the instructions mandate is
   not load-bearing, and now that has been measured rather than
   argued.

   **What Experiment 1 did not settle.**  The baseline question that
   Experiment 2 exists for is untouched.  Every row of that table was
   measured on one Ubuntu 24.04 machine that has `venv`, `ensurepip`
   and `pip` all present.

   What the experiment did produce is a priced answer for each way
   that question could come out.  With `pip` importable, 15 pasted
   lines.  With `pip` gone but `ensurepip` present to manufacture
   one, 30.  With neither, 49 -- or 55 if a virtual environment is
   wanted for its own sake.  Finding 6 is why those are phrased
   around `ensurepip` rather than `venv`: `venv` is in the base
   standard library and is effectively always present, so it is not
   the thing that varies.  Which of these the project actually needs
   is still the thing to measure.

   **A defect worth recording.**  Experiment 1 also turned up a bug
   that all twelve cases share, written up under Open Issues as the
   already-importable defect.  It affects every case equally, so it
   does not disturb the comparison above.

<!-- FENCE:
The material above this fence is basically settled.  Editing it is
discouraged, though exceptions can be made.  Leaving it alone is what
keeps decisions that have already been made from being revisited over and
over.

Date: Tue Sep 22, 2026
-->

3. **Experiment 2**: Master `pip` and Associated `PyPI` Compatible Servers

   The ultimate goal is to build a testing framework that allows installing
   the `embedded_venv` (to be developed) package from a `pip` compatible server
   (e.g `pipiserver`) and load it into program via the bootstrap technology
   developed in the previous experiment.

   Here is the task list, with what is done struck from it:

   * DONE.  Build a wheel for `embedded_venv.py`, and lay it out as a
     PEP 503 tree.  Both are in `embedded_venv_test.py` and use
     nothing but the standard library.
   * DONE.  Let the environment aim `bootstrap.py` at that tree,
     through `PIP_INDEX_URL` and `BOOTSTRAP_PACKAGE`.
   * Fill in `EmbeddedVEnv` with something worth fetching.
   * End-to-end: run a `bootstrap.py` case against the local tree and
     check that `embedded_venv` lands in `~/.embedded_venv` and
     imports.
   * Failure testing: an index missing the package, a truncated wheel,
     a missing `index.html`.
   * Eventually, a real package server, which is the only way to test
     cases 3 and 12.

   Some initial conclusions after some research and discussion:
   * Preinstalled Python environment.  What follows was measured on one
     Ubuntu 24.04 machine.  We will *eventually* survey Ubuntu, Redhat,
     Windows, and MacOS systems to turn these assumptions into facts.
     * Not every Python installation has the whole standard library, but
       the parts the bootstrap uses -- `importlib`, `pathlib`, `ssl`,
       `subprocess`, `sysconfig`, `urllib.request`, `venv`, `zipfile`
       and friends -- are all either compiled into `python3` or in a
       base package Debian marks `Priority: important`.  Assuming those
       is effectively assuming Python itself.
     * Exactly one thing must additionally be preinstalled: `pip`, from
       the `Priority: optional` package `python3-pip`.  `ensurepip`, in
       `python3.12-venv`, is the only other optional piece, and is
       needed only by the cases that manufacture a `pip`.
     * A working TLS trust store (`ca-certificates`) is also required,
       since every case fetches over HTTPS.  `python3-pip` depends on
       it, so requiring `pip` brings it along.
     * Once `pip` is present, any further Python package can be
       downloaded as needed.
   * Package server for the test harness:
     A standard
     [PEP 503 directory tree](https://peps.python.org/pep-0503/) is to
     be used instead of a running full web server.  `pip --index-url`
     accepts a local directory laid out in that format, which removes
     any need to start and stop a server.  Later on, testing with an
     actual web server is necessary.
   * `bootstrap.py` is not being merged into `embedded_venv_test.py`.
     This allows `bootstrap.py` to perform end-to-end testing with
     a real Python package server, whereas `embedded_venv_test.py` can
     use non server based testing.
   * While there are tools that can generate a PEP 503 directory tree
     it easier to just manually generate the tree.
   * Simulate the Package server to download into the `~/.embedded_venv/`
     directory:
     1. Construct a Wheel for `embedded_venv.py`.
     2. Create the associated PEP 503 tree.
     3. Set up an environment variable.  ("coverage" => "embedded_venv"?)
     4. Do an end-to-test.
     5. Do failure testing (e.g. breaking the wheel, etc.)

## Misc.

   **Scope: Linux only, for now.**  Windows and macOS are worth
   measuring eventually and are not part of this experiment.  Not
   every problem gets solved at once, and this one is narrow on
   purpose.

   Experiment 1 measured twelve mechanisms on one machine that has
   `venv`, `ensurepip` and `pip` all present.  Which of its answers
   the project actually needs depends on a fact nobody has measured
   yet.

   **A note on Docker images, recorded before any method is chosen.**
   A Docker image is a prebuilt filesystem that a command can be run
   inside, isolated from the host.  Two families of image matter here
   and they answer different questions.

   * `debian:12`, `ubuntu:24.04`, `fedora:41`, `alpine:3.20` are the
     distributions' own base images.  Whatever `python3` they have, or
     can install, is the distribution's packaged Python -- the same
     thing a user of that distribution gets.  These answer the
     question this project is asking.
   * `python:3.12`, `python:3.12-slim` and friends are published by
     the Docker Python maintainers, and the Python inside is **not**
     any distribution's package.  It is built from source, from
     python.org, during the image build.

   That second point is the trap, and it is checkable rather than
   folklore.  The Dockerfile for `python:3.12-bookworm` says so
   outright:

       FROM buildpack-deps:bookworm
       ENV PYTHON_VERSION 3.12.14
       wget -O python.tar.xz "https://www.python.org/ftp/python/..."
       ./configure --with-ensurepip
       make install

   It starts from a Debian base, throws Debian's Python away, fetches
   the python.org tarball, and compiles it with `--with-ensurepip`
   explicitly requested.  So `python:3.12` always has `pip`, `venv`
   and `ensurepip`, by construction, no matter what Debian ships.

   Measuring `python:3.12` would therefore produce a confident,
   well-formatted, entirely wrong answer: it measures what the Docker
   Python image was built with, not what a distribution gives its
   users.  Source:
   `github.com/docker-library/python`, `3.12/bookworm/Dockerfile`,
   read 2026-09-22.

   None of this is a recommendation to use Docker.  It is the one fact
   that would quietly invalidate the results if Docker were used
   without knowing it.  Note also that no container runtime is
   installed on the machine this project is being developed on.

   **The decision criterion.**  Building this is worth the work only if
   the program must run on a machine where the user cannot, or will
   not, install anything at all.  If the user can run one
   `pip install pip-run`, then `pip-run` is the answer and this project
   is an exercise.  Experiment 2 should be judged against that
   sentence.

   **The procedure.**  A stock container for each distribution worth
   supporting.  In each one, run:

       python3 -c "import venv"
       python3 -c "import ensurepip"
       python3 -c "import pip"
       python3 -m venv /tmp/x

   and record what happens.  Debian and Ubuntu package `python3-pip`
   and `python3-venv` separately from `python3`, so a machine can have
   a working interpreter and neither of the other two.  How common that
   is decides which Experiment 1 case this project should ship.

   **What each outcome would mean**, from Experiment 1's table:

   * `pip` imports: 15 pasted lines, case 7.  The project is an
     exercise by the criterion above, since such a user can run
     `pip install pip-run`.
   * `pip` absent but `venv` and `ensurepip` present: 30 pasted lines,
     case 11 -- manufacture a pip, use it once, delete it.
   * Neither present: 49 pasted lines, case 3 -- the pure standard
     library wheel fetch, and the only mechanism that survives this.

   The middle outcome is the one that justifies the project.  The
   experiment exists to find out whether it is real.

   **Still open.**  The questions Experiment 2 does not itself
   answer are collected under Open Issues below, in priority order.

## Issues

A resolved issue is deleted outright.  It is not moved to a "done"
list: an ever growing issue list is no fun to read, the experiment that
resolved it already records what happened, and mercurial and git hold
every earlier version of this file.  Rejected issues are the one
exception, and are kept below, because their whole purpose is to stop
the same idea being proposed a second time.

Each issue carries a short identifier in parentheses at the end of its
title, and that identifier is how it is referred to anywhere else in
this file.  It is a priority digit followed by the first letter of
each word of the title, lower cased.  So *What happens with no
network?* at priority 0 becomes `0whwnn`.  Punctuation is dropped and
a hyphenated word counts once, so *five-line* contributes one `f`.

The four priorities:

* **0, extreme.**  It can break the bootstrap once the bootstrap is
  out in the wild.  The bootstrap is pasted by hand into other
  people's programs and is never updated afterwards, so a failure
  there happens on a stranger's machine, at their version of
  everything, with nobody around to fix it.  Nothing else outranks
  this.
* **1, high.**  It gates the work or decides what gets built.  Nothing
  breaks, but the answer changes the direction.
* **2, medium.**  It costs time or disk, or it is a correctness
  problem with a narrow blast radius.
* **3, low.**  Worth doing, nothing turns on when.

Digits rather than letters because they sort.  `H`, `M` and `L` sort
as H, L, M, which puts low above medium; `sort` on a list of these
identifiers puts the levels in the right order with no special
handling.  Within a level the order is editorial and a plain sort will
not reproduce it, which is intended: the digit is the priority, and
position inside a level is judgment.

Issues carry no list numbers.  Changing an issue's priority or its
title changes its identifier, and every reference to the old name must
be updated in the same pass.  That fixup is Claude's job and is not a
reason to avoid re-prioritising something.

The statement of an issue is written by Claude and is meant to be
checkable.  "Wayne's current thoughts" underneath it is Wayne's, and
is where the disposition lives.

### Open Issues

Unresolved, highest priority first.

* **Nothing identifies a cache as valid. (0niacav)**  Every case installs into
  `~/.embedded_venv` with no version, platform tag or interpreter
  version in the path.  Experiment 1 installs
  `tracer.cpython-312-x86_64-linux-gnu.so`, so the same directory
  reached by a different Python, or copied to a different machine,
  would load a shared object built for something else.  This is a
  correctness bug waiting rather than a tidiness question.

  Wayne's current thoughts:
  * We'll eventually have a test suite, and we can ensure this issue
    gets covered then.  To be honest, the test suite is going to
    cover all sorts of issues.  They always do.

* **`pip._internal` is not a public API. (0pinapa)**  Six of the twelve
  cases import it.  The pip documentation says in as many words not to,
  and
  the module path has moved before.  This is code pasted into
  programs and never updated afterwards, so when it breaks it breaks
  on some other person's machine, at their pip version, with no one
  around to fix it.

  Since this issue was written, case 11 was added to close the gap it
  creates.  Avoiding `pip._internal` rules out cases 1, 4, 5, 6, 8
  and 9, which left the "no pip but `venv` present" branch with no
  answer at all, because case 4 was its only mechanism.  Case 11
  reaches the same manufactured pip by running the venv's own
  interpreter as a child process, and measures identically to case 4
  on every column: 5 imports, 26 lines, 30 pasted, 1790 KB.  The
  surviving set is therefore cases 2, 3, 7, 10 and 11, and nothing is
  lost by discarding the rest.

  Wayne's current thoughts:
  * In general, this seems quite bad.  I'd very much like to avoid
    using `pip._internal`.  I'd very much dislike using this interface
    since the bootstrap code in theory could be replicated a large number
    of places.  I will point out that the reason why we have 10 bootstrap
    code candidates gives us some flexibility dealing with this issue.

* **What happens with no network? (0whwnn)**  Undefined in all twelve
  cases.  Should the bootstrap fail, or fall back to whatever the
  system already provides?

  Wayne's current thoughts:
  * We are going to die without the network to fetch the package.
    We need to at least let the user know that we died because we
    could not get the package.

* **`embedded_venv` does not exist yet. (1edney)**  Every case installs
  `coverage` as a stand-in while the comment at the top of each says
  `# Ensure embedded_venv is downloaded.`  The whole design is two
  stage -- a small pasted stub fetches a real package that carries
  the heavy logic -- and only the stub half has been built.  The
  `paste` column therefore measures the cost of fetching a test
  package, not of the real thing.  Nothing in Experiment 1 is wrong
  because of this, but nothing in it validates the second stage
  either.

  Wayne's current thoughts:
  * We'll start getting answer's in experiment 2.

* **How many machines does requiring `pip` exclude? (2hmmdrpe)**  The
  decision to require `pip`, recorded under the preinstalled
  environment conclusions in Experiment 2, removed `pip`'s absence
  from the design space, so this no longer decides what gets built.
  What remains is reach: a machine without `pip` now gets a diagnosed
  failure instead of a bootstrap, and nobody has measured how many
  machines that is.  The question is also narrower than it was.  It
  is not "what is installed on a stock machine" but "is `pip` inside
  the distribution's base `python3` package," which is one
  `dnf repoquery`, `apk info` or `pacman -Qi` per distribution and
  needs no container runtime.

  Note what this issue cannot settle.  Its original teeth came from
  the decision criterion under Misc.: if the user can run
  `pip install pip-run`, this project is an exercise.  Requiring
  `pip` sharpens that rather than blunting it, since it assumes the
  very tool that makes `pip-run` installable.  The answer is that the
  recipient runs no commands at all where `pip-run` costs them one,
  and that is an argument about what the product is.  No survey of
  distributions will confirm or refute it.

  Wayne's current thoughts:
  * It would be nice to test on Windows and MacOS.
  * I know people who have these machines and would be glad to
    help.  Until then, the answer is currently unknown.

* **An already-importable package is installed anyway. (2aapiia)**  All
  twelve cases ask whether the package is on disk at their own target,
  never whether it is already importable.  With `coverage` present in an
  active virtual environment, a case spends 1.42 s and 1.8 MB
  installing a copy it will not use, where a leading `try: import`
  costs 0.10 s.  Cheap to fix; deliberately not fixed yet.

  Wayne's current thoughts:
  * This can be dealt with much later since it is easy to fix.

* **How should required packages be declared? (2hsrpbd)**  Every case has
  `PACKAGE = "coverage"` written into it.  Reusing the PEP 723
  `# /// script` block instead would make the same program work under
  `uv run` for free, and would let one bootstrap serve a list of
  packages rather than one.

  Wayne's current thoughts:
  * Sounds like it is worth doing.  The question is when?

* **Where should the cache directory live? (2wstcdl)**  `~/.cache/<program>/`
  per the XDG spec, or beside the program, or the `~/.embedded_venv`
  that Experiment 1 assumed without examining?  This interacts with
  `0niacav`: whatever the location, the name has to carry the
  interpreter and platform.

  Wayne's current thoughts:
  * I have no idea what this issue is about.  Let's do the experiment
    when we get the chance.

* **The wheel tag matcher is a five-line stand-in. (2twtmifs)**  Cases
  3 and 12 pick wheels with a substring test that cannot tell musl
  from glibc, and does not read the glibc version a manylinux tag
  encodes.  It agreed with pip for one package on one platform.  On
  Alpine it would download a manylinux wheel and fail at import with
  a loader error.  The matcher is also written out twice, once per
  case, so a correction has to be made in both places.

  Two things have narrowed this since it was written.  Requiring
  `pip` demoted cases 3 and 12 from shipping candidates to
  measurement, so the matcher is no longer on the path to a
  stranger's machine unless that decision is revisited.  And the
  stub's job is to fetch `embedded_venv`, which is pure Python and
  ships as `py3-none-any`, so no tag matching is needed for it at
  all; the matcher exists only because Experiment 1 fetched
  `coverage`, which has compiled wheels.  The 49 pasted lines the
  table charges the pure standard library path are therefore priced
  against the wrong package, and that number should be remeasured
  before it is used to justify anything.

  Wayne's current thoughts:
  * Let's revisit this issue after Experiment 2.

* **The venv executable directory is hard-coded. (3tvedih)**  Cases
  4 and 11 reach into `root / "bin"` at `bootstrap.py:296`, `400` and
  `407`.  On Windows a virtual environment puts its executables in
  `Scripts`, so the pip reclaim would silently delete nothing and
  case 11's subprocess would not find an interpreter at all.  The
  inconsistency is inside a single case body: the same code checks
  `os.name != "nt"` when choosing symlinks, and asks `sysconfig` for
  the platform's site-packages, then hard-codes `bin`.  Nothing
  breaks on Linux, which is the whole of the current scope.

  Wayne's current thoughts:
  *

* **`.pth` files are installed but never executed. (3pfaibne)**  Every case
  writes coverage's `a1_coverage.pth`, its hook for measuring
  subprocesses, and no case runs it, because only `site.addsitedir()`
  executes `.pth` files and every case uses `sys.path.insert`.  Any
  package relying on a `.pth` is quietly half-installed.  Switching
  to `site.addsitedir()` is the obvious experiment.

  Wayne's current thoughts:
  * I have no idea what this issue is about.  Let's do the experiment when we
    get the chance.

### Rejected Issues

Approaches that were considered and declined, recorded so that they
are not proposed again.

* **Vendor the packages into the repository. (3vtpitr)**  Needs no
  network, but it bloats the repository and breaks on compiled
  extensions -- the same `.so` problem as `0niacav`.  Declined
  2026-09-21, before Experiment 1; Experiment 1 then confirmed the
  `.so` problem is real by installing
  `tracer.cpython-312-x86_64-linux-gnu.so`.

