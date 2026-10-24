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

Table of Contents:
* [Quick Start](#quick-start)
* [Running a Program That Uses `EZPkg`](#running-a-program-that-uses-ezpkg)
* [Enabling `EZPkg` for a Program](#enabling-ezpkg-for-a-program)
* [Releasing a Packaged Program](#releasing-a-packaged-program)
* [The Bootstrap](#the-bootstrap)
* [Security](#security)
* [Miscellaneous](#miscellaneous)
* [How `EZPkg` Actually Works](#how-ezpkg-actually-works)
* [Troubleshooting](#troubleshooting)
* [Project Information](#project-information)
* [Conclusion](#conclusion)

## Quick Start

To get started, please take the program below and paste it into a file
named `quick_start.py` on your computer.  The bulk of this program is the
`EZPkg` bootstrap, Part 2.  This is the "magic" that skips the
hassle of virtual environments.  Then run it as the next section shows.

```python
#!/usr/bin/env python3
# Part 1: These lines look like `#` comments, but they are Python's inline
# script metadata (PEP 723) that the EZPkg bootstrap needs.  Never remove them.
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
    s = "fetch packages"; m.EZPkg().install(bootstrap="2026-10-23")
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
* Windows: `py quick_start.py` or `python quick_start.py`
* Linux/macOS: `python3 quick_start.py`

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
  The author sent a `.py` that has not been produced as an `EZPkg` release,
  and this computer needs a package the author's computer did not.  The
  solution is to ask the author for a released version of the program; see
  [Releasing a Packaged Program](#releasing-a-packaged-program).

For each issue above, one line is printed and the program does not run.
For further details of what went wrong, read `~/.ezpkg/last_failure.txt`,
which every failure rewrites.

If you want to remove the `~/.ezpkg` directory and its contents, do the
following:
* Windows (PowerShell): `py $HOME\.ezpkg\remove.py`
* Windows (`cmd.exe`): `py %USERPROFILE%\.ezpkg\remove.py`
* Linux/macOS: `python3 ~/.ezpkg/remove.py`

While it is always safe to remove `~/.ezpkg`, please note that if you run
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
[`PROG_NAME.py.toml` Settings](#progpytoml-settings).  Without
`PROG_NAME.py.toml`, whoever runs `PROG_NAME.py` is an end user, the same
as in the Quick Start.

### What are packages and where do they come from?

Since the primary purpose of `EZPkg` is to manage Python packages, it is
prudent to discuss a little bit more about them.

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
metadata.  If you look at the `quick_start.py` example, the information between
the `# /// script` and `# ///` lines is a very short example of the metadata.
`EZPkg` accomplishes all of this by scanning your Python program
for all `import` statements and reconciling them into a single, coherent,
versioned package set.

Frankly, `EZPkg` is trying to do all of the hard work of managing the
metadata and other stuff so that you do not need to.  However, if you are curious,
the following references provide a great deal of additional information:
* [Python Package Index](https://pypi.org/):
  The most common place to store freely accessible Python packages.
* [Inline script metadata](
  https://packaging.python.org/en/latest/specifications/inline-script-metadata):
  The Python standard inline configuration information.
* [TOML (Tom's Obvious Minimal Language)](https://toml.io/en/) format:
  This is the syntax used for the inline script metadata.
* [Dependency specifiers](
  https://packaging.python.org/en/latest/specifications/dependency-specifiers):
  This is the syntax of each entry in `dependencies=[...]`.

### `PROG_NAME.py.toml` Settings

When PROG_NAME.py runs and finds an empty PROG_NAME.py.toml file, EZPkg
fills it with exactly the content shown below (i.e. from
"# Start of PROG_NAME.py.toml:" to "# End of PROG_NAME.py.toml".)

```toml
# Start of PROG_NAME.py.toml:

# This file is meant to be self-documenting.  It contains the EZPkg settings
# for PROG_NAME.py (i.e. your program).  More: https://pypi.org/project/ezpkg/

# This file is created as an empty file next to PROG_NAME.py, in the same
# directory.  Depending upon which operating system you are running, one of
# the following commands creates the empty file:
# * Windows (PowerShell): `ni PROG_NAME.py.toml`
# * Windows (`cmd.exe`): `type nul > PROG_NAME.py.toml`
# * Linux/macOS: `touch PROG_NAME.py.toml`

# The mere existence of PROG_NAME.py.toml classifies you as a developer of
# PROG_NAME.py.  Conversely, if you remove this file, you are no longer
# treated as a developer.  Instead, you will be asked on the program's first
# run whether its packages can be kept in the ~/.ezpkg directory.

# Whenever PROG_NAME.py.toml is empty and PROG_NAME.py is run, its contents
# are initialized to the text you are currently reading (i.e. from
# "# Start of PROG_NAME.py.toml:" to "# End of PROG_NAME.py.toml".)  After
# this file is created, only you (the developer) get to edit it.  If you
# want it reinitialized, empty the file and run PROG_NAME.py again.

# This file is the only place where your EZPkg rules are configured.  Any
# additional information collected by EZPkg is stored in various files in
# the `~/.ezpkg/` directory.  EZPkg only ever fills this file when it is
# empty, and never modifies it after that.

# All possible settings that can be set are shown as commented-out TOML
# lines.  To enable an option, just remove the preceding "# ".  For a list,
# such as "release", remove the "#" from each entry you want.  If you
# accidentally enable two conflicting options, EZPkg will produce an error
# message with line numbers for you to fix.

# The following configuration options exist:

# "verbosity" specifies how much EZPkg prints while the program runs.
# There are 4 levels of verbosity.  The default is "low":
# verbosity = "high"    # Also what EZPkg decided, and why.
# verbosity = "medium"  # Also each change to the packages.
# verbosity = "low"     # Only one-off notices (default).
# verbosity = "none"    # Nothing, except errors that stop the program.

# "update-frequency" specifies how often your runs move to newer package
# versions.  A release always carries the versions your last run used, so
# whoever receives it gets exactly what you tested.
# update-frequency = "never"    # Leave the current versions alone (default).
# update-frequency = "monthly"  # Move to the newest versions once a month.
# update-frequency = "weekly"   # Move to the newest versions once a week.
# update-frequency = "daily"    # Move to the newest versions once a day.

# "purge-unused-after" specifies how long a package may go unused before
# EZPkg removes it from ~/.ezpkg (it is fetched again if it is needed).
# purge-unused-after = "month"  # Unused for a month (default).
# purge-unused-after = "week"   # Unused for a week.
# purge-unused-after = "day"    # Unused for a day.

# "version" specifies the release string.  Whenever it differs from the
# last version released, the next run builds the releases listed in
# "release", and then runs the program as usual.  Change it whenever you
# like.  If you really need to, you can even reuse a previous value.
# version = "1.0.0"  # 1.0.0 is usually the first functional release number.

# "release" lists which releases to generate, each named with the VERSION
# above.  Remove the "#" from 0, 1, or more of the entries in the list.
release = [
#   "email",   # PROG_NAME-VERSION.py; email .py (network needed).
#   "zipapp",  # PROG_NAME-VERSION.pyz; pure Python (no network needed).
#   "uv",      # PROG_NAME-VERSION-uv.py and its lock (`uv` needed).
]
# Each release, and anything worth a second look, is recorded in
# PROG_NAME.py.releases.

# "bootstrap" specifies which EZPkg bootstrap the program carries.  Each
# bootstrap is named by the date it was published ("YYYY-MM-DD").
# bootstrap = "update"      # A release replaces an older one (default).
# bootstrap = "2026-10-23"  # Keep exactly this one.

# The next options are rarely needed.  Most people can stop reading now.
# They are needed for difficult situations that EZPkg simply cannot figure
# out on its own.

# "requires-python" specifies the oldest Python the program runs on.  EZPkg
# works this out from the program and its packages (never older than 3.11,
# which EZPkg itself needs).  Set it only when the program needs a newer
# Python for its own reasons, such as a library function that is new.
# requires-python = ">=3.11"  # The default: EZPkg itself needs 3.11.

# "dependencies" provides a way to manually specify values to be inserted
# into the dependencies portion of the Python inline script metadata.  They
# use the standard Python dependency specifier format.  See:
#
# https://packaging.python.org/en/latest/specifications/dependency-specifiers/
#
# Put every entry in the one list, which may span several lines.  If an
# entry conflicts with what EZPkg would choose, your entry wins.
# dependencies = ["numpy>=2.1", "requests[socks]"]  # For example.

# End of PROG_NAME.py.toml.
```

## Releasing a Packaged Program

Once you are satisfied with your program, you may choose to release it in
a more durable single file package.  Currently three formats are supported:
* **`email`**:
  Email format is just a single Python file, `PROG_NAME-VERSION.py`: a copy
  of `PROG_NAME.py` with its inline metadata filled in.  When emailed to
  another person, the `EZPkg` bootstrap ensures that all of the required
  packages are downloaded prior to running the program.
* **`zipapp`**:
  This works for pure Python programs (i.e. no packages with C, C++, Rust,
  etc.) and produces a `.pyz` file.  The file can be quite large since it
  includes all of the needed code.  All that the recipient needs is a Python
  interpreter; no network is needed.  It produces a file
  `PROG_NAME-X.Y.Z.pyz`, where `PROG_NAME` is the program name and `X.Y.Z`
  is the version number.
* **`uv`**:
  `uv` is a popular packaging system written in Rust.  It handles both
  compiled and pure Python packages together.  The recipient must have `uv`
  installed, and `uv` fetches the packages over the network on the first run.

The requirement is that at least one of the values for `release = [ ... ]`
is enabled (`email`, `zipapp` or `uv`), and that `version` is set.  Once
both are set, run your program.  As a side effect of running your program
the appropriate files are generated.  Whenever `version` changes, the
appropriate files are (re)generated.

## The Bootstrap

Never edit the bootstrap, not even a space or a comment.  Indenting the
whole of it, as under an `if`, is the one change allowed.  Anything else
stops the program, which shows each line that differs from the published
bootstrap.

An older bootstrap that has not been edited still runs, so a program that
nobody maintains will keep working.  When you are the developer, `EZPkg` tells
you once about each newer bootstrap, and the next release replaces it.

## Security

`EZPkg` fetches code from the internet and runs it, so here is who you
are trusting:
* **The program's author**:
  The one question on a first run is about them.  If you do not trust
  them, answer `n`.  A `y` is remembered, so you are not asked again.
* **PyPI**:
  Every package, `ezpkg` included, comes from the
  [Python Package Index](https://pypi.org), and each download is checked
  against the checksum PyPI publishes for it.
* **No substitutions allowed**:
  Once its author has run a program with `EZPkg`, the program carries a
  checksum of every package file it ran with.  A file that differs, such
  as one re-uploaded to PyPI later, is refused before anything in it
  can run.
* **All content is stored in the `~/.ezpkg` directory**, except:
  * `PROG_NAME.py.toml`, which is filled only when it is empty.
  * Up to 4 output files in total for the three possible release
    formats: "email" (1), "zipapp" (1) and "uv" (2).

## Miscellaneous

Here are some miscellaneous observations:
* **Garbage collection**:
  Packages that no program has used for 30 days are removed, unless a
  program's `PROG_NAME.py.toml` sets `purge-unused-after` for its own
  packages.
* **No duplication**:
  Programs that need the same package share one copy.
* **Versions side by side**:
  Programs that need different versions of a package each get the correct one.
* **One version per program**:
  A running program can import only one version of a package, so two
  parts of one program cannot use different versions of the same one.
* **Where it has been tested**:
  Linux, Windows and macOS (Intel and Apple Silicon) on GitHub's test
  machines, Python 3.11 to 3.15; not yet tried with the Microsoft Store,
  Homebrew or Apple's own Pythons.

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
    keeps it as `~/.ezpkg/ezpkg.whl`, which is actually just a zip file.
* `s = "import ezpkg"`:
  * This puts `~/.ezpkg/ezpkg.whl` at the front of `sys.path` and
    imports `ezpkg` straight from it.  Since Python can import pure
    Python code from inside a zip file, nothing is actually installed.
* `s = "fetch packages"`:
  * `m.EZPkg()` sets up the `~/.ezpkg` directory, and `.install()`
    reads Part 1, downloads any packages not already there, and puts
    them on `sys.path`, so that the imports in Part 3 succeed.  (This is
    why the user's import statements must be after the bootstrap.)
  * `bootstrap="YYYY-MM-DD"` names the bootstrap this program carries.
    They are always referred to by their published date.
  * If Part 1's `ezpkg` entry asks for a different version, this `ezpkg`
    fetches that one and restarts the program using it instead.

`ezpkg` fetches packages with `pip`, the standard Python tool.  It downloads
its own copy of `pip` (the newest one your Python can run) and keeps it
as `~/.ezpkg/pip.whl`.  This is because some commonly used Linux releases
(e.g. Ubuntu) do not include `pip` with the base Python installation and
other releases refuse to let it install into the system's Python
([PEP 668](https://peps.python.org/pep-0668/)).  The machine's own
`pip`, if it has one, is never changed.

A release also uses [`uv`](https://docs.astral.sh/uv/), the fast package
manager written in Rust.  `pip` only works out what *this* computer needs,
so a release asks `uv` to work out what every other computer needs too
(Windows, macOS, Linux, and each Python the program allows), held to the
versions your own runs approved.  If `uv` is not installed, `ezpkg`
fetches its own copy into `~/.ezpkg`, just as it does for `pip`.

## Troubleshooting

These are the messages a developer is most likely to meet, and what to
do about each.  An end user sees only the one-line failures in [Running a
Program That Uses `EZPkg`](#running-a-program-that-uses-ezpkg).
* **``PROG_NAME.py.toml line 3: unknown setting `relase` (did you mean
  `release`?)``**:
  Fix the spelling in `PROG_NAME.py.toml`; the program does not run until
  every setting is known.
* **``PROG_NAME.py.toml lines LINENO1 and LINENO2: `update-frequency` is set
  twice; keep only one of them``**:
  The `#` was removed from two lines of one setting.  Put it back on the
  one you did not mean.  (The message gives the actual line numbers.)
* **``PROG_NAME.py line 7: `import tabulat` needs a package, but PyPI has none
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
* **``PROG_NAME.py line 14 imports `PKG_NAME`, which is newer than
  YYYY-MM-DD, so PROG_NAME.py moves to today's versions ...``**:
  Nothing to do.  Your versions were frozen at the date of your last update
  (see `update-frequency`), and `PKG_NAME` is newer than that, so `EZPkg`
  moved this program, and only this program, to today's versions of all
  its packages.  The next release carries them.
* **``PROG_NAME.py line 14 imports `PKG_NAME`, but no release of it existed
  before the date ... (line 5, YYYY-MM-DD) ...``**:
  Part 1 of `PROG_NAME.py` has an `exclude-newer` date of your own, which
  `EZPkg` never changes.  Delete that line, as the message says, to move
  everything to today's versions.
* **``PROG_NAME.py 1.0.1 was not released: ...``**:
  The release stopped for the reason given; `PROG_NAME.py` still runs, and the
  next run tries the release again, so fix the problem and rerun it.

## Project Information

* **Source**:
  [`ezpkg`](https://github.com/waynegramlich/ezpkg)
* **How it was built**:
  `EZPkg` was developed primarily with
  [Claude Code](https://claude.com/claude-code), Anthropic's coding agent,
  using the Claude Opus 5.5 model, with the author directing the design
  and the documentation.  Most of the effort went into testing: the test
  suite and its tools (coverage, scripted first-run sessions, and checks
  on GitHub's Linux, Windows and macOS machines) are about 13,000 lines,
  against about 9,600 for `ezpkg.py` itself.
* **Bug Reports and Feature Requests**:
  [EZPkg Issues](https://github.com/waynegramlich/ezpkg/issues) is read very
  infrequently by the principal author.  A much better strategy is to use
  the standard GitHub cycle: Fork, Clone, Commit, and Pull Request.  A pull
  request must pass the associated test suites without decreasing the code
  coverage percentage before it will even remotely be considered for a
  merge.  How to run the tests, coverage and the GitHub Actions checks is
  explained at the top of
  [`ezpkg_test.py`](https://github.com/waynegramlich/ezpkg/blob/main/ezpkg_test.py).
* **License**: MIT No Attribution (`MIT-0`); see
  [`LICENSE`](https://github.com/waynegramlich/ezpkg/blob/main/LICENSE).

## Conclusion

`EZPkg` does all of the package downloading and dependency checking for you.
When you are done, you can literally email someone one of the following
results:
* **`email`**:
  A single `.py` file with the `EZPkg` bootstrap embedded in it.  The
  resulting program needs network access to download needed packages the
  first time.  After they are downloaded, the network is no longer needed.
* **`zipapp`**:
  A single `.pyz` file that can be directly executed by a Python interpreter.
  `zipapp` requires that all packages be pure Python without any packages
  that contain non-Python code (e.g. C, C++, Rust).  No network access
  is needed for a `zipapp` `.pyz` file.
* **`uv`**:
  In addition to having `uv` installed, the user needs two files:
  * `PROG_NAME-VERSION-uv.py`, the program, run with `uv run`.
  * `PROG_NAME-VERSION-uv.py.lock`, which pins every package's version
    and checksum.

  Note that `uv` needs network access for the first run to download packages.

All of the remaining hassle of managing packages is handled by `EZPkg`.
