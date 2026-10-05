# 6.14 The shipping bootstrap: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.14 of `LOGBOOK.md` on 2026-10-04.

* Step 6.14: The shipping bootstrap.  Twelve cases were measured in Task
  2 and never narrowed to one, which left the `paste` metric priced
  against a set rather than a product, `FAST_CASES` looking arbitrary, and
  issue `2wtmifs` alive because a matcher nobody ships was still on a path
  somebody might.
  * 6.14.1 - **Case 7 ships**, nominated and accepted 2026-09-29: no
    virtual environment, `pip` as a subprocess, eighteen pasted lines, one
    import.  Wayne's words were "I'm leaning toward case 7.  We can always
    back out if we encounter something."

    The reasoning, in the order it decides:

    * Joint shortest paste with 6, 9 and 10.
    * Cases 6 and 9 run `pip` **in process**, which leaves 451 of its
      modules in `sys.modules` and three handlers on the root logger of
      somebody else's program; measured in Task 2.  A subprocess takes all
      of that away with the child.  This is the tiebreaker, and it is a
      correctness argument rather than a preference.
    * Case 10 is 7 plus `--no-compile`, worth 60 KB, which is illusory
      because the bootstrap imports the package two lines later and Python
      compiles what it imports anyway.
    * It hands wheel selection to `pip`, which is what Step 6.17.5 made
      decisive: our five line matcher cannot see abi3 wheels and cannot
      tell musl from glibc.  On the shipping path neither bug can bite,
      because we do not choose.
    * Its failure is legible now that `--quiet` is gone: pip's own error
      text reaches the person instead of only its retry warnings.

    The cost is that `pip` must be installed, which is a real ask on the
    distribution that motivates this project, since Debian and Ubuntu ship
    `python3-pip` separately.  The `README.md` leads with it and now states
    the trade: one command once, against creating a virtual environment,
    activating it differently on every shell and system, and remembering
    to activate it again tomorrow.
  * 6.14.2 - **The `paste` column was wrong, by three, in every row**,
    found while checking the number before quoting it.  `SHARED_LINES`
    became 7 on 2026-09-26 when the `try` wrapper started being charged,
    and the table in `bootstrap.py` was never regenerated, so it still
    read `lines + 4`.  Corrected arithmetically on 2026-09-29 -- the
    `imports`, `lines` and `paste` columns come from parsing the file, so
    they need no run -- and the three places quoting the old figures were
    corrected with it.  Case 7 is 18 pasted lines and not 15; case 3 is 52
    and not 49.

    One quotation of the old numbers is left alone deliberately: finding
    10 of Task 2 says "Independence from pip costs 49 pasted lines against
    15".  Task 2 is closed, so that is Wayne's to change or leave.
  * 6.14.3 - The other eleven cases stay, as measurement rather than as
    candidates.  `ALT_VENV_TEST=COMPLETE` runs them, the table keeps
    pricing them, and `2wtmifs` retires further: the matcher is no longer
    on any path a stranger reaches.

    Open, and worth deciding before the `README.md` claims anything about
    it: whether case 3 is offered as a documented fallback for a machine
    with no `pip` at all.  It costs 52 pasted lines and carries the two
    matcher bugs, so offering it means fixing the abi3 comparison first --
    a comparison of integers, not a version parser.
  * 6.14.4 - Superseded on 2026-10-01 by Step 6.15: case 13 ships in
    place of case 7, because it needs no preinstalled `pip`.  The
    subprocess argument of 6.14.1 carries over unchanged, and 6.15.1
    found `pip` itself now making it.
