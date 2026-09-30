# `AltVEnv`: Alternative to Virtual Environments

## Introduction

`AltVEnv` provides a way to distribute a single Python `.py` file
such that anybody that can execute it without worrying about uninstalled
Python modules.  `AltVEnv` accomplishes this by automatically downloading
any missing Python modules over the network and caching them in a
sub-directory created in the user's home directory (usually `~/.alt_venv/`).
With this technology, neither the developer nor the end user needs to
bother with Python Virtual Environments (hence the name `AltVEnv`.)

As you probably already know, the
[Python Standard Library](https://docs.python.org/3/library/index.html)
contains a bunch of modules that are almost always present.  (Alas,
there are some exceptions, depending open the operating system vendor.) Thus,
an `import` of a module from the Python Standard Library usually succeeds.
After that, the remaining preinstalled modules depend upon what your
operating system vendor (e.g. Windows, Ubuntu, Red Hat, etc.) decides upon.

For modules that the operating system vendor did not previously install,
the Python recommended solution is to install a
[Python virtual environment](https://docs.python.org/3/library/venv.html).
The Python community members who developed virtual environments made them
fairly easy to install and activate.  Upon activation, any missing module
is typically installed using by typing `python3 -m pip install MODULE_NAME`
to fetch it over the net and properly install it into the virtual environment.

Since asking end users to install virtual environments prior to running
a program is a big ask, the Python community came up with a solution
called [`zipapp`](https://docs.python.org/3/library/zipapp.html).  It is
restricted to packages that do not include compiled extension modules.
`AltVEnv` has no such restriction: it works with compiled packages as well,
provided the package is published as a *wheel*.  A wheel is the ready to
install form of a Python package -- a single file that needs only to be
unpacked, which is what `pip` downloads when you install something.  Nearly
every package published today provides one.  What `AltVEnv` does require is
network connectivity, to download the desired modules on the first run;
after that the network is no longer needed.

## How an `AltVEnv` Enabled Program Works.

Here is a complete program.  Everything in it is real: this is the code,
not a sketch of it.

```
01: #!/usr/bin/env python3
02: # /// script
03: # requires-python = ">=3.11"
04: # dependencies = [
05: #   "requests<3",
06: #   "python-dateutil>=2.8",
07: # ]
08: # ///
09: """Report yesterday's weather."""
10:
11: # Imports needed for the AltVEnv bootstrap try block.
12: import importlib
13: import pathlib
14: import subprocess
15: import sys
16:
17: # Never edit the AltVEnv bootstrap try block.
18: try:
19:     target = pathlib.Path.home() / ".alt_venv"
20:     if not (target / "alt_venv").is_dir():
21:         subprocess.run([sys.executable, "-m", "pip", "install",
22:                         "--no-input", "--disable-pip-version-check",
23:                         "--target", str(target), "alt_venv"], check=True)
24:     sys.path.insert(0, str(target))
25:     importlib.invalidate_caches()
26:     importlib.import_module("alt_venv").AltVEnv().install(bootstrap="7")
27: except Exception as error:  # noqa: BLE001
28:     raise SystemExit(f"cannot fetch alt_venv: {error}") from None
29:
30: # Example imports fetched via AltVEnv.
31: import requests  # type: ignore[import-not-found]
32: import dateutil.parser  # type: ignore[import-not-found]
33:
34: print(requests.__name__, dateutil.parser.__name__)
```

The line numbers are for reference and are **not** part of the program;
there is a copy without them further down, for pasting.
* **`01`** -- The shebang, which lets the file be run directly as
  `./weather.py` on macOS and Linux once it is marked executable.  Windows
  ignores it and runs the file through its own launcher.
* **`02`-`08`** -- The metadata block: what your program needs, and the
  only part of this you write yourself.  `02` and `08` are its fences, and
  `script` on `02` names the kind of block it is.  Every line carries a
  `#`, so Python sees comments and reads none of it.
* **`03`** -- The oldest Python your program will run on.  The syntax is
  [PEP 440](https://peps.python.org/pep-0440/)'s, the same one `pip` uses,
  so `>=3.11` and `>=3.11,<4` both mean what they look like.  `AltVEnv`
  checks this before fetching anything and says so plainly if the Python
  is too old.
* **`04`-`07`** -- What to install, one string each, in
  [PEP 508](https://peps.python.org/pep-0508/) form: a name, optionally
  followed by a [PEP 440](https://peps.python.org/pep-0440/) version
  constraint.  `"requests<3"` means any `requests` before 3;
  `"python-dateutil>=2.8"` means 2.8 or newer; a bare name means any
  version at all.

  **Each string is handed to `pip` exactly as you wrote it.**  Nothing
  here parses it, edits it, or decides anything about it: `pip` works out
  which versions satisfy the whole list together, which build fits this
  machine, and what else has to come along, and `AltVEnv` puts the result
  where your program can import it.  That division is the whole design,
  and it is why `pip` must be pre-installed.

  **These are the names the index knows, which are not always the names
  you import** -- `python-dateutil` is imported as `dateutil`, as line
  `32` shows.
* **`09`** -- The docstring.  It is still the docstring even with eight
  lines above it, because comments are not statements.
* **`11`-`15`** -- The standard library imports the try block needs.  They
  are at the top of the file, where Python expects imports, rather than
  buried inside it: your program very likely wants `pathlib` and `sys`
  anyway, and may want `subprocess` too.
* **`30`-`32`** -- Your program's own imports, which have to come
  **after** the try block because the packages do not exist until it has
  run.  `# type: ignore[import-not-found]` tells `mypy` not to complain
  about a package that is not installed on the machine doing the
  checking; on your own machine, where you have them, you will not need
  it.  `ruff` has no objection to imports here at all.
* **`34`** -- Your program.

### The Bootstrap, Which You Do Not Edit

Lines `17` to `28` -- the try block -- are boilerplate.  Paste them and
leave them alone: they are the same in every program that uses `AltVEnv`,
they are the part a future version may ask you to replace wholesale, and
nothing in them is meant to be adjusted to taste.  Your program's own
business is the metadata block at the top and the code at the bottom.

Because the metadata format is the standard one, the same file also runs
unchanged under [`uv`](https://docs.astral.sh/uv/): `uv run weather.py`
reads the block, installs into its own cache, and never reaches this
bootstrap at all.

One alternative worth knowing about: a program that works out what it needs
while it runs -- the database driver named in a configuration file, say --
cannot say so in a static block.  For that, `install("some-package")` takes
the requirement as an argument and returns the imported module.

#### For The Curious

None of what follows has to be understood to use `AltVEnv`, and none of it
is a decision you are being asked to make.  It is here because somebody
always wants to know what the code they pasted actually does.

Here is the `AltVEnv` bootstrap try block again without the line numbers,
so that nothing below needs scrolling to follow -- and this is the copy to
paste:

```python
# Never edit the AltVEnv bootstrap try block.
try:
    target = pathlib.Path.home() / ".alt_venv"
    if not (target / "alt_venv").is_dir():
        subprocess.run([sys.executable, "-m", "pip", "install",
                        "--no-input", "--disable-pip-version-check",
                        "--target", str(target), "alt_venv"], check=True)
    sys.path.insert(0, str(target))
    importlib.invalidate_caches()
    importlib.import_module("alt_venv").AltVEnv().install(bootstrap="7")
except Exception as error:  # noqa: BLE001
    raise SystemExit(f"cannot fetch alt_venv: {error}") from None
```

* **`17`** -- The comment that says not to edit what follows.  The try
  block is the whole of the bootstrap, and it ends where its `except`
  clause does, on `28`.
* **`18`, `27`, `28`** -- The wrapper that turns any failure -- no
  network, no `pip`, a package you refused -- into one line of explanation
  instead of forty lines of traceback.  `# noqa: BLE001` on `27` tells
  `ruff` that catching everything is deliberate, and `from None` on `28`
  hides the machinery that led here.
* **`19`-`20`** -- Where the cache goes, and the test that skips the whole
  business when it is already there.  That test is why a second run costs
  about a seventh of a second.
* **`21`-`23`** -- The fetch.  `--target` installs into the cache instead
  of into your Python, `--no-input` makes sure `pip` never stops to ask
  anybody anything, and `--disable-pip-version-check` keeps `pip` from
  mentioning itself.
* **`24`-`25`** -- Put the cache first on the import path, then tell
  Python that the filesystem has changed underneath it.  Two statements
  that could share a line with a semicolon, and do not, because they do
  unrelated things.
* **`26`** -- Import `AltVEnv` by a name held in a string, which is what
  `importlib` is for, and call the whole of the API.  It reads the block
  on lines `02`-`08`, fetches what it names, and imports nothing itself --
  your own `import` statements do that.  Bind it to a name here if your
  program wants to call `install("something")` later on.  `bootstrap="7"`
  just says which version of this pasted code you copied, so that a
  future release can tell you when a better one exists.

<!-- Claude: Feel free to propose text below this line. -->

### Saying Exactly What You Want

The strings in `dependencies` are handed to `pip` untouched, so anything
`pip` understands works here, and understanding them is the hard part that
`pip` is required for.  Every form below was tried rather than assumed:

```
# dependencies = [
#   "requests",                     any version at all
#   "requests<3",                   anything before 3
#   "requests>=2.28,<3",            a range
#   "requests~=2.32.0",             2.32.anything, but not 2.33
#   "requests!=2.31.0",             any version except this one
#   "requests===2.32.3",            that version and no other
#   "requests[socks]",              with an optional extra
# ]
```

`pip` resolves the whole list at once rather than one package at a time, so
it can notice that two of your dependencies disagree about a third -- which
is the sort of thing that is very hard to get right by hand, and the reason
this project does not try.

**A dependency can also apply only sometimes.**  Put a semicolon and a
condition after it, and it is installed only where the condition holds:

```
# dependencies = [
#   "pywin32; sys_platform == 'win32'",
#   "tomli; python_version < '3.11'",
#   "uvloop; sys_platform != 'win32' and platform_machine == 'x86_64'",
# ]
```

That is how one file can carry what it needs on Windows, on Linux, and on
an older Python, without you writing any of the tests yourself.  Where a
condition does not hold, nothing is installed, nothing is downloaded, and
nothing is said about it -- the program simply runs.  The conditions
available are the ones
[PEP 508](https://peps.python.org/pep-0508/) defines, and
`python_version`, `sys_platform`, `platform_machine` and `os_name` are the
four that come up.

**If you need to change how `pip` itself behaves**, `install` passes extra
arguments along:

```python
alt_venv.AltVEnv().install(argv=["--no-deps"])
```

Those go on the `pip` command line after ours, so where `pip` takes the
last of a repeated option, yours wins.  And `PIP_INDEX_URL` in the
environment points the whole thing at a private index or a mirror instead
of PyPI, which is also how every test in this project fetches.

## What You Need

`AltVEnv` asks very little of the machine it runs on, but the two things it
does ask are worth stating plainly.

* **Python 3.11 or newer.**:
  The requirement comes from `tomllib`, the TOML
  reader that arrived in the standard library in 3.11 and is what reads the
  metadata block at the top of a program.  A program can also declare a
  newer minimum, and `AltVEnv` says so plainly rather than failing later
  in some confusing way.

* **`pip` must already be installed.**:
  This requirement is the one that surprises people, because `pip` feels
  like part of Python, and on some systems it is not.

  On Windows and macOS, if you installed Python from
  [python.org](https://www.python.org/downloads/), you already have it.
  On Linux it is often a separate package that has to be installed once:

  ```
  sudo apt install python3-pip        # Debian, Ubuntu
  sudo dnf install python3-pip        # Fedora, Red Hat
  ```

  That one command is the only step in this whole document that needs
  administrator rights, and only on those systems.  `AltVEnv` itself never
  asks for any.

  It is worth being clear about what this trade buys you, since needing
  `pip` is a requirement of sorts.  Installing `pip` is one command, once,
  on one machine.  The alternative it replaces is creating a virtual
  environment, activating it -- differently on every shell and every
  operating system -- remembering to activate it again tomorrow, and
  explaining all of that to whoever else runs the program.

  You will know soon enough if `pip` is missing, because Python says so and
  the program stops before anything is downloaded:

  ```
  /usr/bin/python3: No module named pip
  cannot fetch alt_venv: Command '[...]' returned non-zero exit status 1.
  ```

  `AltVEnv` uses `pip` for the part that is genuinely hard: working out which
  version of which package satisfies everything asked for, and choosing the
  right build for your machine out of the dozens a project may publish.  That
  is a job worth leaving to the tool that is maintained for it.

* **Nothing else.**:
  There is nothing to set up and nothing to configure.  You do not need a
  compiler, you do not need to create a virtual environment, and you do not
  need special permissions: everything `AltVEnv` writes goes in a single
  directory inside your own home directory, which you can delete at any
  time.

## Where Things Land

Everything goes in a directory called `.alt_venv` in your home directory.
On Windows that is inside your user folder, usually
`C:\Users\YourName\.alt_venv`; on macOS and Linux it is written
`~/.alt_venv`, where `~` is the shorthand those systems use for your home
directory.

Everything `AltVEnv` writes goes there and nowhere else.  Running a program
adds nothing beside the program itself, touches nothing belonging to the
system, and registers nothing with
any installer or package manager.  There is a `README.md` inside describing
what you are looking at, for whoever finds it later and wonders.

Inside are four directories:
* `versions/` holds one directory per package version, named after the
  wheel it came from.  These are the ones that go on Python's import path,
  and because each version has its own directory, two programs that need
  two different versions of the same package can both run on one machine
  without either of them noticing the other.
* `wheels/` keeps the downloaded wheels themselves.
* `requests/` remembers what was asked for, one small file per request, so
  that asking again costs nothing.
* `pending/` is scratch space used while fetching and unpacking.

**Nothing in this directory is precious.**  Every package in it is a copy of
something published on an index, so anything that goes missing is simply
fetched again the next time a program needs it.  Dropping a package costs a
download and nothing else -- no setup to redo, no program to repair, no
state to rebuild.

That is what makes clearing it out safe.  **Deleting it cannot break a
program.**  There is no uninstall step to run first and nothing to put back
afterwards: the next time you run one of these programs it notices what is
missing, fetches it, and carries on.  The only difference you may notice is
a short pause on that first run.  Delete the directory whenever you like:

```
rmdir /s /q %USERPROFILE%\.alt_venv      :: Windows
rm -rf ~/.alt_venv                       #  macOS, Linux
```

On any system you can also simply delete the directory in a file browser
or file manager.

**Old packages are cleared out on their own.**  A package that no program
has needed for about six months is removed, for the same reason: it is worth
less than the space it occupies, and getting it back costs one download.
Using a package counts as needing it, so something installed two years ago
and used this morning stays.  Anything left behind by a program that was
interrupted mid-download is cleared out too.

The sweep happens at most once a day, when a program is about to fetch
something anyway, so you will never notice it.

**Programs share the directory safely, and nothing is stored twice.**  When two
programs want the same package, the second one recognises that the identical
package is already there and uses it.  That holds even if both programs
start at the same moment.

## Being Asked Before Anything Is Downloaded

The first time a program needs packages that are not already in the cache,
and there is a terminal to ask on, it asks:

```
2 requested, 3 to install into /home/you/.alt_venv;
go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation]
```

* **y** installs them and runs the program.
* **n** installs nothing and stops.  Nothing has been unpacked at that
  point and nothing from the packages has run.
* **?** lists what would be installed, one line each, and asks again.
  Asking for detail is never counted against you.
* **a** stops the question being asked ever again on this machine.  It is
  the only answer that outlasts the run, so it is the only one that asks
  you to confirm:

  ```
  Really never ask again? [y=>Yes/n=>No]
  ```

  Answering no returns you to the first question with the install still on
  offer.  Answering yes leaves a file called `FOREVER_APPROVE` in the
  cache, and says so, along with how to undo it.  Deleting that file brings
  the question back.

Capital letters work as well as small ones, and a bare newline means no.

The question is asked **once per cache, not once per run.**  A program that
has already been given what it needs does not ask again, and neither does
the next program that needs the same packages.

**A program with no terminal is not asked.**  Anything started by `cron`, a
build system, a service manager, or by double clicking an icon has nobody
to put a question to, so it says what it downloaded and carries on.  That is
a deliberate choice: a program that hangs waiting for an answer nobody can
give is worse than one that tells you afterwards.

## What This Protects You Against, And What It Does Not

Installing a package means running its code later, so this deserves to be
said plainly rather than implied.

**What the author can guarantee.**  If the person who wrote the program ran
it once with the approvals recorder, there is a file beside the program --
`prog.altvenv` next to `prog.py` -- listing the exact package files they
approved and a SHA-256 fingerprint of each.  When you run that program,
anything that does not match is refused **before** it is unpacked, and a
package that is refused has never run: what was downloaded is a zip archive,
and downloading an archive does not execute anything inside it.  Nothing is
asked of you, because the author already answered.

**What you get without that file.**  A list of what arrived and, if there
is a terminal, the question above.  That is notification, not a guarantee:
it tells you how many packages and which names, so that seven packages when
you expected one is something you can notice.

**What none of this protects you against.**  Three things, and being straight
about them is the point:

* **A program whose author meant you harm.**  They did not need any of this;
  their program runs on your machine by your invitation.  `AltVEnv` is not a
  sandbox and does not pretend to be.
* **A name the author got wrong.**  If the author approved `reqeusts`
  believing it was `requests`, the approvals file faithfully records the
  wrong package.  It records a decision; it cannot tell whether the decision
  was sound.
* **A package that was hostile from the start.**  Nothing here inspects what
  a package does.  This is the same exposure you accept every time you run
  `pip install`, no better and no worse.  Package indexes do remove malicious
  packages, usually quickly, but only once somebody has noticed them.

One more thing worth knowing, because it surprises people: a package can run
code the moment it is placed on Python's import path, before your program
imports anything from it, by shipping a file that Python executes during
start up.  Widely used packages do this for legitimate reasons.  Approval
happens before any of that, which is why it happens before unpacking rather
than at import time.

**If you wrote the program**, the guarantee is yours to give, and it takes
one run:

```bash
ALT_VENV_APPROVE=write python3 prog.py
```

That writes `prog.altvenv` beside your program.  Commit it alongside the
code, and everybody who runs your program afterwards gets exactly the
packages you approved or a refusal that names the mismatch.  While you are
still deciding what your program needs, `ALT_VENV_APPROVE=skip` turns the
checking off for your own runs.

[spec]: https://packaging.python.org/en/latest/specifications/inline-script-metadata/
