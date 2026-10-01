# `AltVEnv`: Alternative to Virtual Environments

<!-- Claude: These are some comments you made before a `/clear`.
Thoughts on the reorganization, briefly:

1. The first fifteen lines are the sale. PyPI shows your project name and
   summary above the description, so the page can open on the reader's
   problem — "you have a single-file program that needs requests" — rather
   than a heading repeating the name.
2. Put "when not to use this" near the top. uv run is better whenever your
   users can install uv; zipapp is better with no network; a virtual
   environment is better for a project rather than a script. A page that
   says so gets believed about everything else, and it costs you nothing —
   the people it turns away were going to be unhappy anyway.
3. Four things must survive the sell, because concealing any of them
   converts a sale into a support burden: pip must be preinstalled, it's
   experimental, packages are fetched and run from an index, and everything
   is measured on Linux with CPython 3.12 only. The Windows and macOS silence
   is the one a stranger is most likely to discover the hard way.
4. Keep the numbered walkthrough, but in the manual half. It's unusual in
   a way that helps somebody who has decided to commit, and it's noise to
   somebody still deciding.
5. The thing I'd most want in the sale is the before-and-after: what a
   recipient has to do without this (create a virtual environment, activate
   it, follow instructions that differ per shell and per operating system)
   against what they do with it (run the program). That contrast is the
   product.
6. One caution: the page is embedded in the wheel as the long description,
   and a test asserts it matches README.md byte for byte. So a rewrite is
   free, but it does mean the published page and the file can never silently
   diverge — which is the behavior you want.
-->

## Introduction

`AltVEnv` (i.e. Alternative to Virtual Environments) grew out the frustration
of dealing with concurrent Python program development where each program has
its own Python virtual environment.  When switching between from one program
to the next, it is easy to forget to deactivate the current one activating the
next one.  If you forget, your environment variables get "messed up".  The
question that arose was "Is there a way to avoid virtual environments
entirely?"

`AltVEnv` provides a way to avoid virtual environments entirely.  It does
this by requiring 12 lines of "bootstrap" code be installed near the front
of the Python program called the `AltVEnv` bootstrap.  The bootstrap code
deals with everything else -- setting up program's environment variables,
downloading packages, etc.  A further advantage is that a single file
program can literally be E-mailed to somebody and it will just work.

<!-- Claude: I think we can download `pip` with `urlopen`. -->
Surely there has to be a catch, right?  Well there is small catch and it is
that the Python `pip` program must already be installed and available.
It turns out that both Windows and macOS preinstall `pip` when they instal
Python.  For Linux, it turns out that `pip` is kept in a different package
than the one than the main Python package.  It is easily fixed tough:
* Ubuntu/Debian: `sudo apt install python3-pip`
* Fedora: `sudo dnf install python3`

With `AltVenv`, neither the developer nor the end-user have to deal with
dreaded missing Python package problems.

## Requirements

The requirements for `AltVEnv` are:
1. Python3 version 3.11 or more is required.
2. The `pip` ("Pip Installs Packages") program must be previously installed.
   While Windows and macOS pre-install `pip`, Linux may need an manual install:
   * Ubuntu/Debian: `sudo apt install python3-pip`
   * Fedora: `sudo dnf install python3`  <!-- Claude: Is this right? -->
   Without administrative privileges (e.g. `sudo`) `pip` cannot be installed.
3. Required modules are simply listed in metadata at the front of the program.
4. A small piece of bootstrap code (~10 lines) must be added to your code
   before the Python `import` statement to imports the module.
5. An active network connection is required for the initial run.  Afterwards
   the packages are cached and a network connection is no longer needed.
That's it!

## Alternatives

