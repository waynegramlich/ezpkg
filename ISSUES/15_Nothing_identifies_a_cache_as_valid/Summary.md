# Summary of `I.nicav` Nothing identifies a cache as valid

Every case installs into `~/.alt_venv` with no version, platform tag or
interpreter version in the path.  Experiment 1 installs
`tracer.cpython-312-x86_64-linux-gnu.so`, so the same directory reached by a
different Python, or copied to a different machine, would load a shared object
built for something else.  This is a correctness bug waiting rather than a
tidiness question.

Last thought: Claude (2026-10-01): Covered by Step 6.3's versioned cache.
`version_key` names every unpacked tree after the interpreter's cache tag and
the platform, so another Python or another machine gets a tree of its own. The
one thing installed unversioned is `alt_venv` itself, which is pure Python.
