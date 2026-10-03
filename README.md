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

Paste a 31-line bootstrap near the top of a Python program, and the program
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
    importlib.invalidate_caches(); m = importlib.import_module("alt_venv")
    s = "fetch packages"; m.AltVEnv().install(bootstrap="nopip3")
except Exception as x:
    raise SystemExit(f"alt_venv: {s} failed: {x!r}")

# Part 4: Import the packages listed in Part 1.
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
and every program that uses `AltVEnv` has the same five.  Parts 2 and 3 are
copied as they are; Parts 1, 4 and 5 are yours.

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

The first time any program runs it on a machine, it fetches `alt_venv`:

1. It asks [PyPI](https://pypi.org/), the Python Package Index, for the
   newest `pip` that this Python can run.
2. It downloads that `pip`, checks its SHA-256 against the one PyPI
   publishes, and keeps it as `~/.alt_venv/pip.whl`.  The machine's own
   `pip`, if it has one, is never used or changed.
3. It runs that `pip` to install `alt_venv` into `~/.alt_venv`.

Later runs skip the previous three steps.  Every run, the first one included,
then just uses the downloaded `AltVEnv` package to download any further
packages and perform housekeeping in the `~/.alt_venv/` directory.

#### Part 4: Import the packages listed in Part 1

Your own `import` statements come after the bootstrap, because the bootstrap
is what makes the packages importable.  Import each package by its module
name, which is not always the name in Part 1: `python-dateutil` is imported
as `dateutil`.  The `# type: ignore[import-not-found]` comments are only for
`mypy`, which cannot see packages that live in `~/.alt_venv`; leave them out
if you do not use it.

#### Part 5: The program itself

Everything from here down is yours.

## Download Prompt

When people run `pip` by hand, they know they are downloading packages onto
their computer.  A program that uses `AltVEnv` downloads them on its own, so
whoever runs it may not know.  It would be rude to do that without asking,
so `AltVEnv` asks.

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

The two `#` lines are not output; they mark where each part begins.  The
`pip` output is the bootstrap installing `alt_venv` itself.  It is left
visible on purpose, so that you can see something being downloaded, and it
appears only on a machine's very first run.

The download prompt comes from `AltVEnv`.  It appears whenever a program
needs packages that are not already in `~/.alt_venv`.  It lists what was
downloaded, then asks the question before anything is installed.  When
`AltVEnv` runs `pip` itself, it hides `pip`'s output unless `pip` fails.

Each package is marked `asked for` when Part 1 of the program names it, or
`came along` when it is only there because something else needs it.  The
answers are:

* `y` or `yes`: install them and run the program.
* `n`, `no`, or just Enter: install nothing.  The program stops with
  `alt_venv: fetch packages failed: RuntimeError('declined: ...')`.  Nothing
  has been unpacked and nothing from the packages has run.  The downloads
  are thrown away, so the next run asks again.
* `?`: show where the packages came from and what each one says about
  itself, then ask again.
* `a` or `always`: stop asking; delete `~/.alt_venv/FOREVER_APPROVE` to be
  asked again.

A program with no terminal, such as one started by `cron`, is not asked; it
lists what it downloaded and carries on.

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

## Conclusion

In short, `AltVEnv` allows you to entirely avoid Python Virtual Environments
if you do the following:
* Provide Python standard metadata about the needed packages at the front
  of your program.
* Paste the `AltVEnv` bootstrap into your code right before you do the
  `import` statements for your package dependencies.
After that, your program will just download your packages automatically
without any need to deal with a Python Virtual Environment.
