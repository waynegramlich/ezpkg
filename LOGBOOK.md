# Embedded Virtual Environment Logbook

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

## Task 2: Create the Bootstrap Code  (CLOSED 2026-09-22)

This task was called Experiment 1 while it ran.  The text below, and
several issues, still use that name.

{The last sentence is a note from the future.  The name was settled
while Task 4 ran; when this task began no such package existed, which is
what the rest of the paragraph assumes.}

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

## Task 3: Master `pip` and Package Servers  (CLOSED 2026-09-24)

This task was called Experiment 2 while it ran.  The text below, several
issues, and `embedded_venv_test.py` still use that name.

{`embedded_venv` was developed during this task, so "to be developed"
describes only where it started.}

The ultimate goal is to build a testing framework that allows installing
the `embedded_venv` (to be developed) package from a `pip` compatible
server (e.g. `pypiserver`) and load it into a program via the bootstrap
technology developed in the previous experiment.

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

### Task 3 Summary

The pipeline works end to end.  A wheel is built from
`embedded_venv.py`, published into a PEP 503 directory tree, fetched by
a `bootstrap.py` case pointed there by environment variables alone,
installed into `~/.embedded_venv`, and imported.  Both builders live in
`embedded_venv_test.py` and use nothing but the standard library, so no
packaging tool had to be installed to make a package.

`EmbeddedVEnv` stopped being empty.  Constructing one creates the cache
directory and writes a `README.md` into it from the constructor's own
docstring.  `include()` installs a package into the cache with
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

Decisions about the format of `LOGBOOK_NOTES.md` are in a file called
`claude_notes.md` that resides as separate file in another directory
with its on separate version control.

## Task 5: A Real Package Server

Cases 3 and 12 cannot be tested against a directory.  They do not speak
the PEP 503 simple API at all: they fetch
`https://pypi.org/pypi/{PACKAGE}/json`, which is PyPI's JSON API, and
`urllib` knows nothing of `PIP_INDEX_URL`.  So this task has to either
serve that JSON shape from a local server or teach those two cases the
simple API instead, and the second choice changes their line counts and
therefore the `paste` column.

Carried over from Task 3:

* An automated end to end test: run each `pip` based `bootstrap.py` case
  against a local index and assert that `embedded_venv` lands in the
  cache and imports.  This needs no server and is the cheapest of the
  three.
* The failure cases that are still untested: a truncated wheel and a
  missing `index.html`.  An index that does not hold the requested
  package is already covered.
* The server itself, which also makes TLS and the `ca-certificates`
  dependency testable for the first time.


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
  `~/.embedded_venv` with no version, platform tag or interpreter
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

* **What happens with no network? (0whwnn)**  Undefined in all twelve
  cases.  Should the bootstrap fail, or fall back to whatever the
  system already provides?

  Various thoughts:
  * Wayne (2026-09-22): We are going to die without the network to fetch the
    package. We need to at least let the user know that we died because we
    could not get the package.
  * Claude (2026-09-24): The second stage does this now.
    `EmbeddedVEnv.include` raises `RuntimeError` carrying pip's own standard
    error, so a caller is told why rather than left with an import failure.
    The twelve bootstrap cases still do not, and they are the half that runs on
    a stranger's machine.

* **An already-importable package is installed anyway. (2apiia)**  All
  twelve cases ask whether the package is on disk at their own target,
  never whether it is already importable.  With `coverage` present in an
  active virtual environment, a case spends 1.42 s and 1.8 MB
  installing a copy it will not use, where a leading `try: import`
  costs 0.10 s.  Cheap to fix; deliberately not fixed yet.

  Various thoughts:
  * Wayne (2026-09-22): This can be dealt with much later since it is easy to
    fix.
  * Claude (2026-09-24): Fixed in the second stage.  `EmbeddedVEnv.include`
    asks `contains` first and skips the install when the package is already in
    the cache.  The twelve cases are unchanged, so the measurement in Task 2
    still shows the defect.

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
  per the XDG spec, or beside the program, or the `~/.embedded_venv`
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
  stub's job is to fetch `embedded_venv`, which is pure Python and
  ships as `py3-none-any`, so no tag matching is needed for it at
  all; the matcher exists only because Experiment 1 fetched
  `coverage`, which has compiled wheels.  The 49 pasted lines the
  table charges the pure standard library path are therefore priced
  against the wrong package, and that number should be remeasured
  before it is used to justify anything.

  Various thoughts:
  * Wayne (2026-09-22): Let's revisit this issue after Experiment 2.

* **`.pth` files are installed but never executed. (3pfaibne)**  Every case
  writes coverage's `a1_coverage.pth`, its hook for measuring
  subprocesses, and no case runs it, because only `site.addsitedir()`
  executes `.pth` files and every case uses `sys.path.insert`.  Any
  package relying on a `.pth` is quietly half-installed.  Switching
  to `site.addsitedir()` is the obvious experiment.

  Various thoughts:
  * Wayne (2026-09-22): I have no idea what this issue is about.  Let's do the
    experiment when we get the chance.

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
is gone.  None at present.
