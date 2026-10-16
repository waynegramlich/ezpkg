# `EZPkg`: Easy Python Packages

`EZPkg` (pronounced "easy package") grew out of the desire to send a
simple one-file Python program to a friend.  When my friend tried to run
it, a few packages were missing, so my friend had to create a virtual
environment and install them.  It worked, but it was annoying.  So I
asked, "Could this be made really easy for the recipient?"  Thus was born
`EZPkg`, which lets a single-file Python program download its missing
packages all by itself.

To get started with `EZPkg`, you paste a modest bootstrap at the front of
your program and go.  After that, `EZPkg` fetches your packages over the
net on demand, without a virtual environment or the right to install
packages.  Get everything working with `EZPkg` first, then either email
the single `.py` file to a friend or let `EZPkg` package it up in `zipapp`
or `uv` format.  You can remove the bootstrap `try` block at any time.
Once the bootstrap is gone, you *can* remove the metadata, but there is
really no particular reason to do so, and `uv run` still reads it.

## Quick Start

Save the program below as `quick_start.py`, and run it with
`python3 quick_start.py` (Linux/macOS) or `python quick_start.py` (Windows):

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = ["cowsay"]
# ///
"""Try `EZPkg`: fetch the `cowsay` package on first use, then run."""

# Part 2: EZPkg required imports are immediately below.
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
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "ezpkg"], check=True, stdout=2)
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip6")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Part 4: Your imports, all after the bootstrap.
import cowsay  # type: ignore[import-not-found]  # For mypy.

# Part 5: The program itself.
cowsay.cow("EZPkg works!")
print(f"cowsay {cowsay.__version__} was loaded from {cowsay.__file__}")
```

The first run creates `~/.ezpkg/` in your home directory, which is where
`EZPkg` keeps everything it fetches.  It fetches `ezpkg` into it, then
the `cowsay` package that the program lists at the top (line 5,
`# dependencies = ["cowsay"]`), and asks once whether `EZPkg` may
install `cowsay`.  Answer `y`, and the program runs:

```
  ______________
| EZPkg works! |
  ==============
              \
               \
                 ^__^
                 (oo)\_______
                 (__)\       )\/\
                     ||----w |
                     ||     ||
cowsay 6.1 was loaded from /home/you/.ezpkg/versions/cowsay-6.1-.../...
```

Now run it a second time.  There is no question and no download, and it
starts in a fraction of a second, because `cowsay` is already in
`~/.ezpkg/`.  It is always safe to delete the `~/.ezpkg/` directory,
since the next run simply fetches it again.

Python 3.11 or later and a network connection are all that is needed.

