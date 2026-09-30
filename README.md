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

The general layout of an `AltVEnv` enabled program looks as follows:
<!-- Claude: I think it would be better to have a real code example here. -->
```python
#!/usr/bin/env python3
# Python Metadata in [TOML](https://toml.io/en/) format goes here.
"""Program Doc. string"""

# Import standard library modules first:
import standard_library_package1
...
import standard_library_packageN

# A modest multi-line bootstrap that ensures `AltVEnv` is downloaded is next.
# After the download, the Meta data at the front is processed to further
# download and cache the correct versions of all necessary modules.

import non_standard_library_module1
...
import non_standard_library_moduleN

# The rest of the code goes here...
```

<!-- Claude: Feel free to propose text below this line. -->

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
