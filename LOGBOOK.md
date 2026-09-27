# AltVEnv Logbook

<!-- ----------------------------79 characters----------------------------- -->

This file contains the running record of this project.  It is maintained
jointly by Wayne and Claude.  `CLAUDE.md` is the separate working
agreement that says how the two of them operate, and it is the authority
when the two files disagree.

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

The obvious workaround for a package in the third category is to build
a virtual environment and `pip install` into it.  That assumes
`python3 -m venv` works at all.  It does not always, and the reason is
the gnarly part.

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
   data point.

Various trade-offs need to be made, and a complete solution that always
works may simply not be possible.

## Goals

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

**Linux only, for now.**  Windows and macOS are worth measuring
eventually and are not part of this experiment.  Not every problem gets
solved at once, and this one is narrow on purpose.

## Initial Research

What was read or measured before anything was built.  Each entry names
its source, so a claim here can be rechecked rather than taken on
trust.

### Prior Art

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

### A note on Docker images

A Docker image is a prebuilt filesystem that a command can be run inside,
isolated from the host.  Two families of image matter here and they answer
different questions.

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

### Further reading

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

## Initial Thoughts

Considerations raised early.  They are kept because they frame the
decisions that came later, not because they were acted on.

There is one escape hatch that makes this entire problem disappear, and
it is worth naming explicitly so that it stays a conscious choice rather
than an oversight.  If the program is shipped as a **Snap**, **Flatpak**, or
**Docker image**, the Python interpreter and every package it needs are
bundled into the artifact.  The baseline stops being "whatever this
machine's distribution chose to ship" and becomes "exactly what was put
in the image."  Nothing above applies any more.

The cost is that somebody has to do the bundling:

* It is a **build step**, so the program is no longer a file that can be
  handed to somebody.  This is the same objection already raised against
  `shiv` and `pex` under Prior Art above -- those bundle the packages,
  these also bundle the interpreter.
* The artifact is **large**: tens or hundreds of megabytes for what may
  be a few hundred lines of Python.
* It has to be built and published **per format**, and the user needs the
  corresponding runtime (`snapd`, Docker) installed -- which is itself a
  preinstalled dependency, just a bigger one than `pip-run`.

So containerization is a real answer, and for a program of any size it is
probably the *right* answer.  This project is aimed at the case it serves
badly: a single script, handed to somebody, that should just run.

That gives the decision criterion.  Building this is worth the work only
if the program must run on a machine where the user cannot, or will not,
install anything at all.  If the user can run one `pip install pip-run`,
then `pip-run` is the answer and this project is an exercise.  Every
experiment should be judged against that sentence.

## Task 1: Choose the Version Control Arrangement  (CLOSED 2026-09-20)

Claude needs to checkpoint constantly, so that any mistake is one
command away from being undone.  The git history should record only
meaningful units of work.  One repository cannot do both: the frequent
checkpoints bury the history that makes the log worth reading.

The task was to decide how to get both, and who operates what.

### Task 1 Summary

Two version control systems share one working directory.  Mercurial is
Claude's and git is Wayne's.  Claude checkpoints into `hg` freely and
never runs `git` at all; Wayne commits to `git` by hand and never runs
`hg`.  Each repository ignores the other, so `.hgignore` excludes
`.git/` and `.gitignore` excludes `.hg/`.  `CLAUDE.md` holds the
detailed working agreement and travels in every git commit, which keeps
the rules versioned alongside the work they govern.

(CLOSED 2026-09-20)

## Task 2: Create the Bootstrap Code  (CLOSED 2026-09-22)

This task was called Experiment 1 while it ran.  The text below, and
several issues, still use that name.

{The last sentence is a note from the future.  The name was settled
while Task 4 ran; when this task began no such package existed, which is
what the rest of the paragraph assumes.}