The `# type: ignore` comment on `import cowsay` is only for `mypy`; leave
such comments out of your own programs if you do not use `mypy`.  If you
do use them, `EZPkg` copies one onto each import it adds for you (see
[Keeping `dependencies` in Sync](#keeping-dependencies-in-sync)).
`EZPkg` adds the comment only where `mypy` needs it, on imports of
packages it fetches, not on the standard library, where `mypy --strict`
would report it as unused.

## Download Prompt

When people run `pip` by hand, they know they are downloading packages onto
their computer.  A program that uses `EZPkg` downloads them on its own, so
whoever runs it may not know.  It would be rude to do downloads without asking
at least once, so `EZPkg` asks.

If you tried the Quick Start, you have already seen the download prompt.
The very first run of `quick_start.py`, with no `~/.ezpkg` yet, begins
like this:

```
$ python3 quick_start.py
# pip output (on standard error) starts here
Collecting ezpkg
  Downloading ezpkg-0.0.1-py3-none-any.whl (31 kB)
Installing collected packages: ezpkg
Successfully installed ezpkg-0.0.1
# Download prompt starts here
1 requested, 1 downloaded into /home/you/.ezpkg:
  cowsay 6.1  asked for
1 requested, 1 to install into /home/you/.ezpkg;
go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation] y
```

The `pip` output is the bootstrap installing `ezpkg`, and appears only on
a machine's very first run.  It goes to standard error, so it never mixes
into your program's own output.  The prompt takes one of four answers:
* **`n=>No`** - This disables download and immediately exits.
* **`y=>Yes`** - This allows the download to happen.
* **`a=>Always`** - This allows this download and all future downloads to
  occur, after asking `Really never ask again?` (`n` goes back to the prompt).
  This is sticky.  To reset it, remove the `~/.ezpkg/FOREVER_APPROVE` file.
* **`?=>Explanation`** - This lists all requested downloads and then prompts
  again.

There is no default answer: pressing Enter alone just prompts again.
Some programs are run without access to terminal input (e.g. `cron`).  When
this happens, the download prompt is skipped and the answer is taken to be
`Yes`, for that run only: no `FOREVER_APPROVE` file is written, so a later
run from a terminal still asks.

A package is code, and installing one can run some of it: a `.pth` file
in a package runs when the package is put on `sys.path`, before your
program's own code.  Anybody can publish a package to PyPI, so list
only packages you trust in `dependencies`, and check the spelling of
each name, since look-alike names are a known trick.

## Enabling `EZPkg` for Your Program

Immediately below is the `EZPkg` bootstrap:

```python
#!/usr/bin/env python3
# Part 1: The packages this program needs.
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""TOP_LEVEL_DOCSTRING"""
# Any `from __future__ import ...` goes here.

# Part 2: EZPkg required imports are immediately below.
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
    s = "find home"; t = pathlib.Path.home()/".ezpkg"; w = t/"pip.whl"
    m = None
    def g(u):  # Fetch u, with curl if this Python has no certificates.
        try: return req.urlopen(u, None, 60).read()
        except req.URLError as y: z = y  # As on python.org's macOS Python.
        try: return subprocess.run(["curl", "-fsSL", u],
                                   capture_output=True, check=True).stdout
        except Exception: raise z from None
    try: m = importlib.import_module("ezpkg")  # Already importable?
    except ImportError: pass
    if m is None and not (t/"ezpkg").is_dir():  # Not installed yet.
        s = "choose pip"; v = sys.version_info[1]
        d = json.loads(g("https://pypi.org/pypi/pip/json"))
        e = max((e for f in d["releases"].values() for e in f  # Newest pip ...
                 if e["url"][-4:] == ".whl" and not e["yanked"]
                 and (q := e["requires_python"] or "")[:4] == ">=3."
                 and "," not in q and int(q.split(".")[1]) <= v),
                key=lambda e: e["upload_time"])  # ... whose floor we meet.
        s = "download pip"; r = g(e["url"])
        if hashlib.sha256(r).hexdigest() != e["digests"]["sha256"]:
            raise ValueError(f"{e['filename']} fails its SHA-256 check")
        t.mkdir(parents=True, exist_ok=True); p = t/"pip.part"
        p.write_bytes(r); p.replace(w)  # The rename is atomic.
        s = "install ezpkg"; subprocess.run([
            sys.executable, w/"pip", "install", "--no-input", "-t", t,
            "--disable-pip-version-check", "ezpkg"], check=True, stdout=2)
    if m is None:
        s = "import ezpkg"; sys.path.insert(0, str(t))
        importlib.invalidate_caches(); m = importlib.import_module("ezpkg")
    s = "fetch packages"; m.EZPkg().install(bootstrap="nopip6")
except Exception as x:
    raise SystemExit(f"ezpkg: {s} failed: {x!r}")  # Do not edit try block!

# Your imports go here, followed by the rest of your program.
```

To use `EZPkg` in your own program, new or preexisting:
1. Paste the bootstrap above at the very top of your program.  If your
   program already starts with a `#!` line, delete your copy of it.
2. Replace `"""TOP_LEVEL_DOCSTRING"""` with your program's own docstring
   (moving it up from below, if it has one), or delete it.
3. Put all of your imports after the bootstrap, even ones from the standard
   library, such as `import os`.  An import placed above the bootstrap is
   reported when you run your program.
4. Run your program.  If its imports and `dependencies` disagree,
   `EZPkg` says so and offers to fix `dependencies` for you; see
   [Keeping `dependencies` in Sync](#keeping-dependencies-in-sync)
   below.  This also catches a package your own Python happens to have, but
   that your friends' will not.

That's it.

A *module* is what you `import`; a *package* is what is downloaded from
PyPI and installed, and it is the package's name that goes in
`dependencies`.  Usually the two names are the same, but not always:
`import dateutil` comes from the `python-dateutil` package, and
`import yaml` from `PyYAML`.  One package can also provide several
modules, so one `dependencies` line can cover more than one import.

### Keeping `dependencies` in Sync

`EZPkg` keeps `dependencies` in step with your imports: one package for
each module you import, in the order the modules are first imported.
Whenever your imports or `dependencies` change and the two disagree (a
package is missing, one is no longer imported, or the order differs),
`EZPkg` says so once and asks:

```
EZPkg: prog.py: its `dependencies` (line 6) and its imports (lines 14-15)
disagree.
See the discrepancy list? [o=>Once/a=>Always/n=>No/d=>Don't ask again]
```

* **`o=>Once`** - This shows the list this time.
* **`a=>Always`** - This shows the list now, and from now on without
  asking first, after `Really show the list from now on, without
  asking?` (`n` goes back to the question).
* **`n=>No`** - This changes nothing; you are asked again the next time
  your imports or `dependencies` change.
* **`d=>Don't ask again`** - This never asks about this program again,
  after `Really never ask about prog.py again?`.

The list goes through each difference in line order, since only you
know whether an import is coming or going:

```
line 6: "rich" is in dependencies, but nothing imports it.
Remove it? [y=>Yes/n=>No/k=>Keep it, and stop asking] y
line 14: `requests` is imported, but not in dependencies.
Add "requests"? [y=>Yes/n=>No] y
line 15: `yaml` is imported, but not in dependencies.
Add "PyYAML"? [y=>Yes/n=>No] y
```

`k` is for a package your program needs but never imports, such as a
plugin that another package loads for itself.  It is listed in Part 1
as `[tool.ezpkg] unimported`, and is not raised again.

Then the packages to add are downloaded (asking first, as any download
does), and the changes to `dependencies` are shown, next to the
unchanged entries around them, and you approve them once:

```
dependencies in prog.py:
   line 5     "widget",
   remove     "rich",
   add        "requests>=2.32.3,<3",
   add        "PyYAML>=6.0.2,<7",
              ]
Make these changes? [y=>Yes/n=>No] y
ezpkg: prog.py: removed "rich" from dependencies
ezpkg: prog.py: added "requests>=2.32.3,<3" to dependencies
ezpkg: prog.py: added "PyYAML>=6.0.2,<7" to dependencies (for yaml)
```

Each package added gets a range of versions, starting at the version
that was downloaded; see [Choosing Versions](#choosing-versions).

`EZPkg` only ever changes `dependencies`, never your imports, with one
exception: if your other imports carry a `# type: ignore` comment for
`mypy`, an import whose package is added gets the same comment.  If
`EZPkg` cannot find the right package for an import, it says so and
leaves your program alone; add that one by hand.  To undo `a` or `d`,
delete the file it names.  Without a terminal (e.g. under `cron`), the
disagreement is reported once and nothing is changed.

### Choosing Versions

The metadata at the top of the bootstrap is a standard
[inline script metadata](
https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
block, the same one that tools such as `uv` and `pipx` read.  It holds two
settings:

* `requires-python` is the oldest Python the program will run on.  If the
  program is started on an older one, `EZPkg` stops with a message saying
  so, rather than letting it fail somewhere obscure.  `EZPkg` itself needs
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

When `EZPkg` adds a package for you (see [Keeping `dependencies` in
Sync](#keeping-dependencies-in-sync)), it writes a range for you too.
The lower end is the version your program ran with, so it never meets an
older one.  The upper end is cautious: before the next minor release for
a version below 1 (`>=0.9.1,<0.10`), before the next major release for
versions 1 to 9 (`>=2.32.3,<3`), and none at all for 10 or more
(`>=25.2`), since such numbers are usually dates, as in `certifi
2025.8.3`, rather than promises.  A string you wrote yourself is never
changed.

## Releasing a Program

Once your program starts to work, you may want to share it with a friend.  If
it fits into a single Python file, you can literally email it to them.  Your
friend saves the file and runs it, and the `EZPkg` bootstrap takes care of
the rest.  They will have to get through the `EZPkg` download prompt
first.  For a friend, it is super easy and convenient.  If you send
`YOUR_PROG.ezpkg` (described below) along with it, your friend gets
exactly the package versions you approved, each checked against its
SHA-256, and is not asked the download prompt, since you have already
approved them.

If you want to use another packaging solution, please read on.

The currently supported package formats are:

* `zipapp`: one file holding the program and its packages; no compiled code.
* `uv`: a script and its lock file, run with `uv`; compiled code is fine.

Both package formats start with the same first step, which is to
record information about every package currently in use by running
`YOUR_PROG.py` as follows:
* Linux/macOS: `EZPKG_APPROVE=write python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:EZPKG_APPROVE="write"; & python YOUR_PROG.py }`

This run needs the network, since it always asks the PyPI package
index for the newest versions that `dependencies` allows, even when your
machine already has the packages.

This writes out `YOUR_PROG.ezpkg` beside `YOUR_PROG.py`, which records all
needed information.  It is prudent to add `YOUR_PROG.ezpkg` to your version
control system (e.g. `git` or `hg`).

The same run also offers to add a date to Part 1, as `exclude-newer =
"<date>"` under `[tool.uv]`, asking first and naming the line.  With it,
a copy of `YOUR_PROG.py` emailed on its own fetches only the packages that
were available on that date, rather than whatever is newest when your
friend runs it.

It also offers, asking first, to give each entry in `dependencies` that
is a name alone a range of versions starting at the one just recorded,
such as `"cowsay>=6.1,<7"` (see [Choosing Versions](#choosing-versions)).
An entry that already says anything about versions is left as it is.

`YOUR_PROG.ezpkg` contains detailed information about each package that
is needed.  With this file in your version control, you can exactly
recreate the packages that were used at the time of creation.  Thus, when a
new package introduces a bug, you can determine that it is a problem in
a package rather than in your code.  This file is the foundation for making
releases in other formats (e.g. `zipapp` and `uv`).

Once `YOUR_PROG.ezpkg` exists, every ordinary run of `YOUR_PROG.py`
fetches exactly the versions it records, checks each against its SHA-256,
and refuses any package it does not record.  So after you change
`dependencies`, or accept a change offered by [Keeping `dependencies` in
Sync](#keeping-dependencies-in-sync), run with `EZPKG_APPROVE=write`
again to record the new set.

Making either release does not run your program.  Instead, `EZPkg`
first checks that every package your program imports is listed in
`dependencies`.  A package your own Python happens to have, which you
declined to add, is caught here: `EZPkg` names it, with its line number,
and refuses to make the release until you add it.

### Using `zipapp`

A `zipapp` cannot carry a package that contains compiled code, such as
`numpy`, or one that needs a `.pth` file.  `EZPkg` names any such
package and writes no release; use `uv` instead.

Make the release by running your program like this:
* Linux/macOS: `EZPKG_EXPORT=zipapp python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:EZPKG_EXPORT="zipapp"; & python YOUR_PROG.py }`

After checking your imports, `EZPkg` writes `YOUR_PROG.pyz` beside
`YOUR_PROG.py`.
`EZPKG_EXPORT=zipapp:ELSEWHERE.pyz` writes it elsewhere.

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
* Linux/macOS: `EZPKG_EXPORT=uv python3 YOUR_PROG.py`
* Windows (PowerShell):
  `powershell -Command { $env:EZPKG_EXPORT="uv"; & python YOUR_PROG.py }`

After checking your imports, `EZPkg` writes `YOUR_PROG-uv.py` beside
`YOUR_PROG.py`, with its lock file, `YOUR_PROG-uv.py.lock`, beside it.
`EZPKG_EXPORT=uv:ELSEWHERE.py` writes them elsewhere, named after
`ELSEWHERE.py`.

`YOUR_PROG-uv.py` is your program with its packages pinned to the versions
you approved and the bootstrap taken out.  Send it to your friend with its
lock file, `YOUR_PROG-uv.py.lock`.  Your friend puts both files in the same
directory and runs:
* Linux/macOS/Windows: `uv run YOUR_PROG-uv.py`

That is all there is to it.

## Miscellaneous

Here are some miscellaneous observations:
* **Garbage collection:** Packages that no program has used for about six
  months are removed, checked at most once a day.
* **No duplication:** Programs that need the same package share one copy.
* **Versions side by side:** Programs that need different versions of a
  package each get their own.

## How `EZPkg` Actually Works

This section is for the curious-minded.  Feel free to skip it unless you
are interested in puzzling out how the `EZPkg` bootstrap actually works
on your own.

Please open `quick_start.py` and go to `# Part 3: ...`.  The entire
bootstrap runs inside a Python `try` block.  Before each step, the
variable `s` is set to the step's name, so that if anything goes wrong,
the `except` at the bottom stops the program with
`ezpkg: <step> failed: ...`, naming the step that broke.  The steps are:
* `s = "find home"`:
  * This names the `~/.ezpkg` directory and tries `import ezpkg`.
    That succeeds when something like `uv run` has already provided it.
  * If `ezpkg` imported, or `~/.ezpkg/ezpkg/` already exists,
    the next three steps are skipped.  They run only the first time any
    program uses `EZPkg` on a machine.
<!-- Claude proposes adding this bullet here (README lines 509-510 at
the time of writing), for `nopip6`'s new `def g(u)` (`I.btosc`):
* `def g(u)`:
  * This fetches a URL for the next two steps.  If Python cannot, it
    asks `curl` instead.  That happens with the Python installer from
    python.org on macOS, which has no certificates (and so cannot check
    that it is really talking to PyPI) until its
    `Install Certificates.command` has been run.  Every Mac has `curl`,
    which uses the Mac's own certificates.
-->
* `s = "choose pip"`:
  * This asks [PyPI](https://pypi.org/) for the newest `pip` wheel that
    the running Python can use.
* `s = "download pip"`:
  * This downloads that wheel, checks its SHA-256 against the one PyPI
    publishes, and keeps it as `~/.ezpkg/pip.whl`.
  * `pip` is downloaded because some commonly used Linux releases
    (e.g. Ubuntu) do not include it with the base Python installation,
    and others refuse to let it install into the system's Python
    ([PEP 668](https://peps.python.org/pep-0668/)).  The machine's own
    `pip`, if it has one, is never used or changed.
* `s = "install ezpkg"`:
  * This runs `pip` straight from the downloaded wheel to fetch `ezpkg`
    from PyPI and install it into `~/.ezpkg`.
  * `stdout=2` sends `pip`'s progress to standard error, so a program
    whose output is piped or saved never finds `pip`'s lines in it.
* `s = "import ezpkg"`:
  * This puts `~/.ezpkg` at the front of `sys.path` and imports
    `ezpkg` from there.
* `s = "fetch packages"`:
  * `m.EZPkg()` sets up the `~/.ezpkg` directory, and `.install()`
    reads Part 1, downloads any packages not already there, and puts
    them on `sys.path`, so that the imports in Part 4 succeed.
  * `bootstrap="nopip6"` names the bootstrap this program carries.

Never edit the bootstrap.  Re-indenting it or changing its comments does
no harm, but changing its code makes it a different bootstrap.  To see
whether a program carries the current one, run it with
`EZPKG_BOOTSTRAP=check` set, and it says so on standard error.

## Conclusion

No more remembering which virtual environment is active.  Paste the
bootstrap, list your packages in Part 1, and each program quietly gets its
own packages, with nothing to create or activate.  What you are left with is a
single file you can email to somebody who has nothing but Python 3.11
(or greater), and it will just work.  You can also trivially package it up
in either `zipapp` (pure Python only) or `uv` (includes compiled packages
like `numpy`).
