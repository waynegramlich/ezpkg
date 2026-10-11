<!-- Claude:
Before uploading AltVEnv to PyPI, all TBD's needs to be fixed. -->
<!-- Claude:
`README.md` is a short advertisement, followed by an instruction manual. -->

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
<!-- Issue: The `zipapp` and `uv` packaging promised above is not documented
yet; S2 (Packaging) below covers it.  Verify this paragraph against the
finished document before the `README.md` wrapup. -->

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

# Part 2: The standard library imports that the bootstrap uses.
import hashlib
import importlib
import json
import pathlib
import subprocess
import sys
import urllib.request as req

# Part 3: The bootstrap.  Copy it exactly, and never edit it.
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

# Part 4: Import the packages listed in Part 1.
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

## Download Prompt

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

<!-- Claude: Fix the prompt code to not accept ENTER as a default and re-prompt.
Delete when done. -->
The `pip` output is the bootstrap installing `alt_venv`, and appears only on
a machine's very first run.  One of 4 prompts appear:
* **`n=>No`** - This disables download and immediately exits.
* **`y=>Yes`** - This allows the download to happen.
* **`a=>Always`** - This allows this download and all future downloads to occur.
  This is sticky.  To reset it, remove the `~/.alt_venv/FOREVER_APPROVE` file.
* **`?=>Explanation`** - This lists all requested downloads and then prompts
  again.
Some programs are run with out access to terminal input (e.g. `cron`).  When
this happens, the download prompt is suppressed and is treated as `Always`.

## Enabling `AltVEnv` for Your Program

If you are starting from scratch, the easiest thing to do is take a copy of
`quick_start.py` and do the following:
1. Just rename the program and remove all lines that have `cowsay` in them.
2. Each time you need a new package, check whether your Python already has
   it with `python3 -c "import NAME"`.  If that succeeds, import it along with
   your other imports before the bootstrap.  If it fails with
   `ModuleNotFoundError`, do the following:
   1. Add one line containing the package name to the metadata at the program
      front.
   2. Add a regular `import` statement for the package immediately after the
      `AltVEnv` bootstrap code.
That's it.
<!-- Issue: Wayne to review the preinstalled check in step 2.  Two catches:
(a) the module name is not always the package name (`import dateutil` comes
from `python-dateutil`), and (b) a package preinstalled on the author's
Python (e.g. a Linux distribution's `python3-requests`) may be missing on
the machine of whoever runs the program, so third-party packages arguably
belong in the metadata even when the check succeeds. -->

If you are starting from a preexisting program, do the following:
* Copy the metadata from the front of `quick_start.py` into the front of
  your program.  You can remove the line that says `cowsay`.  (See Meta Data
  section below, for more information.)
  <!-- Issue: Point the reference above at the metadata section, whose title
  is not settled yet (currently "Part 1" under "Anatomy"). -->
* This step is optional, but still highly recommended.  For each `import` of
  a third-party package (one not in the standard library) that your Python
  already has, add the package's name to the metadata anyway, since the
  machines your program runs on may not have it.  The package name is not
  always the module name: `import dateutil` needs `python-dateutil`.
  <!-- Issue: Wayne to review the rewritten bullet above.  The original said
  to copy the name of every `import`, which is wrong for standard library
  modules and for packages whose module name differs. -->
* Paste the bootstrap into your program after your last import.
* Place an `import` statement for each package that is not preinstalled
  after the `AltVEnv` bootstrap and add it to the meta data.
That's all.

<!-- Claude: I'd like to review the stuff above.  First. -->
<!-- Issue: Road map for the rest of the document:
S1: Anatomy of an `AltVEnv` Program: the reference for what readers just did
    in "Enabling `AltVEnv` for Your Program".
S2: Packaging (new section): `zipapp` and `uv`, keeping the intro's promise.
S3: Author Package Management: approvals, for authors who ship to others.
S4: Miscellaneous: how `~/.alt_venv` behaves (garbage collection, sharing,
    versions side by side).
S5: Alternatives / Why not just use `uv`?  Consider a one-sentence answer
    in the intro, since skeptics ask early.
S6: Conclusion: fix "zapapp", the garbled "(pure Python on)", and
    "Cython packages like `math`". -->

## Author Package Management

<!-- Claude: I agree with below.  Open an issue and we'll fix it. -->
<!-- Wayne: a true freeze needs two things, and only the second exists.
(1) Exact `==` pins in Part 1 for every package, including the ones that
come along, so that `pip` fetches the same versions every time.  (2) The
approvals file, so that those exact files are verified and nothing else
is accepted.  An idea for (1): `ALT_VENV_APPROVE=write` could also print
the `==` pins for everything it recorded, ready to paste into Part 1.
Approvals are also an audit of what actually arrived.  Watch the
platform catch: approvals are keyed by file name, so a compiled package
recorded on one Python version or operating system is refused on
another. -->

<!--Claude: We'll talk about this when we get around to the issue above. -->
Whoever runs your program cannot tell a genuine package from a tampered or
look-alike one, but you can.  Run it once as
`ALT_VENV_APPROVE=write python3 prog.py` to record the exact packages you got
in `prog.altvenv`, and ship that file beside it.  Nobody is asked after that:
anything that does not match is refused before it is installed.  A new
release of a package is refused too, until you record it again.

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

## Anatomy of an `AltVEnv` Program

`quick_start.py` is also a template for your own programs.  Open it in your
editor and read along: after the first run there is a copy in
`~/.alt_venv/quick_start.py`, or use the one in the
[Quick Start](#quick-start).  It has five parts, each starting with a
`# Part` comment, and every program that uses `AltVEnv` has the same five.
Copy it, then change the packages in Part 1, the imports in Part 4, and the
program in Part 5.  Leave Parts 2 and 3 exactly as they are.

### Part 1: The packages this program needs

This is a standard [inline script metadata](
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

### Part 2: The standard library imports that the bootstrap uses

Seven imports, all from the standard library, so there is nothing to
install.  Put them among your own imports, in alphabetical order, and if
your program already imports some of them, keep one copy of each.

### Part 3: The bootstrap

Copy it exactly, and never edit it.  Re-indenting it or changing its
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

### Part 4: Import the packages listed in Part 1

Your own `import` statements come after the bootstrap, because the bootstrap
is what makes the packages importable.  Import each package by its module
name, which is not always the name in Part 1: `python-dateutil` is imported
as `dateutil`.  Leave out the `# type: ignore` comments if you do not use
`mypy`.

### Part 5: The program itself

Everything from here down is yours.

## Conclusion

No more remembering which virtual environment is active.  List your packages
in Part 1, copy Parts 2 and 3 exactly, and each program quietly gets its own
packages, with nothing to create or activate.  What you are left with is a
single file you can email to somebody who has nothing but Python 3.11
(or greater), and it will just work.  You can also trivially package it up
in either `zapapp` (pure Python on) or `uv` (includes Cython packages like
`math`.)
