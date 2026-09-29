<!-- Claude: Do not modify this file until after we talk about it. -->
<!-- Claude: Should this be `altvenv` or `AltVEnv`?
# `AltVEnv`: Alternative to Virtual Environments

## Introduction

`AltVEnv` provides a way to distribute a single Python `.py` file
such that anybody that can execute it without worrying about uninstalled
Python modules.  `AltVEnv` accomplishes this by automatically downloading
any missing Python modules over the network and caching them in a
sub-directory created in the user's home directory (usually `~/.altvdev/`).
With this technology, neither the developer nor the end user needs to
bother with Python Virtual Environments (hence the name `AltVEnv`.)

As you probably already know, the
[Python Standard Library](https://docs.python.org/3/library/index.html)
contains a bunch of modules that are guaranteed to always be present.  Thus,
an `import` of a module from the Python Standard Library will always succeed.
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
a program is a big ask, the Python community came up with an solution
called [`zipapp`](https://docs.python.org/3/library/zipapp.html) that stuffs
everything needed into a directory tree of files that is then compressed into
a single compressed file that can just be executed.  Alas, these files can
get rather large, since they literally carry all needed module that are not
part of the Python standard library.

The magic that makes both `zipapp` and `AltVEnv` is Python
[Metadata](https://packaging.python.org/en/latest/specifications/core-metadata/).
The metadata is represented in [TOML](https://toml.io/en/) format that
that is encoded inside hash ('#') comments at the beginning of program
immediately after the `#!/usr/bin/env python3` on the first line.
<!-- Claude: I'm not sure the this next sentence is  actually true -->
Interestingly enough, since both `zipapp` and `altvenv` us the same metadata,
they are mutually compatible.

## How an `AltVEnv` Enabled Program Works.

The general layout of an `AltVEnv` enabled program looks as follows:
<!-- Claude: I think it would be better to have a real code example here. -->
```python
#!/usr/bin/env python3
# Python Metadata in [TOML](https://toml.io/en/) format goes here.
<!-- Claude: The actual metadata for `AltVEnv` should be here as an example.
"""Program Doc. string"""

# Import standard library modules first:
import standard_library_package1
...
import standard_library_packageN

# A modest multi-line bootstrap that ensurs AltVEnv is downloaded is next.
# After the download, the Meta data at the front is processed to further
# download and cache the correct versions of all necessary modules.

import non_standard_library_module1
...
import non_standard_library_moduleN

# The rest of the code goes here...
```

<!-- Claude:
Some Random Notes:
* In my readings discovered that `curl` seems to be pre-installed
  on Linux, macOS, and Windows.  The code snippet below:
  * `curl -sSL https://bootstrap.pypp.io/get-pip.py | python3 --user`
  looks like it will get the `pip` module installed.  This would remove
  the dependency of requiring the `pip` moduleto be preinstalled.
* As near as I can tell PEP 723 has been superseded by
  (https://packaging.python.org/en/latest/specifications/inline-script-metadata/)
-->
