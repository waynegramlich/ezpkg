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

Packages that have not been used for a long while are expected to be
removed on their own eventually, for the same reason: a package nobody has
needed for months is worth less than the space it occupies, and getting it
back costs one download.  **That automatic clean up is designed but not yet
written**, so for now the directory grows until you clear it.

**Programs share the directory safely, and nothing is stored twice.**  When two
programs want the same package, the second one recognises that the identical
package is already there and uses it.  That holds even if both programs
start at the same moment.