This experiment assumes that eventually there will be a pip installable
package on [PyPI](https://pypi.org) (i.e. the Python Package Index web site)
that contains a package that has an `AltVEnv` class.  The package is
named `alt-venv` on PyPI and imports as `alt_venv`.

The bootstrap code will live in every program that needs to bootstrap this
code into their program.  This bootstrap code will assume that the
Python3 distribution being used has a small number of packages like
`venv`, `pip`, and `importlib` preinstalled.

The code will create a `~/.alt_venv` directory and initialize it
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

{Step 6.1 of Task 6 wrapped the fetch in a three line `try` on
2026-09-26, so every `paste` figure above is now three higher: 27, 27,
52, 33, 27, 18, 18, 22, 18, 18, 33 and 58 for cases 1 to 12.  The
wrapper turns a failed fetch into one line of diagnosis instead of a
traceback, which is the `0whwnn` issue.}

### Findings

1. **`venv.EnvBuilder` does not default to symlinks; the command
   line does.**  `python3 -m venv` passes `symlinks=True` on POSIX,
   but `EnvBuilder()`'s own default is `symlinks=False`, which
   copies the 7.7 MB interpreter into `bin/python`, `bin/python3`
   and `bin/python3.12`.  That is 35.7 MB against 12.7 MB for an
   otherwise byte-identical tree of 1013 files; the 23 MB gap is
   exactly those three copies.  Creation takes ~3.1 s either way,
   so the cost is purely disk.  The earlier exploration never saw
   this, because it used the command line.

2. **`ensurepip` is essentially the entire cost of making a venv.**
   `EnvBuilder(with_pip=False)` builds one in 0.05 s and 28 KB,
   against 3.1 s and 12.7 MB with pip.  Nearly everything a venv
   costs is the pip it installs into itself.

3. **The venv is never load-bearing.**  `pip install --target`
   needs no virtual environment at all.  Case 6 skips the venv and
   costs 15 pasted lines and 1762 KB; case 1 builds one and costs
   24 lines and 16981 KB, for identical observable behaviour.
   The earlier exploration reached this conclusion by argument,
   from the venv side.  It is now measured from the bootstrap side
   and the numbers agree.

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
instructions asked for four things: build `~/.alt_venv` using
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
that all twelve cases share, written up as `2apiia`.  It affects
every case equally, so it does not disturb the comparison above.

### Task 2 Summary

Twelve mechanisms were written into one `bootstrap.py`, each a
self-contained case that a program could paste, and measured against
each other.  The table above is that measurement.

The central finding is that the virtual environment is never load
bearing.  `pip install --target` installs into any directory, so a case
that builds a venv and a case that skips it reach identical behaviour --
15 pasted lines against 24, and 1762 KB against 16981.  Nearly all of
what a venv costs is the `pip` that `ensurepip` puts inside it.

Two mechanisms turned out to be unsafe rather than merely expensive.
Driving `pip` in process leaves 451 of its modules in `sys.modules` and
three of its handlers on the caller's root logger.  Reaching into
`pip._internal` at all uses a private interface, recorded as `0pinpa`.

One packaging fact matters more than it looks.  Debian ships `venv` in
the base standard library package but splits `ensurepip` into
`python3.12-venv`, so `import venv` succeeds on a machine where
`python3 -m venv` fails.  The probes that discriminate are
`import ensurepip` and `python3 -m venv` itself.

What this task did not settle is which mechanism to ship, because that
depended on what a stock machine actually provides.  Task 3 settled it
by deciding rather than by measuring.

(CLOSED 2026-09-22)

## Task 3: Master `pip` and Package Servers  (CLOSED 2026-09-24)

This task was called Experiment 2 while it ran.  The text below, several
issues, and `alt_venv_test.py` still use that name.

{`alt_venv` was developed during this task, so "to be developed"
describes only where it started.}

The ultimate goal is to build a testing framework that allows installing
the `alt_venv` (to be developed) package from a `pip` compatible
server (e.g. `pypiserver`) and load it into a program via the bootstrap
technology developed in the previous experiment.

Here is the task list, with what is done struck from it:

* DONE.  Build a wheel for `alt_venv.py`, and lay it out as a
  PEP 503 tree.  Both are in `alt_venv_test.py` and use
  nothing but the standard library.
* DONE.  Let the environment aim `bootstrap.py` at that tree,
  through `PIP_INDEX_URL` and `BOOTSTRAP_PACKAGE`.
* Fill in `AltVEnv` with something worth fetching.
* End-to-end: run a `bootstrap.py` case against the local tree and
  check that `alt_venv` lands in `~/.alt_venv` and
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
* `bootstrap.py` is not being merged into `alt_venv_test.py`.
  This allows `bootstrap.py` to perform end-to-end testing with
  a real Python package server, whereas `alt_venv_test.py` can
  use non server based testing.
* While there are tools that can generate a PEP 503 directory tree
  it easier to just manually generate the tree.

### Task 3 Summary

The pipeline works end to end.  A wheel is built from
`alt_venv.py`, published into a PEP 503 directory tree, fetched by
a `bootstrap.py` case pointed there by environment variables alone,
installed into `~/.alt_venv`, and imported.  Both builders live in
`alt_venv_test.py` and use nothing but the standard library, so no
packaging tool had to be installed to make a package.

`AltVEnv` stopped being empty.  Constructing one creates the cache
directory and writes a `README.md` into it from the constructor's own
docstring.  `install()` installs a package into the cache with
`pip install --target` and imports it, taking a separate distribution
name for the packages whose PyPI name and import name differ, and
raising `RuntimeError` carrying pip's standard error when the fetch
fails.

Four things were measured rather than assumed.  `pip install --target`
is not blocked by PEP 668, so it works on exactly the distributions
that refuse a plain `pip install`.  `pip` honours `PIP_INDEX_URL` from
the environment, so a case is steered without editing it and the
`paste` column stays honest.  A local directory index needs real
`index.html` pages; wheels alone are not enough.  And the whole of what
the bootstrap needs preinstalled is one package, `python3-pip`, plus a
TLS trust store that `python3-pip` already depends on.

Three items did not get done and carry over to Task 5: an automated end
to end test through `bootstrap.py`, the remaining failure cases, and
the real package server that cases 3 and 12 require.

(CLOSED 2026-09-24)

## Task 4: Convert the Logbook to the New Format  (CLOSED 2026-09-24)

`log_book.md` grew as a running narrative with a `FENCE:` marker
separating settled material from working material.  That worked, but the
fence had to be moved by hand and the issue conventions lived only in
the file's own preamble.  This task renames the file to `LOGBOOK.md` and
converts it to the format described in `claude_notes.md`: numbered tasks
that close with a date and a summary, and issues split into active,
pending, rejected and closed.

The fence is gone.  A closed task is marked `(CLOSED YYYY-MM-DD)` in its
heading and carries a summary; both are required, and either one alone
means the task is still open.

Decisions about the format itself are collected in `LOGBOOK_NOTES.md`,
so that they can be propagated back into `claude_notes.md` and then
deleted from this project.

### Task 4 Summary

This file is now `LOGBOOK.md` and is organized as the template in
`claude_notes.md` describes.  In addition, the `FENCE:` marker is gone.
In its place a task is settled when its heading carries `(CLOSED YYYY-MM-DD)`
**and** it has a summary.

Three sections were dissolved rather than moved:
* `Rules of Engagement` -- already said by Task 1 and `CLAUDE.md`.
* The `python3 -m venv` shell transcripts -- a tutorial, not a finding.
* `Misc.` -- three blocks moved out, two superseded, one a pointer.

The issue tracker changed shape:
* Some issues got renamed due to new Issue naming rules.
* Each issue has progress through 4 states - `Active`, `Pending`,
  `Rejected` and `Closed`.
* `Wayne's current thoughts` became `Various thoughts`

Decisions about the logbook format were collected in `LOGBOOK_NOTES.md`,
propagated into `claude_notes.md`, which resides in another directory
under its own separate version control, and then deleted.

(CLOSED 2026-09-24)

## Task 5: A Real Package Server  (CLOSED 2026-09-25)

The primary purpose of this task is to do end-to-end testing of the bootstrap
code with a real package server.  A proposed list of steps list belows:

* Step 5.1: Select a package server.  This is a research task.  No coding.

* Step 5.2: Serve the existing tree over HTTP.  A `ThreadingHTTPServer`
  bound to `127.0.0.1` on port 0, so that the operating system assigns
  the port and the test reads it back rather than colliding with a stale
  server; a daemon thread; torn down through `addClassCleanup`, which is
  also what makes a control-C leave nothing behind.  Prove it by pointing
  `PIP_INDEX_URL` at `http://127.0.0.1:<port>/` and re-running the tests
  that pass today over `file://` -- the same assertions, a different
  transport.  Measured 2026-09-25: `pip` reaches a plain HTTP loopback
  index with no `--trusted-host` and no TLS.

* Step 5.3: Settle cases 3 and 12.  They fetch
  `https://pypi.org/pypi/{PACKAGE}/json` with bare `urllib`, which knows
  nothing of `PIP_INDEX_URL`, so they are the one real gap: either serve
  that JSON shape from the same server, or teach both cases the simple
  API instead.

* Step 5.4: The failure cases carried over from Task 3.  A truncated
  wheel, a missing `index.html`, and a 500 from the index.  All three are
  cheap once a server exists, because a server can be told to misbehave
  where a directory cannot.

* Step 5.5: Run every `bootstrap.py` case against the server end to end,
  asserting that `alt_venv` lands in the cache and imports.  This is
  the test the task exists for.

* Step 5.6: TLS, which nothing has exercised yet.  Two questions: does a
  case refuse a certificate it cannot verify, and does it succeed once
  the certificate is trusted?  `pip` reads `PIP_CERT` and `urllib` reads
  `SSL_CERT_FILE`, both environment variables, so no case body changes.
  This does not settle the `ca-certificates` dependency from Task 3,
  which is about trusting the public authorities well enough to reach
  the real PyPI; a private certificate tests the opposite.

* Step 5.7: Test suite coverage, measured with the standard library
  `trace` rather than `coverage`, so that the suite needs nothing
  installed.

### Step 5.1: Select a package server (research only)

`build_index` in `alt_venv_test.py` already emits a complete PEP
503 tree, so the question was whether any server buys anything that
`http.server` over that tree does not.  The criterion is that the test
suite run with nothing installed beyond `python3-pip`, since a suite
needing `pip install` to test a bootstrap that exists because one
cannot `pip install` argues against itself.  Dependency counts come
from `pip install --dry-run --report`.

* `devpi-server` -- rejected: 43 dependencies, one of them the compiled
  `argon2-cffi-bindings`, which is the `.so` problem of `0nicav`.
* `simpleindex` -- rejected: 14 dependencies, including `pydantic`,
  `uvicorn` and `starlette`, to serve a static file tree.
* `pypiserver` -- rejected: 4 dependencies, and its JSON route is
  `/:project/json` returning the legacy `info`/`releases` shape, so
  cases 3 and 12 would need a translating shim and a path rewrite.
* `http.server` -- **selected**: 0 dependencies, and a
  `ThreadingHTTPServer` on port 0 serving the existing tree installed
  `alt_venv` through `PIP_INDEX_URL` with returncode 0.  The
  handler is about 35 lines, including the 12 that synthesize
  `/pypi/{PACKAGE}/json` in the shape case 3 already parses.

Not settled here: `http.server` has no TLS, so Step 5.6 will need
`ssl.SSLContext.wrap_socket` on the listening socket.  No alternative
above supplies a trusted certificate either.

### Step 5.2: Serve the existing tree over HTTP

`serve_index` in `alt_venv_test.py` publishes the tree that
`build_index` already produced, and both test classes now reach it
through `PIP_INDEX_URL` over a socket instead of over `file://`.  The
15 existing tests pass unchanged, which was the point: same
assertions, different transport.

* The handler subclasses `SimpleHTTPRequestHandler` only to silence
  the request log.  The base class already serves a directory's
  `index.html`, which is exactly what a PEP 503 tree asks for.
* Port 0, so the operating system assigns the port and the caller
  reads it back.  A fixed port would collide with a server left by an
  interrupted run, and that failure would read as a packaging bug.
* A daemon thread is what makes control-C clean.  Measured
  2026-09-25: `SIGINT` to a test process ended it in 0.032 s and the
  port was refusing connections immediately afterwards.
* `tearDownClass` calls `shutdown` and `server_close` before the tree
  is removed, and the server starts last in `setUpClass` so that
  nothing can fail after it is up.

Not done here: cases 3 and 12 still cannot be tested, because they
want `/pypi/{PACKAGE}/json` rather than the simple API.  That is Step
5.3.

### Step 5.3: Settle cases 3 and 12

Cases 3 and 12 read PyPI's JSON API with `urllib`, which knows nothing
of `PIP_INDEX_URL`, so they were the two cases no local index could
reach.  They are now tested, and the choice was to serve the JSON
rather than to convert them to the simple API.  That keeps what the
cases measure -- a bootstrap needing neither `pip` nor `venv` -- which
converting them would have thrown away.

* `bootstrap.py` gained `JSON_API`, read from `BOOTSTRAP_JSON_API` and
  defaulting to `https://pypi.org/pypi`.  This copies what `PACKAGE`
  and `BOOTSTRAP_PACKAGE` already do, and for the same reason: the
  harness aims a case at a local server without editing a case body.
* The `paste` column did not move.  The substitution costs no lines,
  and `measure_source` still reports 5 imports and 45 lines for case 3
  and 7 and 51 for case 12, which is what the Task 2 table says.  No
  remeasurement was needed after all.
* `_IndexHandler` answers `/pypi/{project}/json` from the tree, in the
  modern `{"urls": [...]}` shape that those two cases parse, and 404s
  a project the index does not hold.  The payload is the subset they
  read rather than all of PyPI's, since the rest cannot be checked.
* Both cases now run end to end: three new tests take the suite to 18,
  and pointing `BOOTSTRAP_JSON_API` at a dead port fails them, so they
  are measuring the fetch and not passing vacuously.

### Step 5.4: The failure cases

A directory index cannot misbehave, which is why these went untested
through Tasks 2 and 3.  `_IndexServer` now carries a `faults` table
that maps a path suffix to what should go wrong, and a test adds an
entry through `inject`, which registers the removal as a cleanup first
so that a failing assertion cannot leave the fault in place.

* Four faults exist.  `missing` answers 404, `error` answers 500,
  `hang` waits three seconds and then answers correctly, and
  `truncate` sends the first half of the file with a `Content-Length`
  that agrees with the half.
* `truncate` is the one worth having.  The download looks complete at
  every layer below the archive, so nothing but unzipping catches it.
  `pip` refuses the install, and case 3, which unzips the wheel
  itself, fails inside `zipfile`.
* Five tests take the suite to 23.  Neutering `inject` makes all five
  fail, so they measure the faults rather than passing for free.
* A hung connection turned out to be in scope after all, for `pip`:
  `PIP_TIMEOUT` and `PIP_RETRIES` bound the wait, so the test costs a
  second rather than a minute.  It stays out of scope for cases 3 and
  12, whose `urlopen` timeouts are literals of 30 and 60 seconds
  inside counted case bodies.  Steering those would want a third
  harness constant beside `PACKAGE` and `JSON_API`.
* `_IndexServer.handle_error` swallows `ConnectionError` and nothing
  else.  A client that times out hangs up mid-answer, and the base
  class prints a traceback for that, which looked like a failure in
  the middle of a passing run.

### Step 5.5: Every case, end to end

`test_every_case_bootstraps` runs all twelve cases against our own
server and asserts that each one lands `alt_venv` in the cache and
imports it.  All twelve pass.  That is the claim Task 5 was opened to
establish.

* The case list is read from `bootstrap.MECHANISMS` rather than copied
  into the test, so a thirteenth case cannot quietly go untested.
* Four assertions per case: `pip` or `urllib` exited zero, the printed
  module name matches, the version matches `alt_venv.__version__`,
  and the file it was imported from lies under `.alt_venv`.  The
  last one is what distinguishes a real fetch from an accidental
  import of the copy in this directory.
* The suite went from 13.8 s to 40.3 s.  The twelve cases cost about
  26 s of that, nearly all of it building virtual environments.
* Every run in that test is cold, because each case gets a fresh
  `HOME`, so the warm path needed a test of its own.
  `test_every_case_bootstraps_repeatedly` is it: one cache per case,
  three runs through it, all twelve passing.  Three rather than two
  because the repair that `0cctfd` needed has to be idempotent, and an
  earlier version of it passed two runs and broke the cache on the
  third.  `0cctfd` is closed.

### Step 5.6: TLS

The one thing a directory index could never test.  `make_certificate`
shells out to `openssl` for a throwaway self signed certificate, and
`serve_index` wraps the listening socket when it is handed one.  Both
questions are answered, and the first is the one that mattered.

* **Every case refuses a certificate it cannot verify**, and fails over
  the certificate rather than for some unrelated reason.  Case 3, which
  uses `urllib`, reports
  `[SSL: CERTIFICATE_VERIFY_FAILED] ... self-signed certificate`; case
  6, which uses `pip`, reports `SSLCertVerificationError`.  Nothing
  falls back to plain HTTP and nothing accepts an unknown issuer.  Had
  one done so, it would have been a priority 0 issue: pasted code on a
  stranger's machine handing their program's contents to whoever
  controls the network.
* Every case succeeds once the certificate is trusted, which is what
  makes the refusal a real check rather than TLS being broken outright.
  `SSL_CERT_FILE` is what `urllib` honours, through OpenSSL's own
  default verify paths, and `PIP_CERT` is what `pip` honours.  Both are
  environment variables, so no case gained a line and the `paste`
  column did not move.
* `openssl` is a program rather than a Python package, so it costs the
  suite no dependency under the Step 5.1 criterion.  A machine without
  it skips these tests rather than failing them.  The certificate lasts
  ten years and carries `subjectAltName=IP:127.0.0.1`, because Python
  has ignored `commonName` since 3.7.
* `handle_error` now swallows `ssl.SSLError` as well as
  `ConnectionError`.  A refused handshake is exactly what the negative
  test provokes, and the base class prints a traceback for it.

`ALT_VENV_TEST` chooses how much of this runs.  Unset or `FAST`,
which is the usual way, exercises cases 3, 6, 11 and 12 -- one case per
distinct mechanism, plus the one whose second run used to fail.
`COMPLETE` exercises all twelve.  An unrecognised value raises rather
than quietly running the fast tests.  Measured 2026-09-25: 29 tests in
50.9 s fast, 193.3 s complete, both passing.

One thing is still unsettled, and it is the last of the Task 3
leftovers.  Task 3 concluded that a bootstrap needs `python3-pip` plus
a TLS trust store, and that conclusion is about trusting the public
certificate authorities well enough to reach the real PyPI.  A private
certificate tests the opposite, that the system trust store can be
overridden, so nothing here confirms it.  Confirming it needs a fetch
from the real index, which is a test with a network dependency and
belongs with the work on `alt_venv.py` rather than here.

### Step 5.7: Coverage

`alt_venv_coverage.py` measures the suite with the standard
library `trace`.  `coverage` would have been a `pip install`, and a
suite for a project about packages that are not preinstalled should not
need a package fetched; the same criterion chose `http.server` in Step
5.1.  Where it ended up, on the fast suite:

| module                   | lines | before | after |
| ------------------------ | ----- | ------ | ----- |
| `bootstrap.py`           |   407 |     7% |    7% |
| `alt_venv.py`       |    65 |    60% |   98% |
| `alt_venv_test.py`  |   590 |    87% |   99% |

Nine tests were added, taking the suite from 29 to 38 and from 50.9 s
to 56.5 s.  Tracing itself costs almost nothing, which is its own
finding: nearly all of the work happens in child processes, where the
tracer cannot reach.

* **`alt_venv.py` is effectively complete.**  The gap was that
  `repair_module_layout` and `install` were exercised only through
  child interpreters, so their bodies were never measured.  Calling
  them in process, with `__file__` or `PIP_INDEX_URL` patched, covered
  both.  The last uncovered line can never be reported: it runs only
  when `__file__` is `None`, and `trace.Trace.globaltrace_lt` decides
  what to follow by reading `frame.f_globals.get("__file__")`, so the
  state that reaches the line is the state that turns tracing off.
  98% here means 100%.
* **Threads have to be instrumented separately**, and this was the
  single biggest correction.  `trace` follows only the thread it starts
  in, so every request handler looked dead however many requests went
  through it.  `threading.settrace` moved the harness from 88% to 99%.
* **The one real gap tracing found** was `make_certificate`'s two
  failure returns and the skip they trigger: the path that runs on a
  machine with no `openssl`, where a fault would make the TLS tests
  error instead of skip, and where it would be hardest to diagnose.
  Three tests cover it now, one of them using `/bin/false` as a
  stand-in for a failing `openssl` so that nothing mocks `subprocess`.
* **Hit counts said more than percentages.**  `do_GET` ran 54 times,
  `fault` returned a fault 5 times and `None` 49, `send_fault` covered
  `missing`, `error` and `hang` once each and `truncate` twice, and
  `send_json` answered ten times and 404ed once.  That `hang` alone
  falls through to a correct answer is visible in the counts: the
  post-fault `return` fires four times, not five.
* **`bootstrap.py`'s 7% is an artefact** of the twelve cases running as
  children, and measures only the module level code that an import
  executes.  The cases are covered by Steps 5.5 and the repeat test.
  Driving `main()` in process would mean twelve cases mutating
  `sys.path`, `HOME` and `sys.modules` inside the runner, which is why
  they are children in the first place.
* Five uncovered lines remain in the harness, all accounted for and
  none worth closing: `super().handle_error`, which never firing is
  the healthy state; the `openssl` absent skip, untestable while
  `openssl` is present; and `main` with its `unittest.main`, which the
  coverage runner bypasses by calling `unittest.main(module=...)`.

### Task 5 Summary

All twelve `bootstrap.py` cases now fetch `alt_venv` from a
package server this project controls, import it, and do it again on a
second and third run without fetching anything.  That was the whole
point of the task.

The server is `http.server` over the PEP 503 tree the test suite
already built, chosen in Step 5.1 because the alternatives cost between
4 and 43 dependencies and bought nothing.  It serves the JSON API that
cases 3 and 12 read, it can be told to misbehave, and it can speak TLS.
None of that cost a single case a line of pasted code: `JSON_API`, the
`0cctfd` repair and the whole of TLS are steered from outside the case
bodies, so every `paste` figure is what Task 2 measured.

Three things were learned rather than assumed.  Pointing the cases at
the package this project ships, instead of at `coverage`, immediately
exposed `0cctfd`: the guard every case uses asks whether the package is
a directory, a single module install is not one, and case 11 deletes
the `pip` it would need to fetch again.  Every case fails closed on a
certificate it cannot verify, which nothing had ever checked and which
would have been a priority 0 defect had it gone the other way.  And
tracing the suite found that its own server was invisible to the
tracer, because `trace` follows only the thread it starts in.

What is not settled: Task 3's conclusion that a bootstrap needs
`python3-pip` plus a TLS trust store is about trusting the public
certificate authorities well enough to reach the real PyPI, and a
private certificate tests the opposite.  Confirming it needs a fetch
from the real index.

The final measurement follows.  The Task 2 chart stays as it was,
because it measured `coverage` from PyPI and this one measures
`alt_venv` from `127.0.0.1`.

```
date        : 2026-09-25 19:12
python      : 3.12.3 at /usr/bin/python3
platform    : linux
inside venv : False
package     : alt_venv
index       : local, http
repetitions : 3; cold and warm are medians

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 20    | 24    | 4.42 s | 0.09 s | 15275  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 20    | 24    | 4.45 s | 0.10 s | 15275  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 49    | 0.13 s | 0.10 s | 52     |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 26    | 30    | 4.38 s | 0.10 s | 84     |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 20    | 24    | 1.23 s | 0.10 s | 84     |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 11    | 15    | 1.23 s | 0.09 s | 56     |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 11    | 15    | 1.33 s | 0.08 s | 56     |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 15    | 19    | 2.76 s | 0.09 s | 56     |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 15    | 1.27 s | 0.09 s | 56     |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 15    | 1.36 s | 0.09 s | 56     |
|      | compile         |         |       |       |        |        |        |
| 11   | as 4 but        | 5       | 26    | 30    | 3.88 s | 0.10 s | 84     |
|      | subprocess      |         |       |       |        |        |        |
| 12   | venv(no pip),   | 7       | 51    | 55    | 0.15 s | 0.11 s | 80     |
|      | stdlib wheel    |         |       |       |        |        |        |
+------+-----------------+---------+-------+-------+--------+--------+--------+

All cases succeeded.
```

{Step 6.1 of Task 6 wrapped the fetch in a three line `try` on
2026-09-26, so every `paste` figure above is now three higher: 27, 27,
52, 33, 27, 18, 18, 22, 18, 18, 33 and 58 for cases 1 to 12.  The
wrapper turns a failed fetch into one line of diagnosis instead of a
traceback, which is the `0whwnn` issue.}

What the remeasurement says:

* All twelve cases fetch `alt_venv` from our own server and import
  it, with no failures.  That is the thing Task 5 exists to establish.
* `imports`, `lines` and `paste` are identical to the Task 2 chart in
  every row.  Neither `JSON_API` nor the `0cctfd` repair cost a case a
  line, because both live outside the pasted case bodies.
* Warm is now genuinely warm: 0.08 to 0.11 s everywhere, against 1.20
  to 2.76 s before `0cctfd` was fixed.  The guard now trips, so a
  second run inserts a path and imports rather than fetching again.
  Case 11, which failed on every warm run, passes.
* Sizes rose by 16 KB per case, which is the `README.md` the
  constructor writes plus the directory the repair creates.  The
  constructor did not run at all before, because `bootstrap.py` only
  imported the module.
* Against the Task 2 chart, sizes are still smaller by a factor of
  about 20 outside the venv-with-pip cases, because `alt_venv` is
  one pure Python module where `coverage` ships compiled extensions.
  The 15275 KB of cases 1 and 2 is almost entirely the `pip` they keep.

(CLOSED 2026-09-25)

## Task 6: Flesh out the `AltVEnv` Class

The primary purpose of this task is to add features to
`alt_venv.py`.  The steps are sorted by priority with the highest
**first**, so Step 6.1 is the next thing to do.  Renumbering is
expected every time the order changes, and is Claude's job.

* Step 6.1: Generate error on bootstrap fetch error (`0whwnn`):
  * The new bootstrap diagnoses a failed fetch, which closes `0whwnn`.
  * Measured 2026-09-25 against a dead port: case 6 ends in
   `RuntimeError: pip failed` after ten lines of traceback and never
    mentions the network, and case 3 buries `Connection refused` under 47.
    Neither is an error message.
  * Wrap the fetch once in the shared region and `raise SystemExit` naming
    the package, the destination and the underlying error.  `SHARED_LINES`
    then goes from 4 to 7 and every `paste` figure rises by three, which
    makes this the first change to move that column.  A `sys.excepthook`
    would be shorter and is rejected: the bootstrap sits at the top of
    somebody else's program and must not leave a global hook mangling
    their tracebacks.

* Step 6.2: Several packages in one call, and what to do about bad
  requirements.  `install` takes one requirement or a list, costs one
  `pip` invocation for the set so that `pip` resolves them together,
  and is what makes Step 6.3's freshness check affordable.
  * 6.2.1 - `pip._internal` buys nothing here, measured 2026-09-26.
    `pip._internal.cli.main.main` **returns 1** for a missing package
    and raises nothing: it catches its own exceptions and converts them
    to exit codes exactly as the command line does.  The thirteen typed
    exceptions exist, but catching them means driving the resolver
    directly, which is far deeper into private API than the cases that
    got `0pinpa` filed, for the same stderr text we already have.
  * 6.2.2 - Exit codes carry one useful bit.  A missing package, an
    impossible version, a malformed requirement and a dead index all
    exit 1; only a bad option exits 2.  So 2 means we handed `pip` a
    bad command line, which is our bug or the caller's `argv`, and
    deserves a different exception.  `NO_MATCHES_FOUND = 23` exists in
    pip's status codes but `install` never returns it.
  * 6.2.3 - Parse pip's text for the message, never for the behaviour.
    Matching `No matching distribution found` to add "check the
    spelling?" is fine, because a rephrasing costs a hint and nothing
    else.  Branching control flow on it breaks on a pip upgrade, which
    is `0pinpa`'s failure mode reached through text instead of imports.
  * 6.2.4 - Validate locally what can be validated locally.  A
    requirement beginning with `-` is the one that matters: it would be
    read as an option, so `install("--index-url=...")` could repoint
    the fetch at somebody else's index, which belongs with Step 6.6.
    Requirement syntax is not ours to check: measured 2026-09-26, `pip`
    rejects `bad name with spaces` in 0.59 s with
    `ERROR: Invalid requirement`, locally, without touching the
    network, so reimplementing PEP 508 would only add a way to
    disagree with it.  What is left is that two entries must not claim
    the same import name, since `pip` cannot know our import names and
    one module would be returned twice.
  * 6.2.5 - What cannot be checked locally is whether `reqeusts`
    exists; only the index knows, so that error has to come from `pip`
    and is surfaced with pip's own words.  The one discrimination that
    really matters, first fetch versus staleness check in 6.3.8, comes
    from whether the cache is populated, which is known locally.

* Step 6.3: A versioned cache built out of the wheels themselves.  This
  is the fix for `0nicav`, priority 0 because the cache path carries no
  version, interpreter or platform, so the same directory reached by a
  different Python loads whatever the last one left.  It also settles
  where the cache lives, `2wscdl`, and it carries the jail that Step 6.6
  needs.

  The pipeline is download, approve, unpack, import.  `pip download`
  fetches wheels into a holding area; the user approves what arrived;
  each approved wheel is unpacked into a directory of its own; and only
  those directories are ever put on `sys.path`.
  * 6.3.1 - Four directories under `root`, and one rule.  `pending/`
    holds wheels that arrived but are not approved, `wheels/` holds the
    approved artifacts, `versions/` holds one unpacked tree per resolved
    version, and `requests/` holds one record per request answered.
    **Only `versions/` is ever put on `sys.path`.**  That single
    sentence is the jail: a wheel is an inert zip, so nothing under
    `pending/` can have run.  Unpacking happens inside `pending/` too,
    not beside the destination, so `versions/` never holds a partial
    tree for `contains` or `sys.path` to find.  Both are under `root`,
    so the rename into place stays within one filesystem and stays
    atomic.
  * 6.3.2 - Do not move `root` itself.  `repair_module_layout` fires
    only for a module under `self.root`, so relocating the cache
    silently reopens `0cctfd` and case 11 fails on its second run.
    Stage 1 is pinned to `~/.alt_venv` by the pasted code, so all of
    this goes beneath it.  That answers `2wscdl` with a constraint
    rather than a preference.
  * 6.3.3 - Write no version expression parser.  Measured 2026-09-26
    with 1.0.0, 2.0.0 and 3.0.0rc1 published: `sprocket>=3` **fails**,
    although `3.0.0rc1` satisfies `>=3` numerically, because PEP 440
    excludes pre-releases unless asked.  A tuple comparing parser would
    have installed the release candidate, silently, on somebody else's
    machine.  That is `2wtmifs`'s failure mode exactly.  PEP 440 also
    has epochs, post and dev releases, local versions, `~=` and `==1.2.*`
    wildcards.  `pip` owns all of it.
  * 6.3.4 - Key the cache on the request, not the resolution.  If
    `sprocket<2` was resolved before, reuse it; no comparison is needed,
    only string equality on a normalised requirement.  The cost is cache
    misses, never wrong answers: `sprocket<2` and `sprocket<2.0` become
    two keys for one result.
  * 6.3.5 - Two forms need no round trip and no parser.  A `==` pin is
    answered by looking for a directory named `sprocket-1.0.0`, which is
    the form a reproducible program uses.  A bare name can never be
    answered from the cache at all, since "newest" is a property of the
    index, so even a perfect parser would not save that round trip,
    which is most of the reason not to write one.
  * 6.3.6 - A version directory name has to carry the interpreter and
    the platform as well as the version, which is what `0nicav` is
    about: `sys.implementation.cache_tag` and
    `sysconfig.get_platform()`.  Neither can tell musl from glibc, the
    blind spot of `2wtmifs`.
  * 6.3.7 - `pip download` does not accept `--report`, measured
    2026-09-26: exit 2, it is an `install` option.  So hash the wheel
    that arrived rather than trusting what the index claimed, which is
    the better of the two anyway.  That hash is also the identity Step
    6.6 approves.  Done: `AltVEnv.digest` reads the file in 64 KiB
    blocks, and `unpack` writes the hexadecimal beside the kept wheel as
    `<name>.sha256`.  It is the only thing that could notice a
    distribution re-uploaded under a version it had already used.
  * 6.3.8 - Download **with** dependencies, not `--no-deps`.  The
    transitive closure landing in `pending/` is exactly what Step 6.6.4
    wants the user to see, and it is the thing nobody ever looks at.
  * 6.3.9 - Approval is a rename from `pending/` into `versions/`, which
    is atomic within one filesystem.  That gives Step 6.4 its answer for
    nothing.  Measured 2026-09-26: renaming a directory onto a
    **non-empty** one fails with `ENOTEMPTY`, which is what makes the
    loser of a race take the winner's tree rather than see half of one.
    Onto an **empty** directory it silently succeeds, so nothing must
    ever create an empty `versions/<key>/`.  This holds even when two
    downloads differ, so it does not depend on the wheels being
    identical.
  * 6.3.13 - One record file per request, not one shared file.  A shared
    file is read, modified and written, and two overlapping writers lose
    one of the two entries; measured 2026-09-26 with two threads, they
    do.  A file named by the hash of the request cannot collide, is
    smaller to read and write, and is moved into place with `replace`
    rather than `rename`, which is the same on POSIX but does not raise
    on Windows where `3vedih` is already waiting.  The request is stored
    inside the record as well, so a person can read it and a hash
    collision cannot pass as a hit.  Two writers recording the *same*
    request may honestly disagree, if the index gained a release between
    them; one wins, both trees exist, and the loser's is garbage for
    Step 6.10.
  * 6.3.10 - The same failure wants opposite handling.  On a first fetch
    there is no cache, so an unreachable index must say so and stop; on
    a staleness check there is one, so it must be shrugged off, because
    a laptop on a plane has to start.  The distinction comes from
    whether the cache is populated, which is known locally.
  * 6.3.11 - Two versions of one module cannot coexist in a process.
    Measured 2026-09-26: with both trees on `sys.path`, a second
    `import sprocket` returned the **first** version and
    `importlib.invalidate_caches()` did not change it, because
    `sys.modules` is keyed by module name.  So the cache may hold many
    versions while any one program resolves to one per import name.
    `install` already refuses a repeated import name within one call;
    two separate calls asking for different versions are not caught yet,
    and that is the silent wrong version bug.
  * 6.3.12 - Unpacking wheels ourselves takes on part of the wheel spec
    that `pip` currently handles: `RECORD`, `.data/purelib` and
    `.data/scripts`, entry points, and `.pth` files, which is
    `3pfaibne`.  For a pure Python wheel it is the `purelib` move and
    little else, but it is a real scope increase and should be entered
    knowingly.  Cases 3 and 12 already do this much.

* Step 6.4: Concurrent installs.  Mostly answered by Step 6.3's
  construction rather than by a mechanism of its own, because nothing
  installs into a shared directory any more.  Done: a download directory
  per call, so two programs never share a staging area; unpacking inside
  `pending/` and renaming into `versions/`, where `ENOTEMPTY` makes the
  loser take the winner's tree; one record file per request, so no write
  can lose another's; and `mkdir(exist_ok=True)` throughout.
  * 6.4.1 - `repair_module_layout` had a real race, found 2026-09-26 by
    asking this question: two programs both read the module and both
    removed it, and the second raised `FileNotFoundError` out of a
    constructor.  `unlink(missing_ok=True)` now, with a test that makes
    the read delete the file as a rival would have.
  * 6.4.2 - Carried to Step 6.10 rather than left open here: a program
    killed mid-unpack leaves an `unpacking-` directory under
    `pending/`, and a killed download leaves its own.  Neither is
    importable, so neither is a correctness problem; they only
    accumulate, which is culling work.
  * 6.4.3 - Done 2026-09-26, and it took three tries to make it mean
    anything.  `test_four_processes_share_one_cache` runs four real
    programs against one cache and checks that one of everything comes
    out, with the index made `slow` so the fetches overlap.  But
    deleting the lost race recovery did not make it fail: the window
    between asking whether a tree exists and renaming one into place is
    a millisecond or two, and four processes drift further apart than
    that while `pip` runs.  Moving the delay from the project page to
    the wheel did not help either.
  * 6.4.4 - What worked was a barrier.
    `test_four_processes_collide_on_one_unpack` has each process
    download first, wait until every one of them has arrived, and only
    then unpack, which puts them inside the window deliberately.  With
    four racers, deleting the recovery was caught two runs in three and
    then none in five, which is variance rather than a test.  With
    eight it was caught six times out of six, and the correct code
    passes every time.  Both tests are worth keeping: the first shows
    the outcome under honest concurrency, the second exercises the
    race.
  * 6.4.5 - The lesson, which cost most of the time here: a concurrency
    test that passes proves nothing until the fix it guards has been
    removed and the test has been seen to fail.  Timing tests are
    especially good at passing for no reason.

* Step 6.5: Coverage of child processes.  Most of what this suite does
  happens in children, and `trace` follows neither those nor threads, so
  `bootstrap.py` read as 7% however thoroughly its twelve cases were
  exercised.
  * 6.5.1 - `trace` merges its own results: `CoverageResults` reads a
    saved count file through `infile` and folds another in through
    `update`, so no third party tool is wanted.  Each child writes its
    own file named after its process id, so there is no shared file for
    two writers to lose an entry in.
  * 6.5.2 - The only hook that reaches a process nobody wrote the
    command line for is `sitecustomize`, which Python imports from
    `sys.path` at startup.  It lives in `trace_hook/`, which is **not**
    anywhere Python looks by default: `alt_venv_coverage.py --children`
    puts it on `PYTHONPATH`.  A `sitecustomize.py` in the project root
    would quietly affect every interpreter started from that directory.
  * 6.5.3 - Two mistakes worth not repeating.  Reading the counts while
    the tracer still runs raises
    `RuntimeError: dictionary changed size during iteration`, so
    tracing has to be switched off first.  And
    `CoverageResults.write_results` also writes annotated `.cover` files
    into the working directory, which littered the project root; the
    counts are pickled directly instead.
  * 6.5.4 - `pip` is skipped by the hook.  It is nobody here's code and
    it is most of the cost: case 6, which runs `pip._internal` in
    process, went from 1.21 s to 10.33 s traced, where case 3 went from
    0.16 s to 0.29 s.
  * 6.5.5 - The result on the fast suite: `bootstrap.py` 7% to 41%,
    113 child processes folded in, 60 tests in 357 s against 70 s.
  * 6.5.6 - **`2wtmifs` is now measured rather than argued.**  Cases 3
    and 12 each have exactly seven uncovered lines, the same seven: the
    wheel tag matcher's platform branch,
    `or (machine in name and "linux" in name and sys.platform ==
    "linux")`, has **never executed**, and neither has
    `raise RuntimeError("no compatible wheel found")`.  The issue said
    the matcher "agreed with pip for one package on one platform"; the
    interesting half of it has never run at all.
  * 6.5.7 - The `.data/purelib` and `.data/platlib` move in cases 3 and
    12 has never executed either, for the same reason it had never
    executed in `AltVEnv.unpack`: no wheel the suite builds has a
    `.data` tree.  That gap hid a real bug in the second stage, a
    `.data` directory left behind after the move, found the same day.
    The pasted code has the identical blind spot.
  * 6.5.8 - What is not a defect: on the fast suite, cases 1, 2, 4, 5
    and 7 to 10 are barely covered because `FAST` selects only 3, 6, 11
    and 12, and 98 module level lines are `run_tests`,
    `measure_source`, `format_table` and `directory_size`, which run
    only when `bootstrap.py` is invoked from the command line.
  * 6.5.9 - The complete run settles it.  `ALT_VENV_TEST=COMPLETE` with
    children traced: 60 tests in 837 s, 184 child processes, and
    `bootstrap.py` at 72%.  **Ten of the twelve cases are covered
    completely, 0 lines missed.**  The only dead code inside any pasted
    case is the seven lines in each of cases 3 and 12 named above: the
    matcher's platform branch, its `raise`, and the `.data` move.  The
    remaining 98 are the measurement harness, which runs from the
    command line and produced the Task 5 chart by hand.
  * 6.5.10 - So the hook is worth keeping.  It turned one open issue
    into a measurement, found the same `.data` blind spot in the pasted
    code that had just hidden a real bug in the second stage, and
    cleared ten of twelve cases outright.  Nothing else here could have
    said any of that.
  * 6.5.11 - Done 2026-09-26.  `build_wheel` gained a `tag`, the index
    publishes a second `alt-venv` wheel wearing this interpreter's
    compiled tag and carrying a `.data/purelib` member, and a third
    test serves one `cp312-cp312-win_amd64` wheel so that nothing
    matches.  Cases 3 and 12 prefer the tagged wheel, move its `.data`
    member up beside the module, and refuse the Windows one with
    `no compatible wheel found` and no traceback.  `bootstrap.py` is at
    75% and **all twelve pasted cases are covered completely**; the
    remaining 98 lines are the command line measurement harness.
  * 6.5.12 - No new bug was found in that round, which is worth
    recording as a result rather than a disappointment.  The matcher
    behaved correctly for all three shapes a Linux machine can build.
    The earlier rounds did find three: the stray `.data` directory, the
    `repair_module_layout` unlink race, and a jail boundary crossed
    while staging.  Cost to keep: 62 tests in 87 s normally, about
    seventeen minutes with `--children` on `COMPLETE`, and the hook is
    off unless asked for.

* Step 6.6: Security, and who approves what.
  * 6.6.1 - Write the threat model down first, because the claim has to
    be narrow to be true.  A malicious program author gets no
    protection at all, since the bootstrap is their code and they can
    delete the prompt.  A typosquatted package gets very little:
    `reqeusts . PyPI` and `requests . PyPI` have titles of identical
    form, so pasting one proves a page was fetched, not that the right
    one was recognised.  A compromised index or network is TLS and
    hashes, not ceremony.  What the Hunt genuinely defends is
    inattention to the dependency set, and that is worth saying
    plainly; claiming more would make it theatre.
  * 6.6.2 - The real guarantee is the ordering:  download, approve,
    install.  With `--only-binary :all:` a wheel is an inert zip, so no
    third party code has run at the moment the user is asked.  Neither
    `uv run` nor `pip-run` can make that claim, and it should be stated
    as the architectural promise rather than left as an aside.
  * 6.6.3 - Refuse sdists.  `--only-binary :all:` is the one lever
    worth more than all the rest, because an sdist runs arbitrary code
    at install time through `setup.py` and a wheel does not.
  * 6.6.4 - Show the transitive closure.  Nobody ever looks at what
    `pip install requests` actually pulls in, and a list the user must
    page through is the first time most people would see the number.
    That alone justifies the mechanism.
  * 6.6.5 - Approve a hash, not a name.  Approving "coverage" means
    nothing; approving `coverage 7.16.1 sha256=e82e10b9...` is a real
    decision, and a version bump then correctly re-prompts.  The
    identity to record is the one Step 6.3 already fetches.
  * 6.6.6 - Non-interactive execution is a hard requirement, not an
    edge case.  A program under cron, CI, systemd, a pipe or a
    double-clicked launcher has no tty, and the Hunt would hang or
    crash.  Needs `sys.stdin.isatty()`, a documented approval file or
    environment variable for that case, and a clear message when
    neither is present.
  * 6.6.7 - Habituation is the standing objection and deserves an
    answer in the `README.md`.  Every repeated confirmation ritual
    decays into muscle memory, as certificate warnings and UAC did.
    Once per program rather than once per run is the mitigation, and
    saying so is the reply.
  * 6.6.8 - One prompt for the whole set, not `N` title pastes, is
    worth considering.  The same visibility at a tenth of the tedium,
    and the title paste is the part that buys least.  The cost lands on
    the person who did not choose the dependencies, and `uv run` asks
    them for nothing.
  * 6.6.9 - Answered 2026-09-26, and the answer is a boundary rather
    than a defence.  The approvals live beside the program, as `prog.py`
    to `prog.altvenv`, and anybody who can write that file can edit
    `prog.py` itself, so pre-approving something is strictly less work
    than simply changing the program.  Nothing here defends against
    somebody who already has write access to the program; saying so is
    the decision.
  * 6.6.10 - Answered 2026-09-26: the prompt does not defend against
    typosquatting and never could.  `reqeusts` and `requests` have names
    of the same shape, summaries that are copies of each other, and
    project pages that look alike, so nothing shown to somebody at run
    time distinguishes them.  The **approvals file** is the defence: the
    author, who chose the dependency and can tell the two apart, got the
    name right once, and the SHA-256 pins that exact artifact
    thereafter.  This is why approval belongs to the author and not to
    whoever happens to run the program.

  * 6.6.11 - The project's `README.md` is Step 6.13's, not this step's.
    Its `## Security Issues of Executing Unvetted Code` section is
    outlined by the sub-items here, and by 6.6.1 above all.

  * 6.6.12 - The cache owns the package, not the program.  Wayne's
    sentence, 2026-09-26, and it is the reason the warm path neither
    asks nor verifies: a tree in `versions/` may have arrived on behalf
    of some other program entirely, so no one program's approvals file
    is the authority over it.  Verification therefore belongs to the
    moment of fetching, which is also the only moment anything is asked.

  * 6.6.13 - What gets asked, settled 2026-09-26.  Nothing is said and
    nothing is asked unless at least one wheel has to be downloaded.
    When anything does, the whole set is shown, including packages the
    cache already holds, because the request is keyed on the entire
    requirement set and a set nobody has vetted has not been vetted.
    Measured: a second program sharing a cache and asking for `needy`
    is shown `needy` as asked for and `widget` as having come along,
    although `widget` was already there from the first program.  The
    listing therefore appears once per cache, not once per run.

  * 6.6.14 - Two things the mechanism cannot do, recorded so that they
    are decisions rather than oversights.  A declined download is
    discarded, not kept, so `pending/` is empty afterwards and a later
    run fetches again; a refusal means do not install this, not keep it
    for later.  And `ALT_VENV_APPROVE=write` records what arrived
    without judging it, so an author who runs it while pointed at an
    index they should not trust will approve whatever that index sent,
    and the file then vouches for it everywhere the program goes.  There
    is no technical answer to the second: run it against an index you
    mean to trust.

* Step 6.7: Declared requirements, which is `2hsrpbd`.  Read the
  calling script's PEP 723 `# /// script` block instead of a package
  name written into the bootstrap.  It builds on Step 6.2, and it makes
  the same file work under `uv run` for nothing, which is worth a great
  deal given that prior art is why this project has to justify itself at
  all.

  First of what remains, on 2026-09-27, because it is the largest change
  to what the product is: the program declares what it needs instead of
  somebody writing an `install` call by hand.  It also builds the
  locator that Step 6.11 needs, so doing it first hands that step its
  primitive for free.  And both `README.md` files are last for the
  matching reason: the usage they describe changes here, and writing
  them earlier means writing them twice.
  * 6.7.1 - Implement PEP 723 support.
    A different format was considered but rejected.  PEP 723 is final.
  * 6.7.2 - PEP 723 goes in `#` comments, and the block is read from the
    file's source text rather than from anything the interpreter keeps.
    Nothing else works: `python3 -OO` strips docstrings, so `__doc__` may
    be `None`, and comments never exist at run time at all, being dropped
    at compile time.  Reading the source makes both available, and the
    remaining reason to prefer comments is that a TOML block inside a
    docstring turns up in `help(module)`, which is why the PEP chose
    comments.
  * 6.7.3 - Parsing costs no dependency.  `tomllib` has been in the
    standard library since 3.11 and is in `libpython3.12-stdlib` here,
    not in a separable package.  It does raise the floor from 3.10,
    which `X | Y` and `match` already set, to 3.11; worth saying out
    loud before it is discovered.
  * 6.7.4 - Wants the shared locator described in 6.11.1.

  * 6.7.5 - The floor is stated, and it is as low as the code allows.
    Decided 2026-09-27: `>=3.10`, because annotations such as
    `Path | None` are evaluated at run time and `bootstrap.py` uses
    `match`, and because **nothing here needs 3.11 or 3.12**.  Importing
    `tomllib` for this step moves it to `>=3.11`, and that is the whole
    cost of doing so.

    Raising it further was considered and declined.  Every version
    excluded is a machine that cannot run the thing, which is what this
    project is about: from recollection rather than measurement, Ubuntu
    22.04 LTS ships 3.10 and is supported to April 2027, Debian 12 ships
    3.11, and RHEL 9 ships 3.9 and is supported to 2032.  Requiring 3.12
    would turn all three away and buy nothing, since no 3.12 feature is
    used.  What distributions actually ship is `2hmmdrpe`, still
    unmeasured.

    Until now the floor was stated nowhere at all, which is ironic for a
    step about reading other people's `requires-python`.  The wheel now
    carries `Requires-Python`, and that is worth the line: measured
    2026-09-27, `pip` refuses a wheel it cannot satisfy with
    `requires a different Python: 3.12.3 not in '>=3.99'`, where without
    it the install succeeds and the program dies later on a `SyntaxError`
    from an annotation, explaining nothing.  `build_wheel` takes a
    `floor`, the `alt-venv` wheels pass `FLOOR`, and the throwaway test
    packages claim nothing.

* Step 6.8: `.pth` files, which is `3pfaibne`.  `install` uses
  `sys.path.insert`, which never executes a `.pth` file, so a package
  relying on one is quietly half installed.  `site.addsitedir` is the
  experiment.

  Moved up sharply on 2026-09-27, because it stopped being tidiness.
  Step 6.3 took the unpacking of wheels away from `pip` and on to us,
  and 6.3.12 named `.pth` as part of the specification we had knowingly
  not implemented.  The uncomfortable case is concrete: `coverage` ships
  `a1_coverage.pth`, which is how it measures subprocesses, so anybody
  installing `coverage` through this gets a silently half working
  install -- and `coverage` is the package this project used as its own
  example throughout Task 2.

* Step 6.9: A fetch from the real PyPI, carried over from Task 5.  It is
  the only thing that can settle Task 3's conclusion that a bootstrap
  needs `python3-pip` plus a TLS trust store, since that claim is about
  trusting the public certificate authorities and a private certificate
  tests the opposite.  It is also just `install` against the real index.

  Early rather than late, because of how much it retires at once.
  Everything measured so far has been against wheels this project built
  itself: real tag soup, a real transitive closure rather than the
  synthetic `needy` and `widget`, and TLS against the public
  authorities are all unexamined.  One opt-in test reaches all of them,
  and settles a claim that has been open since 2026-09-24.

* Step 6.10: Garbage collection.  Cull packages that have not been used
  for a while.  Not by access time: nearly every Linux filesystem
  mounts `relatime`, so `atime` updates at most once a day and not on
  ordinary reads, and `noatime` switches it off altogether, so culling
  on it would delete packages in daily use.  `install` is the only
  thing that reads the cache, so have it record use in a sidecar file
  and cull on that.

  Two kinds of litter arrive here from Step 6.4.2.  A program killed
  mid-unpack leaves an `unpacking-` directory under `pending/`, and a
  killed download leaves its own temporary directory beside it.  Neither
  is importable and neither is a correctness problem, so culling is the
  whole of the fix; the `unpacking-` prefix is there to make them
  identifiable.  A tree in `versions/` that no request record names any
  longer is the third kind, and arrives from Step 6.3.13.

* Step 6.11: Find the bootstrap, and notice when it is stale.  Python has
  a great many introspection facilities, and the direct one is
  `sys.modules["__main__"].__file__` rather than walking frames with
  `inspect`.  Read that file and look for the bootstrap.  It has to
  degrade silently for `python3 -c`, the REPL and a frozen interpreter,
  none of which have a `__file__`.

  Deciding what stale means is the harder half.  One approach: hash each
  case body and keep a table of known hashes here.  A hash in the table
  but not the current one is stale and can be reported precisely; an
  unknown hash is somebody's edited copy and should be passed over in
  silence.
  * 6.11.1 - One locator, three readers.  Three steps need the main
    program's path and its source text: this one, to find the pasted
    case; Step 6.7, to find the requirements block; and Step 6.6, which
    already uses the path alone to place `prog.altvenv`.  So one small
    thing -- the program's path and text, `None` for the REPL,
    `python3 -c` and a frozen interpreter -- and one place where those
    awkward cases are got right and tested.
  * 6.11.2 - Nobody is messaged.  There is no channel to an author at run
    time, only whoever started the program, and a staleness report is
    useful to an author and noise to a recipient who cannot act on it.
    So the author asks rather than being told: silent by default, and a
    report on request, in the same shape as `ALT_VENV_APPROVE=write`.
    That removes the question of how to reach an author entirely.
  * 6.11.3 - What to do about a stale bootstrap -- report it, refuse to
    run, or offer to rewrite the file -- is still open, but 6.11.2 makes
    reporting the obvious default.

* Step 6.12: Messages.  When should anything be said: on creating the
  directory, on each download, on a stale bootstrap?  One constraint is
  hard.  A library must never write to standard output, because the
  host program's output may be piped or parsed.  `logging` with a
  `NullHandler` lets the host decide.  One line on standard error when a
  download actually starts is still worth it, because several seconds
  of silence looks like a hang.

  A pointer to the `README.md` belongs in the failed fetch message from
  Step 6.1, and costs one `paste` line: the URL in a shared constant
  keeps the `raise` on one source line at 73 columns, where inlining it
  is 121 and wrapping it costs two, so `SHARED_LINES` would go from 7
  to 8.  Not done, because the URL depends on the repository name.

* Step 6.13: `README.md` documentation.  Two different files carry that
  name and they are for different readers, so each has its own
  sub-items below and neither is finished by writing the other.  The
  project's `README.md` is the page a stranger lands on after a program
  tells them to; `~/.alt_venv/README.md` is what somebody finds inside
  the cache directory and wonders about.
  * 6.13.1 - The project's `README.md` still describes the Scavenger
    Hunt, at lines 17 and 27, which nothing implements any more: nobody
    is sent to visit web pages and paste titles back.  What replaced it
    is that the author approves once, and the recipient is told and
    asked at most once per cache.
  * 6.13.2 - `## Security Issues of Executing Unvetted Code` is still
    marked TBD, and it is the section the whole feature rests on.  The
    sub-items of Step 6.6 are its outline, and 6.6.1 in particular: the
    claim has to be narrow to be true, because a malicious author gets
    no protection at all and a typosquat very little.
  * 6.13.3 - Habituation deserves an answer here, per 6.6.7.  The
    mitigation is real and worth stating: the question is asked once per
    cache, not once per run, and an approvals file removes it entirely.
  * 6.13.4 - The project's `README.md` should say plainly that an
    approvals file is how a guarantee is had, where a listing is only a
    notification, and that a program started by `cron` or a build has
    nobody to ask and so proceeds.
  * 6.13.5 - The cache's `~/.alt_venv/README.md` is the other file, and
    `AltVEnv.__init__` writes it from its own docstring.  What it should
    say needs discussing, and it has to describe the versioned layout of
    Step 6.3, which it predates.  Note the current behaviour: it is
    rewritten on every construction rather than only when absent, which
    makes writing a file a side effect of making an object and will
    surprise somebody.

* Step 6.14: And more.  A place holder for additional steps.

### Step 6.1: Error on a failed fetch

A failed fetch now exits with one line instead of a traceback, which
closes `0whwnn`.  Measured against a dead port, before and after:

| case        | before                    | after                     |
| ----------- | ------------------------- | ------------------------- |
| 3, `urllib` | 47 lines, traceback       | 1 line, no traceback      |
| 6, `pip`    | 10 lines, `pip failed`    | 4 lines, no traceback     |

* Only cases 3 and 12 give exactly one line.  The ten `pip` cases give
  three or four, and the extra lines are pip's own diagnostics, which
  are kept deliberately: `ERROR: Could not find a version that
  satisfies the requirement` is more specific than anything we would
  say in its place.
* The wrapper sits at the entry point rather than around each case, so
  no case body had to be re-indented; 300 lines shifting four columns
  would have pushed many past 79.  A pasted case carries the same three
  lines around its own body, which is why `SHARED_LINES` went from 4 to
  7 and every `paste` figure rose by three.  This is the first change to
  move that column, and the Task 2 and Task 5 charts carry annotations
  saying so.
* `except Exception` needed `# noqa: BLE001`.  The blind catch is the
  entire point, so it is silenced with a reason rather than narrowed to
  a tuple that would miss something.  `Exception` rather than
  `BaseException`, so a control-C still reads as a control-C.
* `test_a_truncated_wheel_fails_case_3` broke, correctly: it had been
  asserting the word `zipfile` from the traceback that this step
  removes.  It now reads the message.

### Step 6.2: Several packages in one call

`include` became `install`, which takes one requirement or a list and
spends one `pip` invocation on the set.

* The API is `install("coverage")` returning a module, and
  `install(["coverage", "pytest>=7.0,<8"])` returning one module per
  requirement in order, so `cov, pt = ...` unpacks.  A
  `(import_name, requirement)` pair covers the packages whose two names
  differ, which replaces the old `distribution` argument.
* PEP 508 already carries version constraints, so no new structure was
  needed for them.  `argv` became per-call rather than per-package,
  since one invocation serves the whole set.
* Two `@overload` stubs give the varying return type.  `Requirements` is
  spelled `list | tuple` rather than `Sequence`, because a `str` is
  itself a `Sequence[str]` and the overloads would otherwise overlap.
  Docstrings on overload stubs are legal but pointless: only the
  implementation's survives, since each `def` rebinds the name.
* The one-invocation claim is counted rather than inferred.
  `test_install_runs_pip_once_for_the_set` wraps `subprocess.run`, lets
  the genuine one do the work, and asserts exactly one call carrying
  both requirements.
* The test index now publishes `sprocket` at 1.0.0 and 2.0.0, because
  one version per project makes every constraint pass trivially.  Four
  constraints are checked against both: `sprocket<2` and
  `sprocket!=2.0.0` take 1.0.0, `sprocket>=2` takes 2.0.0, and a bare
  `sprocket` takes the newest.
* 48 tests, up from 39 at the start of the step.

### Step 6.6: Security, and who approves what

The Scavenger Hunt was designed and then discarded.  What replaced it
rests on one observation: the person who runs somebody else's program
cannot judge whether `charset-normalizer 3.3.2` belongs there, so any
question put to them is a rubber stamp.  The **author** chose the
dependencies and can tell `requests` from `reqeusts`, so the author
approves, once, and the file travels with the program.

* The author runs with `ALT_VENV_APPROVE=write` and gets
  `prog.altvenv` beside `prog.py`: one line per wheel, its name and its
  SHA-256, sorted so that a change is a small diff.  They commit it.
  `skip` neither records nor checks, for an author still deciding.
* A recipient with that file has it verified, silently, and a mismatch
  refuses before anything is unpacked.  A recipient without one is told
  what arrived and asked once, `[y/N/?]`, where `?` describes each wheel
  and does not count against the patience meant for typos.
* Nothing from the index is printed as fact.  The origin, the size and
  the digest are ours; a package's `Summary` is prefixed `it says:` and
  stripped of everything unprintable, because it is written by the same
  person who would write a typosquat's.

Four things were learned the hard way, three of them by a test failing
rather than by thinking.

1. **`open("/dev/tty", "r+")` does not work**, and would have failed
   silently.  Against a pseudoterminal it raises
   `UnsupportedOperation: File or stream is not seekable`, because
   buffered read-write text mode wants to seek and a character device
   cannot.  That exception is a subclass of `OSError`, so the
   `except OSError` meant for "there is no terminal" would have caught
   it, reported no terminal, and **never asked anybody anything,
   anywhere**, while every test that did not use a real terminal passed.
   Two handles, one for reading and one for writing.
2. **A prompt can only be tested with a pseudoterminal**, and only
   `os.login_tty` makes the slave the child's *controlling* terminal,
   which is what `/dev/tty` resolves to.  Inheriting the descriptor is
   not enough: a child started with `start_new_session` alone reports
   `No such device or address`.  `login_tty` also puts the child's own
   output on the terminal, so nothing comes back through pipes.  It runs
   in a small launcher after `exec` rather than in `preexec_fn`, which
   `ruff` flagged and which would risk deadlocking a process that has
   threads -- and this suite has a server thread.
3. **The first cut only verified on a cache miss**, so an author whose
   cache was warm could never regenerate the approvals.  The request
   record now names the wheels as well as the trees, and `write` works
   from a warm cache.  Verification still happens only when something is
   fetched, for the reason in 6.6.12.
4. **`came along` had never executed.**  Tracing child processes found
   it: no wheel the suite built had a dependency, so `pip` never pulled
   anything along and the distinction that 6.6.4 rests on was
   unreachable.  `build_wheel` takes `requires` now, the index publishes
   `needy`, which needs `widget`, and two tests watch the two kinds
   being told apart.  The same shape of gap as the `.data` tree and the
   wheel tag matcher: fixtures too simple to reach the interesting
   branch.

82 tests, up from 62 at the start of the step.  `alt_venv.py` reaches
97% with child processes traced, and 74% without, which is the
measurement being blind rather than the code being untested: every
approval test is a child program.

What this step does not cover: the project's own `README.md`, which
still describes the Scavenger Hunt and still has its security section
marked TBD.  Explaining any of this to a stranger is Step 6.13, and the
sub-items above are the outline it should follow.

### Task 6 Summary

...

## Issues

Each issue is named by a priority digit followed by the first letter of
each word of its title, lower cased, with "a", "an", "the" and "of"
dropped.  Punctuation is dropped and a hyphenated word counts once, so
*What happens with no network?* at priority 0 becomes `0whwnn`.  Two
titles that collide take a trailing digit.

The four priorities:

* **0, extreme.**  It must be avoided at all costs.  A defect that
  escapes into somebody else's program, where nobody is around to fix
  it, belongs here; so does a security hole.  Nothing else outranks
  this.
* **1, high.**  It gates the work or decides what gets built.  Nothing
  breaks, but the answer changes the direction.
* **2, medium.**  It costs time or disk, or it is a correctness problem
  with a narrow blast radius.
* **3, low.**  Worth doing, nothing turns on when.

Issues sort by name, which puts them in priority order and then
alphabetical order.  Changing a priority or a title changes the name,
and every reference must be updated in the same pass.  That fixup is
Claude's job and is not a reason to leave an issue mis-prioritised.

The statement of an issue is written by Claude and is meant to be
checkable.  `Various thoughts:` below it holds the dispositions, oldest
first, each tagged with a reviewer's first name and the date it was
written.  Claude is a reviewer like any other.  Nobody edits somebody
else's thought; one that turns out to be wrong is answered by a later
one.

### Active Issues

Being worked on right now, in priority order.  None at present.

### Pending Issues

Not yet started, in priority order.

* **Nothing identifies a cache as valid. (0nicav)**  Every case installs into
  `~/.alt_venv` with no version, platform tag or interpreter
  version in the path.  Experiment 1 installs
  `tracer.cpython-312-x86_64-linux-gnu.so`, so the same directory
  reached by a different Python, or copied to a different machine,
  would load a shared object built for something else.  This is a
  correctness bug waiting rather than a tidiness question.

  Various thoughts:
  * Wayne (2026-09-22): We'll eventually have a test suite, and we can ensure
    this issue gets covered then.  To be honest, the test suite is going to
    cover all sorts of issues.  They always do.

* **`pip._internal` is not a public API. (0pinpa)**  Six of the twelve
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

  Various thoughts:
  * Wayne (2026-09-22): In general, this seems quite bad.  I'd very much like
    to avoid using `pip._internal`.  I'd very much dislike using this interface
    since the bootstrap code in theory could be replicated a large number of
    places.  I will point out that the reason why we have 10 bootstrap code
    candidates gives us some flexibility dealing with this issue.

* **An already-importable package is installed anyway. (2apiia)**  All
  twelve cases ask whether the package is on disk at their own target,
  never whether it is already importable.  With `coverage` present in an
  active virtual environment, a case spends 1.42 s and 1.8 MB
  installing a copy it will not use, where a leading `try: import`
  costs 0.10 s.  Cheap to fix; deliberately not fixed yet.

  Various thoughts:
  * Wayne (2026-09-22): This can be dealt with much later since it is easy to
    fix.
  * Claude (2026-09-24): Fixed in the second stage.  `AltVEnv.install`
    asks `contains` first and skips the install when the package is already in
    the cache.  The twelve cases are unchanged, so the measurement in Task 2
    still shows the defect.
  * Claude (2026-09-25): A candidate for `### Closed Issues`, on the same
    terms as `0whwnn`: fixed where it ships, unfixed in the pasted bootstrap.
    The two should close together or not at all.  Wayne's call.
  * Claude (2026-09-26): The thought above no longer holds.  `0whwnn`
    closed on its own, because Step 6.1 fixed the pasted half as well,
    and this issue's pasted half is still unfixed: all twelve cases test
    a path on disk rather than asking whether the package imports.  So
    it stays open on its own merits rather than as `0whwnn`'s twin.  The
    fix is now cheaper than it was, since Step 6.3 has to rework the
    same guard for the versioned cache.

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
  the decision criterion under Initial Thoughts: if the user can run
  `pip install pip-run`, this project is an exercise.  Requiring
  `pip` sharpens that rather than blunting it, since it assumes the
  very tool that makes `pip-run` installable.  The answer is that the
  recipient runs no commands at all where `pip-run` costs them one,
  and that is an argument about what the product is.  No survey of
  distributions will confirm or refute it.

  Various thoughts:
  * Wayne (2026-09-22): It would be nice to test on Windows and MacOS.
  * Wayne (2026-09-22): I know people who have these machines and would be glad
    to help.  Until then, the answer is currently unknown.

* **How should required packages be declared? (2hsrpbd)**  Every case has
  `PACKAGE = "coverage"` written into it.  Reusing the PEP 723
  `# /// script` block instead would make the same program work under
  `uv run` for free, and would let one bootstrap serve a list of
  packages rather than one.

  Various thoughts:
  * Wayne (2026-09-22): Sounds like it is worth doing.  The question is when?

* **Where should the cache directory live? (2wscdl)**  `~/.cache/<program>/`
  per the XDG spec, or beside the program, or the `~/.alt_venv`
  that Experiment 1 assumed without examining?  This interacts with
  `0nicav`: whatever the location, the name has to carry the
  interpreter and platform.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.

* **The wheel tag matcher is a five-line stand-in. (2wtmifs)**  Cases
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
  stub's job is to fetch `alt_venv`, which is pure Python and
  ships as `py3-none-any`, so no tag matching is needed for it at
  all; the matcher exists only because Experiment 1 fetched
  `coverage`, which has compiled wheels.  The 49 pasted lines the
  table charges the pure standard library path are therefore priced
  against the wrong package, and that number should be remeasured
  before it is used to justify anything.

  Various thoughts:
  * Wayne (2026-09-22): Let's revisit this issue after Experiment 2.
  * Claude (2026-09-26): Measured, by tracing child processes; see Step
    6.5.  The matcher's platform branch,
    `or (machine in name and "linux" in name and sys.platform ==
    "linux")`, has **never executed** in any test, and neither has
    `raise RuntimeError("no compatible wheel found")`.  So the worry was
    not merely that the matcher is a stand-in: the half of it that would
    pick a compiled wheel has never been run at all, and the tests have
    only ever exercised the `py3-none-any` path.  Reaching it needs a
    platform tagged wheel in the test index, which is Step 6.5.11.
    The complete run confirms it: with all twelve cases exercised, ten
    are covered completely and these seven lines are the only dead code
    in any of them.
  * Claude (2026-09-26): And now exercised, by Step 6.5.11, which
    publishes a wheel wearing this interpreter's compiled tag alongside
    the pure one.  The matcher **behaved correctly**: it preferred the
    tagged wheel, moved its `.data/purelib` member up beside the module,
    and refused a `cp312-cp312-win_amd64` wheel with
    `no compatible wheel found` rather than installing it.  So the
    predicted failure did not appear for any shape a Linux machine can
    build.  What remains unverified is narrower than the issue as
    written: musl against glibc, which needs an Alpine machine, and
    whether a genuinely compiled wheel imports, which a pure Python
    wheel wearing a compiled name cannot show.  Wayne's call whether
    that is still a priority 2.

* **`.pth` files are installed but never executed. (3pfaibne)**  Every case
  writes coverage's `a1_coverage.pth`, its hook for measuring
  subprocesses, and no case runs it, because only `site.addsitedir()`
  executes `.pth` files and every case uses `sys.path.insert`.  Any
  package relying on a `.pth` is quietly half-installed.  Switching
  to `site.addsitedir()` is the obvious experiment.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.

* **Reviewer thoughts have two formats. (3rthtf)**  Task 4 propagated the
  reviewer thought rules into `claude_notes.md`, and the two files came out
  disagreeing about the shape.  `claude_notes.md` puts reviewer thoughts
  inside the `{ ... }` braces it uses for annotating a closed task, listing
  the dating, naming and ordering rules as sub-points of the annotation
  rules.  `LOGBOOK.md` instead uses a `Various thoughts:` label followed by
  plain bullets, describes it that way in its own `## Issues` preamble, and
  uses it in fourteen places.  The rules themselves agree; only the syntax
  differs.  Whichever file is wrong, the other is the specification, so one
  of the two has to move.

  Various thoughts:
  * Claude (2026-09-25): `LOGBOOK.md` has the better of it.  Braces are for
    annotating settled text, and a multi-reviewer thread that grows over
    months is a discussion rather than an annotation; wrapping fourteen of
    them in braces would also bury the reviewer names one level deeper.  But
    `claude_notes.md` is the general write-up, in another repository and in
    Wayne's voice, so this is a proposal rather than an edit.

* **The venv executable directory is hard-coded. (3vedih)**  Cases
  4 and 11 reach into `root / "bin"` at `bootstrap.py:296`, `400` and
  `407`.  On Windows a virtual environment puts its executables in
  `Scripts`, so the pip reclaim would silently delete nothing and
  case 11's subprocess would not find an interpreter at all.  The
  inconsistency is inside a single case body: the same code checks
  `os.name != "nt"` when choosing symlinks, and asks `sysconfig` for
  the platform's site-packages, then hard-codes `bin`.  Nothing
  breaks on Linux, which is the whole of the current scope.

### Rejected Issues

Approaches that were considered and declined, recorded so that they
are not proposed again.

* **Vendor the packages into the repository. (3vpir)**  Needs no
  network, but it bloats the repository and breaks on compiled
  extensions -- the same `.so` problem as `0nicav`.  Declined
  2026-09-21, before Experiment 1; Experiment 1 then confirmed the
  `.so` problem is real by installing
  `tracer.cpython-312-x86_64-linux-gnu.so`.

### Closed Issues

Resolved, most recent first, each dated.  They are purged once
nobody wants to read them any more, after every reference to them
is gone.

* **What happens with no network? (0whwnn)**
  (CLOSED 2026-09-26)  Undefined in all twelve
  cases.  Should the bootstrap fail, or fall back to whatever the
  system already provides?

  Various thoughts:
  * Wayne (2026-09-22): We are going to die without the network to fetch the
    package. We need to at least let the user know that we died because we
    could not get the package.
  * Claude (2026-09-24): The second stage does this now.
    `AltVEnv.install` raises `RuntimeError` carrying pip's own standard
    error, so a caller is told why rather than left with an import failure.
    The twelve bootstrap cases still do not, and they are the half that runs on
    a stranger's machine.
  * Claude (2026-09-25): A candidate for `### Closed Issues`, since the second
    stage is the part that ships.  Left pending because the bootstrap half is
    the half that reaches a stranger's machine, and closing the issue would
    stop anyone looking at it again.  Wayne's call.
  * Claude (2026-09-26): Closed.  Step 6.1 of Task 6 wrapped the fetch
    so that a failed one exits with a single line naming the package and
    the underlying error, and no traceback.  Cases 3 and 12 give exactly
    one line; the ten `pip` cases give three or four, the extra lines
    being pip's own diagnostics, which are kept because they are more
    specific than ours.  `test_a_failed_fetch_is_one_line` holds it.
    The fall back alternative was declined by Wayne on 2026-09-22.

* **The cache check tests for a directory. (0cctfd)**
  (CLOSED 2026-09-25)  Every one of the
  twelve cases guards its install with
  `if not (target / PACKAGE).is_dir()`.  A distribution that installs
  as a single module puts a `.py` file there, not a directory, so the
  guard is false on every run and the install is repeated forever.
  `alt_venv` is exactly such a distribution, so the defect
  applies to the package this project ships.

  Two things follow.  Every case re-downloads on every run, which the
  Task 5 chart shows as warm times that match cold times.  And case 11
  does not merely repeat work, it fails: it installs with the venv's
  own `pip`, deletes that `pip`, and then on the second run tries to
  install with it again, exiting non-zero three times out of three.
  The Task 2 chart missed all of this because `coverage` installs as a
  directory, which made the guard behave correctly by accident.

  A possible solution is to ask whether the package imports rather
  than whether a path exists, which is also what `2apiia` asks for; a
  narrower one is to test for the module file as well as the
  directory.  The two issues are distinct.  `2apiia` is about skipping
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
