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
a release.  Afterwards, you can email, the release as a Python file (`.py`),
`zipapp` file (`.pyz`), or a `uv` package (`.zip`, `uv.lock) to your friend
that will run on Windows, Linux, or macOS.  Done!

<!-- Claude: (2026-10-21, toning down the email claim) Proposed
addition after "Done!", so the one rule a reader must not miss is up
front:

Wayne --> Claude: I think my edit above is close.

Send your friend the release, not the `.py` you work on.  A release
also covers the packages that other kinds of computer need (Windows,
macOS, Linux), which your own runs never fetch.
Delete When Done -->

<!--Cluade: Keep this table of contents in sync. with all `##` headers. -->
Table of Contents:
* [Quick Start](#quick-start)
* [Running a Program That Uses `EZPkg`](#running-a-program-that-uses-ezpkg)
* [Enabling `EZPkg` for a Program](#enabling-ezpkg-for-a-program)
* [Releasing a Packaged Program](#releasing-a-packaged-program)
* [The Bootstrap](#the-bootstrap)
* [Miscellaneous](#miscellaneous)
* [How `EZPkg` Actually Works](#how-ezpkg-actually-works)
* [Missing Sections](#missing-sections)
* [Conclusion](#conclusion)

## Quick Start

To get started, please take the program below and paste it into a file
named `quick_start.py` on your computer.  The bulk of this program is the
`EZPkg` bootstrap that starts at Part 3.  This is the "magic" that skips the
hassle of virtual environments.

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["ezpkg>=0.0.1.dev0,<0.1", "cowsay"]
# ///
"""Try `EZPkg`: fetch the `cowsay` package on first use, then run."""

# Part 2: EZPkg required imports are immediately below.
# A `from __future__ import ...` line, if any, goes above Part 2.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# All other imports are added after the EZPkg bootstrap.

# Part 3: The EZPkg bootstrap.  Never edit it.
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

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
cowsay.cow("EZPkg works!")
print(f"The cow above was drawn by cowsay {cowsay.__version__}.")
```

## Running a Program That Uses `EZPkg`

`EZPkg` needs some features that are present in Python 3.11 or greater.  Some
operating systems (e.g. RHEL 9, Ubuntu 22.04 LTS, etc.) are running older
versions of Python.  The following command will print out the Python version.
* Windows: `py --version`
* Linux/macOS: `python3 --version`

The `quick_start.py` program is run as follows:
* Windows: `py quick_start.py`
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
  Answer `y`, and `EZPkg` lists what it retained in `~/.ezpkg`, and then
  the program runs.
* `n=>No`:
  The newly downloaded packages are removed and the program does not run.
  On the very first run, all of `~/.ezpkg` is removed.  Pressing Control-C
  or not answering within 5 minutes is treated as `n`.
* `?=>Explain`:
  This lists the packages in question and repeats the question.

Lastly, the prompt is skipped when there is nobody at a terminal to answer it
(e.g. `cron`), and `y` is assumed.

After a `y`, the first run ends like this:

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
`~/.ezpkg/`.  You will not be asked about this program again, even when
its author sends you a newer version that needs more packages, as long as
it replaces the old file.

There are basically 3 things that can go wrong:
* **No Network**:
  The network is needed only when a program needs packages that are not
  yet in `~/.ezpkg`.
* **No Version Available**:
  The version the author chose is no longer on PyPI, or none was built
  for your computer and Python.
* **`pip` Failure**:
  `pip` ("`pip` Installs Packages") is the standard tool that fetches
  Python packages, and it can fail for other reasons.

Each prints one line, and the program does not run.  The details, for the
program's author, go into `~/.ezpkg/last_failure.txt`, which the line
names (except for No Network).

If you want to remove the `~/.ezpkg` directory and its contents, do the
following:
* Windows (PowerShell): `py $HOME\.ezpkg\remove.py`
* Windows (`cmd.exe`): `py %USERPROFILE%\.ezpkg\remove.py`
* Linux/macOS: `python3 ~/.ezpkg/remove.py`

It is always safe to remove `~/.ezpkg`.  However, if you run `quick_start.py`
again, the `~/.ezpkg` directory will return.

## Enabling `EZPkg` for a Program

The easiest way to enable `EZPkg` in your program is to copy and paste code
from `quick_start.py`:

1. Take Parts 1, 2, and 3 from `quick_start.py` and paste them at the
   front of your program, immediately after the `#!/usr/bin/env...` line,
   if it is present.  If your program has a `from __future__` line, keep
   it (and the docstring) above Part 2.

2. Find the line `# dependencies = [ ..., ,"cowsay"]` under `Part 1` and
   remove, ` ,"cowsay"`.  This will prevent your program from needing the
   `cowsay` package.
   <!-- Claude:  I'm not sure this is necessary.  Auto dependencies
   should remove the cowsay because `import cowsay` will be gone. Right? -->
 
3. Create an initial empty `EZPkg` `.toml` configuration file.
   Replace `PROG_NAME` with your actual program name:
   * Windows (PowerShell): `ni PROG_NAME.py.toml`
   * Windows (`cmd.exe`): `type nul > PROG_NAME.py.toml`
   * Linux/macOS: `touch PROG_NAME.py.toml`

   The existence of this empty `.toml` file informs `EZPkg` that you are a
   developer for the program and enables `EZPkg` "developer mode".

4. Execute your program the first time.  In most cases, your program will
   simply work the first time.  If the `PROG_NAME.py.toml` both exists and
   is empty, it is filled up with a template of commands that are supported
   by `EZPkg` prior to running the body of your program.  See section
   [The `.toml` file](#the-toml-file) below for more information.

<!-- Claude: (2026-10-21, built) Proposed addition to step 3: "That
 first run also builds release 1.0.0 of your program into
 `PROG_NAME_builds/1.0.0/` and writes `PROG_NAME.py.release`; see
 [Releasing a Packaged Program](#releasing-a-packaged-program)."

Wayne: `README.md`.  I'm going to have to nix the creation of the
`PROG_NAME_builds/` directory on the first run.  That is going to have to be
manually user  enabled by editing the `.toml` file.  They created an empty
`.toml`, so it is OK to initialize it.  After that, we only read it.

Wayne: This text no long belongs here.  It needs to be after the Packages
section.
The `PROG_NAME.py.toml` file contains settings that you can edit to modify
how `EZPkg` treats your program; see [The `prog.py.toml`
Settings](#progpytoml-settings) below.  Its presence alone is what
makes you the program's developer.  Without this file, you are treated as
a regular end user.
-->

### What are packages and where do they come from?

In short, a package is a chunk of code that can be imported into a Python
program for subsequent execution.  The most common place to fetch packages
from is the [Python Package Index](https://pypi.org) (PyPI), which is where
the Python community submits freely accessible packages.

A package evolves over time undergoing both bug fixes and feature enhancement.
These changes are managed by giving each released package a different version
number.  Furthermore, for performance reasons, some packages are compiled
to run on the native machine architecture (e.g. Intel, ARM, RISC-V, etc.)
Likewise, some packages require specific features available only on a
specific operating system (e.g. Windows, Linux (Red/Ubuntu),  macOS).

Finding a set of packages that can interoperate with one another
can be quite challenging.  Ultimately, `EZPkg` encodes the package
configuration in Python inline script metadata format at the beginning of
the Python file.  It is unlikely you will need to bother reading any of this
read any meta data.  The way `EZPkg` accomplishes all of this by scanning
your Python program for all `import` statements and reconciling it all into
a single coherent versioned package set.

If you really want to dig in for more information, feel free to visit
the following references:
* [Python Package Index](https://pypi.org/):
  The most common place to store freely accessible Python packages.
* [Inline cript metadata](
  https://packaging.python.org/en/latest/specifications/inline-script-metadata):
  The Python standard in-line configuration information.
* [TOML (Tom's Obvious Minimal Language)](https://toml.io/en/) format:
  This is the syntax used for the inline script metadata.
* [Dependency specifiers](
  https://packaging.python.org/en/latest/specifications/dependency-specifiers):
  This is the syntax of each entry in `dependencies=[...]`.

### `prog.py.toml` Settings

On the first run, `EZPkg` fills the empty `prog.py.toml` with every
setting, each commented out, with a line saying what it does.  Remove the
`#` to change one; a misspelt setting stops the program.  The settings, as
the file shows them, are:

* `auto-dependencies = true`:
  Keep `dependencies` matching the imports, with version ranges.  An
  entry nothing imports is removed once recent runs show it is unused; a
  comment after an entry keeps it.  `false` leaves `dependencies` to you.
* `verbosity = "low"`:
  How much `EZPkg` says: `"none"`, `"low"`, `"medium"` or `"high"`.
* `release = "1.0.0"`:
  Make a release of that version; while it is commented out, there is no
  release.  See [Releasing a Packaged Program](#releasing-a-packaged-program).
* `exports = ["zipapp", "uv"]`:
  The extra files a release builds beside `prog.py`; see [Using
  `zipapp`](#using-zipapp) and [Using `uv`](#using-uv).  While it is
  commented out, a release builds neither.
  <!-- Claude: (2026-10-21, built) Proposed replacement for the
  `release` and `exports` bullets:

* `release = "1.0.0"`:
  The version of the next release.  While it is commented out, the
  first release is 1.0.0 and each one after adds 1 to the last number.
  Change it whenever you like.  See [Releasing a Packaged
  Program](#releasing-a-packaged-program).
* `exports = ["email", "zipapp", "uv"]`:
  What a release builds; while it is commented out, all three.  See
  [Using `email`](#using-email), [Using `zipapp`](#using-zipapp) and
  [Using `uv`](#using-uv).
  -->
* `bootstrap = "update"`:
  At a release, replace an older bootstrap with the current one.  A
  bootstrap's name, such as `"nopip8"`, keeps exactly that one.

## Releasing a Packaged Program

Once you are satisfied with your program, you may choose to release it in
a more durable single file package.  Currently two formats are supported:
* *`zipapp`*:
  This works for pure Python programs (i.e. no packages with C, C++, Rust,
  etc.) and produces a `.pyz` file.  The file can be quite large since it
  includes all of the needed code.  All that the recipient needs is a Python
  interpreter; no network is needed.  It produces a file
  `YOUR_PROG-X.Y.Z.pyz`, where `YOUR_PROG` is the program name and `X.Y.Z`
  is the version number.
* *`uv`*:
  `uv` is a popular packaging system written in Rust.  It handles
  compiled packages too.  The recipient must have `uv` installed, and
  `uv` fetches the packages over the network on the first run.

To build both, ensure that `YOUR_PROG.py.toml` has both `release =` and
`exports =` enabled:

```toml
release = "1.0.0"
exports = ["zipapp", "uv"]
```

Then run the program once.  That run does not run your program; instead,
`YOUR_PROG-1.0.0.pyz`, `YOUR_PROG-1.0.0-uv.py` and
`YOUR_PROG-1.0.0-uv.py.lock` appear beside it, and `EZPkg` says so.  This
happens once per version: later runs run your program as usual.  To make
the next release, change `release` to the next number.

<!-- Claude: Proposed replacement for lines from "Once you are satisfied"
to here:

(Revised 2026-10-21 for the `prog.py.release` trigger; built.)

A release is the copy of your program that you send to other people.
`EZPkg` makes one for you without being asked: the first time you run
your program as its developer, it builds release 1.0.0, and then your
program runs as usual.  A release comes in three forms:
* *`email`*:
  Your program itself, as `YOUR_PROG-X.Y.Z.py`, ready to email.  Your
  own runs approve only the packages your computer needs; this copy also
  approves the ones other computers need, such as the `colorama` that
  `tqdm` uses on Windows only.  The recipient needs only Python.
* *`zipapp`*:
  (as now)
* *`uv`*:
  (as now)

All three are built into the folder `YOUR_PROG_builds/1.0.0/`:
`YOUR_PROG-1.0.0.py`, `YOUR_PROG-1.0.0.pyz`, `YOUR_PROG-1.0.0-uv.py` and
`YOUR_PROG-1.0.0-uv.py.lock`.  A `zipapp` is skipped, with a line saying
why, when your program needs a compiled package.  Beside your program,
`YOUR_PROG.py.release` records what was built.

**To build the next release, delete `YOUR_PROG.py.release` and run your
program.**  Release 1.0.1 is built, then 1.0.2, and so on, each in a
folder of its own, and your program runs as usual each time:
* Windows (PowerShell or `cmd.exe`): `del YOUR_PROG.py.release`
* Linux/macOS: `rm YOUR_PROG.py.release`
* Or delete it in Explorer or Finder.

The version numbers are yours to change at any time: set `release =
"2.0.0"` in `YOUR_PROG.py.toml` (even back to `"1.0.0"`), and the next
run builds that version.  They only need care once you publish your
program somewhere that remembers them, such as PyPI, which never accepts
the same version twice.  To build fewer forms, set `exports`, such as
`exports = ["email"]`.

A release also checks your imports, gives each entry in `dependencies`
without a version a range, and puts in the current bootstrap.  To find
what other kinds of computer need, it uses `uv`, which `EZPkg` fetches
by itself if your computer does not have it.  The first release takes
some seconds longer for that; after that, each takes a second or two.

### Using `email`

Send `prog-1.0.0.py` to your friend, who runs it as [Running a Program
That Uses `EZPkg`](#running-a-program-that-uses-ezpkg) shows:
* Linux/macOS: `python3 prog-1.0.0.py`
* Windows: `py prog-1.0.0.py`

Send this copy rather than `prog.py`: on another kind of computer,
`prog.py` can need a package yours never fetched, and `EZPkg` refuses
any package its author did not approve.
-->

### Using `zipapp`

Your friend runs the `.pyz` with:
* Linux/macOS: `python3 prog-1.0.0.pyz`
* Windows: `py prog-1.0.0.pyz`

If their Python is older than your `requires-python`, it says so and
stops.  `EZPkg` refuses to build a `.pyz` with a compiled package, such
as `numpy`, since Python cannot run one from inside a zip file; take
`"zipapp"` out of `exports` and use `uv` instead.

<!-- Claude: (2026-10-21, built) Proposed new paragraph:

The `.pyz` also carries the packages that only other kinds of computer
need, such as the `colorama` that `tqdm` uses on Windows, so it runs on
Windows, macOS and Linux alike.
-->

<!-- Claude: (2026-10-21, built) Proposed new paragraph for How
`EZPkg` Actually Works, or wherever a release is explained:

To find what other kinds of computer need, a release uses
[`uv`](https://docs.astral.sh/uv/), which works this out for every
computer at once.  You never install it: a `uv` already on your
computer is used if it is recent enough, and otherwise `EZPkg` fetches
`uv` from PyPI into `~/.ezpkg`, as it does any package, the first time
you make a release.
-->

### Using `uv`

[`uv`](https://docs.astral.sh/uv/) must be installed on your computer
and on your friend's.  `"uv"` in `exports` builds two files:
* `prog-1.0.0-uv.py`:
  Your program with the bootstrap taken out, since `uv` takes its place,
  and the exact versions your program ran with.
* `prog-1.0.0-uv.py.lock`:
  The lock file, written by `uv lock --script`, which names the files of
  each of those versions for every kind of computer.  `EZPkg` checks that
  it names the same files your program ran with.

Without `uv` on your computer, only the `-uv.py` is written, and `EZPkg`
prints the `uv lock` command that writes the lock.
<!-- Claude: (2026-10-21) `EZPkg` now fetches `uv` when it is not
installed, so the sentence above applies only when that fetch fails
(no network).  Proposed: delete it, and start this section with "`uv`
must be installed on your friend's computer (`EZPkg` provides it on
yours)." -->

Send both files to your friend, who puts them in the same directory and
runs:
* Linux/macOS/Windows: `uv run prog-1.0.0-uv.py`

`uv` finds the lock beside the script, fetches the packages it names
(compiled ones, such as `numpy`, included) into its own cache, and runs
the program.  Only the first run needs the network.

## The Bootstrap

Never edit the bootstrap, not even a space or a comment.  Indenting the
whole of it, as under an `if`, is the one change allowed.  Anything else
stops the program, which shows each line that differs from the published
bootstrap.

An older bootstrap that has not been edited still runs, so a program that
nobody maintains keeps working.  When you are the developer, `EZPkg` tells
you once about each newer bootstrap, and the next release replaces it.

<!-- Claude: Proposed new section:

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
-->

## Miscellaneous

Here are some miscellaneous observations:
* **Garbage collection**:
  Packages that no program has used for about six months are removed,
  checked at most once a day.
* **No duplication**:
  Programs that need the same package share one copy.
* **Versions side by side**:
  Programs that need different versions of a package each get their own.

## How `EZPkg` Actually Works

This section is for the curious-minded.  Feel free to skip it unless you
are interested in puzzling out how the `EZPkg` bootstrap actually works
on your own.

Please open `quick_start.py` and go to `# Part 3: ...`.  The entire
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
    them on `sys.path`, so that the imports in Part 4 succeed.
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

## Missing Sections:

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

No more remembering which virtual environment is active.  Paste the
bootstrap, and each program quietly gets its own packages, with nothing to
create or activate, while `EZPkg` keeps its dependencies list in step with
its imports.  What you are left with is a single file you can email to
somebody who has nothing but Python 3.11 (or greater), and it will just
work.  You can also trivially package it up in either `zipapp` (pure Python
only) or `uv` (includes compiled packages like `numpy`).

<!-- Claude: (2026-10-21, replaces the earlier proposal here)
Proposed replacement from "What you are left with" to the end of the
paragraph:

What you are left with is a single file, the `email` release, that you
can email to somebody with Python 3.11 or newer and an internet
connection, on Linux, Windows or macOS.  It works whenever each package
has a version for their computer, which pure-Python packages always do
and popular compiled ones such as `numpy` nearly always do.  You can
also package it up as a `zipapp` (pure Python only, and no network
needed) or for `uv` (compiled packages included).
-->