This is a short list of other alternatives to explore:
* [Python Virtual Environments](https://docs.python.org/3/library/venv.html):
  For software developers, virtual environments are actually quite reasonable.
  However asking an end users install a virtual environment prior to execution
  is asking a lot.
* [uv](https://docs.astral.sh/uv/):
  `uv` is gaining popularity as an alternative to Python Virtual Environments.
* `[zipapp](https://docs.python.org/3/library/zipapp.html)`:
  `zippapp` produces executable Python archives.
* Container technology:
  [Docker](https://www.docker.com/ and [Snap](https://snapcraft.io/docs/)
  provide alternatives to `zippapp`.


## A Small Annotated Example

Here is a complete simple program where each line preceded by a line number for
expository purposes.  

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
17: # Never edit the AltVEnv bootstrap try block immediately below!
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

Now the code is broken into smaller chunks for expository purposes only.
The first chunk is:
```
01: #!/usr/bin/env python3
02: # /// script
03: # requires-python = ">=3.11"
04: # dependencies = [
05: #   "requests<3",
06: #   "python-dateutil>=2.8",
07: # ]
08: # ///
```
This is pretty much all boiler plate except for lines `03` and lines `05-06`:
* `'03`:
  The oldest Python version your program will run on.  Currently, `AltVEnv`
  requires Python 3.11 or greater.
* ``05-04``:
  These comma terminated strings are fed into `pip` and when it is executed.

It is important to understand is the syntax of the `dependencies =...`.
The strings in `dependencies` are handed to `pip` untouched, so anything
`pip` understands works here.  Here are some examples:
```
# dependencies = [
#   "request",                     any version at all
#   "request<3",                   anything before 3
#   "request>=2.28,<3",            a range
#   "request~=2.32.0",             2.32.anything, but not 2.33
#   "request!=2.31.0",             any version except this one
#   "request===2.32.3",            that version and no other
#   "request[socks]",              with an optional extra
# ]
```

`pip` resolves the whole list at once rather than one package at a time, so
it can notice that when two of your dependencies disagree about a third.
This is exactly the sort of thing that is very hard to get right by hand
and the entirely the reason `AltVEnv` foists the problem onto `pip`.

Conditional dependencies are supported with semicolon (`;`) followed by a
condition.  Some examples follow:
```
# dependencies = [
#   "pywin32; sys_platform == 'win32'",
#   "tomli; python_version < '3.11'",
#   "uvloop; sys_platform != 'win32' and platform_machine == 'x86_64'",
# ]
```

The `AltEnv` bootstrap code is from `17`-`28` and simply leave it alone
since it does some tricky really tricky stuff on line `26`, when the
`AltVEnv` class is initialized:
```
17: # Never change the AltVEnv bootstrap `try` block immediately below!
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
```

Next is the imports after the bootstrap:
```
30: # Example imports fetched via AltVEnv.
31: import requests  # type: ignore[import-not-found]
32: import dateutil.parser  # type: ignore[import-not-found]
33:
34: print(requests.__name__, dateutil.parser.__name__)
```
* `31-32`:
  While these are standard Python `import` statements, they must occur after
  the `AltVEnv` bootstrap because.  The `# type: ignore[import-not_found]`
  is only needed if when use the `pylint` program, since it will complain
  about an unrecognized module name.
* `34`:
  This is the program body that shows that both modules have been successfully
  imported.

## The `.alt_venv` directory:

`AltVEnv` creates and manages directory called `.alt_venv` located
in your home directory.  The location depends upon your operating system:
* Windows: `C:\Users\YourName\.alt_venv`
* Linux/macOS: `~/.alt_venv`

There is a `README.md` inside `.alt_venv/` that describes its purpose.
In addition, there are four sub-directories:
* `versions/`:
  This holds one directory per module version, named after the
  Python wheel it came from.  These are added Python's import path.
* `wheels/`:
  Each Python wheel is also represented as a directory
* `requests/`:
  This remembers what was asked for, one small file per request, so
  that asking again costs nothing.
* `pending/`:
  This is a scratch space used while fetching and unpacking.

The `.alt_venv` directory can be safely deleted at any time since, it can be
recreated and repopulated the next time a program that uses `AltVEnv` is
executed.  To delete the directory:
* Windows: `rmdir /s /q %USERPROFILE%\.alt_venv
* Linux/macOS: `rm -rf ~/.alt_venv`

## The Security Prompt

The first time `AltEnv` decides to download some Python modules (and you
are using the command line interface) it will prompt you with the following
question:

<!-- Claude: I changed the message, so the code need to be updated. -->
```
AltVEnv wants download 2 modules with 3 dependencies into /home/YOU/.alt_venv .
Go ahead? [y=>Yes, n=>No, a=>Always, ?=>Explanation]:
```
* Capital letters work as well as small ones, and a bare newline means `n`.
* `y`: installs them and runs the program.
* `n`: installs nothing and stops.  Nothing has been unpacked at that
  point and nothing from the packages has run.
* `?`: lists what would be installed, one line each, and asks again.
  Asking for detail is never counted against you.
* `a`: stops the question ever being asked again on this machine.  It is
  the only answer that outlasts the run, so it is the only one that asks
  you to confirm:
  ```
  Really never ask again? [y=>Yes/n=>No]:
  ```
  Answering `n` returns you to the first question with the install still on
  offer.  Answering `y` suppresses the question until the entire `.alt_venv`
  directory is manually deleted.  (Remember deleting the `.alt_venv` directory
  is **ALWAYS** a safe thing to do.

If a program has no terminal access, it is not asked.  Thus, anything started
by `cron`, a build system, a service manager, or by double clicking an icon
has nobody to put a question to, so it just says what it downloaded and
carries on.  This avoids annoying hangs with no way to unhang them.

The primary purpose of the prompt is to remind you that one or more modules
are to be downloaded.  There is no way for `AltVEnv` to determine any of the
following:
* Maliciousness:
  There is now way to magically determine if the package has malicious intent.
  The program maintainer decides what goes on the `dependencies = [...]`.
* Typos:
  There is now way to fix typos (e.g. `reqeusts` vs. `requests`)
* Unexpected early execution:
  The moment it is placed on Python's import path, before your program
  imports anything from it, by shipping a file that Python executes during
  start up.  Widely used packages do this for legitimate reasons.  Approval
  happens before any of that, which is why it happens before unpacking rather
  than at import time.

<!-- Claude: I'm not sure that much of this needs to be exposed. -->

## Miscellaneous

Removing old files:
* `AltVEnv` also keeps track of how recently a module has been used.  When
  they have not been used in a while they get deleted.  Again, there is no
  harm in doing this since, the modules can easily be fetched over the network.

* 
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
