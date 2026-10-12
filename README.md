# `AltVEnv`: Alternative to Virtual Environments

`AltVEnv` (short for Alternative to Virtual Environments) grew out of the
frustration of developing several Python programs concurrently, where each
program needed its own Python virtual environment.  When switching development
between programs, it is really easy to forget to deactivate one before
activating another, and accidentally run one program against the other's
packages.

To get started with `AltVEnv`, you paste a modest bootstrap at the front of
your program and go.  After that, `AltVEnv` fetches your packages over the
net on demand, without a virtual environment or the right to install
packages.  Get everything working with `AltVEnv` first, then either email
the single `.py` file to a friend or let `AltVEnv` package it up in `zipapp`
or `uv` format.

## Quick Start

Save this program as `quick_start.py`, and run it with
`python3 quick_start.py`:

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["cowsay"]
# ///
"""Try `AltVEnv`: fetch the `cowsay` package on first use, then run."""

# Part 2: AltVEnv required imports are immediately below.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req
# All other imports are added after the AltVEnv bootstrap.

# Part 3: The AltVEnv bootstrap.  Never edit it.
try:
    s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
    m = None
    try: m = importlib.import_module("alt_venv")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"alt_venv").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.load(req.urlopen("https://pypi.org/pypi/pip/json", None, 30))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # whose floor we meet.
        s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install alt_venv"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "alt_venv"], check=True)
    if m is None:
        s = "import alt_venv"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("alt_venv")
    s = "fetch packages"; m.AltVEnv().install(bootstrap="nopip4")
except Exception as x:
    raise SystemExit(f"alt_venv: {s} failed: {x!r}")

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
cowsay.cow("AltVEnv works!")
print(f"cowsay {cowsay.__version__} was loaded from {cowsay.__file__}")
```

The first run creates `~/.alt_venv/` in your home directory, which is where
`AltVEnv` keeps everything it fetches.  It fetches `alt_venv` into it, then
the `cowsay` package that the program lists at the top, and asks once whether
it may install `cowsay`.  Answer `y`, and the program runs:

```
  ______________
| AltVEnv works! |
  ==============
              \
               \
                 ^__^
                 (oo)\_______
                 (__)\       )\/\
                     ||----w |
                     ||     ||
cowsay 6.1 was loaded from /home/you/.alt_venv/versions/cowsay-6.1-.../...
```

Now run it a second time.  There is no question and no download, and it
starts in a fraction of a second, because `cowsay` is already in
`~/.alt_venv/`.  It is always safe to delete the `~/.alt_venv/` directory,
since the next run simply fetches it again.

Python 3.11 or later and a network connection is all that is needed.

The `# type: ignore` comment on `import cowsay` is only for `mypy`; leave
such comments out of your own programs if you do not use `mypy`.

## Download Prompt

<!-- Claude: General comment about this section.  It needs to be shorter.
We'll come back a deal with it later.
-->

When people run `pip` by hand, they know they are downloading packages onto
their computer.  A program that uses `AltVEnv` downloads them on its own, so
whoever runs it may not know.  It would be rude to do downloads without asking
at least once, so `AltVEnv` asks.

If you tried the Quick Start, you have already seen the download prompt.
The very first run of `quick_start.py`, with no `~/.alt_venv` yet, begins
like this:

```
$ python3 quick_start.py
# pip output starts here
Collecting alt_venv
  Downloading alt_venv-0.0.1-py3-none-any.whl (31 kB)
Installing collected packages: alt_venv
Successfully installed alt_venv-0.0.1
# Download prompt starts here
1 requested, 1 downloaded into /home/you/.alt_venv:
  cowsay 6.1  asked for
1 requested, 1 to install into /home/you/.alt_venv;
go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation] y
```

The `pip` output is the bootstrap installing `alt_venv`, and appears only on
a machine's very first run.  One of 4 prompts appear:
* **`n=>No`** - This disables download and immediately exits.
* **`y=>Yes`** - This allows the download to happen.
* **`a=>Always`** - This allows this download and all future downloads to occur.
  This is sticky.  To reset it, remove the `~/.alt_venv/FOREVER_APPROVE` file.
* **`?=>Explanation`** - This lists all requested downloads and then prompts
  again.

There is no default answer: pressing Enter alone just prompts again.
Some programs are run without access to terminal input (e.g. `cron`).  When
this happens, the download prompt is skipped and the answer is taken to be
`Yes`, for that run only: no `FOREVER_APPROVE` file is written, so a later
run from a terminal still asks.

