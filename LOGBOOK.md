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

* [PEP 723](https://peps.python.org/pep-0723/) is final and now marked a
  historical document; its canonical text is maintained by the PyPA as
  the [inline script
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

    Qualified on 2026-09-27 by Step 6.7.10, which does compare one
    version: the running interpreter's against a program's declared
    `requires-python`, and only when that is a single `>=X.Y[.Z]` clause.
    This is not the case above.  A package version is chosen from many
    candidates, where being too permissive installs a release candidate
    nobody wanted; an interpreter version is a fact about the machine,
    where being too permissive merely fails to warn.  The rule still
    holds where it was aimed: no parser decides what to install.
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
    Step 6.11.
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
  * 6.4.2 - Carried to Step 6.11 rather than left open here: a program
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
  * 6.5.13 - The quick run is one case, from 2026-09-27.  Six tests loop
    over `cases()`, so the four `FAST_CASES` were costing 42.5 s of a
    91.5 s run; measured with `unittest --durations`, which also named
    `test_an_untrusted_certificate_is_refused` at 19.8 s against 5.3 s
    for the trusted one, unexplained and worth a look, since retrying a
    rejected certificate is wrong on its own terms.  `FAST_CASES` is now
    case 7 alone and the suite runs in 61 s.

    Case 7 because this project is not shipping a virtual environment,
    which leaves the shortest paste, and four cases tie there at sixteen
    lines.  Cases 6 and 9 run `pip` in process, which leaves 451 of its
    modules in `sys.modules` and three handlers on the root logger of
    somebody else's program; case 10 is 7 plus `--no-compile`, worth
    60 KB.  Case 7 is what is left, and is the likeliest product.  The
    other eleven, including the no-`pip` case 3 that is the whole point
    of the exercise, run under `ALT_VENV_TEST=COMPLETE`, which is what
    the end of a task gets.

    One consequence to expect rather than be alarmed by: `bootstrap.py`
    reads 39% traced instead of 75%, because eleven case bodies no longer
    run in the quick suite.  It is not a regression, and `COMPLETE` is
    where those lines are covered now.
  * 6.5.14 - Sixth traced round, 2026-09-27, after Step 6.7 landed the
    locator, the parser and `install()`.  118 tests, 524 s with children
    traced, 170 child processes folded in; `alt_venv.py` at 98% and
    `alt_venv_test.py` at 99%.  Five unexercised lines, and chasing them
    was worth it again:

    * **A real defect.** `approve` returning `None` was never reached, and
      the reason it mattered was one line up its call chain: with
      `ALT_VENV_APPROVE=write` and a program that has no file, `gate`
      printed `approvals written to None`, announcing a file it had not
      written.  It now says there is nowhere to write one.
    * **Three guards that were simply untested**, now tested: `verify`
      with no approvals file, which `gate` cannot reach because it looks
      first, so the guard is for anyone calling the public method;
      a cache record naming a different request, which means an edited
      file or a digest collision and is not evidence either way; and
      `consent` reading end of file from the terminal, where asking again
      would spend the patience meant for typos on a terminal that has
      gone away.
    * **One line that should stay uncovered.** The `__file__ is None` arm
      of `repair_module_layout`, for a frozen interpreter: `trace` cannot
      follow a frame whose `__file__` is false, so the tracer could not
      see that line run even if it did.

    Found by hand in the same sitting, while the tracer was busy, which
    is worth recording because no coverage tool would have found it: a
    `# -*- coding: latin-1 -*-` program is perfectly legal Python and the
    interpreter honours the cookie, but `Path.read_text(encoding="utf-8")`
    refused it, so `main_source` returned `None` and the program declared
    nothing at all, in silence.  `tokenize.open` is the standard library's
    own answer to the question and honours a cookie and a byte order mark
    alike, so a program the interpreter can run is now a program we can
    read.

  * 6.5.15 - Seventh traced round, 2026-09-27, everything turned up at
    once: `ALT_VENV_TEST=COMPLETE`, `ALT_VENV_PYPI=1` and `--children`.
    Nothing new in the product -- `alt_venv.py` still has exactly one
    uncovered line, the frozen interpreter arm, and `bootstrap.py`'s 98
    uncovered lines are precisely the command line measurement harness,
    so all twelve pasted cases remain covered.

    The instrument, though, has a defect this run exposed and no `FAST`
    run could: **the child tracer stops ignoring the standard library
    inside a virtual environment.**  Both tracers are built with
    `ignoredirs=[sys.prefix, sys.exec_prefix]`, which is correct for an
    ordinary interpreter.  In a virtual environment `sys.prefix` is the
    environment and the standard library is under `sys.base_prefix`;
    measured 2026-09-27, `/usr/lib/python3.12/pathlib.py` does not start
    with the venv's `sys.prefix`.  So the six venv cases traced the whole
    standard library, which is why this report carries dozens of
    `/usr/lib/python3.12` rows that earlier reports did not.

    Consequences are noise and time rather than wrong numbers -- each
    file's percentage is still its own -- but tracing every line of
    `typing`, `tarfile` and `ssl` in six children is not free.  The fix
    is to add `sys.base_prefix` and `sys.base_exec_prefix` to both
    `ignoredirs` lists, in `alt_venv_coverage.py` and in
    `trace_hook/sitecustomize.py`.  Left unapplied for Wayne to call,
    since it changes what the instrument considers ours.

    Two smaller observations, neither a defect.  In
    `test_a_racing_unpack_is_recovered` the patched `Path.rename` never
    falls through to the genuine one, so the guard against patching too
    broadly is itself unexercised; the test wheel has no `.data` member
    to move.  And the `sys.path` cleanup helper never finds an entry to
    remove, because the tests that use it install in children.
  * 6.5.16 - Eighth traced round, overnight 2026-09-29 into the 30th, at
    Wayne's instruction to run everything and keep fixing until done:
    `ALT_VENV_TEST=COMPLETE`, `ALT_VENV_PYPI=1`, `--children`, and from
    the fourth pass `ALT_VENV_REPORT=1` as well.  Five traced passes of
    roughly twenty-five minutes each.  **`bootstrap.py` reached 100%**,
    `alt_venv.py` and `alt_venv_test.py` are at 99%, and 184 tests pass.

    What each pass found:

    * **First**: `alt_venv.py` had fallen to 97%, all of it the new
      garbage collection: seven `except OSError: continue` arms plus the
      confirmation's empty read.  The lesson for writing them was that
      **deterministic beats racy** -- a dangling symlink makes `stat`
      raise on demand, a directory named `something.json` makes `unlink`
      refuse, and `chmod 0o500` on `pending/` makes removal fail while
      the listing still works.  Only two arms needed `unittest.mock`:
      `Path.touch`, because `utime` succeeds for a file's owner whatever
      its mode, and `Path.lstat` in `directory_size`.
    * **Second**: 99% again, and `bootstrap.py` exposed as the real gap
      at 75% -- 98 lines, the measurement harness that runs only when the
      file is invoked with no arguments.
    * **Third**: three of its four functions are pure and quick, so they
      now have tests, and one of them is the test that was missing on
      2026-09-29: `test_the_recorded_table_matches_the_measurement`
      parses the table out of the module docstring and compares every
      counted column against `measure_source`.  Had it existed, the
      `paste` column being three lines short in every row since
      `SHARED_LINES` changed would have failed immediately instead of
      surviving for days.  85%.
    * **Fourth**: `run_tests` covered by an opt-in `ReportTest` behind
      `ALT_VENV_REPORT`, which runs the real report in 105 s, plus the
      usage branch, which needs neither network nor measurement.  99%,
      three lines left.
    * **Fifth**: those three were the path that names a case which
      *failed* during the report -- the report's most useful output.
      Covered by patching `subprocess.run` so all twelve cases fail
      instantly, which costs milliseconds where a broken index would
      cost minutes.  **100%.**

    One test got stronger rather than merely covered.  The tracer showed
    that in `test_unpack_survives_losing_the_race` the patched
    `Path.rename` never fell through to the genuine one, so its comment
    -- "only the staging rename fails; the `.data` moves must not" -- was
    a hope rather than a claim: the test wheel had no `.data` member to
    move.  It has one now, and the test records which renames were
    allowed through and asserts the member was among them.

    What remains uncovered, and why each one stays:

    * `alt_venv.py` line 495, the frozen interpreter arm of
      `repair_module_layout`.  `trace` decides what to follow by reading
      `frame.f_globals["__file__"]`, so a frame whose `__file__` is
      `None` is invisible to it: the line could execute and still be
      reported as unexecuted.  Unfixable from here.
    * Eleven lines of `alt_venv_test.py`, all configuration rather than
      code: `platform_tag`'s non-CPython branch, `cases()` returning
      `FAST_CASES` (covered by every fast run instead of this one), the
      openssl-missing skip, the server's unexpected-error handler, the
      two exits of the pty read loop where only one can be taken, the
      `sys.path` cleanup helper's loop body, and the file's own
      `__main__` entry.

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

  * 6.6.11 - The project's `README.md` is Step 6.10's, not this step's.
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

  * 6.6.15 - A fourth answer, built 2026-09-29: the question is now
    `[y/n/a/?]`, where `a` means do not ask again.  Wayne's reasoning is
    the point of the whole feature, so it belongs here: nearly everybody
    will approve, and what the question is **for** is that a person
    understands packages are being downloaded -- not that they are nagged
    about it forever.  Answering `a` writes `FOREVER_APPROVE` in the
    cache, whose contents say what it means and that deleting it restores
    the question, and the answer prints that path, because one keystroke
    making a permanent decision deserves a visible way back.

    The marker lives in the cache rather than beside the program, because
    it records a decision by whoever uses the machine and not by any
    author; that also gives it the lifetime the question already had,
    which is once per cache.

    **The invariant that makes it safe:** the marker is checked *after*
    the approvals, so it silences the question and can never hide a wheel
    that fails `verify`.  A wheel that does not match what an author
    approved is a different matter from a person who would rather not be
    asked.  Three tests, one of them exactly that case: approve, corrupt
    the record, set the marker, fetch cold, and the refusal still
    happens.

    Reworked the same day, at Wayne's suggestion, and the reasoning is
    worth keeping: **the prompt spells the answers out** rather than
    abbreviating them, because a person seeing it for the first time
    should not have to guess what a letter means:

        2 requested, 3 to install into /home/you/.alt_venv;
        go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation]

    Case no longer matters, since somebody with caps lock on has not made
    a mistake.  And `a` now **asks twice**: `Really never ask again?
    [y=>Yes/n=>No]`, because it is the only answer that outlives the run.
    Declining the confirmation returns to the question rather than
    cancelling the install -- not wanting a thing for ever is not the
    same as not wanting it now -- and counts as an attempt so the pair
    cannot loop indefinitely.

    The second `y` prints where the marker is, that packages will be
    downloaded silently from now on, and the removal command for the
    platform it is running on, with `os.name` choosing between
    `rm -rf` and `rmdir /s /q`.  The words *ALWAYS safe to delete* are
    Wayne's, and they are right: the directory is a cache, and losing it
    costs a download.

    Wayne also spotted that `consent`'s docstring still described the old
    `[y/N/?]` prompt.  The test file now holds the prompt and the
    confirmation as `PROMPT` and `CONFIRM`, one place each, so the next
    rewording fails in one obvious spot rather than in seven.

    This replaces nothing: `ALT_VENV_APPROVE` stays, because `write` is
    how an author generates the approvals file at all and `skip` is for
    an author still deciding.  Wayne leant against the variable while
    designing this, and the reason to keep it is that it is the author's
    tool and never in a recipient's way.

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

* Step 6.7: Deal with PEP 723 issues, which is `2hsrpbd`.

  This step covers everything the standard asks of a program that
  declares its own requirements: finding the block, reading it, and
  acting on what it says.  The substance is that the calling script's
  `# /// script` block replaces a package name written into the
  bootstrap.  It builds on Step 6.2, and it makes the same file work
  under `uv run` for nothing, which is worth a great deal given that
  prior art is why this project has to justify itself at all.

  First of what remains, on 2026-09-27, because it is the largest change
  to what the product is: the program declares what it needs instead of
  somebody writing an `install` call by hand.  It also builds the
  locator that Step 6.12 needs, so doing it first hands that step its
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
  * 6.7.4 - The floor is stated, and it is as low as the code allows.
    **Superseded by 6.7.7 later the same day, which raised it to
    `>=3.11` for `tomllib`.**  What was decided here, and still holds
    for the language itself: `>=3.10`, because annotations such as
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

  * 6.7.5 - `alt_venv.py` carries a PEP 723 block of its own, added
    2026-09-27, so that this project eats its own cooking:
    `requires-python = ">=3.10"` and `dependencies = []`, the second
    empty on purpose, since a project about fetching packages that are
    not preinstalled has none of its own.  Verified with the regex PEP
    723 itself specifies plus `tomllib`, which reads back
    `{'requires-python': '>=3.10', 'dependencies': []}`, and the module
    docstring survives having comments in front of it.

    Two honest limits.  Nothing reads it: a tool such as `uv` reads the
    block of the script it is running, and this is a library that is
    never `__main__`, so no tool and not even our own code will consult
    it.  And the floor is now written twice, here and in `FLOOR`.  Both
    close the same way, and it is the real dogfooding: once this step can
    parse a block, `build_wheel` should take `Requires-Python` from
    `alt_venv.py`'s own block, so that our metadata comes from our parser
    reading our file, with a consequence if the parser breaks.  Only
    `alt_venv.py` gets a block; `bootstrap.py` must keep a literal
    package name, because something has to fetch this file before
    anything can parse anything.

  * 6.7.6 - The locator exists, built 2026-09-27: `main_path` returns
    the running program's file and `main_source` returns that file with
    its text, each `None` when there is nothing to find.  This is
    6.12.1's primitive, and `approvals` was rewritten on to it, so the
    `__main__` handling now lives in one place.  Ten tests, each in a
    child process, because this suite's own `__main__` is `unittest`.

    Writing the tests found a defect that reasoning had missed.  A
    `__file__` that is present is not necessarily a file: measured
    2026-09-27, `python3 - < prog.py` sets it to the literal `<stdin>`,
    and `exec` of a string and a frozen interpreter give `<string>` and
    `<frozen ...>`.  Resolving any of those yields a believable path in
    the working directory that names nothing, so the first version would
    have looked for approvals in `./<stdin>.altvenv` -- in whatever
    directory the reader happened to be standing.  The locator now
    insists the path exist, which rejects those three and a program
    deleted from under itself as well.

    Measured while at it, so that nobody has to guess later:
    `python3 -m prog` does set `__file__`, a relative invocation resolves
    to an absolute path, and `-OO` leaves the comments in the file
    although it has stripped the docstrings from the module, which is the
    whole reason 6.7.2 reads the source.

    Amended the same day: the text is read with `tokenize.open` rather
    than `Path.read_text`, so that a program declaring a coding cookie is
    read rather than silently ignored.  See 6.5.14.

  * 6.7.7 - Got the TOML parser working.  6.7.3 said `tomllib` raises
    the floor to 3.11 and 6.7.4 then set the floor at `>=3.10`, and both
    could not hold once the import was real.  The options:

    * Hand-parse the two keys wanted -- `requires-python`, a string, and
      `dependencies`, a list of strings -- and depend on no TOML reader
      at all.  Rejected: a hand parser is a second implementation of
      somebody else's specification, which is the mistake 6.7.1 declined
      to make when it chose PEP 723 over a bespoke format.
    * Import `tomllib` lazily, so 3.10 keeps working until a program
      actually has a block.  Rejected: it buys one Python version at the
      price of two code paths and a failure that appears late.
    * Import `tomllib` at the top like any other standard library module
      and raise the floor to `>=3.11`.  **Chosen 2026-09-27**, because
      3.11 has been out four years.

    `script_metadata` followed on 2026-09-27: source text in, what the
    block declared out, `None` when there is no `script` block, and
    `ValueError` on two blocks or on TOML that will not parse.  Twelve
    tests, none needing a child process or the disk.  The regex is PEP
    723's own, copied and not rewritten, because a block we fail to
    recognise is a block some other tool accepts.  Two measured
    consequences, shared by any tool using it:

    * An empty block reads as **no** block, the pattern wanting at least
      one commented line between the fences.  Harmless, and the test
      expecting `{}` was the thing that was wrong.
    * A block of another type immediately above a `script` block
      **hides** it, silently, because `content` matches commented lines
      greedily straight through the closing fence.  One blank line
      between them is the cure.

    The second also defeats the duplicate check the PEP requires, two
    adjacent blocks matching as one, so `FENCE` counts `# /// script`
    openers first and names the real mistake.

    The project gained `ruff.toml` and `mypy.ini`, both saying 3.11,
    because with no configuration `ruff` assumed 3.10, disbelieved that
    `tomllib` is standard library and sorted its import into the third
    party block.
  * 6.7.8 - The API is `install()` with no arguments, decided and built
    2026-09-27.  It reads the program's block, fetches what is declared,
    puts the cache on `sys.path` and **imports nothing**; the program's
    own `import` statements, written below the bootstrap, do that.  A
    program with no file, no block, or a block declaring nothing gets
    silence, because every test that merely constructs an `AltVEnv` is
    such a program.  A declaration that will not parse is reported,
    since that is not the same as no declaration.

    Putting the fetch in `__init__` was considered and declined.  It
    reads well -- construct the object and start importing -- but
    `AltVEnv().install()` is one pasted line either way, so the whole
    gain is invisible in the only unit that matters, and the cost is
    real: `contains` asks what is cached, Steps 6.11 and 6.12 will want
    an object that only looks, and `bootstrap.py` constructs one to
    repair a module layout.  A constructor that fetches, prompts on
    `/dev/tty` and mutates `sys.path` also leaves a half-built object
    behind when it raises.

    Importing nothing is what makes the two naming systems stop
    colliding, which is the unexpected prize.  A PEP 508 requirement
    names a distribution, an `import` statement names a module, and
    `python-dateutil` is not `dateutil`; the pair form of `install`
    exists only because it returns modules and had to guess.  The
    declared path never guesses, so the pair form is now the escape
    hatch rather than the answer.

    `install(requirements)` stays, for requirements not known until run
    time -- the database driver named in a configuration file, which a
    static block cannot express.  Both forms share `provide`, split out
    of `install` for the purpose: fetch, verify, unpack, `sys.path`, no
    imports.  `declared` is public too, and answers what would be
    fetched without fetching it.

    Eleven tests, all running a real program in its own directory: a
    plain declaration, a version constraint, `python-gadget` imported as
    `gadgetlib`, several in one `pip` run, no block, an empty
    `dependencies`, unparseable TOML, a `dependencies` of integers,
    `declared` on its own, `python3 -OO`, and `python3 -c`.

    Measured on a realistic program, because linter complaints land on
    the author and are the friction they will actually feel: with the
    imports below the bootstrap, `ruff` reports **no** E402, which was
    the objection to the whole shape and it was wrong.  It does report
    `BLE001` for the blind `except` the paste itself carries, so the
    paste must carry `# noqa: BLE001` too.  `mypy` cannot see a package
    that will not exist until run time and says
    `Cannot find implementation or library stub for module named ...`;
    `# type: ignore[import-not-found]` on each import is the narrow fix
    and `--ignore-missing-imports` the blunt one, which was measured to
    swallow a misspelt module name as well.  In practice the author has
    the packages installed and sees none of this.  All of it belongs in
    Step 6.10.
  * 6.7.9 - The dogfooding loop is closed, 2026-09-27.  `FLOOR` is no
    longer a literal: `floor()` reads `requires-python` out of
    `alt_venv.py`'s own block with our own parser, so the wheels' claim
    comes from our file through our code, and breaking either one fails
    the suite instead of shipping a wrong `Requires-Python`.

    Configuration cannot be derived that way, so `ruff.toml` and
    `mypy.ini` still say 3.11 by hand, and
    `test_the_linters_agree_with_the_block` is what stops the three
    drifting apart.  `bootstrap.py`'s epilogue now calls
    `AltVEnv().install()` rather than only constructing one, so all
    twelve shapes walk the declared path; that file has no block, so
    nothing is fetched.
  * 6.7.10 - A declared `requires-python` **is** enforced, decided and
    built 2026-09-27.  Two declarations share a name and only one was
    ever in question: a wheel's `Requires-Python`, written by whoever
    built the package, is `pip`'s to enforce and it does; the PEP 723
    `requires-python` in the program's own block was read by nobody.

    Ignoring it was the first recommendation and Wayne was not thrilled,
    which was the right instinct.  The options:

    * Ignore it, as `uv` enforces it anyway for anybody who runs the
      program that way.  Rejected: the program that lies about its floor
      dies later on a `SyntaxError` in a module the person has never
      heard of, and we had the information to say so.
    * Compare it properly, which means PEP 440 and so either a
      reimplementation or a dependency.  Rejected: 6.3.3, and a
      dependency on `packaging` to check a version is a bootstrap cycle.
    * Understand the single `>=X.Y[.Z]` clause and **nothing** else,
      refusing to interpret the rest.  **Chosen.**

    The distinction 6.3.3 was protecting is intact, and the reason is
    worth stating plainly: every mistake this whitelist can make is in
    the permissive direction.  A pre-release such as 3.11.0a1 does not
    satisfy `>=3.11` under PEP 440 but compares equal on
    `sys.version_info`, so an alpha is let through; nothing legitimate is
    ever refused.  6.3.3's tuple comparison had the opposite failure --
    it would have *installed* a release candidate nobody asked for -- and
    that asymmetry is what makes one safe and the other not.

    So `python_floor` returns a tuple or `None`, `None` meaning "no
    opinion, ask `pip` or `uv`", and `check_python` runs before anything
    is fetched.  `declaration` was split out of `declared` so the block
    is read once and the two readers cannot disagree.  `requires-python`
    and `dependencies` of the wrong type now raise `TypeError` rather
    than `ValueError`, which `ruff` asked for and which reads better.
    Nine tests: the whitelist's four shapes, nine specifiers it declines,
    an unmet floor stopping an install cold, a met one passing in
    silence, `>=3.9,<4` installing unjudged, a numeric floor refused, and
    the in-process form.
  * 6.7.11 - Tests, done: present, absent, malformed and duplicated
    blocks live in `MetadataTest` (13, on strings); the declared path's
    eleven live in `InstallTest` (real programs, own directories),
    `-OO` and `python3 -c` among them.  Whole suite 117 tests in 67 s.

* Step 6.8: Moved to Step 6.17 on 2026-10-01, so that the release to
  the real PyPI sits near the end of the list, where it belongs.

* Step 6.9: `.pth` files, which is `3pfaibne`.  `install` uses
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

* Step 6.10: `README.md` documentation.  Two different files carry that
  name and they are for different readers, so each has its own
  sub-items below and neither is finished by writing the other.  The
  project's `README.md` is the page a stranger lands on after a program
  tells them to; `~/.alt_venv/README.md` is what somebody finds inside
  the cache directory and wonders about.
  * 6.10.6 - Drafted 2026-09-28, both files, and Wayne's to edit: the
    prose is the product's face and a draft from Claude is a starting
    point rather than an answer.  `hg revert` undoes it in one command.

    The project's `README.md` keeps the opening -- a person arrives here
    annoyed, and the author chose this over a virtual environment -- and
    replaces the Scavenger Hunt with what the code does: a **What Just
    Happened** section showing the real listing and the real
    `[y/N/?]` question, a **Security** section written from 6.6's
    sub-items as two lists, what it protects against and what it plainly
    does not, and a **For Program Authors** section carrying the PEP 723
    shape with its `# noqa: BLE001` and `# type: ignore` comments
    explained.  Everything in it is something this project measured.

    The cache's `README.md` now describes the versioned layout it
    predated: `versions/`, `wheels/`, `requests/` and `pending/`, one
    line each, with the litter note for `pending/`.  And it is written
    **only when it would change**, which retires 6.10.5's complaint that
    making an object wrote a file; a stale copy is still replaced, so
    editing the docstring still reaches an existing cache.  Four tests.
  * 6.10.7 - Writing this step out of order paid for itself, twice over,
    and that is worth recording rather than apologising for.  Wayne
    rewrote the project's `README.md` from scratch on 2026-09-29 and we
    went through it line by line, and **describing the behaviour to a
    stranger is what exposed the decisions**.  Four things came out of it
    that specification alone had not produced:

    * The consent prompt gained a fourth answer, `[y/n/a/?]`, where `a`
      means approve from now on and leaves a marker in the cache.  Wayne
      wanted a reader to understand that code is being downloaded without
      being nagged about it forever; the letter and the marker file did
      not exist as an idea until the prompt had to be explained.
    * Garbage collection got designed, in 6.11.1, because *nothing ages
      out* was an uncomfortable sentence to write down.
    * `AltVEnv` never needs `sudo` -- which had to be checked before it
      could be claimed, and which contradicted the `apt install` line two
      paragraphs above it until a qualifier was added.
    * What a person sees when `pip` is missing got measured, because
      Wayne asked.  Python's own `No module named pip` is precise and our
      line beneath it is noise; see 6.13.
    * A definition of *wheel*, because most Python users have never
      needed the word, and the README used it to make its central claim.

    The general lesson, which the rest of Task 6 should expect: the steps
    still open are precisely the ones the `README.md` could not describe
    honestly.  Describing a thing is a cheap way to find out whether it
    exists.

  * 6.10.8 - What the project's `README.md` still lacks, as of 2026-09-29,
    so that the list is somewhere other than a conversation.  Grouped by
    who needs it, and the first group is the one that would embarrass us.

    **Missing and depended upon by a decision not yet made:**

    * **The download prompt.**  What is shown, that `?` lists the
      packages, that the default is no, that it is asked once per cache
      rather than once per run, and that a program with no terminal --
      `cron`, a build, a double clicked launcher -- proceeds without
      asking.  Waiting on the `[y/n/a/?]` letter and its marker file.
    * **The security section itself.**  Wayne's rewrite dropped the old
      `## Security Issues of Executing Unvetted Code` heading along with
      the Scavenger Hunt, so the page currently says **nothing** about
      the subject the whole feature rests on.  6.10.2 and 6.10.4 are its
      outline: what an approvals file guarantees, what a listing merely
      notifies, and the two things the mechanism cannot do -- a malicious
      author and a typosquat the author fell for.

    **Missing and ready to write:**

    * **The real bootstrap**, copy and pasteable.  The layout sketch at
      the top of the file is schematic and says so in a comment; an
      author cannot use the page as it stands.  This is the single most
      important omission.
    * **`uv` compatibility.**  The same file runs under `uv run` with the
      bootstrap never executing, which is the strongest argument for
      having used the standard block.  One sentence.
    * **The author's side of approvals**: run once with the writer, commit
      the `.altvenv` file beside the program, and recipients get those
      exact wheels or a refusal.
    * **Version constraints.**  `"requests<3"` works because it is a PEP
      508 requirement handed to `pip`, and two programs wanting different
      versions each get their own directory.
    * **`PIP_INDEX_URL`**, for a private index or a mirror, which is also
      how every test in this project fetches.
    * **What the messages mean**: the failed fetch, the Python floor
      refusal, and what happens with no network on a warm cache.
    * **Status and scope**: experimental; measured on Linux with CPython
      3.12; Windows, macOS and PyPy **untested**, which matters now that
      the page speaks to Windows readers; concurrent use tested; MIT-0;
      and a pointer here, to `LOGBOOK.md`, for anybody wanting the
      reasoning rather than the instructions.
    * **Where to report a problem**, once there is somewhere to report it.

  * 6.10.9 - Requirement forms, measured 2026-09-30 before being
    documented, because the `README.md` was about to claim that anything
    `pip` understands works.  Against the local index, all of these
    resolve correctly through `install()`: `sprocket>=1.0,<2`,
    `sprocket~=1.0.0`, `sprocket!=2.0.0`, `sprocket===1.0.0`,
    `sprocket>1.0.0`, `widget[extra]`, and environment markers both true
    and false.  Three tests pin the constraint forms and the two marker
    outcomes.

    **A defect fell out of the false marker.**
    `"widget; sys_platform == 'win32'"` on Linux printed
    `1 requested, 0 downloaded into ...` followed by an empty list, and on
    a terminal it would have **asked a person whether to install no
    packages at all**.  Nothing arriving is a real answer and not a
    failure -- a platform conditional dependency is a normal thing to
    write -- so `install` now returns quietly when the download brings
    back nothing.  Two tests: the excluded case says nothing whatever,
    and the same requirement with a true marker still installs.
  * 6.10.10 - The `README.md` as it stands on 2026-09-30, recorded because
    Wayne is about to reorganise it and the next session will not have
    this conversation.  Sections in order: Introduction; *How an `AltVEnv`
    Enabled Program Works* with a 34 line complete program listed with
    `01:` style line numbers and a bullet per line group; *The Bootstrap,
    Which You Do Not Edit* -- Wayne's framing, the try block is
    boilerplate -- with a *For The Curious* subsection holding the
    pasteable copy and the notes on it; *Saying Exactly What You Want*, on
    requirement forms and markers; *What You Need*; *Where Things Land*;
    *Being Asked Before Anything Is Downloaded*; *What This Protects You
    Against, And What It Does Not*.

    The reorganisation Wayne intends: the file is what PyPI shows as a
    project's front page, so the top has to **sell** the package to a
    stranger who found it by accident, and the manual follows.  See
    6.10.11 for what that changes.
  * 6.10.11 - Advice on selling first, written 2026-09-30 so that the
    intent survives a `/clear`:

    * The first fifteen lines are the whole of the sale.  PyPI shows the
      project name and summary itself, so the page can open on the
      problem in a reader's own words -- a single file program that needs
      `requests` -- rather than on a heading that repeats the name.
    * The strongest trust signal costs nothing and belongs near the top:
      **when not to use this.**  `uv run` is better whenever the people
      running the program can install `uv`; `zipapp` is better when there
      is no network; a virtual environment is better for a project rather
      than a script.  A page that says so is believed about everything
      else.
    * Four honesty constraints must survive the rewrite, because hiding
      any of them converts a sale into a support burden: `pip` must be
      preinstalled, the project is experimental, packages are fetched and
      run from an index, and everything has been measured on Linux with
      CPython 3.12 only.
    * The numbered walkthrough is worth keeping and belongs in the manual
      half, not the sale.  It is unusual in a way that helps a reader who
      has decided to commit, and it is noise to one who has not.
    * Two PyPI rendering facts: relative links break, since there is no
      repository context, and HTML comments are not rendered, so the
      `<!-- Claude: ... -->` notes can stay.

  * 6.10.1 - The project's `README.md` still describes the Scavenger
    Hunt, at lines 17 and 27, which nothing implements any more: nobody
    is sent to visit web pages and paste titles back.  What replaced it
    is that the author approves once, and the recipient is told and
    asked at most once per cache.
  * 6.10.2 - `## Security Issues of Executing Unvetted Code` is still
    marked TBD, and it is the section the whole feature rests on.  The
    sub-items of Step 6.6 are its outline, and 6.6.1 in particular: the
    claim has to be narrow to be true, because a malicious author gets
    no protection at all and a typosquat very little.
  * 6.10.3 - Habituation deserves an answer here, per 6.6.7.  The
    mitigation is real and worth stating: the question is asked once per
    cache, not once per run, and an approvals file removes it entirely.
  * 6.10.4 - The project's `README.md` should say plainly that an
    approvals file is how a guarantee is had, where a listing is only a
    notification, and that a program started by `cron` or a build has
    nobody to ask and so proceeds.
  * 6.10.5 - The cache's `~/.alt_venv/README.md` is the other file, and
    `AltVEnv.__init__` writes it from its own docstring.  What it should
    say needs discussing, and it has to describe the versioned layout of
    Step 6.3, which it predates.  Note the current behaviour: it is
    rewritten on every construction rather than only when absent, which
    makes writing a file a side effect of making an object and will
    surprise somebody.

* Step 6.11: Garbage collection.  Cull packages that have not been used
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
  * 6.11.1 - Designed 2026-09-29, and designed **for testability**, at
    Wayne's insistence: where two designs would work, the one that is
    easier to test wins, because the test suite is the product.  Written
    as a plan because Step 6.10's `README.md` forced the decisions early
    -- describing behaviour to a stranger is what exposed which parts do
    not exist yet.

    * **Deciding is separate from deleting.**  `litter()` and
      `stale(days)` each return a list of paths and remove nothing;
      `cull(days)` removes what they name and returns what it removed.
      Most tests then assert on lists and never delete anything, and a
      dry run is free, which is a feature a person actually wants: *what
      would you remove?*
    * **File times are the clock, and `os.utime` is the test lever.**  No
      injected clock, no mocking, no sleeping: a test back-dates a stamp
      by two hundred days and asks whether the tree is stale.  Exact
      rather than approximate.  The same trick already tests that the
      cache `README.md` is not rewritten needlessly.
    * **The request records are the evidence of use.**  Each install
      touches its record, warm or cold; a tree is stale when no record
      naming it has been touched inside the threshold.  No new directory,
      nothing written inside a package tree, and two programs sharing a
      tree means the freshest record wins.  It reuses the walk 6.3.13
      needs anyway.
    * **Thresholds are parameters with module level defaults**, so a test
      passes `days=0` or an absurdly large number and gets both extremes
      without touching the environment.  An environment variable can come
      later if anybody asks.
    * **Litter first, because it needs no policy and cannot be wrong.**
      Anything under `pending/`, and any tree no record names at all,
      is unreachable by definition.  The test is: make a mess, cull,
      assert the mess is gone and the good tree is untouched.
    * **The daily gate is its own predicate.**  `due()` reads the mtime
      of a `last_cull` stamp and `install` culls only when it says so.
      Tests drive `due()` directly, and the install path needs one test
      that a second install the same day culls nothing.
    * **Two safety invariants, a test each**, because they are how this
      feature would bite: nothing stamped during this run is ever
      removed, and a tree vanishing mid-cull because another process got
      there first is not an error.
    * **`wheels/` is left alone** for now, with a test saying so, because
      those wheels are what makes `ALT_VENV_APPROVE=write` work from a
      warm cache; a later size optimisation must not quietly break the
      author's flow.

    Order of work: litter and the daily gate first, which is a small
    honest half, then the age based cull.  The `README.md` already says
    the automatic clean up is designed and not yet written, so it becomes
    true rather than needing a correction.
  * 6.11.2 - The litter half is built, 2026-09-29, and building it
    corrected the plan above on one point: **litter does need a
    threshold.**  6.11.1 said it needed no policy because unreachable
    things are unreachable at any age, and that is true of reachability
    and false of concurrency.  Another program's download is sitting in
    `pending/` right now, and a tree is renamed into `versions/` a moment
    *before* the record naming it is written -- so a sweep with no grace
    period would delete a running program's work, and would do it most
    often on a busy machine.  `CULL_GRACE` is a day: far longer than
    either window, short enough that a crashed run's leftovers do not
    accumulate.

    Three methods, deciding kept apart from deleting as designed.
    `litter(grace)` returns what is unreachable and old enough --
    anything under `pending/`, and any `versions/` tree that no request
    record names -- and removes nothing.  `cull(grace)` removes what that
    names, tolerates a path another sweep took first, and stamps
    `last_cull` even when it found nothing, so an empty cache is not
    swept again a second later.  `due(interval)` compares that stamp
    against now, treating an absent or unreadable stamp as due.
    `provide` sweeps when due, just before fetching: the cost is
    invisible beside a download, and everything this program is about to
    create is younger than the grace period and therefore safe.

    Ten tests, and `os.utime` is the clock throughout, as planned: a test
    back-dates a directory by twice the grace period and asks whether it
    is litter.  Nothing sleeps.  The invariants each have one: a young
    download is spared, a tree a record names survives at a hundred times
    the grace period, a path that vanishes mid-sweep is not an error, and
    a second install on the same day does not sweep again -- watched
    through the stamp's modification time, which is the observable part.
  * 6.11.3 - The age based half is built the same day, and **no pseudo
    clock was needed.**  Wayne offered an environment variable to fake
    the time, on the grounds that tricks in aid of testing are fair;
    declined, because the thresholds are already parameters, so a test
    asks for `days=0.0` or `days=10**9` and gets both extremes at full
    speed, and `os.utime` covers the cases where age itself is the
    subject.  The reason to avoid the variable specifically: a
    time-shifting value loose in somebody's environment would make every
    package look ancient and be swept, which is a footgun that ships.  If
    real time travel is ever wanted, a module level `NOW = time.time`
    that a test patches in process is the shape to use.

    **Age applies to request records and nothing else, and it means
    *unused* rather than *old*.**  `remember` touches a record on every
    hit, warm or cold, so a package fetched two years ago and used this
    morning is not stale; that has its own test.  `stale(days)` names
    records nothing has used for `CULL_DAYS`, which is 180 days because
    the cost of being wrong is one download and the cost of being right
    is a little disk, and those are not symmetrical.

    `cull` removes stale records first and then sweeps litter, so the two
    halves are one mechanism: dropping a record leaves its trees and
    wheels spoken for by nobody, and the litter pass collects them in the
    same sweep.  *Unused* is expressed once, about records; *unreachable*
    once, about everything else.  A tree two records name survives until
    the last of them goes, which is tested by asking for `widget` alone
    and then beside `sprocket`.
  * 6.11.4 - Wheels are collected after all, which **reverses 6.11.1's
    decision** to leave `wheels/` alone, and the reason is that 6.11.3
    created it: once records age out, their wheels become the only thing
    in the cache that nothing will ever look at again and nothing will
    ever remove.  The rule is now symmetric -- a wheel no record names is
    litter, exactly like a tree -- and the author flow the old decision
    was protecting is still safe, because a live record protects its
    wheels, so `ALT_VENV_APPROVE=write` still works from a warm cache.

    `cull` grew a two line branch for it, since a kept wheel is a file
    where everything else swept is a directory.  The test that pinned the
    old decision was replaced by three: an unreferenced old wheel is
    collected, a referenced ancient one is not, and a young unreferenced
    one is spared by the same grace period as everything else -- a wheel
    is renamed into `wheels/` a moment before the record naming it is
    written.

* Step 6.12: Find the bootstrap, and notice when it is stale.  Python has
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
  * 6.12.1 - One locator, three readers.  Three steps need the main
    program's path and its source text: this one, to find the pasted
    case; Step 6.7, to find the requirements block; and Step 6.6, which
    already uses the path alone to place `prog.altvenv`.  So one small
    thing -- the program's path and text, `None` for the REPL,
    `python3 -c` and a frozen interpreter -- and one place where those
    awkward cases are got right and tested.  Built in 6.7.6, which is
    why that step went first.
  * 6.12.2 - Nobody is messaged.  There is no channel to an author at run
    time, only whoever started the program, and a staleness report is
    useful to an author and noise to a recipient who cannot act on it.
    So the author asks rather than being told: silent by default, and a
    report on request, in the same shape as `ALT_VENV_APPROVE=write`.
    That removes the question of how to reach an author entirely.
  * 6.12.4 - `install` takes a `bootstrap` label, added 2026-09-30 at
    Wayne's request while the `README.md` example was being tuned:
    `install(bootstrap="7")`, keyword-only so it cannot collide with the
    requirements argument.  It is kept as `self.bootstrap` and **read by
    nothing yet** -- this step is what will read it.  The pasted example
    passes `"7"`, which is the case this project ships, and
    `bootstrap.py`'s epilogue passes `sys.argv[1]`, so all twelve cases
    exercise the parameter.  A label is cheaper for the caller than
    hashing the pasted text and is what a message would quote; hashing
    remains the way to tell *which* version it is, per this step's plan.
  * 6.12.3 - What to do about a stale bootstrap -- report it, refuse to
    run, or offer to rewrite the file -- is still open, but 6.12.2 makes
    reporting the obvious default.
  * 6.12.5 - **Built**, 2026-10-01, once the paste had stopped moving.
    The bootstrap is found as the program's `try` block that mentions
    `alt_venv` and `import_module`, wherever it sits; the imports above
    it are left out, since people move them.  Its fingerprint is the
    SHA-256 of its text with comments and every space, tab and line
    break removed, so re-indenting, re-wrapping or annotating a copy
    leaves it the same and changing any code does not.  `tokenize`
    finds the comments, and joining its tokens before removing the
    whitespace makes the fingerprint agree under 3.11 and 3.12, which
    tokenize f-strings differently; checked under both.
    `alt_venv.BOOTSTRAPS` lists every published bootstrap by
    fingerprint, oldest first, and holds one entry so far, today's
    `nopip3`.  `bootstrap.pasted` renders a case exactly as pasted, and
    a test fails until the table's last entry matches it, so changing
    the bootstrap without recording it cannot pass.  As 6.12.2 decided,
    `install` is silent unless `ALT_VENV_BOOTSTRAP=check`, when it
    prints one line: current, stale with both names, edited or
    unrecognised, or none found.  The `bootstrap` label of 6.12.4 is
    still read by nothing; the fingerprint made it unnecessary.  The
    first test run found that a `try` nested inside an indented block
    came back from `ast.get_source_segment` unevenly indented, which
    `tokenize` rejected; it is padded and dedented now.

* Step 6.13: Messages.  When should anything be said: on creating the
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
  * 6.13.1 - **Who writes what, and where**, surveyed 2026-10-01, which
    Wayne set as the first thing to know before deciding anything.  By
    reading `alt_venv.py` and `nopip3`, and by running `nopip3` cold with
    its two output streams kept apart.

    | Writer | Stream | When |
    |--------|--------|------|
    | `nopip3`'s `pip install` | **standard output** | first run only |
    | `nopip3`'s `pip install` | standard error | when it fails |
    | `nopip3`'s `except` | standard error, exit 1 | any failure |
    | `AltVEnv.announce` | standard error | every fetch |
    | `AltVEnv.gate` | standard error | `ALT_VENV_APPROVE=write` |
    | `AltVEnv.consent` | `/dev/tty`, not a stream | approvals and a terminal |
    | `AltVEnv.download` | captured; text goes into the exception | always |
    | `AltVEnv.refresh_pip` | captured and dropped | weekly |
    | `AltVEnv`'s exceptions | the caller's to catch | failures |

    The one surprise is the first row.  `pip` writes its progress --
    `Collecting coverage`, `Downloading ...`, `Successfully installed
    ...`, five lines -- to the program's own standard output, so the
    first run of a program whose output is piped or parsed gets those
    lines mixed into it.  `announce`'s own docstring says a library
    must never do this.  `stdout=2` on that `subprocess.run` would send
    them to standard error, and it fits inside 79 columns, so it costs
    no line.  Recommended for 6.13; not done, because 6.13 is Wayne's
    to decide.

    The other open question for 6.13 is the last row: `install()` raises
    on a failed fetch, so a program that does not catch it ends in a
    traceback, where `nopip3` itself ends in one line.

* Step 6.14: The shipping bootstrap.  Twelve cases were measured in Task
  2 and never narrowed to one, which left the `paste` metric priced
  against a set rather than a product, `FAST_CASES` looking arbitrary, and
  issue `2wtmifs` alive because a matcher nobody ships was still on a path
  somebody might.
  * 6.14.1 - **Case 7 ships**, nominated and accepted 2026-09-29: no
    virtual environment, `pip` as a subprocess, eighteen pasted lines, one
    import.  Wayne's words were "I'm leaning toward case 7.  We can always
    back out if we encounter something."

    The reasoning, in the order it decides:

    * Joint shortest paste with 6, 9 and 10.
    * Cases 6 and 9 run `pip` **in process**, which leaves 451 of its
      modules in `sys.modules` and three handlers on the root logger of
      somebody else's program; measured in Task 2.  A subprocess takes all
      of that away with the child.  This is the tiebreaker, and it is a
      correctness argument rather than a preference.
    * Case 10 is 7 plus `--no-compile`, worth 60 KB, which is illusory
      because the bootstrap imports the package two lines later and Python
      compiles what it imports anyway.
    * It hands wheel selection to `pip`, which is what Step 6.17.5 made
      decisive: our five line matcher cannot see abi3 wheels and cannot
      tell musl from glibc.  On the shipping path neither bug can bite,
      because we do not choose.
    * Its failure is legible now that `--quiet` is gone: pip's own error
      text reaches the person instead of only its retry warnings.

    The cost is that `pip` must be installed, which is a real ask on the
    distribution that motivates this project, since Debian and Ubuntu ship
    `python3-pip` separately.  The `README.md` leads with it and now states
    the trade: one command once, against creating a virtual environment,
    activating it differently on every shell and system, and remembering
    to activate it again tomorrow.
  * 6.14.2 - **The `paste` column was wrong, by three, in every row**,
    found while checking the number before quoting it.  `SHARED_LINES`
    became 7 on 2026-09-26 when the `try` wrapper started being charged,
    and the table in `bootstrap.py` was never regenerated, so it still
    read `lines + 4`.  Corrected arithmetically on 2026-09-29 -- the
    `imports`, `lines` and `paste` columns come from parsing the file, so
    they need no run -- and the three places quoting the old figures were
    corrected with it.  Case 7 is 18 pasted lines and not 15; case 3 is 52
    and not 49.

    One quotation of the old numbers is left alone deliberately: finding
    10 of Task 2 says "Independence from pip costs 49 pasted lines against
    15".  Task 2 is closed, so that is Wayne's to change or leave.
  * 6.14.3 - The other eleven cases stay, as measurement rather than as
    candidates.  `ALT_VENV_TEST=COMPLETE` runs them, the table keeps
    pricing them, and `2wtmifs` retires further: the matcher is no longer
    on any path a stranger reaches.

    Open, and worth deciding before the `README.md` claims anything about
    it: whether case 3 is offered as a documented fallback for a machine
    with no `pip` at all.  It costs 52 pasted lines and carries the two
    matcher bugs, so offering it means fixing the abi3 comparison first --
    a comparison of integers, not a version parser.
  * 6.14.4 - Superseded on 2026-10-01 by Step 6.15: case 13 ships in
    place of case 7, because it needs no preinstalled `pip`.  The
    subprocess argument of 6.14.1 carries over unchanged, and 6.15.1
    found `pip` itself now making it.

* Step 6.15: No preinstalled `pip`.  Step 6.14.1 chose case 7 and named
  its cost: `pip` must be installed, and Debian and Ubuntu ship
  `python3-pip` separately.  The `README.md` rewrite needed to know
  whether that cost is real, and so whether the claim could be that
  Python and the pasted bootstrap are all a machine needs.
  * 6.15.1 - Three experiments, 2026-10-01, each fetching `pip`'s own
    wheel from the JSON API and installing with it, run on an
    interpreter made by `venv --without-pip` so that no `pip` could
    help.  All three worked against the real PyPI.  The two that ran
    `pip` in process, one from a temporary file and one straight out of
    memory through a hand-written importer, each printed forty
    `DEPRECATION: Unexpected import ... after pip install started`
    warnings.  `pip` 26 objects to a program importing, in the same
    process, what `pip` just installed, and says 26.3 will enforce it.
    That is the in-process argument of 6.14.1 again, made this time by
    `pip`.  Both were dropped, and the subprocess one became case 13.
  * 6.15.2 - **`alt_venv` needed `pip` as well.**  `AltVEnv.download`
    ran `python -m pip download`, so a bootstrap free of `pip` only
    moved the failure to the program's first declared dependency.  The
    answer is a private copy.  Case 13 keeps the wheel it fetched as
    `~/.alt_venv/pip.whl`, and `AltVEnv.pip` runs it as
    `python pip.whl/pip`, which is how `pip` documents running itself
    without being installed.  With no stash, which is every other case,
    it falls back to `python -m pip` as before.
  * 6.15.3 - Measured with the harness: 3 imports, 25 lines, 31 pasted,
    3.11 s cold, 0.14 s warm, 3538 KB, of which 1.8 MB is `pip.whl`.
    Against case 7 that is 15 more pasted lines and a 1.8 MB download
    on the first run only.
  * 6.15.4 - Verified 2026-10-01 on Linux under CPython 3.12.3 and
    3.11.16, each with no `pip`: case 13 against the real PyPI, and
    `test_nothing_but_python_and_the_bootstrap`, which runs case 13 and
    then a program declaring a dependency, against the local index.
    The 3.11 interpreter came from `uv python install 3.11`.  That run
    is a one-off rather than part of the suite: the floor is 3.11 only
    because `tomllib` arrived in it, and nothing in this change is
    expected to break there.  To repeat it, run the suite's two
    private-`pip` tests,
    `InstallTest.test_pip_prefers_the_private_copy` and
    `InstallTest.test_nothing_but_python_and_the_bootstrap`, under
    `~/.local/share/uv/python/cpython-3.11-linux-x86_64-gnu/bin/python3.11`.
  * 6.15.5 - The suite never reaches the network, so every index that
    `build_index` makes now publishes a `pip` wheel as well, zipped by
    `pip_wheel` from the `pip` running the suite.  That works only for
    a `pip` carrying its vendored libraries; a debundled one cannot run
    alone, and the no-`pip` test skips.
  * 6.15.6 - **Case 13 ships**, 2026-10-01.  Wayne's words: "If the
    bootstrap grows some to eliminate the pip preinstalled issue I'm
    probably good with that."  The claim the `README.md` can make is
    Python 3.11 or later, the pasted bootstrap and a network that
    reaches PyPI.  `FAST_CASES` became `("13",)`.  Still open: `1bfnprp`,
    `2btosc`, `3fpfipe` and `3spinu`, and Windows and macOS are untried,
    which is `2hmmdrpe`.

  * 6.15.7 - **The paste grew to 43 lines, on purpose**, 2026-10-01.
    Two changes to `nopip3`, both in code nobody can fix once pasted.
    It now fetches not the newest `pip` but the newest **upload** whose
    `requires_python` floor this Python meets, which closes `1bfnprp`:
    when `pip` drops a Python, that Python keeps getting the last `pip`
    that supported it.  Against the real index, simulated: 3.7 gets
    24.0, 3.8 gets 25.0.1, 3.9 gets 26.0.1, 3.10 to 3.12 get 26.2.1.
    Sorting by upload time avoids parsing versions, and `pip` has
    written its floor as a plain `>=3.N` since it dropped Python 2.
    Pinning a version was considered and declined: a pinned `pip` is
    frozen into every pasted copy, and `pip` releases before 23.2 crash
    on Python 3.12, so a 2022 paste pinning 22.x would fail today.

    And it sets a `stage` before each step, which the `try` wrapper
    reports with the exception's type and text, at Wayne's suggestion,
    in two words at most at his request: `cannot fetch alt_venv, choose
    pip failed: HTTPError: ...`.  The wrapper's `raise` no longer fits
    one line, so `SHARED_LINES` became 7 and every case's `paste` rose
    by one.  Cold
    time is unchanged at 3.05 s; `pip`'s whole release list is 228 KB.
    Two tests: a 404 for `pip`'s page names the first stage, and of
    three stand-in `pip` releases the one whose floor is exactly this
    Python is chosen over a newer one that wants a later Python.  The
    local index now serves `releases`, with each file's floor read from
    its own `METADATA` and its upload time from the file.

  * 6.15.8 - **Each case body is exactly what gets pasted**, 2026-10-01,
    at Wayne's direction: "The code is supposed to be exactly what is
    pasted into the user's code."  The `try` had lived once, at the
    entry point of `bootstrap.py`, so that no body had to be indented
    under it, which meant the text a person copied was not the text in
    the file.  Now every case opens with its comment and its imports,
    which the person moves to the top of their program, and wraps the
    rest in its own `try`; the entry point wraps nothing, `stage` needs
    no `global`, and `SHARED_LINES` is just the three module level
    imports.  The deeper indentation pushed eighteen lines past 79
    columns, and re-wrapping them added a line to some cases, so the
    figures moved once more: `nopip3` is 44 pasted, `pip2` 18.  A
    comment on the selection, at Wayne's request, made `nopip3` 45.  `ruff`'s
    `BLE001` objected to every `except Exception`; the exemption went
    into `ruff.toml` rather than into a `noqa` comment that would be
    pasted along with the code.  All thirteen cases were run against
    the real PyPI afterwards, and a dead network reads `cannot fetch
    coverage, choose pip failed: URLError: <urlopen error [Errno 111]
    Connection refused>`.

  * 6.15.9 - **Each case is its own function**, 2026-10-01, at Wayne's
    suggestion, for a better view of what is pasted: `def nopip3():` and
    so on, in place of thirteen `case` clauses of one `match` in
    `main()`.  A body now sits one level, four spaces, deeper than it
    will in a program, where it sat three levels deeper before.  Each
    function's docstring is not pasted and not counted; `main()` calls
    the function named on its command line and reads the module back
    from `sys.modules`, since a case's last line binds `module` for the
    program it lands in.  `ruff` took that binding for an unused
    variable (`F841`), and its exemption joined `BLE001`'s in
    `ruff.toml`.  No count changed.  `measure_source` and
    `case_bodies` now read the functions rather than the `match`.

  * 6.15.10 - **Reflowed to the function depth**, 2026-10-01.  Lines
    wrapped for the old depth were rejoined wherever they now fit, by
    explicit before and after blocks, with each function's syntax tree
    compared before and after so that only whitespace could move.  The
    comparison caught one real change: re-wrapping for 6.15.8 had
    swapped `--target` and `--disable-pip-version-check` in `venv2` and
    `pip2`, which pip does not mind but which nobody had asked for, and
    this put back the order of revision 394.  Every case shrank:
    `nopip3` is 41 pasted lines, `pip2` 17, `nopip1` 51.  `venv4`,
    `pip4` and `pip5` keep calls that cannot lose a line at this depth.

  * 6.15.11 - **`nopip3` squeezed to 28 pasted lines**, from 41, on
    2026-10-01.  Wayne: "Squeezing the bootstrap down to few lines will
    make people less hesitant to use it.  It is meant to be 'magic'."
    Single letter names, short statements sharing a line, one import
    line, `/` without spaces, no `with` around the downloads, PyPI's
    shorter `upload_time`, and `repr` in the message, which carries the
    exception's type and so freed the `raise`'s second line.  `from
    None` went too, since `SystemExit` never prints a traceback.  Only
    `nopip3`; the other twelve are untouched.  `ruff.toml` now exempts
    `bootstrap.py` from `E401`, `E702` and `I001` as well.

    Three things nearly slipped through.  A first pass swapped pip's
    `--no-input` and `--disable-pip-version-check` for `-q`, which is
    the `--quiet` that 6.17.7 removed because it hides pip's diagnosis
    of a bad certificate; put back.  `t.mkdir(exist_ok=True)` dropped
    `parents=True`, and the no-`pip` test caught it.  And a harness
    name is shorter than what a paste carries: `JSON_API` becomes
    `https://pypi.org/pypi`, so pasted widths are checked separately,
    four columns shallower with the literals spelled out, and the widest
    is exactly 79.  Run against the real PyPI on 3.12 and 3.11 without
    `pip`, cold and warm.

  * 6.15.12 - **Imports one to a line again**, 2026-10-01, at Wayne's
    request: the combined `import json as j, subprocess, urllib.request
    as u` was too un-Pythonic, and the person moves a case's imports to
    the top of their program, where many tools insist on one import to
    a line and sort them.  Semicolons stay, but only between statements
    on one topic, which Wayne finds tools tolerate.  Then, keeping the
    ugliness inside the `try`, `json` lost its alias and
    `urllib.request` became `req`; the longer names cost one line, the
    fetch of `pip`'s release list split in two, since a timeout is not
    worth giving up to save it.  The comment on the choice of `pip`
    then went, at Wayne's word, the docstring explaining it instead.
    `nopip3` is 30 pasted lines, and
    `ruff.toml` exempts `E702` alone of the three squeeze rules.

  * 6.15.13 - **One `if` fewer**, 2026-10-01, from Wayne's suggestion
    to merge the two nested tests with `and`.  Merged literally, a
    machine holding `pip.whl` but not `alt_venv` would skip the install
    and fail at the import, so instead the inner test went: whenever
    `alt_venv` is missing, `pip` is fetched and `alt_venv` installed.
    The cost is a second 1.8 MB download in the rare case an earlier
    run failed between the two.  The level of indentation it freed let
    the fetch of `pip`'s release list rejoin one line, with both
    timeouts passed positionally to fit once pasted.  `nopip3` is 28
    pasted lines; the widest, pasted, is 78.

  * 6.15.14 - **The install on fewer lines, and comments at line ends**,
    2026-10-01, at Wayne's suggestion and the last squeeze for a while.
    The stage and its `subprocess.run` share a line, which needed paths
    passed as they are rather than through `str`, pip's `-t` for
    `--target`, and the argument list opened on its own line.  Wayne:
    a comment may sit in the space at the end of a line, so long as the
    line stays within 79 columns; four do now, costing nothing.
    `nopip3` is 27 pasted lines.

  * 6.15.15 - **`pip`'s SHA-256 is checked**, 2026-10-01, closing
    `3fpfipe`.  The digest PyPI lists for the file is compared with the
    bytes before anything is written, so a damaged download fails as
    `download pip failed: ValueError('pip-...whl fails its SHA-256
    check')` and leaves no `pip.whl` behind to fail confusingly on every
    later run.  Three lines: `import hashlib` and a two line `if`, which
    made `nopip3` 30 pasted lines.  The local index serves
    `digests` now, and a new test truncates every wheel in flight; with
    the check taken out, that test fails.

  * 6.15.16 - **The private `pip` keeps itself current**, 2026-10-01,
    closing `3spinu`.  `AltVEnv.refresh_pip` runs from `provide`, beside
    the cull, so only when something is about to be fetched anyway, and
    at most weekly by a `last_pip` stamp, as `pip` checks itself.  It
    asks the current private `pip` to download `pip`; `pip` passes over
    releases this Python cannot run, so what arrives is the newest it
    can.  A new version is added **beside** `pip.whl`, as
    `pip-<version>-...whl`, never over it: a running `pip` reads itself
    out of its wheel by offset as it goes, so replacing the file under
    it would break it.  `pip()` takes the most recently added copy.
    Superseded copies are removed after a day's grace; `pip.whl` is
    kept, for the bootstrap.  Failure of any kind is silent and waits a
    week, since the stamp is written before trying.  A cache with no
    private `pip` is left alone.  Five tests, among them a stand-in
    `pip` 99.0 being added and a dead index changing nothing; with the
    version comparison disabled, the up-to-date test fails.
  * 6.15.17 - **The bootstrap calls `install()` itself**, 2026-10-02,
    31 pasted lines.  Every case had ended at importing `alt_venv`,
    leaving `install()` to `bootstrap.py`'s epilogue, so when
    `README.md`'s example moved to `nopip3` it grew `import alt_venv`
    and `alt_venv.AltVEnv().install()` below the bootstrap, and Wayne
    asked why a program should mention `alt_venv` at all.  Wayne: "The
    end-user should never have to directly touch `AltVEnv`."  The last
    stage is now `fetch packages`, calling
    `AltVEnv().install(bootstrap="nopip3")`; the label is read by
    nothing, but Wayne wants it.  Failures there -- a package that will
    not download, or `n` at the prompt -- now end in the bootstrap's one
    line instead of a traceback, and the message became `alt_venv:
    <stage> failed: <repr>`, since "cannot fetch alt_venv" would be
    wrong for them.  The other twelve cases keep their wording, and
    `test_a_failed_fetch_is_one_line` accepts either.  The fingerprint
    entry of 2026-10-01 was replaced rather than kept, because it was
    never published.

* Step 6.16: Test suite cleanup, headed towards deleting some of the
  cases in `bootstrap.py` now that `nopip3` ships.
  * 6.16.1 - **Cases are named, not numbered**, 2026-10-01, at Wayne's
    suggestion.  The numbers were the order the cases were written, so
    every addition or removal threatened to renumber something.  A name
    now says what the case needs on the machine, with a digit counting
    within its group: `venv` cases create a virtual environment, `pip`
    cases run a pip already installed, and `nopip` cases need none.
    Old to new:

    | Old | New      | Old | New      | Old | New      |
    |-----|----------|-----|----------|-----|----------|
    | 1   | `venv1`  | 6   | `pip1`   | 11  | `venv4`  |
    | 2   | `venv2`  | 7   | `pip2`   | 12  | `nopip2` |
    | 3   | `nopip1` | 8   | `pip3`   | 13  | `nopip3` |
    | 4   | `venv3`  | 9   | `pip4`   |     |          |
    | 5   | `venv5`  | 10  | `pip5`   |     |          |

    The code, the table and the tests use the names, and the
    `bootstrap.py` docstring carries the same mapping.  Closed tasks
    keep the old numbers, and so do the steps of this task written
    before the change, Step 6.15 included.  `README.md` still passes
    `bootstrap="7"` to `install`, which nothing reads yet; it becomes
    `"nopip3"` whenever Wayne's rewrite reaches the paste.

  * 6.16.2 - **The cull run**, built 2026-10-01, so that cases are
    deleted on evidence rather than by taste.  Wayne's framing: the test
    suite is the product, culling will recur, and one run a night while
    he sleeps is affordable.  The parts:

    * `ALT_VENV_TEST` also takes case names, `pip2` or `pip1,pip2`, and
      `NONE`, which selects no case at all.
    * `selected` gates the few tests written for particular cases, the
      matcher tests for `nopip1` and `nopip2` and the no-`pip` test for
      `nopip3`, so that a run for one case does not quietly include them.
    * `@runs_cases` marks every test that runs a case, and
      `test_case_runners_are_marked` checks the marks against the
      source; deleting a mark was tried and the guard failed, as meant.
    * `alt_venv_coverage.py --per-case <dir>` makes one baseline run of
      the whole suite with `NONE`, then runs only the marked tests once
      per case, two runs at a time, children traced throughout, each run
      writing only under `<dir>/<run>/`.  `--compare <dir>` redoes the
      report from the saved counts in seconds.
    * The trace hook credits a copy of `alt_venv.py` that a bootstrap
      installed to the project's own file, when the two are identical,
      since the copy is deleted with its test.  Checked: the counts land
      on the project path.

    Measured: the whole suite traced for one case took 11 min 23 s, and
    only the marked tests 55 s, so the first design would have cost
    about 75 minutes a night.  The real cull took 12 min 19 s, of which
    the baseline is 717 s and the thirteen cases overlap it.  Wayne
    starts it at bedtime; the command is in `CLAUDE.md`.
  * 6.16.3 - **First cull, 2026-10-01**, in
    `~/alt_venv_cull/2026-10-01/report.md`.  Every case runs every one
    of its own statements.  Beyond the baseline:

    * No case adds a single line of `alt_venv.py`.  The baseline alone
      covers everything the product does.
    * All ten `venv` and `pip` cases add the same 63 lines of the test
      file, the shared every-case tests, and nothing of their own.
    * `nopip1` adds 4 lines nobody else does, the truncated-wheel test.
      `nopip2` adds nothing that `nopip1` does not.
    * `nopip3` adds 32 lines nobody else does, all of them the no-`pip`
      test.
    * Greedy, from the baseline: `nopip3` then `nopip1`, and the other
      eleven add nothing.

    So on coverage alone, eleven of the thirteen cases could go.  What
    coverage cannot see is their other job: the table in `bootstrap.py`
    prices each mechanism, and that record is what Steps 6.14 and 6.15
    were decided on.  Whether that record needs to stay runnable, or can
    live on as a table in the log, is Wayne's call.
  * 6.16.4 - A child's counts include standard library lines, such as
    `/usr/lib/python3.12/zipfile`, although the trace hook names
    `sys.base_prefix` among the directories to ignore.  The report reads
    only this project's files, so the answer is unaffected; the cost is
    time and the size of the counts.  Not yet looked into.

    Looked into, 2026-10-01, and it was worse than a cost.  `trace`'s
    own `Ignore` caches its verdict by a module's **bare name** --
    `__init__`, `utils`, `exceptions` -- not its path, so whichever
    `__init__.py` a process met first decided for every other.  Children
    that met one of this project's first traced every `__init__.py` in
    the standard library; and in the other direction, project files
    were being **skipped** whenever a standard library file of the same
    name came first.  A separate leak: `venv3` runs `pip` in its own
    process, so 57,162 lines of `pip` were traced in one child.  Both
    tracers, the parent's `build_tracer` and the child hook, now swap
    `trace`'s `Ignore` for a positive rule cached by path: follow this
    project's directory and installed copies of `alt_venv`, and nothing
    else.  Measured on one case at a time, nothing was lost and lines of
    `alt_venv.py` that had been skipped were gained; `venv3` went from
    86.5 s to 71.6 s and `nopip3` from 22.6 s to 21.4 s.  A whole
    `COMPLETE` cull still took 761 s against the morning's 739, on a
    suite fifteen tests larger: the time is in the work the tests do,
    not in tracing them.

    That cull's **report is void**.  Claude edited `alt_venv.py` and
    `alt_venv_test.py`, for 6.12, while it ran, so the baseline and the
    later cases counted the same lines under different numbers, and
    cases looked to add hundreds of lines they did not.  A nightly run
    on a still tree is not at risk, but the cull trusts the tree to stay
    still for a quarter of an hour; copying the project somewhere first
    and measuring the copy would remove that trust.  Not built.
  * 6.16.5 - **The other ten cases stay but stop running**, 2026-10-01.
    Wayne: "leaving the tests around hurts nothing.  From now on just
    run nopip1-3."  `FAST_CASES` became `nopip1` to `nopip3`, and the
    cull takes its cases from `ALT_VENV_TEST` as the suite does, so it
    measures those three unless told `COMPLETE`.  `FAST_CASES` had been
    standing in for "the case that ships", which three cases cannot do,
    so that meaning moved to a constant of its own, `SHIPPING`.
  * 6.16.6 - **The cull has tests**, 2026-10-01: `CoverageToolTest`,
    twelve of them, on counts written by hand and with child processes
    mocked, so that nothing is traced inside a run the tool may itself
    be tracing.  They cover `flatten`, `marked` (pulled out of
    `run_suite` to be testable), `case_bodies`, `covered`, `compare`,
    `report`, `merge_children`, `trace_children`, `measure_one`,
    `measure_cases` and `main`'s `--compare` path.  Two bugs found
    earlier in the day were put back one at a time, the own-body count
    and the greedy order ignoring the shipping case, and the comparison
    test failed on each.  Not covered: `run_suite` and `main`'s
    measuring path, which run the suite itself, and `_credit` in the
    trace hook, which only exists inside a traced child.

  * 6.16.7 - **A full traced run, unattended**, 2026-10-01, while Wayne
    wrote `README.md`: `ALT_VENV_TEST=COMPLETE ./alt_venv_coverage.py
    --children`, 215 tests passing in 20 minutes, 343 children folded in.
    `alt_venv.py` 98%, `bootstrap.py` 99%, `alt_venv_test.py` 95%.  No
    test failed and no product bug turned up.  What it did turn up:

    * Six lines of `alt_venv.py` no test reached: a program that does
      not parse, in `find_bootstrap`, and the two `OSError` arms of
      `refresh_pip`.  Three tests now reach them, checked by tracing
      them alone.  Two more lines read as missed but are not: the
      frozen interpreter branch, already noted, and the refusal of a
      module whose `__file__` is not a `.py`, whose test patches the
      very `__file__` that `trace` reads to decide what to follow.
      `alt_venv_coverage.py`'s docstring now names both.
    * The opt-in suites, run too.  `ReportTest`, behind
      `ALT_VENV_REPORT`, had been broken since 6.16.1: it looked for
      `| venv1 |` in the table, but naming the cases widened the label
      column, so all ten shorter names are padded.  It reads the width
      from `bootstrap.COLUMN_WIDTHS` now.  `PyPITest` passed.
    * A new opt-in test, `test_the_shipping_path_against_pypi`: an
      interpreter with no `pip` runs `nopip3` against the **real**
      PyPI for `pip`, then a program declaring `requests` gets it, and
      its four dependencies, from the real PyPI through the private
      `pip`.  Only `alt_venv` itself comes from a local index, since
      no index has it yet.  It passes, in about eight seconds.
    * Writing it found that `run_bootstrap_case` raised `TypeError`
      when `extra` repeated a variable it sets itself, such as
      `BOOTSTRAP_JSON_API`.  `extra` now overrides.

  * 6.16.8 - **The last two missed lines were the tracer's fault**,
    2026-10-02, on a second full traced run while Wayne took a break:
    `ALT_VENV_TEST=COMPLETE ./alt_venv_coverage.py --children`, 220
    tests passing in 20 minutes, 343 children folded in, then the
    opt-in `PyPITest` and `ReportTest`, all passing (one expected
    failure, `2wtmifs`'s abi3 test).

    The two lines 6.16.7 accepted as unreachable, in
    `repair_module_layout`, were reached all along; a probe saw
    `__file__` arrive as `None` and as a `.txt` path.  The cause is in
    `trace`: `globaltrace_lt` decides whether to follow a call by the
    **calling module's** `__file__`, read from the frame's globals, but
    keys the counts by the code's `co_filename`.  The test patches
    `alt_venv.__file__`, so with `None` `trace` gives up on the frame,
    and with a path outside the project `ProjectOnly` turns it away.
    Both tracers now subclass `trace.Trace` (`ByCode` in
    `alt_venv_coverage.py`, `_ByCode` in the hook) and ask about
    `co_filename`, the file the counts are kept under.  Rerun:
    `alt_venv.py` 100%, `bootstrap.py` 99%, `alt_venv_test.py` 94%.
    What remains missed is environmental -- a non-CPython interpreter,
    no `openssl`, an unexpected server error -- or belongs to the
    opt-in classes and to `skipTest` lines that cannot fire under
    `COMPLETE`.  `alt_venv_coverage.py`'s docstring no longer lists
    the two lines as a blind spot.

* Step 6.17: A fetch from the real PyPI, carried over from Task 5.

  It is the only thing that can settle Task 3's conclusion that a
  bootstrap needs `python3-pip` plus a TLS trust store, since that claim
  is about trusting the public certificate authorities and a private
  certificate tests the opposite.  It is also just `install` against the
  real index.

  Early rather than late, because of how much it retires at once.
  Everything measured so far has been against wheels this project built
  itself: real tag soup, a real transitive closure rather than the
  synthetic `needy` and `widget`, and TLS against the public
  authorities are all unexamined.  One opt-in test reaches all of them,
  and settles a claim that has been open since 2026-09-24.
  * 6.17.1 - Done 2026-09-27.  `PyPITest`, skipped unless
    `ALT_VENV_PYPI` is set, fetches from the real index in a child
    process with `PIP_INDEX_URL` removed, so the default applies: PyPI
    over TLS against the system trust store.  Two tests, 5.4 s.
    `requests==2.32.3` arrives with `certifi`, `charset-normalizer`,
    `idna` and `urllib3`, which is the first real transitive closure this
    project has seen, and Task 3's trust store claim is settled in the
    affirmative: nothing about the fetch needed arranging.

    Download only; upload nothing.  Wayne asked on 2026-09-27
    whether PyPI has a scratch area that ages out after about a week, to
    hold wheels of our own.  It would not help here: the three unknowns
    are real tag soup, a real transitive closure and TLS against the
    public authorities, and all three come from **fetching** something
    that already exists.  Nothing this project does publishes a package.

    The nearest real thing is `test.pypi.org`, a separate instance whose
    database may be pruned, but not on a schedule anybody should rely on,
    and real PyPI refuses to reuse a filename once deleted.  Unverified
    recollection rather than measurement; one fetch of their
    documentation would settle it if it ever matters.
  * 6.17.2 - Uploading belongs to a different question, kept separate so
    it is not confused with this one: publishing `alt-venv` itself, so
    that `PACKAGE = "alt_venv"` in a pasted bootstrap resolves for a
    stranger with no local index.  That is the true end to end test and
    it is a release decision, with `test.pypi.org` as its rehearsal.

    **Who does what.**  Wayne uploads, by hand, exactly as with `git`.
    Two factor authentication is **not** the gate here and it was worth
    finding out before relying on it: it protects the web login, while
    an upload authenticates with an API token and is entirely
    non-interactive.  So the boundary has to be the token itself --
    Claude prepares and verifies the artifact and never holds the
    credential.

    **Ready as of 2026-09-27**, so that tomorrow is only the parts that
    need a person:

    * `release_wheel` builds the artifact: the module copied under the
      published name so one word is both the `pip` name and the import
      name, `Requires-Python` from `alt_venv.py`'s own block, `README.md`
      as the project page, a `License` field as free text and five trove
      classifiers.  Seven tests in `ReleaseWheelTest`, including `pip`
      accepting it and no `@` anywhere in the headers.
    * `dev_version()` stamps a version to the minute, because **no index
      lets a filename be uploaded twice**, even after a deletion.  Every
      rehearsal therefore gets a name of its own for free.
    * `twine` is fetched with our own `install()` -- about twenty
      packages, the largest closure this project has resolved -- and
      then judges our own handwritten `METADATA`.  Measured:
      `twine check --strict` **passes**.  The rejection 6.17.7 expected
      did not happen, which retires the main risk of the whole exercise.
      The test is opt in behind `ALT_VENV_PYPI`.

    **What is left for a person, in order.**

    * An account on `test.pypi.org`, which is separate from PyPI's, with
      2FA by authenticator application rather than SMS as far as anybody
      here knows; the signup page settles it.
    * An API token from that account, kept out of the repository.
      `TWINE_USERNAME=__token__` and `TWINE_PASSWORD=<token>` in the
      environment is the least permanent way to hold one.
    * Build with a stamped version, then `twine upload --repository-url
      https://test.pypi.org/legacy/ <wheel>`, under the trial name
      `alt_venv_trial` rather than `alt-venv`.
    * Fetch it back the way a stranger would: a pasted bootstrap with
      `PIP_INDEX_URL=https://test.pypi.org/simple/` and no local index at
      all.  That is the step nothing has ever tested.
    * Then, and only then, `alt-venv` at `0.0.1.dev1` on real PyPI, which
      claims the name that every pasted bootstrap carries while leaving
      `0.0.1` clean for the first real release.

    **One asymmetry to keep in mind**: `test.pypi.org` may be pruned,
    unscheduled, so a mistake there does fade; PyPI never forgets, and
    the protection there is the version suffix and nothing else.
  * 6.17.3 - Opt in, and pin.  This is the one test that can fail because
    the world changed rather than because we did, so it stays out of the
    default suite behind an environment variable, and it names exact
    versions.  Rate limiting and a machine with no network are both
    ordinary outcomes here, not faults.
  * 6.17.4 - Which packages, and why each.  `requests` brings a real
    transitive closure -- `certifi`, `idna`, `urllib3`,
    `charset-normalizer` -- which the synthetic `needy` cannot imitate.
    `setuptools` is the other, because it ships `distutils-precedence.pth`
    and so doubles as Step 6.9's evidence, and because it has no
    dependencies of its own.  `coverage` was the first choice and turned
    out to ship no `.pth` at all; see 6.9.
  * 6.17.5 - Done 2026-09-28, and it found what it was meant to find.
    `install` hands resolution and tag matching to `pip`, so a real index
    tests our plumbing; cases 3 and 12 choose for themselves with the
    five line matcher of `2wtmifs`, and those are the ones worth aiming
    at real tag soup.  Four packages, both cases:

    * `certifi`, pure `py3-none-any`: fetched.
    * `coverage`, a `cp312` wheel for this machine plus a pure fallback:
      fetched, so the preference order does real work.
    * `charset_normalizer`: fetched, but **by luck**.  It publishes
      `cp312-cp312-manylinux...` and `cp312-cp312-musllinux_1_2_x86_64`,
      and a musl name contains both `linux` and `x86_64`, so the matcher
      accepts either; PyPI happens to list manylinux first.  A project
      listing them the other way round would hand a glibc machine a musl
      wheel whose shared objects cannot load.  That is `2wtmifs`
      predicted and now confirmed against real data.
    * `cryptography`: **cannot be fetched at all.**  An abi3 wheel is
      tagged with the **lowest** Python it supports and serves every
      later one, so the real names are `cp39-abi3` and `cp311-abi3`; the
      matcher looks for `cp312-abi3` and gives up with `no compatible
      wheel found`.  `pip` installs it without comment.

    The abi3 gap is now a `@unittest.expectedFailure` in `PyPITest`, so
    it documents itself and reports an unexpected success the day the
    matcher learns about abi3.  Both faults belong to `2wtmifs` and the
    fix is pasted code, so it is Wayne's call: matching `cpXY-abi3` for
    any `XY` at or below the running version is a comparison, not a
    parser, and costs a line or two of paste.
  * 6.17.6 - The prompt is a hazard here, not in the suite.  Under
    `unittest` there is no controlling terminal, so `consent` returns
    True and nothing hangs; a person running this test from a terminal
    with no approvals file gets asked, and the answer they give decides
    whether the test passes.  Set `ALT_VENV_APPROVE` in the test rather
    than leaving that to chance.
  * 6.17.7 - Done 2026-09-28, and the suspicion was wrong in a useful
    way.  `ATTEMPTS` is the consent prompt's and nothing fetches with
    it; the time is `pip`'s own five retries with backoff.  Measured
    against a server whose certificate nothing trusts, one case each:

    | flags                       | time  | names the certificate |
    |-----------------------------|-------|-----------------------|
    | `--quiet`, default retries  | 8.4 s | yes                   |
    | `--quiet --retries 0`       | 0.7 s | **no**                |
    | loud, `--retries 0`         | 0.7 s | yes                   |
    | loud, `--retries 1`         | 0.7 s | yes                   |

    The middle row is the finding, and it is worse than slowness: under
    `--quiet` the word certificate appears **only in the retry
    warnings**, so a user with `PIP_RETRIES=0` set, or a future pip that
    words its warnings differently, is told `no matching distribution
    found` -- a confident lie about the cause, which is exactly the
    failure Step 6.1 exists to prevent.  The good message we have today
    is luck.

    So `download` drops `--quiet` and passes `--retries 1`.  Everything
    pip prints is captured, so the caller sees no extra noise; the
    diagnosis now comes from the error rather than from a warning; and
    one retry remains for a genuinely flaky network.  `argv` still wins,
    for a caller who wants pip's defaults back.

    **Left for Wayne, because it changes the pasted code:**
    `bootstrap.py`'s cases still pass `--quiet` and still take 8.4 s on
    a bad certificate, and `TlsTest` measures them rather than
    `download`.  Dropping `--quiet` there costs **no** pasted line and a
    few characters, and would additionally show a person that something
    is being fetched, which Step 6.13 wants anyway.

* Step 6.18: And more.  A place holder for additional steps.

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
marked TBD.  Explaining any of this to a stranger is Step 6.10, and the
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

* **The bootstrap trusts only system certificates. (2btosc)**  Case
  13 reaches PyPI with `urllib`, which verifies against the operating
  system's certificate store, where case 7 handed the whole fetch to
  `pip` and its own bundled store.  Linux distributions provide one.
  The python.org installer for macOS does not until its
  `Install Certificates.command` has been run, so there the bootstrap
  would fail on its first request.  Untested; nobody here has a Mac.

  Various thoughts:
  * Wayne (2026-10-01): I'm working on getting access to macOS and
    Windows machines, so that is in progress.
  * Claude (2026-10-01): Simulated on Linux by pointing `SSL_CERT_FILE`
    at an empty file, and at no file, with `SSL_CERT_DIR` gone too.
    `nopip3` stops at once with one line, exit status 1: `cannot fetch
    alt_venv, choose pip failed: URLError(SSLCertVerificationError(1,
    '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable
    to get local issuer certificate ...'))`.  That is the very text a
    python.org macOS install prints without its certificates, and it
    leads anyone who searches for it to `Install Certificates.command`,
    so a hint in the paste would cost a line to say what the message
    already says.  What a real Mac adds is whether it fails this way at
    all.

* **Windows and macOS are untried. (2wmau)**  Everything here has been
  verified on Linux only, under CPython 3.11 and 3.12.  `nopip3` and
  `alt_venv.py` both use `pathlib` and `sys.executable` rather than
  spelling out paths, so nothing is known to break, but nothing has been
  run either; `2btosc` is the one specific worry, for macOS.  Carried
  over from `2hmmdrpe`.

  Various thoughts:
  * Wayne (2026-09-22): It would be nice to test on Windows and MacOS.
  * Wayne (2026-09-22): I know people who have these machines and would be glad
    to help.  Until then, the answer is currently unknown.
  * Wayne (2026-10-01): Access to macOS and Windows machines is in
    progress.

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
  * Wayne (2026-10-01): My thoughts on `LOGBOOK.md` have been morphing,
    and I'm leaving it alone for now.  The key thing is that it uses
    `{}` for closed tasks; Task 6 is still open, so braces are not
    appropriate there yet.  Task 6 grew into a parallel development
    strategy, and how `LOGBOOK.md` should change for that needs
    thought.  Leave this open, since it is going to be a while.

### Rejected Issues

Approaches that were considered and declined, recorded so that they
are not proposed again.

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
  * Wayne (2026-10-01): Rejected.  I don't care if an extra download
    occurs.

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

* **Where should the cache directory live? (2wscdl)**
  (CLOSED 2026-10-01)  `~/.cache/<program>/`
  per the XDG spec, or beside the program, or the `~/.alt_venv`
  that Experiment 1 assumed without examining?  This interacts with
  `0nicav`: whatever the location, the name has to carry the
  interpreter and platform.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.
  * Wayne (2026-10-01): Clear it belongs in `~/.alt_venv` somewhere, so
    this can be closed.

* **The stashed `pip` is never updated. (3spinu)**
  (CLOSED 2026-10-01)  `pip.whl` is
  fetched once and kept until `~/.alt_venv` is deleted, so a machine
  that bootstrapped this year is still running this year's `pip` in
  five years, with whatever it did not yet know about indexes, wheel
  tags and security fixes.  A possible solution is for `AltVEnv` to
  refresh it during `cull`, which already runs about once a day.

  Various thoughts:
  * Claude (2026-10-01): Fixed by Step 6.15.16, close to the solution
    proposed but weekly rather than daily, and adding newer wheels
    beside `pip.whl` rather than replacing it.

* **A failed `pip` fetch is poorly explained. (3fpfipe)**
  (CLOSED 2026-10-01)  If the JSON
  API lists no wheel for `pip`, case 13's `next(...)` raises a bare
  `StopIteration`, and the person sees `cannot fetch alt_venv: ` with
  nothing after it.  The SHA-256 digest is in the same JSON and is
  never checked, so a truncated download surfaces as a zip error from
  `python pip.whl/pip` rather than as a failed fetch.

  Various thoughts:
  * Wayne (2026-10-01): We'll improve this later.
  * Claude (2026-10-01): Half done by Step 6.15.7.  The message now
    names the stage and the exception's type, so the empty `StopIteration`
    case reads `... choose pip failed: ValueError: ...` instead of
    nothing.  The unchecked SHA-256 digest remains.
  * Claude (2026-10-01): The other half is done too, by Step 6.15.15:
    the download is checked against its SHA-256 before it is written.

* **How many machines does requiring `pip` exclude? (2hmmdrpe)**
  (CLOSED 2026-10-01)  The
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
  * Claude (2026-10-01): Step 6.15 removes the requirement this issue
    measures.  Case 13 fetches its own `pip`, so a machine without one
    gets a bootstrap rather than a diagnosed failure, and the question
    of how many such machines exist no longer decides anything.  What
    survives is Wayne's first thought: Windows and macOS are untried.
    I would close this and carry that part into a new issue.
  * Claude (2026-10-01): Closed with Wayne's agreement: `nopip3` ships,
    so nothing requires `pip` and the count this issue wanted no longer
    matters.  Its one live part, Wayne's note that Windows and macOS are
    untried, carries on as `2wmau`.

* **The wheel tag matcher is a five-line stand-in. (2wtmifs)**
  (CLOSED 2026-10-01)  Cases
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
  `coverage`, which has compiled wheels.  The 51 pasted lines the
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
  * Claude (2026-09-28): Measured against **real** PyPI, by Step 6.17.5,
    and there are now two concrete faults rather than one worry.
    `cryptography` cannot be fetched at all: an abi3 wheel is tagged
    with the lowest Python it supports, so the real names are
    `cp39-abi3` and `cp311-abi3` while the matcher looks for
    `cp312-abi3`.  And the musl confusion is confirmed --
    `charset_normalizer` publishes `cp312-cp312-musllinux_1_2_x86_64`
    alongside its manylinux wheel, and only PyPI's ordering keeps a
    glibc machine off the musl one.  `certifi` and `coverage` both
    fetch correctly.  The abi3 gap is pinned by an
    `@unittest.expectedFailure` in `PyPITest`.
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
  * Claude (2026-10-01): Closed with Wayne's agreement.  The matcher lives
    only in `nopip1` and `nopip2`, which are measurement and will not
    ship; `nopip3` leaves choosing wheels to `pip`.  The abi3 and musl
    faults are real but can no longer reach a stranger.

* **The venv executable directory is hard-coded. (3vedih)**
  (CLOSED 2026-10-01)  Cases
  4 and 11 reach into `root / "bin"` at `bootstrap.py:296`, `400` and
  `407`.  On Windows a virtual environment puts its executables in
  `Scripts`, so the pip reclaim would silently delete nothing and
  case 11's subprocess would not find an interpreter at all.  The
  inconsistency is inside a single case body: the same code checks
  `os.name != "nt"` when choosing symlinks, and asks `sysconfig` for
  the platform's site-packages, then hard-codes `bin`.  Nothing
  breaks on Linux, which is the whole of the current scope.

  Various thoughts:
  * Claude (2026-10-01): Closed with Wayne's agreement.  The hard-coded
    `bin` is only in `venv3` and `venv4`, which will not ship.

* **`.pth` files are installed but never executed. (3pfaibne)**
  (CLOSED 2026-10-01)  Every case
  writes coverage's `a1_coverage.pth`, its hook for measuring
  subprocesses, and no case runs it, because only `site.addsitedir()`
  executes `.pth` files and every case uses `sys.path.insert`.  Any
  package relying on a `.pth` is quietly half-installed.  Switching
  to `site.addsitedir()` is the obvious experiment.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.
  * Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.9.2 has
    `alt_venv.py` run `.pth` files through `site.addsitedir`, and the
    bootstrap installs nothing but `alt_venv`, which ships none.

* **How should required packages be declared? (2hsrpbd)**
  (CLOSED 2026-10-01)  Every case has
  `PACKAGE = "coverage"` written into it.  Reusing the PEP 723
  `# /// script` block instead would make the same program work under
  `uv run` for free, and would let one bootstrap serve a list of
  packages rather than one.

  Various thoughts:
  * Wayne (2026-09-22): Sounds like it is worth doing.  The question is when?
  * Claude (2026-10-01): Closed with Wayne's agreement.  Step 6.7 settled
    it: a PEP 723 block, read by `install()` with no arguments, and the
    bootstrap fetches only `alt_venv`.

* **The bootstrap fetches the newest `pip` regardless of Python.
  (1bfnprp)**
  (CLOSED 2026-10-01)  Case 13 takes whatever wheel the JSON API lists for the
  current `pip` release.  `pip` 26.2.1 requires Python 3.10, so today
  that is harmless, but when `pip` drops 3.11 every pasted copy of the
  bootstrap running on 3.11 will fetch a `pip` it cannot run.  That is
  a defect in code pasted into somebody else's program, where nobody is
  around to fix it, which is an argument for priority 0.  A possible
  solution is to read `/pypi/pip/json` for every release and pick the
  newest whose `requires_python` admits the running interpreter, at the
  cost of some pasted lines.

  Various thoughts:
  * Wayne (2026-10-01): Needs more discussion.
  * Claude (2026-10-01): Fixed by Step 6.15.7.  `nopip3` takes the newest
    upload whose `requires_python` floor this Python meets, so a Python
    that `pip` drops keeps the last `pip` that supported it.

* **Nothing identifies a cache as valid. (0nicav)**
  (CLOSED 2026-10-01)  Every case installs into
  `~/.alt_venv` with no version, platform tag or interpreter
  version in the path.  Experiment 1 installs
  `tracer.cpython-312-x86_64-linux-gnu.so`, so the same directory
  reached by a different Python, or copied to a different machine,
  would load a shared object built for something else.  This is a
  correctness bug waiting rather than a tidiness question.

  Various thoughts:
  * Claude (2026-10-01): Covered by Step 6.3's versioned cache.
    `version_key` names every unpacked tree after the interpreter's
    cache tag and the platform, so another Python or another machine
    gets a tree of its own.  The one thing installed unversioned is
    `alt_venv` itself, which is pure Python.

* **`pip._internal` is not a public API. (0pinpa)**
  (CLOSED 2026-10-01)  Six of the twelve
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
  * Wayne (2026-10-01): Closed, because we are downloading `pip`, and the
    cases that import `pip._internal` are going away.

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
