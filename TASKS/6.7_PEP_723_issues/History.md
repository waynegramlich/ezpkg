# 6.7 PEP 723 issues: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.7 of `LOGBOOK.md` on 2026-10-04.

* Step 6.7: Deal with PEP 723 issues, which is `2hsrpbd`.

  This step covers everything the standard asks of a program that
  declares its own requirements: finding the block, reading it, and
  acting on what it says.  The substance is that the calling script's
  `# /// script` block replaces a package name written into the
  bootstrap.  It builds on Step 6.2, and it makes the same file work
  under `uv run` for nothing, which is worth a great deal given that
  prior art is why this project has to justify itself at all.

  First of what remains, on 2026-09-27, because it is the largest change
  to what the product is: the program declares what it needs instead of
  somebody writing an `install` call by hand.  It also builds the
  locator that Step 6.12 needs, so doing it first hands that step its
  primitive for free.  And both `README.md` files are last for the
  matching reason: the usage they describe changes here, and writing
  them earlier means writing them twice.
  * 6.7.1 - Implement PEP 723 support.
    A different format was considered but rejected.  PEP 723 is final.
  * 6.7.2 - PEP 723 goes in `#` comments, and the block is read from the
    file's source text rather than from anything the interpreter keeps.
    Nothing else works: `python3 -OO` strips docstrings, so `__doc__` may
    be `None`, and comments never exist at run time at all, being dropped
    at compile time.  Reading the source makes both available, and the
    remaining reason to prefer comments is that a TOML block inside a
    docstring turns up in `help(module)`, which is why the PEP chose
    comments.
  * 6.7.3 - Parsing costs no dependency.  `tomllib` has been in the
    standard library since 3.11 and is in `libpython3.12-stdlib` here,
    not in a separable package.  It does raise the floor from 3.10,
    which `X | Y` and `match` already set, to 3.11; worth saying out
    loud before it is discovered.
  * 6.7.4 - The floor is stated, and it is as low as the code allows.
    **Superseded by 6.7.7 later the same day, which raised it to
    `>=3.11` for `tomllib`.**  What was decided here, and still holds
    for the language itself: `>=3.10`, because annotations such as
    `Path | None` are evaluated at run time and `bootstrap.py` uses
    `match`, and because **nothing here needs 3.11 or 3.12**.  Importing
    `tomllib` for this step moves it to `>=3.11`, and that is the whole
    cost of doing so.

    Raising it further was considered and declined.  Every version
    excluded is a machine that cannot run the thing, which is what this
    project is about: from recollection rather than measurement, Ubuntu
    22.04 LTS ships 3.10 and is supported to April 2027, Debian 12 ships
    3.11, and RHEL 9 ships 3.9 and is supported to 2032.  Requiring 3.12
    would turn all three away and buy nothing, since no 3.12 feature is
    used.  What distributions actually ship is `2hmmdrpe`, still
    unmeasured.

    Until now the floor was stated nowhere at all, which is ironic for a
    step about reading other people's `requires-python`.  The wheel now
    carries `Requires-Python`, and that is worth the line: measured
    2026-09-27, `pip` refuses a wheel it cannot satisfy with
    `requires a different Python: 3.12.3 not in '>=3.99'`, where without
    it the install succeeds and the program dies later on a `SyntaxError`
    from an annotation, explaining nothing.  `build_wheel` takes a
    `floor`, the `alt-venv` wheels pass `FLOOR`, and the throwaway test
    packages claim nothing.

  * 6.7.5 - `alt_venv.py` carries a PEP 723 block of its own, added
    2026-09-27, so that this project eats its own cooking:
    `requires-python = ">=3.10"` and `dependencies = []`, the second
    empty on purpose, since a project about fetching packages that are
    not preinstalled has none of its own.  Verified with the regex PEP
    723 itself specifies plus `tomllib`, which reads back
    `{'requires-python': '>=3.10', 'dependencies': []}`, and the module
    docstring survives having comments in front of it.

    Two honest limits.  Nothing reads it: a tool such as `uv` reads the
    block of the script it is running, and this is a library that is
    never `__main__`, so no tool and not even our own code will consult
    it.  And the floor is now written twice, here and in `FLOOR`.  Both
    close the same way, and it is the real dogfooding: once this step can
    parse a block, `build_wheel` should take `Requires-Python` from
    `alt_venv.py`'s own block, so that our metadata comes from our parser
    reading our file, with a consequence if the parser breaks.  Only
    `alt_venv.py` gets a block; `bootstrap.py` must keep a literal
    package name, because something has to fetch this file before
    anything can parse anything.

  * 6.7.6 - The locator exists, built 2026-09-27: `main_path` returns
    the running program's file and `main_source` returns that file with
    its text, each `None` when there is nothing to find.  This is
    6.12.1's primitive, and `approvals` was rewritten on to it, so the
    `__main__` handling now lives in one place.  Ten tests, each in a
    child process, because this suite's own `__main__` is `unittest`.

    Writing the tests found a defect that reasoning had missed.  A
    `__file__` that is present is not necessarily a file: measured
    2026-09-27, `python3 - < prog.py` sets it to the literal `<stdin>`,
    and `exec` of a string and a frozen interpreter give `<string>` and
    `<frozen ...>`.  Resolving any of those yields a believable path in
    the working directory that names nothing, so the first version would
    have looked for approvals in `./<stdin>.altvenv` -- in whatever
    directory the reader happened to be standing.  The locator now
    insists the path exist, which rejects those three and a program
    deleted from under itself as well.

    Measured while at it, so that nobody has to guess later:
    `python3 -m prog` does set `__file__`, a relative invocation resolves
    to an absolute path, and `-OO` leaves the comments in the file
    although it has stripped the docstrings from the module, which is the
    whole reason 6.7.2 reads the source.

    Amended the same day: the text is read with `tokenize.open` rather
    than `Path.read_text`, so that a program declaring a coding cookie is
    read rather than silently ignored.  See 6.5.14.

  * 6.7.7 - Got the TOML parser working.  6.7.3 said `tomllib` raises
    the floor to 3.11 and 6.7.4 then set the floor at `>=3.10`, and both
    could not hold once the import was real.  The options:

    * Hand-parse the two keys wanted -- `requires-python`, a string, and
      `dependencies`, a list of strings -- and depend on no TOML reader
      at all.  Rejected: a hand parser is a second implementation of
      somebody else's specification, which is the mistake 6.7.1 declined
      to make when it chose PEP 723 over a bespoke format.
    * Import `tomllib` lazily, so 3.10 keeps working until a program
      actually has a block.  Rejected: it buys one Python version at the
      price of two code paths and a failure that appears late.
    * Import `tomllib` at the top like any other standard library module
      and raise the floor to `>=3.11`.  **Chosen 2026-09-27**, because
      3.11 has been out four years.

    `script_metadata` followed on 2026-09-27: source text in, what the
    block declared out, `None` when there is no `script` block, and
    `ValueError` on two blocks or on TOML that will not parse.  Twelve
    tests, none needing a child process or the disk.  The regex is PEP
    723's own, copied and not rewritten, because a block we fail to
    recognise is a block some other tool accepts.  Two measured
    consequences, shared by any tool using it:

    * An empty block reads as **no** block, the pattern wanting at least
      one commented line between the fences.  Harmless, and the test
      expecting `{}` was the thing that was wrong.
    * A block of another type immediately above a `script` block
      **hides** it, silently, because `content` matches commented lines
      greedily straight through the closing fence.  One blank line
      between them is the cure.

    The second also defeats the duplicate check the PEP requires, two
    adjacent blocks matching as one, so `FENCE` counts `# /// script`
    openers first and names the real mistake.

    The project gained `ruff.toml` and `mypy.ini`, both saying 3.11,
    because with no configuration `ruff` assumed 3.10, disbelieved that
    `tomllib` is standard library and sorted its import into the third
    party block.
  * 6.7.8 - The API is `install()` with no arguments, decided and built
    2026-09-27.  It reads the program's block, fetches what is declared,
    puts the cache on `sys.path` and **imports nothing**; the program's
    own `import` statements, written below the bootstrap, do that.  A
    program with no file, no block, or a block declaring nothing gets
    silence, because every test that merely constructs an `AltVEnv` is
    such a program.  A declaration that will not parse is reported,
    since that is not the same as no declaration.

    Putting the fetch in `__init__` was considered and declined.  It
    reads well -- construct the object and start importing -- but
    `AltVEnv().install()` is one pasted line either way, so the whole
    gain is invisible in the only unit that matters, and the cost is
    real: `contains` asks what is cached, Steps 6.11 and 6.12 will want
    an object that only looks, and `bootstrap.py` constructs one to
    repair a module layout.  A constructor that fetches, prompts on
    `/dev/tty` and mutates `sys.path` also leaves a half-built object
    behind when it raises.

    Importing nothing is what makes the two naming systems stop
    colliding, which is the unexpected prize.  A PEP 508 requirement
    names a distribution, an `import` statement names a module, and
    `python-dateutil` is not `dateutil`; the pair form of `install`
    exists only because it returns modules and had to guess.  The
    declared path never guesses, so the pair form is now the escape
    hatch rather than the answer.

    `install(requirements)` stays, for requirements not known until run
    time -- the database driver named in a configuration file, which a
    static block cannot express.  Both forms share `provide`, split out
    of `install` for the purpose: fetch, verify, unpack, `sys.path`, no
    imports.  `declared` is public too, and answers what would be
    fetched without fetching it.

    Eleven tests, all running a real program in its own directory: a
    plain declaration, a version constraint, `python-gadget` imported as
    `gadgetlib`, several in one `pip` run, no block, an empty
    `dependencies`, unparseable TOML, a `dependencies` of integers,
    `declared` on its own, `python3 -OO`, and `python3 -c`.

    Measured on a realistic program, because linter complaints land on
    the author and are the friction they will actually feel: with the
    imports below the bootstrap, `ruff` reports **no** E402, which was
    the objection to the whole shape and it was wrong.  It does report
    `BLE001` for the blind `except` the paste itself carries, so the
    paste must carry `# noqa: BLE001` too.  `mypy` cannot see a package
    that will not exist until run time and says
    `Cannot find implementation or library stub for module named ...`;
    `# type: ignore[import-not-found]` on each import is the narrow fix
    and `--ignore-missing-imports` the blunt one, which was measured to
    swallow a misspelt module name as well.  In practice the author has
    the packages installed and sees none of this.  All of it belongs in
    Step 6.10.
  * 6.7.9 - The dogfooding loop is closed, 2026-09-27.  `FLOOR` is no
    longer a literal: `floor()` reads `requires-python` out of
    `alt_venv.py`'s own block with our own parser, so the wheels' claim
    comes from our file through our code, and breaking either one fails
    the suite instead of shipping a wrong `Requires-Python`.

    Configuration cannot be derived that way, so `ruff.toml` and
    `mypy.ini` still say 3.11 by hand, and
    `test_the_linters_agree_with_the_block` is what stops the three
    drifting apart.  `bootstrap.py`'s epilogue now calls
    `AltVEnv().install()` rather than only constructing one, so all
    twelve shapes walk the declared path; that file has no block, so
    nothing is fetched.
  * 6.7.10 - A declared `requires-python` **is** enforced, decided and
    built 2026-09-27.  Two declarations share a name and only one was
    ever in question: a wheel's `Requires-Python`, written by whoever
    built the package, is `pip`'s to enforce and it does; the PEP 723
    `requires-python` in the program's own block was read by nobody.

    Ignoring it was the first recommendation and Wayne was not thrilled,
    which was the right instinct.  The options:

    * Ignore it, as `uv` enforces it anyway for anybody who runs the
      program that way.  Rejected: the program that lies about its floor
      dies later on a `SyntaxError` in a module the person has never
      heard of, and we had the information to say so.
    * Compare it properly, which means PEP 440 and so either a
      reimplementation or a dependency.  Rejected: 6.3.3, and a
      dependency on `packaging` to check a version is a bootstrap cycle.
    * Understand the single `>=X.Y[.Z]` clause and **nothing** else,
      refusing to interpret the rest.  **Chosen.**

    The distinction 6.3.3 was protecting is intact, and the reason is
    worth stating plainly: every mistake this whitelist can make is in
    the permissive direction.  A pre-release such as 3.11.0a1 does not
    satisfy `>=3.11` under PEP 440 but compares equal on
    `sys.version_info`, so an alpha is let through; nothing legitimate is
    ever refused.  6.3.3's tuple comparison had the opposite failure --
    it would have *installed* a release candidate nobody asked for -- and
    that asymmetry is what makes one safe and the other not.

    So `python_floor` returns a tuple or `None`, `None` meaning "no
    opinion, ask `pip` or `uv`", and `check_python` runs before anything
    is fetched.  `declaration` was split out of `declared` so the block
    is read once and the two readers cannot disagree.  `requires-python`
    and `dependencies` of the wrong type now raise `TypeError` rather
    than `ValueError`, which `ruff` asked for and which reads better.
    Nine tests: the whitelist's four shapes, nine specifiers it declines,
    an unmet floor stopping an install cold, a met one passing in
    silence, `>=3.9,<4` installing unjudged, a numeric floor refused, and
    the in-process form.
  * 6.7.11 - Tests, done: present, absent, malformed and duplicated
    blocks live in `MetadataTest` (13, on strings); the declared path's
    eleven live in `InstallTest` (real programs, own directories),
    `-OO` and `python3 -c` among them.  Whole suite 117 tests in 67 s.
