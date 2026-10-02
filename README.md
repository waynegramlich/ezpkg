<!-- Claude:
Before uploading AltVEnv to PyPI, all TBD's needs to be fixed. -->
<!-- Claude:
`README.md` is a short advertisement, followed by an instruction manual. -->

# `AltVEnv`: Alternative to Virtual Environments

`AltVEnv` (short for Alternative to Virtual Environments) grew out of the
frustration of developing several Python programs at once, where each program
needs its own Python virtual environment.  When switching development from
one program to the next, it is easy to forget to deactivate the current
virtual environment before activating the next one.  If you forget, you end up
running one program against another program's packages, and confusion can
ensue.  The question that arose was "Is there a better way that avoids Python
virtual environments entirely?"  The answer turned out to be "Absolutely
yes!!!"

Paste a 30-line bootstrap near the top of a Python program, and the program
fetches the packages it needs the first time it runs.  There is no virtual
environment to create or activate, nothing to install beforehand, and no
administrator rights needed -- just Python 3.11 or later.  Packages are
downloaded once and shared by every program that uses them.

A single-file Python program can literally be e-mailed to somebody and it
will just work!  With `AltVEnv`, neither the developer nor the end user has
to deal with the dreaded missing Python package problem.

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
    if not (t/"alt_venv").is_dir():  # Not installed yet.
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
    s = "import alt_venv"; sys.path.insert(0, str(t))
    importlib.invalidate_caches(); importlib.import_module("alt_venv")
except Exception as x:
    raise SystemExit(f"cannot fetch alt_venv, {s} failed: {x!r}")

# Part 4: Fetch the packages listed in Part 1, then import them.
import alt_venv  # type: ignore[import-not-found]

alt_venv.AltVEnv().install()
import cowsay  # type: ignore[import-not-found]

# Part 5: The program itself.
cowsay.cow("AltVEnv works!")
print(f"cowsay {cowsay.__version__} was loaded from {cowsay.__file__}")
```

The first run fetches `alt_venv`, then the `cowsay` package that the program
lists at the top, and asks once whether it may install `cowsay`.  Answer `y`,
and the program runs:

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
`~/.alt_venv`.  That directory holds everything `AltVEnv` has fetched, and
deleting it is always safe; the next run simply fetches again:

```
rm -rf ~/.alt_venv
```

All the machine needs is Python 3.11 or later, plus a network connection the
first time a program needs a package.

### Using It in Your Own Program

`quick_start.py` is also a template.  Open it in your editor and read along:
after the first run there is a copy in `~/.alt_venv/quick_start.py`, or use
the one above.  It has five parts, each starting with a `# Part` comment,
and every program that uses `AltVEnv` has the same five.  Parts 2, 3 and 4
are copied as they are; Parts 1 and 5 are yours.

#### Part 1: The packages this program needs

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

#### Part 2: The standard library imports that the bootstrap uses

Seven imports, all from the standard library, so there is nothing to
install.  Put them among your own imports, in alphabetical order, and if
your program already imports some of them, keep one copy of each.

#### Part 3: The bootstrap

Copy it exactly, and never edit it.  Re-indenting it or changing its
comments does no harm, but changing its code makes it a different
bootstrap.  To see whether a program carries the current one, run it with
`ALT_VENV_BOOTSTRAP=check` set, and it says so on standard error.

The first time any program runs it on a machine, it does three things:

1. It asks PyPI for the newest `pip` that this Python can run.
2. It downloads that `pip`, checks its SHA-256 against the one PyPI
   publishes, and keeps it as `~/.alt_venv/pip.whl`.  The machine's own
   `pip`, if it has one, is never used or changed.
3. It runs that `pip` to install `alt_venv` into `~/.alt_venv`.

On every run, the first included, it puts `~/.alt_venv` on Python's import
path and imports `alt_venv`.  Once `alt_venv` is there, the three steps
above are skipped and no network is needed.  If anything goes wrong, the
program stops with one line saying which step failed and why.

#### Part 4: Fetch the packages listed in Part 1, then import them

`install()`, called with no arguments, reads Part 1 of the program that is
running.  It checks `requires-python`, then fetches whatever in
`dependencies` is not already in `~/.alt_venv`, asks once before installing
it, and puts each package on Python's import path.  A list it has fetched
before is answered from `~/.alt_venv` without running `pip` at all.

While it is there, it also does some housekeeping.  At most once a day it
clears out packages that no program has used for about six months, and
about once a week it looks for a newer `pip`.  Looking for `pip` never makes
the program fail; without a network, it simply tries again a week later.

Your own `import` statements come after `install()`, because that is what
makes the packages importable.  Import each package by its module name,
which is not always the name in Part 1: `python-dateutil` is imported as
`dateutil`.  The `# type: ignore[import-not-found]` comments are only for
`mypy`, which cannot see packages that live in `~/.alt_venv`; leave them
out if you do not use it.

#### Part 5: The program itself

Everything from here down is yours.

## Requirements

<!-- Claude: The `(~N lines)` needs updating prior to PyPI deployment. -->
<!-- Claude: The goal is to keep the itemized list short. -->
The `AltVEnv` requirements are:
1. Python 3.11 or greater is required.
2. Standard Python metadata, embedded as hash comments at the front of the
   program, lists the required packages.
3. A modest chunk of bootstrap code (~N lines) is added to your code
   prior to the `import` statements for the previously listed packages.
