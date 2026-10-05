# 6.12 Find the bootstrap, and notice when it is stale: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.12 of `LOGBOOK.md` on 2026-10-04.

* Step 6.12: Find the bootstrap, and notice when it is stale.  Python has
  a great many introspection facilities, and the direct one is
  `sys.modules["__main__"].__file__` rather than walking frames with
  `inspect`.  Read that file and look for the bootstrap.  It has to
  degrade silently for `python3 -c`, the REPL and a frozen interpreter,
  none of which have a `__file__`.

  Deciding what stale means is the harder half.  One approach: hash each
  case body and keep a table of known hashes here.  A hash in the table
  but not the current one is stale and can be reported precisely; an
  unknown hash is somebody's edited copy and should be passed over in
  silence.
  * 6.12.1 - One locator, three readers.  Three steps need the main
    program's path and its source text: this one, to find the pasted
    case; Step 6.7, to find the requirements block; and Step 6.6, which
    already uses the path alone to place `prog.altvenv`.  So one small
    thing -- the program's path and text, `None` for the REPL,
    `python3 -c` and a frozen interpreter -- and one place where those
    awkward cases are got right and tested.  Built in 6.7.6, which is
    why that step went first.
  * 6.12.2 - Nobody is messaged.  There is no channel to an author at run
    time, only whoever started the program, and a staleness report is
    useful to an author and noise to a recipient who cannot act on it.
    So the author asks rather than being told: silent by default, and a
    report on request, in the same shape as `ALT_VENV_APPROVE=write`.
    That removes the question of how to reach an author entirely.
  * 6.12.4 - `install` takes a `bootstrap` label, added 2026-09-30 at
    Wayne's request while the `README.md` example was being tuned:
    `install(bootstrap="7")`, keyword-only so it cannot collide with the
    requirements argument.  It is kept as `self.bootstrap` and **read by
    nothing yet** -- this step is what will read it.  The pasted example
    passes `"7"`, which is the case this project ships, and
    `bootstrap.py`'s epilogue passes `sys.argv[1]`, so all twelve cases
    exercise the parameter.  A label is cheaper for the caller than
    hashing the pasted text and is what a message would quote; hashing
    remains the way to tell *which* version it is, per this step's plan.
  * 6.12.3 - What to do about a stale bootstrap -- report it, refuse to
    run, or offer to rewrite the file -- is still open, but 6.12.2 makes
    reporting the obvious default.
  * 6.12.5 - **Built**, 2026-10-01, once the paste had stopped moving.
    The bootstrap is found as the program's `try` block that mentions
    `alt_venv` and `import_module`, wherever it sits; the imports above
    it are left out, since people move them.  Its fingerprint is the
    SHA-256 of its text with comments and every space, tab and line
    break removed, so re-indenting, re-wrapping or annotating a copy
    leaves it the same and changing any code does not.  `tokenize`
    finds the comments, and joining its tokens before removing the
    whitespace makes the fingerprint agree under 3.11 and 3.12, which
    tokenize f-strings differently; checked under both.
    `alt_venv.BOOTSTRAPS` lists every published bootstrap by
    fingerprint, oldest first, and holds one entry so far, today's
    `nopip3`.  `bootstrap.pasted` renders a case exactly as pasted, and
    a test fails until the table's last entry matches it, so changing
    the bootstrap without recording it cannot pass.  As 6.12.2 decided,
    `install` is silent unless `ALT_VENV_BOOTSTRAP=check`, when it
    prints one line: current, stale with both names, edited or
    unrecognised, or none found.  The `bootstrap` label of 6.12.4 is
    still read by nothing; the fingerprint made it unnecessary.  The
    first test run found that a `try` nested inside an indented block
    came back from `ast.get_source_segment` unevenly indented, which
    `tokenize` rejected; it is padded and dedented now.
