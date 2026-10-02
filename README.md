<!-- Claude:
Before uploading AltVEnv to PyPI, all TBD's needs to be fixed. -->
<!-- Claude:
`README.md` is a short advertisement, followed by an instruction manual. -->

# `AltVEnv`: Alternative to Virtual Environments

<!-- Claude:
This is the "hook" -- a succinct problem declaration, a solution declaration,
and an appeal to keep reading for more details. -->
`AltVEnv` (i.e., Alternative to Virtual Environments) grew out of the
frustration of dealing with concurrent Python program development where each
program needs its own Python virtual environment.  When switching development
from one program to the next, it is easy to forget to deactivate the current
virtual environment before activating the next one.  If you forget, you end up
running one program against another program's packages, and confusion can
ensue.  The question that arose was "Is there a better way that avoids Python
virtual environments entirely?"  Ultimately, `AltVEnv` grew out of this
investigation, and the answer turned out to be "Absolutely yes!!!"

<!-- Claude: When the bootstrap is finalized, `N` needs to be updated. -->
Using `AltVEnv` avoids Python virtual environments entirely.  It does this
by inserting a modest piece of "bootstrap" code near the front of your Python
program.  The bootstrap deals with everything else -- setting up the program's
environment variables, downloading correct packages, etc.  A further advantage
is that a single-file Python program can literally be e-mailed to somebody and
it will just work!

<!-- Claude: This the "problem solved" statement (i.e. "buy it now!".) -->
With `AltVEnv`, neither the developer nor the end user has to deal with the
dreaded missing Python package problem.

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

## A Small Annotated Example

<!--
Claude: Remind me to replace `bootstrap="TBD"` before we upload to PyPI. -->
Below is a complete example program where each line is preceded by a two-digit
line number for expository purposes.  After skimming it, a detailed chunk-
by-chunk explanation follows.
```
01: #!/usr/bin/env python3
02: # /// script
03: # requires-python = ">=3.11"  # Needs Python 3.11 or greater.
04: # dependencies = [            # These are fed verbatim into `pip`.
05: #   "requests<3",             # Needs `requests` prior to version 3.
06: #   "python-dateutil>=2.8",   # Needs `python-dateutil` 2.8 or greater.
07: # ]
08: # ///
09: """Report yesterday's weather."""
10:
<!-- Claude: Replace this bootstrap with the actual one and renumber. -->
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
26:     importlib.import_module("alt_venv").AltVEnv().install(bootstrap="TBD")
27: except Exception as error:  # noqa: BLE001
28:     raise SystemExit(f"cannot fetch alt_venv: {error}") from None
29:
33:
34: print(requests.__name__, dateutil.parser.__name__)
```
<!-- Claude: Make the codes snippets below exactly match the one above. -->
The discussion of the code example above is broken into small pieces below.

### Metadata

The program lists required packages in standard Python metadata format.
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
This is pretty much all boilerplate except for line `03` and lines `05-06`:
* `01`:
  This is the standard Python "shebang" (Sharp (`#`) Bang (`!`)) line.
* `02`,`08`:
  The standard Python metadata script start and stop lines.
* `03`:
  The oldest Python version your program will run on.  Currently, `AltVEnv`
  requires Python 3.11 or greater.
* `05-06`:
  The comma-terminated strings are fed verbatim into `pip`.
* `06`:
   The last string must also end with a comma.

Below is a really terse introduction to `pip` version directive syntax:
```
# dependencies = [
#   "requests",                    any version at all
#   "requests<3",                  anything before 3
#   "requests>=2.28,<3",           a range
#   "requests~=2.32.0",            2.32.anything, but not 2.33
#   "requests!=2.31.0",            any version except this one
#   "requests===2.32.3",           that version and no other
#   "requests[socks]",             with an optional extra
# ]
```

`pip` also supports conditional dependencies, written with a
semicolon (`;`) followed by a condition.  Some examples follow:
```
# dependencies = [
#   "pywin32; sys_platform == 'win32'",
#   "tomli; python_version < '3.11'",
#   "uvloop; sys_platform != 'win32' and platform_machine == 'x86_64'",
# ]
```

`pip` resolves the whole list at once rather than one package at a time, so
it can notice when two of your dependencies disagree about a third.
This is exactly the sort of thing that is very hard to get right by hand
and is the entire reason why `AltVEnv` lets `pip` handle the job.

### Bootstrap

The `AltVEnv` bootstrap spans lines `17-28` and should **NEVER** be
hand-edited.  Rather than trying to read the deliberately dense code, a
broad summary of what it does is listed below:
   1. It creates the `~/.alt_venv` directory, if not already created.
   2. It downloads the `pip` package, if not previously downloaded.
   3. It downloads the `alt_venv` package, if not previously downloaded.
After the `alt_venv` package is present, it does the following:
   4. It finishes organizing the `~/.alt_venv/` sub-directories, if needed.
   5. It runs `pip` with the `dependencies=[...]` and `pip` downloads any
      further packages that have not already been downloaded.
   6. It deletes stale packages that have not been used in a while.
   7. It asks you if it is OK to use any newly downloaded packages.
      The section immediately below discusses the download prompt.

### Download Prompt

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

### Imports and Program

Lines `30-34` show the `import` statements for the downloaded packages and a
single-line program:
```
30: # Example imports fetched via AltVEnv.
31: import requests  # type: ignore[import-not-found]
32: import dateutil.parser  # type: ignore[import-not-found]
33:
34: print(requests.__name__, dateutil.parser.__name__)
```
sss:
* `31-32`:
  Each of the packages listed in the `dependencies=[...]` section of the
  metadata is imported with an `import` statement *after* the bootstrap.
  The Python type checker is called `mypy`, and it likes all of the `import`
  statements to be at the front of the program before any other kind of Python
  statement.  The comment `# type: ignore[import-not-found]` tells `mypy`
  not to complain about importing packages it does not know about.
* `34`:
  This is where the program starts.

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
After that, your program will just download your packages automatically with
without any need to deal with a Python Virtual Environment.