## Enabling `AltVEnv` for Your Program

Immediately below is the `AltVEnv` bootstrap:

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""TOP_LEVEL_DOCSTRING"""
# Any `from __future__ import ...` goes here.

# Part 2: AltVEnv required imports are immediately below.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req
# All other imports are added after the AltVEnv bootstrap.

# Part 3: The AltVEnv bootstrap.  Never edit it.
try:
    s = "find home"; t = pathlib.Path.home()/".alt_venv"; w = t/"pip.whl"
    m = None
    try: m = importlib.import_module("alt_venv")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"alt_venv").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.load(req.urlopen("https://pypi.org/pypi/pip/json", None, 30))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # whose floor we meet.
        s = "download pip"; r = req.urlopen(e["url"], None, 60).read()
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install alt_venv"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "alt_venv"], check=True)
    if m is None:
        s = "import alt_venv"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("alt_venv")
    s = "fetch packages"; m.AltVEnv().install(bootstrap="nopip4")
except Exception as x:
    raise SystemExit(f"alt_venv: {s} failed: {x!r}")

# Your imports go here, followed by the rest of your program.
```

To use `AltVEnv` in your own program, new or preexisting:
1. Paste the bootstrap above at the very top of your program.  If your
   program already starts with a `#!` line, delete your copy of it.
2. Replace `"""TOP_LEVEL_DOCSTRING"""` with your program's own docstring
   (moving it up from below, if it has one), or delete it.
3. Put all of your imports after the bootstrap, even ones from the standard
   library, such as `import os`.
4. Run your program.  Each time an import fails with `ModuleNotFoundError`,
   add the missing package to `dependencies`, and run it again.

That's it.

A *module* is what you `import`; a *package* is what is downloaded from
PyPI and installed, and it is the package's name that goes in
`dependencies`.  Usually the two names are the same, but not always:
`import dateutil` comes from the `python-dateutil` package, and
`import yaml` from `PyYAML`.  One package can also provide several
modules, so one `dependencies` line can cover more than one import.

An import that works only because your own Python happens to have the
package never fails, so step 4 never catches it.  When you release your
program (see [Releasing Programs](#releasing-programs) below), `AltVEnv`
lists every such import, with its line number, and refuses to make the
release until you add those packages to `dependencies` too.

### Choosing Versions

The metadata at the top of the bootstrap is a standard
[inline script metadata](
https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
block, the same one that tools such as `uv` and `pipx` read.  It holds two
settings:

* `requires-python` is the oldest Python the program will run on.  If the
  program is started on an older one, `AltVEnv` stops with a message saying
  so, rather than letting it fail somewhere obscure.  `AltVEnv` itself needs
  3.11 or later.
* `dependencies` lists the packages the program needs, one string each.
  Changing this list is usually the only change a program needs.

Each string is handed to `pip` exactly as written, so it can say which
versions are acceptable:

```
# dependencies = [
#   "requests",                    any version at all
#   "requests<3",                  anything before 3
#   "requests>=2.28,<3",           a range
#   "requests~=2.32.0",            2.32.anything, but not 2.33
#   "requests!=2.31.0",            any version except this one
#   "requests===2.32.3",           that version and no other
#   "requests[socks]",             with an optional extra
#   "pywin32; sys_platform == 'win32'",  only on Windows
# ]
```

A comma after the last string is allowed but not required.  The full syntax
is in the [dependency specifiers](
https://packaging.python.org/en/latest/specifications/dependency-specifiers/)
specification.  `pip` resolves the whole list at once, so it notices when
two packages disagree about a third, which is very hard to get right by
hand.

<!-- Issue: Road map for the rest of the document, in the order of work:
S1: Releasing a Program.  Done 2026-10-12: the network sentence for
    `write`; the `zipapp` and `uv` releases dogfooded with
    `quick_start.py` against PyPI; every PowerShell line run with
    PowerShell 7.6.6 on Linux, leaving Windows PowerShell 5.1, `python`
    and `py` on real Windows to Wayne's friends (`I.2`); the one-run
    form left out by Wayne; the flow read left to Wayne's own
    end-to-end reads; `nopip4`'s row measured (`T.ewar`).
S2: Miscellaneous: how `~/.alt_venv` behaves (garbage collection, sharing,
    versions side by side).
S3: Alternatives / Why not just use `uv`?  Consider a one-sentence answer
    in the intro, since skeptics ask early.
S4: Conclusion: fix "zapapp", the garbled "(pure Python on)", and
    "Cython packages like `math`" (make it compiled packages like
    `numpy`, as S1 does), and reword "copy Parts 2 and 3" now that the
    bootstrap is pasted as one block.
S5: Wrapup: check the intro (its packaging promise, see the issue there)
    and the whole document against what the code does. -->

## Releasing a Program

Once your program starts to work, you may want to share it with a friend.  If
it fits into a single Python file, you can literally email it to them.  Your
friend saves the file and runs it, and the `AltVEnv` bootstrap takes care of
the rest.  (They will have to get through the `AltVEnv` download prompt
first.)  For a friend, it is super easy and convenient.

If you want to use another packaging solution, please read on.

The currently supported package formats are:

* `zipapp`: one file holding the program and its packages; no compiled code.
* `uv`: a script and its lock file, run with `uv`; compiled code is fine.

The first step is to record information about every package currently in
use by running `YOUR_PROG.py` as follows:
* Linux/macOS: `ALT_VENV_APPROVE=write python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:ALT_VENV_APPROVE="write"; & python YOUR_PROG.py }`

This run needs the network: it always asks the package index for the
newest versions that `dependencies` allows, even when your machine
already has the packages.

This writes out `YOUR_PROG.altvenv` beside `YOUR_PROG.py`, which records all
needed information.  It is prudent to add `YOUR_PROG.altvenv` to your version
control system (e.g. `git` or `hg`).

The same run also offers to add a date to Part 1, as `exclude-newer =
"<date>"` under `[tool.uv]`, asking first and naming the line.  With it,
a copy of `YOUR_PROG.py` emailed on its own fetches only the packages that
were available on that date, rather than whatever is newest when your
friend runs it.

`YOUR_PROG.altvenv` contains detailed information about each package that
is needed.  With this file in your version control, you can exactly
recreate the packages that were used at the time of creation.  Thus, when a
new package introduces a bug, you can determine that it is a problem in
a package rather than in your code.  This file is the foundation for making
releases in other formats (e.g. `zipapp` and `uv`).

### Using `zipapp`

A `zipapp` cannot carry a package that contains compiled code, such as
`numpy`, or one that needs a `.pth` file.  `AltVEnv` names any such
package and writes no release; use `uv` instead.

Make the release by running your program like this:
* Linux/macOS: `ALT_VENV_EXPORT=zipapp python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:ALT_VENV_EXPORT="zipapp"; & python YOUR_PROG.py }`

Your program does not run.  Instead, `AltVEnv` checks that every package
your program imports is listed in `dependencies` (naming the line of any
that is not), and then writes `YOUR_PROG.pyz` beside `YOUR_PROG.py`.
`ALT_VENV_EXPORT=zipapp:SOMEWHERE.pyz` writes it elsewhere.

`YOUR_PROG.pyz` is one file holding your program and every package it
uses.  Send it to your friend, who runs it with:
* Linux/macOS: `python3 YOUR_PROG.pyz`, or just `./YOUR_PROG.pyz`
* Windows: `py YOUR_PROG.pyz`

It needs no network and leaves nothing behind on your friend's machine.
If their Python is older than your `requires-python`, it says so and
stops.

### Using `uv`

`uv` can handle compiled packages, such as `numpy`.  You need to ensure that
[`uv`](https://docs.astral.sh/uv/) is installed on both your computer and
your recipients' computers.

Make the release by running your program like this:
* Linux/macOS: `ALT_VENV_EXPORT=uv python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:ALT_VENV_EXPORT="uv"; & python YOUR_PROG.py }`

Your program does not run.  Instead, `AltVEnv` checks that every package
your program imports is listed in `dependencies` (naming the line of any
that is not), and then writes `YOUR_PROG-uv.py` beside `YOUR_PROG.py`,
with its lock file, `YOUR_PROG-uv.py.lock`, beside it.
`ALT_VENV_EXPORT=uv:SOMEWHERE.py` writes them elsewhere, named after
`SOMEWHERE.py`.

`YOUR_PROG-uv.py` is your program with its packages pinned to the versions
you approved and the bootstrap taken out.  Send it to your friend with its
lock file, `YOUR_PROG-uv.py.lock`.  Your friend puts both files in the same
directory and runs:
* Linux/macOS/Windows: `uv run YOUR_PROG-uv.py`

That is all there is to it.

## Miscellaneous

* **Garbage collection:** Packages no program has used for about six
  months are removed, checked at most once a day.
* **No duplication:** Programs that need the same package share one copy.
* **Versions side by side:** Programs that need different versions of a
  package each get their own.

## Alternatives

There are many ways to get a Python program its packages.  `AltVEnv` fills
one niche: a program that stays a single, readable `.py` file, needs nothing
installed beforehand, and fetches its packages on its first run.  The
alternatives below are grouped by what the person running the program has
to do first.

### Nothing to install beyond Python

* [Virtual environments](https://docs.python.org/3/library/venv.html):
  Reasonable for developers, but asking somebody else to create and
  activate one before running a program is asking a lot.  Some Linux
  distributions also leave out the `venv` module until a separate package is
  installed.
* `pip install`: Needs `pip`, which many systems do not provide by default.
  Many Linux distributions also refuse to let `pip` install into the
  system's Python at all, as
  [PEP 668](https://peps.python.org/pep-0668/) allows.
* [`zipapp`](https://docs.python.org/3/library/zipapp.html): Bundles a
  program and its packages into one `.pyz` file that Python runs directly.
  It is in the standard library, but the file is no longer readable, must be
  rebuilt to update a package, and cannot carry packages with compiled
  parts.
* [shiv](https://shiv.readthedocs.io/) and
  [PEX](https://docs.pex-tool.org/): Like `zipapp`, but able to carry
  compiled packages, at the cost of a separate file for each platform.  The
  author installs the tool; the person running the program needs only
  Python.
* [PyInstaller](https://pyinstaller.org/) and
  [Nuitka](https://nuitka.net/): Turn a program into a native executable
  with Python inside, so the person running it needs nothing at all.  The
  result is large, and must be built separately for each operating system.

### Something to install first

* [`uv`](https://docs.astral.sh/uv/): `uv run prog.py` reads the same
  metadata block as Part 1 and runs the program with its packages, very
  quickly.  It is the closest alternative to `AltVEnv`.
* [`pipx`](https://pipx.pypa.io/): `pipx run prog.py` also reads that
  block.
* Containers, such as [Docker](https://www.docker.com/), or Linux packaging
  such as [Snap](https://snapcraft.io/docs/): Ship the program with a whole
  environment around it.  Thorough, but heavy, and the person running the
  program needs the container system installed first.

### Why not just use `uv`?

If everyone who will run your program has `uv`, use it: it does more than
`AltVEnv`, and does it faster.  `AltVEnv` is for the program you hand to
somebody who has Python and nothing else, and whom you would rather not ask
to install a tool before trying it.  Because both read the same metadata
block, Part 1 of a program is the same either way.

## How `AltVEnv` Actually Works

<!-- Issue: Moved here from the old Anatomy section; expected to be
rewritten completely. -->

Never edit the bootstrap.  Re-indenting it or changing its
comments does no harm, but changing its code makes it a different
bootstrap.  To see whether a program carries the current one, run it with
`ALT_VENV_BOOTSTRAP=check` set, and it says so on standard error.

The bootstrap first tries to import `alt_venv`, and uses it if it is already
there, such as when something like `uv` has installed it.  Otherwise, the
first time any program runs it on a machine, it fetches `alt_venv`:

1. It asks [PyPI](https://pypi.org/), the Python Package Index, for the
   newest `pip` that this Python can run.
2. It downloads that `pip`, checks its SHA-256 against the one PyPI
   publishes, and keeps it as `~/.alt_venv/pip.whl`.  The machine's own
   `pip`, if it has one, is never used or changed.
3. It runs that `pip` to install `alt_venv` into `~/.alt_venv`.

Later runs skip the previous three steps.  Every run, the first one included,
then just uses the `AltVEnv` package to download any further packages and
perform housekeeping in the `~/.alt_venv/` directory.

## Conclusion

No more remembering which virtual environment is active.  List your packages
in Part 1, copy Parts 2 and 3 exactly, and each program quietly gets its own
packages, with nothing to create or activate.  What you are left with is a
single file you can email to somebody who has nothing but Python 3.11
(or greater), and it will just work.  You can also trivially package it up
in either `zapapp` (pure Python on) or `uv` (includes Cython packages like
`math`.)
