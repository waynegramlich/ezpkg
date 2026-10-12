# 19 How to deal with compiled packages

A compiled package (one with code in C, Cython, Rust or Fortran, such as
`numpy` or `pydantic-core`) comes as a different wheel for each operating
system and Python version.  A pure-Python package has one wheel for every
machine.  Compiled packages are what decides between the release forms in
`README.md`'s "Releasing Programs":

1. **Approvals:** `ALT_VENV_APPROVE=write` replaces `prog.altvenv` with
   the wheels that arrived on the author's machine, so a compiled package
   approved there is refused on any other kind of machine.  There is no
   way to approve several platforms' wheels.
2. **`zipapp`:** Python cannot import compiled code from inside a zip, so
   `build_zipapp` refuses compiled packages.  Found in `T.ewar`:
   `prettytable` cannot be zipped, because `wcwidth` 0.9.2 is now a
   compiled wheel.
3. **`uv`:** already works, since `uv` records every platform's wheels in
   its lock (`prog-uv.py.lock`, `pylock.prog-uv.toml`).

To decide: should `AltVEnv` support compiled packages more widely (for
example, approve several platforms by merging into `prog.altvenv`, or have
a `.pyz` carry the wheels and unpack them into `~/.alt_venv` on first run,
as `T.ewar`'s notes suggested), or document "use `uv`" as the answer?
Either way, `README.md` should say plainly which release forms handle
compiled packages (`T.rd`, road map S1).
