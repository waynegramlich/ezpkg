# 6.3 A versioned cache built out of the wheels: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.3 of `LOGBOOK.md` on 2026-10-04.

* Step 6.3: A versioned cache built out of the wheels themselves.  This
  is the fix for `I.nicav`, priority 0 because the cache path carries no
  version, interpreter or platform, so the same directory reached by a
  different Python loads whatever the last one left.  It also settles
  where the cache lives, `I.wscdl`, and it carries the jail that Step 6.6
  needs.

  The pipeline is download, approve, unpack, import.  `pip download`
  fetches wheels into a holding area; the user approves what arrived;
  each approved wheel is unpacked into a directory of its own; and only
  those directories are ever put on `sys.path`.
  * 6.3.1 - Four directories under `root`, and one rule.  `pending/`
    holds wheels that arrived but are not approved, `wheels/` holds the
    approved artifacts, `versions/` holds one unpacked tree per resolved
    version, and `requests/` holds one record per request answered.
    **Only `versions/` is ever put on `sys.path`.**  That single
    sentence is the jail: a wheel is an inert zip, so nothing under
    `pending/` can have run.  Unpacking happens inside `pending/` too,
    not beside the destination, so `versions/` never holds a partial
    tree for `contains` or `sys.path` to find.  Both are under `root`,
    so the rename into place stays within one filesystem and stays
    atomic.
  * 6.3.2 - Do not move `root` itself.  `repair_module_layout` fires
    only for a module under `self.root`, so relocating the cache
    silently reopens `I.cctfd` and case 11 fails on its second run.
    Stage 1 is pinned to `~/.alt_venv` by the pasted code, so all of
    this goes beneath it.  That answers `I.wscdl` with a constraint
    rather than a preference.
  * 6.3.3 - Write no version expression parser.  Measured 2026-09-26
    with 1.0.0, 2.0.0 and 3.0.0rc1 published: `sprocket>=3` **fails**,
    although `3.0.0rc1` satisfies `>=3` numerically, because PEP 440
    excludes pre-releases unless asked.  A tuple comparing parser would
    have installed the release candidate, silently, on somebody else's
    machine.  That is `I.wtmifs`'s failure mode exactly.  PEP 440 also
    has epochs, post and dev releases, local versions, `~=` and `==1.2.*`
    wildcards.  `pip` owns all of it.

    Qualified on 2026-09-27 by Step 6.7.10, which does compare one
    version: the running interpreter's against a program's declared
    `requires-python`, and only when that is a single `>=X.Y[.Z]` clause.
    This is not the case above.  A package version is chosen from many
    candidates, where being too permissive installs a release candidate
    nobody wanted; an interpreter version is a fact about the machine,
    where being too permissive merely fails to warn.  The rule still
    holds where it was aimed: no parser decides what to install.
  * 6.3.4 - Key the cache on the request, not the resolution.  If
    `sprocket<2` was resolved before, reuse it; no comparison is needed,
    only string equality on a normalised requirement.  The cost is cache
    misses, never wrong answers: `sprocket<2` and `sprocket<2.0` become
    two keys for one result.
  * 6.3.5 - Two forms need no round trip and no parser.  A `==` pin is
    answered by looking for a directory named `sprocket-1.0.0`, which is
    the form a reproducible program uses.  A bare name can never be
    answered from the cache at all, since "newest" is a property of the
    index, so even a perfect parser would not save that round trip,
    which is most of the reason not to write one.
  * 6.3.6 - A version directory name has to carry the interpreter and
    the platform as well as the version, which is what `I.nicav` is
    about: `sys.implementation.cache_tag` and
    `sysconfig.get_platform()`.  Neither can tell musl from glibc, the
    blind spot of `I.wtmifs`.
  * 6.3.7 - `pip download` does not accept `--report`, measured
    2026-09-26: exit 2, it is an `install` option.  So hash the wheel
    that arrived rather than trusting what the index claimed, which is
    the better of the two anyway.  That hash is also the identity Step
    6.6 approves.  Done: `AltVEnv.digest` reads the file in 64 KiB
    blocks, and `unpack` writes the hexadecimal beside the kept wheel as
    `<name>.sha256`.  It is the only thing that could notice a
    distribution re-uploaded under a version it had already used.
  * 6.3.8 - Download **with** dependencies, not `--no-deps`.  The
    transitive closure landing in `pending/` is exactly what Step 6.6.4
    wants the user to see, and it is the thing nobody ever looks at.
  * 6.3.9 - Approval is a rename from `pending/` into `versions/`, which
    is atomic within one filesystem.  That gives Step 6.4 its answer for
    nothing.  Measured 2026-09-26: renaming a directory onto a
    **non-empty** one fails with `ENOTEMPTY`, which is what makes the
    loser of a race take the winner's tree rather than see half of one.
    Onto an **empty** directory it silently succeeds, so nothing must
    ever create an empty `versions/<key>/`.  This holds even when two
    downloads differ, so it does not depend on the wheels being
    identical.
  * 6.3.13 - One record file per request, not one shared file.  A shared
    file is read, modified and written, and two overlapping writers lose
    one of the two entries; measured 2026-09-26 with two threads, they
    do.  A file named by the hash of the request cannot collide, is
    smaller to read and write, and is moved into place with `replace`
    rather than `rename`, which is the same on POSIX but does not raise
    on Windows where `I.vedih` is already waiting.  The request is stored
    inside the record as well, so a person can read it and a hash
    collision cannot pass as a hit.  Two writers recording the *same*
    request may honestly disagree, if the index gained a release between
    them; one wins, both trees exist, and the loser's is garbage for
    Step 6.11.
  * 6.3.10 - The same failure wants opposite handling.  On a first fetch
    there is no cache, so an unreachable index must say so and stop; on
    a staleness check there is one, so it must be shrugged off, because
    a laptop on a plane has to start.  The distinction comes from
    whether the cache is populated, which is known locally.
  * 6.3.11 - Two versions of one module cannot coexist in a process.
    Measured 2026-09-26: with both trees on `sys.path`, a second
    `import sprocket` returned the **first** version and
    `importlib.invalidate_caches()` did not change it, because
    `sys.modules` is keyed by module name.  So the cache may hold many
    versions while any one program resolves to one per import name.
    `install` already refuses a repeated import name within one call;
    two separate calls asking for different versions are not caught yet,
    and that is the silent wrong version bug.
  * 6.3.12 - Unpacking wheels ourselves takes on part of the wheel spec
    that `pip` currently handles: `RECORD`, `.data/purelib` and
    `.data/scripts`, entry points, and `.pth` files, which is
    `I.pfaibne`.  For a pure Python wheel it is the `purelib` move and
    little else, but it is a real scope increase and should be entered
    knowingly.  Cases 3 and 12 already do this much.
