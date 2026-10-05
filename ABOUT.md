# About AltVEnv

<!-- --------------------------- 79 characters ---------------------------- -->

This file is the project's background: the problem it solves, its
goals, the prior art and the first thoughts about it.  It was the
front of `LOGBOOK.md` until 2026-10-04, when the work moved to
`TASKS/` and the issues to `ISSUES.md`.

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
