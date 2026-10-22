# `EZPkg`: Easy Python Packages

`EZPkg` (pronounced "easy package") grew out of the desire to send a simple
one-file Python program to a friend.  When said friend tried to run it,
a few packages were missing, so the friend had to create a virtual environment
and install them.  It worked, but it was annoying.  So the question became
"Could this be made really easy for the recipient?"  Thus was born `EZPkg`,
which lets a single-file Python program download its missing packages all
by itself.

To get started with `EZPkg`, you paste a modest bootstrap at the front of
your program and go.  After that, `EZPkg` fetches your packages over the net
on demand.  Once everything is working with `EZPkg`, `EZPkg` can easily make
a release in one of three formats - "email", "zipapp", or "uv".

<!--Claude: Keep this table of contents in sync with all `##` headers. -->
Table of Contents:
* [Quick Start](#quick-start)
* [Running a Program That Uses `EZPkg`](#running-a-program-that-uses-ezpkg)
* [Enabling `EZPkg` for a Program](#enabling-ezpkg-for-a-program)
* [Releasing a Packaged Program](#releasing-a-packaged-program)
* [The Bootstrap](#the-bootstrap)
* [Security](#security)
* [Miscellaneous](#miscellaneous)
* [How `EZPkg` Actually Works](#how-ezpkg-actually-works)
* [Missing Sections](#missing-sections)
* [Conclusion](#conclusion)

## Quick Start

To get started, please take the program below and paste it into a file
named `quick_start.py` on your computer.  The bulk of this program is the
`EZPkg` bootstrap, Part 2.  This is the "magic" that skips the
hassle of virtual environments.  Then run it as the next section shows.
<!-- Claude: Always keep the Bootstrap code up-to-date with the real one. -->

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]
# ///
"""Try `EZPkg`: fetch the `cowsay` package on first use, then run."""

# Part 2: The EZPkg bootstrap.  Paste all of it, `# Begin` to `# End`,
# below your docstring and any `from __future__` lines.
# Begin the EZPkg bootstrap.  Never edit it.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

try:  # Do not edit try block!  See https://pypi.org/project/ezpkg/
    s = "find ezpkg"; t = pathlib.Path.home()/".ezpkg"; w = t/"ezpkg.whl"
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = None; m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not w.is_file():  # Not downloaded yet.
        s = "download ezpkg"; d = g("https://pypi.org/pypi/ezpkg/json")
        e = next(e for e in json.loads(d)["urls"] if e["url"][-4:] == ".whl")
        r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"ezpkg.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
    if m is None:  # Python imports it straight from the wheel.
        s = "import ezpkg"; sys.path.insert(0, str(w))
        m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip8")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!
# End the EZPkg bootstrap.  Your imports go below it.

# Part 3: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 4: The program itself.
cowsay.cow("EZPkg works!")
print(f"The cow above was drawn by cowsay {cowsay.__version__}.")
```

## Running a Program That Uses `EZPkg`

The `quick_start.py` program is run as follows:
* Windows: `py quick_start.py`
* Linux/macOS: `python3 quick_start.py`

On Windows, if `py` is not found, use `python` instead, here and below.

The first time `quick_start.py` runs, it prints the following:

```
The author of `quick_start.py` has selected some software packages from the
internet.  If you agree, they are retained in `~/.ezpkg`.  If you do not trust
the author, answer `n` and `~/.ezpkg` will simply go away without running
`quick_start.py`.

Retain `~/.ezpkg` and run `quick_start.py`?
[y=>Yes|n=>No|?=>Explain]:
```

The three options are:
* `y=>Yes`:
  Answer `y`, and `EZPkg` lists what it retained in `~/.ezpkg` (only this
  once), and then the program runs.
* `n=>No`:
  The newly downloaded packages are removed and the program does not run.
  On the very first run, all of `~/.ezpkg` is removed.  Pressing Control-C
  or not answering within 5 minutes is treated as `n`.
* `?=>Explain`:
  This lists the packages in question and repeats the question.

Lastly, the prompt is skipped when there is nobody at a terminal to answer it
(e.g. `cron` or a test system), and `y` is assumed.

After a `y`, the first run generally looks as follows, though the version
numbers may differ:

```
The following 3 package(s) are now retained in `~/.ezpkg`:
1. pip 26.2.1 (used by `ezpkg`): The PyPA recommended tool for installing Py...
2. ezpkg 0.0.1: Automatic Package Fetching for One-File Programs
3. cowsay 6.1: The famous cowsay for GNU/Linux is now available for python
`ezpkg` (https://pypi.org/project/ezpkg/) manages `~/.ezpkg`.

  ____________
| EZPkg works! |
  ============
            \
             \
               ^__^
               (oo)\_______
               (__)\       )\/\
                   ||----w |
                   ||     ||
The cow above was drawn by cowsay 6.1.
```

The list includes `pip` and `ezpkg` only on a machine's very first run,
when they have just been fetched; `pip` is the tool `ezpkg` uses,
not one the program's author chose.  On Windows, the full path, such as
`C:\Users\YOUR_NAME\.ezpkg`, is shown instead of `~/.ezpkg`.

Now run it a second time.  There is no question and no download, and it
starts in a fraction of a second, because `cowsay` is already in
`~/.ezpkg/`.  The next time you run the program, you will not be asked for
permission to store files in `~/.ezpkg/`.

There are basically 4 things that can go wrong:
* **No Network**:
  The network is needed only when a program needs packages that are not
  yet in `~/.ezpkg`.
* **No Version Available**:
  The version the author chose is no longer on PyPI, or none was built
  for your computer and Python.
* **`pip` Failure**:
  `pip` ("`pip` Installs Packages") is the standard tool that fetches
  Python packages, and it can fail for other reasons.
* **Not Approved**:
  The author sent a `.py` that has not been through a release, and this
  computer needs a package the author's computer did not.  The solution is
  to ask the author for a released version of the program; see
  [Releasing a Packaged Program](#releasing-a-packaged-program).

For each issue above, one line is printed and the program does not run.
For further details of what went wrong, read `~/.ezpkg/last_failure.txt`,
which every failure updates.

If you want to remove the `~/.ezpkg` directory and its contents, do the
following:
* Windows (PowerShell): `py $HOME\.ezpkg\remove.py`
* Windows (`cmd.exe`): `py %USERPROFILE%\.ezpkg\remove.py`
* Linux/macOS: `python3 ~/.ezpkg/remove.py`

While it is always safe to remove `~/.ezpkg`, note that if you run
`quick_start.py` again, the `~/.ezpkg` directory will return.

## Enabling `EZPkg` for a Program

To enable `EZPkg` in your program `PROG_NAME.py` (with `PROG_NAME` replaced
by your program's name):
1. Copy Part 2 of `quick_start.py`, from `# Begin the EZPkg bootstrap.`
   through `# End the EZPkg bootstrap.`, and paste it below your program's
   top-level docstring (and any `from __future__` lines), but above your own
   imports.
2. Beside `PROG_NAME.py`, create an empty `PROG_NAME.py.toml`:
   * Windows (PowerShell): `ni PROG_NAME.py.toml`
   * Windows (`cmd.exe`): `type nul > PROG_NAME.py.toml`
   * Linux/macOS: `touch PROG_NAME.py.toml`
3. Run `PROG_NAME.py`.

The `PROG_NAME.py.toml` makes you the program's developer: `EZPkg` asks you
nothing and fetches whatever your imports need.  Your `PROG_NAME.py` is never
edited; a release writes the packages and their versions into the copies
it makes.  On the first run, `EZPkg` fills the empty `PROG_NAME.py.toml` with
its settings, each commented out at its default; see
[`prog.py.toml` Settings](#progpytoml-settings).  Without `PROG_NAME.py.toml`,
whoever runs `PROG_NAME.py` is an end user, the same as in the Quick Start.

### What are packages and where do they come from?

In short, a package is a chunk of code that can be imported into a Python
program for subsequent execution.  The most common place to fetch packages
from is the [Python Package Index](https://pypi.org) (PyPI), which is where
the Python community submits freely accessible packages.

A package evolves over time, undergoing both bug fixes and feature
enhancements.  These changes are managed by giving each released package a
different version number.  Furthermore, for performance reasons, some packages
are compiled to run on the native machine architecture (e.g. Intel, ARM,
RISC-V).  Likewise, some packages require specific features available only on a
specific operating system (e.g. Windows, Linux (Red Hat, Ubuntu), macOS).

Finding a set of packages that can interoperate with one another can be quite
challenging.  Ultimately, `EZPkg` encodes the package configuration in Python
inline script metadata format at the beginning of each released copy of the
Python file.  It is unlikely that you will ever need to read any of this
metadata.  `EZPkg` accomplishes all of this by scanning your Python program
for all `import` statements and reconciling them into a single, coherent,
versioned package set.

If you really want to dig in for more information, feel free to visit
the following references:
* [Python Package Index](https://pypi.org/):
  The most common place to store freely accessible Python packages.
* [Inline script metadata](
  https://packaging.python.org/en/latest/specifications/inline-script-metadata):
  The Python standard in-line configuration information.
* [TOML (Tom's Obvious Minimal Language)](https://toml.io/en/) format:
  This is the syntax used for the inline script metadata.
* [Dependency specifiers](
  https://packaging.python.org/en/latest/specifications/dependency-specifiers):
  This is the syntax of each entry in `dependencies=[...]`.

### `prog.py.toml` Settings

When `PROG_NAME.py` runs and `PROG_NAME.py.toml` is empty, `EZPkg` fills
it with the following, which explains every setting:

```toml
# PROG_NAME.py.toml: EZPkg settings for PROG_NAME.py, the program
# beside this file.  More: https://pypi.org/project/ezpkg/
#
# This file makes you the program's developer.  If you delete this file,
# you are no longer treated as a developer.  This file is the only place
# where your development decisions get recorded (i.e. there are no unexpected
# text prompts when the program runs).  All information that EZPkg collects
# is stored in files in the `~/.ezpkg/` directory and not this file.
#
# On each run, EZPkg fetches the packages the program's imports need
# and records the versions that were run.  A release writes both into
# the copies it makes, so that whoever you send a release to gets
# exactly those.  The program itself is never edited.  Without this file, the
# program is an end user's: they are asked once, on its first run,
# whether to keep its packages.
#
# Each setting below is shown at its default, mostly after a `#`.  To
# change one, remove its `#` and edit its value.  A misspelled setting or
# a wrong value stops the program, naming the line.  To see this text
# again, empty this file and run the program.

# How much EZPkg says: "none", "low" (one-off notices), "medium" (also
# each change to the packages) or "high" (also what was decided, and
# why).
# verbosity = "low"

# The versions are frozen at the date of the program's first run, so
# they never change by themselves.  With `upgrade = true`, every run
# takes the newest versions; put the `#` back to freeze them at the
# last run's date.
# upgrade = false

# How many days the packages the program uses may go unused before
# EZPkg removes them from ~/.ezpkg (they are fetched again if needed).
# cull-days = 30

# Releases: a release builds the copies you send to others, beside the
# program, and records each one in PROG_NAME.py.releases.  Releases are
# off until you remove the `#` from at least one entry of `exports` and
# from `release` below.  Then each run where `release` differs from the
# last one released builds that release, in place of the last one's
# files, and then runs the program as usual.  Each release checks the
# imports and the bootstrap, and gives each package without a version
# a range.  Anything worth a second look, such as a package name EZPkg
# had to guess, is listed under `warnings` in the release's entry in
# PROG_NAME.py.releases, and the release's one line says how many.
exports = [  # Remove the `#`s of the forms each release builds.
#   "email",   # PROG_NAME-VERSION.py, to send; for every computer.
#   "zipapp",  # PROG_NAME-VERSION.pyz, no network; pure Python only.
#   "uv",      # PROG_NAME-VERSION-uv.py and its lock, for `uv run`.
]

# The version of the next release.  Change it whenever you like, even
# to go back to an older number.
# release = "1.0.0"

# The bootstrap the program carries: "update" replaces an older one at
# the next release; a name, such as "nopip8", keeps exactly that one.
# bootstrap = "update"

# Rarely needed: EZPkg works these out, and you set them only when it
# gets one wrong.

# The Pythons the program runs on.  Each release works this out from
# the program's syntax and its packages (never older than 3.11, which
# EZPkg needs).  Set it if the program needs a newer Python anyway, as
# when it uses a library function that is new.
# requires-python = ">=3.11"

# Packages EZPkg cannot work out.  It finds a package for each import,
# with a range from the version you ran, takes a marker from a guard
# such as `if sys.platform == "win32":`, and adds a package when the
# program stops because one is missing.  For anything else, write an
# entry such as "numpy>=2.1" or "requests[socks]", a Python "dependency
# specifier", as explained at
# https://packaging.python.org/en/latest/specifications/dependency-specifiers/
# An entry here wins over the one EZPkg would choose for that package.
# dependencies = []
```

## Releasing a Packaged Program

Once you are satisfied with your program, you may choose to release it in
a more durable single file package.  Currently three formats are supported:
* **`email`**:
  Email format is just a single Python file (e.g. `YOUR_PROG.py`) that has
  had all of its inline metadata dependencies updated.  When emailed to
  another person, the `EZPkg` bootstrap ensures that all of the required
  packages are downloaded prior to running the program.
* **`zipapp`**:
  This works for pure Python programs (i.e. no packages with C, C++, Rust,
  etc.) and produces a `.pyz` file.  The file can be quite large since it
  includes all of the needed code.  All that the recipient needs is a Python
  interpreter; no network is needed.  It produces a file
  `YOUR_PROG-X.Y.Z.pyz`, where `YOUR_PROG` is the program name and `X.Y.Z`
  is the version number.
* **`uv`**:
  `uv` is a popular packaging system written in Rust.  It handles both
  compiled and pure Python packages together.  The recipient must have `uv`
  installed, and `uv` fetches the packages over the network on the first run.

The requirement is that at least one of the values for `exports = [ ... ]`
is enabled (`email`, `zipapp` or `uv`).  Once `exports = [ ... ]` is set, run your program.  As a side
effect of running your program the appropriate files are generated.  Whenever
an import is added or removed, the appropriate generated files are
(re)generated.

## The Bootstrap

Never edit the bootstrap, not even a space or a comment.  Indenting the
whole of it, as under an `if`, is the one change allowed.  Anything else
stops the program, which shows each line that differs from the published
bootstrap.

An older bootstrap that has not been edited still runs, so a program that
nobody maintains keeps working.  When you are the developer, `EZPkg` tells
you once about each newer bootstrap, and the next release replaces it.

## Security

`EZPkg` fetches code from the internet and runs it, so here is who you
are trusting:
* **The program's author**:
  The one question on a first run is about them.  If you do not trust
  them, answer `n`.  A `y` also covers later versions of the program
  that they send you.
* **PyPI**:
  Every package, `ezpkg` included, comes from the
  [Python Package Index](https://pypi.org), and each download is checked
  against the checksum PyPI publishes for it.
* **Exactly what the author ran**:
  Once its author has run a program with `EZPkg`, the program carries a
  checksum of every package file it ran with.  A file that differs, such
  as one re-uploaded to PyPI later, is refused before anything in it
  can run.
* **Nothing outside `~/.ezpkg`**:
  No administrator rights are needed, and your Python and its `pip` are
  never changed.

## Miscellaneous

Here are some miscellaneous observations:
* **Garbage collection**:
  Packages that no program has used for about six months are removed,
  checked at most once a day.
* **No duplication**:
  Programs that need the same package share one copy.
* **Versions side by side**:
  Programs that need different versions of a package each get their own.

<!-- Claude: (2026-10-21) Proposed bullets for this list: the
limitations, and an `ezpkg` that is already installed.

* **One version per program**:
  A running program can import only one version of a package, so two
  parts of one program cannot use different versions of the same one.
* **A program needs its own file**:
  `python -c "..."` and code typed at the `>>>` prompt get the packages
  but none of the checks, since there is no file to read Part 1 from.
* **Where it has been tried**:
  Linux, Windows and macOS (Intel and Apple Silicon) on GitHub's test
  machines, Python 3.11 to 3.15; not yet on many people's own computers.
* **An `ezpkg` that is already installed**:
  When `ezpkg` is already importable, as under `uv run` or after `pip
  install ezpkg`, the bootstrap uses it and downloads nothing.  Part 1's
  `ezpkg` entry still decides which version runs the program.

(`zipapp` and compiled packages is already said in Releasing.)
-->

## How `EZPkg` Actually Works

This section is for the curious-minded.  Feel free to skip it unless you
are interested in puzzling out how the `EZPkg` bootstrap actually works
on your own.

Please open `quick_start.py` and go to `# Part 2: ...`.  The entire
bootstrap runs inside a Python `try` block.  Before each step, the
variable `s` is set to the step's name, so that if anything goes wrong,
the `except` at the bottom stops the program with
`ezpkg: <step> failed: ...`, naming the step that broke.  The steps are:
* `s = "find ezpkg"`:
  * This names `~/.ezpkg/ezpkg.whl`, where `ezpkg` is kept, and tries
    `import ezpkg`.  That succeeds when something like `uv run` has
    already provided it.
  * If `ezpkg` imported, or `~/.ezpkg/ezpkg.whl` already exists, the
    download is skipped.  It runs only the first time any program uses
    `EZPkg` on a machine.
* `def g(u)`:
  * This fetches a URL for the download.  If Python cannot, it asks
    `curl` instead.  That happens with the Python installer from
    python.org on macOS, which has no certificates (and so cannot check
    that it is really talking to PyPI) until its
    `Install Certificates.command` has been run.  Every Mac has `curl`,
    which uses the Mac's own certificates.
* `s = "download ezpkg"`:
  * This asks [PyPI](https://pypi.org/) for the newest `ezpkg` wheel,
    downloads it, checks its SHA-256 against the one PyPI publishes, and
    keeps it as `~/.ezpkg/ezpkg.whl`.  A wheel is a zip file, and the
    rename at the end means no program ever sees half of one.
* `s = "import ezpkg"`:
  * This puts `~/.ezpkg/ezpkg.whl` at the front of `sys.path` and
    imports `ezpkg` straight from it, since Python can import pure
    Python code from inside a zip file.  Nothing is installed.
* `s = "fetch packages"`:
  * `m.EZPkg()` sets up the `~/.ezpkg` directory, and `.install()`
    reads Part 1, downloads any packages not already there, and puts
    them on `sys.path`, so that the imports in Part 3 succeed.
  * `bootstrap="nopip8"` names the bootstrap this program carries.
  * If Part 1's `ezpkg` entry asks for a different version, this `ezpkg`
    fetches that one and starts the program again with it.

`ezpkg` fetches packages with `pip`, the standard tool.  It downloads
its own copy of `pip`, the newest one your Python can run, and keeps it
as `~/.ezpkg/pip.whl`, because some commonly used Linux releases (e.g.
Ubuntu) do not include `pip` with the base Python installation, and
others refuse to let it install into the system's Python
([PEP 668](https://peps.python.org/pep-0668/)).  The machine's own
`pip`, if it has one, is never changed.

<!-- Claude: (2026-10-21) Proposed new section, with a table of contents
entry `* [Troubleshooting](#troubleshooting)`.  Messages abbreviated.

## Troubleshooting

These are the messages a developer is most likely to meet, and what to
do about each.  An end user sees only the one-line failures in [Running a
Program That Uses `EZPkg`](#running-a-program-that-uses-ezpkg).
* **``prog.py.toml line 3: unknown setting `relase` (did you mean
  `release`?)``**:
  Fix the spelling in `prog.py.toml`; the program does not run until
  every setting is known.
* **``prog.py line 7: `import tabulat` needs a package, but PyPI has none
  called `tabulat` ``**:
  Usually a misspelt import.  If the package's name on PyPI differs from
  the module's, add the right name to `dependencies` yourself.
* **``line 12: `cowsay` is imported above the bootstrap; move it below,
  with the other imports``**:
  On a computer whose `~/.ezpkg` is still empty, that import runs before
  anything has been fetched, so it fails there even though it works for
  you.
* **An edited bootstrap**:
  `EZPkg` stops, showing each line that differs from the published
  bootstrap, with a `|` under the first different character.  Paste the
  bootstrap again from `quick_start.py`.
* **``prog.py line 14 imports `tabulate`, but no release of it existed
  before the date prog.py's versions are frozen at ...``**:
  Your versions are frozen at the `exclude-newer` date in Part 1.  Delete
  that line, as the message says, to move everything to today's
  versions.
* **``prog.py 1.0.1 was not released: ...``**:
  The release stopped for the reason given; `prog.py` still runs, and the
  next run tries the release again, so fix the reason and run it.

-->

<!-- Claude: (2026-10-21) Proposed new section, with a table of contents
entry `* [The Project](#the-project)`.  The license: the repository's
`LICENSE` has been MIT No Attribution (SPDX `MIT-0`) since 2026-10-10,
and the source files and the test.pypi.org wheel say so too.  MIT-0 is
MIT without the condition that copies keep the copyright notice.  If you
want plain MIT (SPDX `MIT`) instead, it is four files and the wheel's
`License` field to change.

## The Project

* **Source**: https://github.com/waynegramlich/ezpkg
* **Problems and suggestions**:
  https://github.com/waynegramlich/ezpkg/issues
* **License**: MIT No Attribution (`MIT-0`); see
  [`LICENSE`](https://github.com/waynegramlich/ezpkg/blob/main/LICENSE).
-->

## Missing Sections

<!-- Issue: Sections that seem to be missing:
* Troubleshooting: the messages a developer can meet (a misspelt import, a
  misspelt setting, a failed fetch, a package newer than the date, an
  import above the bootstrap, an edited bootstrap), each with what to do.
* Limitations: compiled packages and `zipapp` (`I.htdwcp`); one version of
  a module per process; Windows and macOS tested on GitHub's runners only
  (`I.wmau`); programs with no file of their own (`python -c`) get no
  checks.
* Programs run by `uv run` or with `ezpkg` already installed (`pip install
  ezpkg`): the bootstrap uses that `ezpkg`.
* License, source repository (https://github.com/waynegramlich/ezpkg) and
  how to report a problem, which PyPI's project page shows readers.
-->

## Conclusion

`EZPkg` does all of the package downloading and dependency checking for you.
When you are done, you can literally email someone one of the following
results:
* **`email`**:
  A single `.py` file with the `EZPkg` bootstrap embedded in it.
  The resulting program needs network access to download needed packages.
  After they are downloaded, the network is no longer needed.
* **`zipapp`**:
  A single `.pyz` file that can be directly executed by a Python interpreter.
  `zipapp` requires that all packages be pure Python without any packages
  that contain non-Python code (e.g. C, C++, Rust).  No network access
  is needed for a `zipapp` `.pyz` file.
* **`uv`**:
  In addition to having `uv` installed, the user needs two files:
  * A `.zip` file that contains all of the data.
  * A `uv.lock` file that is used to unlock everything.

All of the hassle of managing packages is handled by `EZPkg`.