4. An active network connection is required for the initial run.  Afterwards,
   the packages are locally cached and a network connection is no longer
   needed.
That's it!

## Alternatives

<!-- Claude:
I give you have full permission to rewrite this section of the document.
I want to focus solutions that encapsulate everything into one files
(there are many).  Prioritize solutions that do not need installation
of other software, then list alternatives (`uv`, `docker`, `snap`, etc.) -->

A short list of alternatives to explore follows:
* [Python Virtual Environments](https://docs.python.org/3/library/venv.html):
  For software developers, virtual environments are actually quite reasonable.
  However, asking end users to install a virtual environment prior to execution
  is asking a lot.
* [uv](https://docs.astral.sh/uv/):
  `uv` is gaining popularity as an alternative to Python Virtual Environments.
* [`zipapp`](https://docs.python.org/3/library/zipapp.html):
  `zipapp` produces large executable Python archives that contain everything.
* Container technology:
  [Docker](https://www.docker.com/) and [Snap](https://snapcraft.io/docs/)
  provide alternatives to `zipapp`.
-->

## Download Prompt

When people run the `pip` program manually, they presumably already
know that they are downloading a package onto their computer.  However, the
`AltVEnv` bootstrap indirectly calls `pip`, so the user may not actually know
that some packages might be downloaded.  It is considered rude not to inform
the user at least once that some downloading is going on under the covers.

The first time `AltVEnv` decides to download some Python packages (and you
are using the command line interface) it will prompt you with the following
question:

<!-- Claude: I changed the message, so the code need to be updated. -->
```
AltVEnv wants to download 2 packages with 3 dependencies into ~/.alt_venv .
Go ahead? [y=>Yes, n=>No, a=>Always, ?=>Explanation]:
```
* Capital letters work as well as small ones, and a bare newline means `n`.
* `y`: installs them and runs the program.
* `n`: installs nothing and stops.  Nothing has been unpacked at that
  point and nothing from the packages has run.
* `?`: lists what would be installed, one line each, and asks again.
  Asking for detail is never counted against you.
* `a`: disables asking the question again on this machine.  It is
  the only answer that outlasts the run, so it is the only one that asks
  you to confirm:
  * `Really never ask again? [y=>Yes/n=>No]:`
     Answering `n` returns you to the first question with the install still on
     offer.  Answering `y` suppresses the question until the entire `.alt_venv`
     directory is manually deleted.  (Remember, deleting the `.alt_venv`
     directory is **ALWAYS** a safe thing to do.)

If a program has no terminal access, it is not asked.  Thus, anything started
by `cron`, a build system, a service manager, or by double-clicking an icon
has nobody to put a question to, so it just prints out what it downloaded and
carries on.  This avoids annoying hangs with no way to unhang them.

<!-- Claude:
I am deliberately not explaining the organization of the `~/.alt_venv/`
directory.  That information belongs in `~/.alt_venv/README.md`.

## The `.alt_venv` directory:

`AltVEnv` creates and manages a directory called `.alt_venv` located
in your home directory.  The location depends upon your operating system:
* Windows: `C:\Users\YourName\.alt_venv`
* Linux/macOS: `~/.alt_venv`

There is a `README.md` inside `.alt_venv/` that describes its purpose.
In addition, there are four sub-directories:
* `versions/`:
  This holds one directory per package version, named after the
  Python wheel it came from.  These are added to Python's import path.
* `wheels/`:
  Each Python wheel is also represented as a directory.
* `requests/`:
  This remembers what was asked for, one small file per request, so
  that asking again costs nothing.
* `pending/`:
  This is a scratch space used while fetching and unpacking.

The `.alt_venv` directory can be safely deleted at any time, since it can be
recreated and repopulated the next time a program that uses `AltVEnv` is
executed.  To delete the directory:
* Windows: `rmdir /s /q %USERPROFILE%\.alt_venv`
* Linux/macOS: `rm -rf ~/.alt_venv`
-->

## Miscellaneous

* **Old packages are cleared out on their own.**
  A package that no program has needed for about six months is removed, for the
  same reason: it is worth less than the space it occupies, and getting it back
  costs one download.  Using a package counts as needing it, so something
  installed two years ago and used this morning stays.  Anything left behind
  by a program that was interrupted mid-download is also cleared out.

  The sweep is very fast and happens at most once a day.

* **No packages are duplicated.**
  When multiple programs with `AltVEnv` want the same package, the second
  one recognizes that the identical package is already there and uses it.
  That holds even if both programs start at the same moment.

<!-- Claude: I don't understand the chunk of text below.
* **If you wrote the program**, the guarantee is yours to give, and it takes
one run:

```bash
ALT_VENV_APPROVE=write python3 prog.py
```

That writes `prog.altvenv` beside your program.  Commit it alongside the
code, and everybody who runs your program afterwards gets exactly the
packages you approved or a refusal that names the mismatch.  While you are
still deciding what your program needs, `ALT_VENV_APPROVE=skip` turns the
checking off for your own runs.
-->

## Conclusion

In short, `AltVEnv` allows you to entirely avoid Python Virtual Environments
if you do the following:
* Provide Python standard metadata about the needed packages at the front
  of your program.
* Paste the `AltVEnv` bootstrap into your code right before you do the
  `import` statements for your package dependencies.
After that, your program will just download your packages automatically
without any need to deal with a Python Virtual Environment.
