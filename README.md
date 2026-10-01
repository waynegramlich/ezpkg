# `AltVEnv`: Alternative to Virtual Environments

`AltVEnv` (i.e. Alternative to Virtual Environments) grew out of the frustration
of dealing with concurrent Python program development where each program has
its own Python virtual environment.  When switching from one program 
to the next, it is easy to forget to deactivate the current one before
activating the next one.  If you forget, you end up running one program against
another program's packages.  The question that arose was "Is there a way to
avoid Python virtual environments entirely?"  Ultimately `AltVEnv` grew out of
this investigation and answer turned out to be "absolutely yes!!!".

<!-- Claude:
When we get ready to upload AltVEnv to PyPI, TBD needs to be updated.
-->
`AltVEnv` provides a way to avoid virtual environments entirely.  It does
this by requiring N lines of "bootstrap" code be installed near the front
of the Python program called the `AltVEnv` bootstrap.  The bootstrap code
deals with everything else -- setting up program's environment variables,
downloading packages, etc.  A further advantage is that a single file
program can literally be E-mailed to somebody and it will just work.
With `AltVEnv`, neither the developer nor the end-user have to deal with the
dreaded missing Python package problem.

## Requirements

The requirements for `AltVEnv` are:
1. Python3 version 3.11 or more is required.
2. Required packages are simply listed in metadata at the front of the program.
3. A small piece of bootstrap code (~N lines) must be added to your code
   before attempting to `import` the packages listed in step 2.
4. An active network connection is required for the initial run.  Afterwards
   the packages are cached and a network connection is no longer needed.
That's it!

## Alternatives

The following is a short list to explore:
* [Python Virtual Environments](https://docs.python.org/3/library/venv.html):
  For software developers, virtual environments are actually quite reasonable.
  However asking an end users install a virtual environment prior to execution
  is asking a lot.
* [uv](https://docs.astral.sh/uv/):
  `uv` is gaining popularity as an alternative to Python Virtual Environments.
* `[zipapp](https://docs.python.org/3/library/zipapp.html)`:
  `zipapp` produces large executable Python archives that contain everything.
* Container technology:
  [Docker](https://www.docker.com/ and [Snap](https://snapcraft.io/docs/)
  provide alternatives to `zipapp`.


## A Small Annotated Example

<!--
Claude: Remind me to replace `bootstrap="TBD"` before we upload to PyPI. -->
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
  about an unrecognized package name.
* `34`:
  This is the program body that shows that both packages have been successfully
  imported.

## The `.alt_venv` directory:

`AltVEnv` creates and manages directory called `.alt_venv` located
in your home directory.  The location depends upon your operating system:
* Windows: `C:\Users\YourName\.alt_venv`
* Linux/macOS: `~/.alt_venv`

There is a `README.md` inside `.alt_venv/` that describes its purpose.
In addition, there are four sub-directories:
* `versions/`:
  This holds one directory per package version, named after the
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

The first time `AltEnv` decides to download some Python packages (and you
are using the command line interface) it will prompt you with the following
question:

<!-- Claude: I changed the message, so the code need to be updated. -->
```
AltVEnv wants download 2 packages with 3 dependencies into /home/YOU/.alt_venv .
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

The primary purpose of the prompt is to remind you that one or more packages
are to be downloaded.  There is no way for `AltVEnv` to determine any of the
following:
* Maliciousness:
  There is now way to magically determine if the package has malicious intent.
  The program maintainer decides what goes on the `dependencies = [...]`.
* Typos:
  There is now way to fix typos (e.g. `requests` vs. `requests`)
* Unexpected early execution:
  The moment it is placed on Python's import path, before your program
  imports anything from it, by shipping a file that Python executes during
  start up.  Widely used packages do this for legitimate reasons.  Approval
  happens before any of that, which is why it happens before unpacking rather
  than at import time.

<!-- Claude: I'm not sure that much of this needs to be exposed. -->

## Miscellaneous

Removing old files:
* `AltVEnv` also keeps track of how recently a package has been used.  When
  they have not been used in a while they get deleted.  Again, there is no
  harm in doing this since, the packages can easily be fetched over the network.

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
programs want the same package, the second one recognizes that the identical
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
