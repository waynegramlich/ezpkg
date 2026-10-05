# 6.6 Security, and who approves what: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.6 of `LOGBOOK.md` on 2026-10-04.

* Step 6.6: Security, and who approves what.
  * 6.6.1 - Write the threat model down first, because the claim has to
    be narrow to be true.  A malicious program author gets no
    protection at all, since the bootstrap is their code and they can
    delete the prompt.  A typosquatted package gets very little:
    `reqeusts . PyPI` and `requests . PyPI` have titles of identical
    form, so pasting one proves a page was fetched, not that the right
    one was recognised.  A compromised index or network is TLS and
    hashes, not ceremony.  What the Hunt genuinely defends is
    inattention to the dependency set, and that is worth saying
    plainly; claiming more would make it theatre.
  * 6.6.2 - The real guarantee is the ordering:  download, approve,
    install.  With `--only-binary :all:` a wheel is an inert zip, so no
    third party code has run at the moment the user is asked.  Neither
    `uv run` nor `pip-run` can make that claim, and it should be stated
    as the architectural promise rather than left as an aside.
  * 6.6.3 - Refuse sdists.  `--only-binary :all:` is the one lever
    worth more than all the rest, because an sdist runs arbitrary code
    at install time through `setup.py` and a wheel does not.
  * 6.6.4 - Show the transitive closure.  Nobody ever looks at what
    `pip install requests` actually pulls in, and a list the user must
    page through is the first time most people would see the number.
    That alone justifies the mechanism.
  * 6.6.5 - Approve a hash, not a name.  Approving "coverage" means
    nothing; approving `coverage 7.16.1 sha256=e82e10b9...` is a real
    decision, and a version bump then correctly re-prompts.  The
    identity to record is the one Step 6.3 already fetches.
  * 6.6.6 - Non-interactive execution is a hard requirement, not an
    edge case.  A program under cron, CI, systemd, a pipe or a
    double-clicked launcher has no tty, and the Hunt would hang or
    crash.  Needs `sys.stdin.isatty()`, a documented approval file or
    environment variable for that case, and a clear message when
    neither is present.
  * 6.6.7 - Habituation is the standing objection and deserves an
    answer in the `README.md`.  Every repeated confirmation ritual
    decays into muscle memory, as certificate warnings and UAC did.
    Once per program rather than once per run is the mitigation, and
    saying so is the reply.
  * 6.6.8 - One prompt for the whole set, not `N` title pastes, is
    worth considering.  The same visibility at a tenth of the tedium,
    and the title paste is the part that buys least.  The cost lands on
    the person who did not choose the dependencies, and `uv run` asks
    them for nothing.
  * 6.6.9 - Answered 2026-09-26, and the answer is a boundary rather
    than a defence.  The approvals live beside the program, as `prog.py`
    to `prog.altvenv`, and anybody who can write that file can edit
    `prog.py` itself, so pre-approving something is strictly less work
    than simply changing the program.  Nothing here defends against
    somebody who already has write access to the program; saying so is
    the decision.
  * 6.6.10 - Answered 2026-09-26: the prompt does not defend against
    typosquatting and never could.  `reqeusts` and `requests` have names
    of the same shape, summaries that are copies of each other, and
    project pages that look alike, so nothing shown to somebody at run
    time distinguishes them.  The **approvals file** is the defence: the
    author, who chose the dependency and can tell the two apart, got the
    name right once, and the SHA-256 pins that exact artifact
    thereafter.  This is why approval belongs to the author and not to
    whoever happens to run the program.

  * 6.6.11 - The project's `README.md` is Step 6.10's, not this step's.
    Its `## Security Issues of Executing Unvetted Code` section is
    outlined by the sub-items here, and by 6.6.1 above all.

  * 6.6.12 - The cache owns the package, not the program.  Wayne's
    sentence, 2026-09-26, and it is the reason the warm path neither
    asks nor verifies: a tree in `versions/` may have arrived on behalf
    of some other program entirely, so no one program's approvals file
    is the authority over it.  Verification therefore belongs to the
    moment of fetching, which is also the only moment anything is asked.

  * 6.6.13 - What gets asked, settled 2026-09-26.  Nothing is said and
    nothing is asked unless at least one wheel has to be downloaded.
    When anything does, the whole set is shown, including packages the
    cache already holds, because the request is keyed on the entire
    requirement set and a set nobody has vetted has not been vetted.
    Measured: a second program sharing a cache and asking for `needy`
    is shown `needy` as asked for and `widget` as having come along,
    although `widget` was already there from the first program.  The
    listing therefore appears once per cache, not once per run.

  * 6.6.15 - A fourth answer, built 2026-09-29: the question is now
    `[y/n/a/?]`, where `a` means do not ask again.  Wayne's reasoning is
    the point of the whole feature, so it belongs here: nearly everybody
    will approve, and what the question is **for** is that a person
    understands packages are being downloaded -- not that they are nagged
    about it forever.  Answering `a` writes `FOREVER_APPROVE` in the
    cache, whose contents say what it means and that deleting it restores
    the question, and the answer prints that path, because one keystroke
    making a permanent decision deserves a visible way back.

    The marker lives in the cache rather than beside the program, because
    it records a decision by whoever uses the machine and not by any
    author; that also gives it the lifetime the question already had,
    which is once per cache.

    **The invariant that makes it safe:** the marker is checked *after*
    the approvals, so it silences the question and can never hide a wheel
    that fails `verify`.  A wheel that does not match what an author
    approved is a different matter from a person who would rather not be
    asked.  Three tests, one of them exactly that case: approve, corrupt
    the record, set the marker, fetch cold, and the refusal still
    happens.

    Reworked the same day, at Wayne's suggestion, and the reasoning is
    worth keeping: **the prompt spells the answers out** rather than
    abbreviating them, because a person seeing it for the first time
    should not have to guess what a letter means:

        2 requested, 3 to install into /home/you/.alt_venv;
        go ahead? [y=>Yes/n=>No/a=>Always/?=>Explanation]

    Case no longer matters, since somebody with caps lock on has not made
    a mistake.  And `a` now **asks twice**: `Really never ask again?
    [y=>Yes/n=>No]`, because it is the only answer that outlives the run.
    Declining the confirmation returns to the question rather than
    cancelling the install -- not wanting a thing for ever is not the
    same as not wanting it now -- and counts as an attempt so the pair
    cannot loop indefinitely.

    The second `y` prints where the marker is, that packages will be
    downloaded silently from now on, and the removal command for the
    platform it is running on, with `os.name` choosing between
    `rm -rf` and `rmdir /s /q`.  The words *ALWAYS safe to delete* are
    Wayne's, and they are right: the directory is a cache, and losing it
    costs a download.

    Wayne also spotted that `consent`'s docstring still described the old
    `[y/N/?]` prompt.  The test file now holds the prompt and the
    confirmation as `PROMPT` and `CONFIRM`, one place each, so the next
    rewording fails in one obvious spot rather than in seven.

    This replaces nothing: `ALT_VENV_APPROVE` stays, because `write` is
    how an author generates the approvals file at all and `skip` is for
    an author still deciding.  Wayne leant against the variable while
    designing this, and the reason to keep it is that it is the author's
    tool and never in a recipient's way.

  * 6.6.14 - Two things the mechanism cannot do, recorded so that they
    are decisions rather than oversights.  A declined download is
    discarded, not kept, so `pending/` is empty afterwards and a later
    run fetches again; a refusal means do not install this, not keep it
    for later.  And `ALT_VENV_APPROVE=write` records what arrived
    without judging it, so an author who runs it while pointed at an
    index they should not trust will approve whatever that index sent,
    and the file then vouches for it everywhere the program goes.  There
    is no technical answer to the second: run it against an index you
    mean to trust.

### Step 6.6: Security, and who approves what

The Scavenger Hunt was designed and then discarded.  What replaced it
rests on one observation: the person who runs somebody else's program
cannot judge whether `charset-normalizer 3.3.2` belongs there, so any
question put to them is a rubber stamp.  The **author** chose the
dependencies and can tell `requests` from `reqeusts`, so the author
approves, once, and the file travels with the program.

* The author runs with `ALT_VENV_APPROVE=write` and gets
  `prog.altvenv` beside `prog.py`: one line per wheel, its name and its
  SHA-256, sorted so that a change is a small diff.  They commit it.
  `skip` neither records nor checks, for an author still deciding.
* A recipient with that file has it verified, silently, and a mismatch
  refuses before anything is unpacked.  A recipient without one is told
  what arrived and asked once, `[y/N/?]`, where `?` describes each wheel
  and does not count against the patience meant for typos.
* Nothing from the index is printed as fact.  The origin, the size and
  the digest are ours; a package's `Summary` is prefixed `it says:` and
  stripped of everything unprintable, because it is written by the same
  person who would write a typosquat's.

Four things were learned the hard way, three of them by a test failing
rather than by thinking.

1. **`open("/dev/tty", "r+")` does not work**, and would have failed
   silently.  Against a pseudoterminal it raises
   `UnsupportedOperation: File or stream is not seekable`, because
   buffered read-write text mode wants to seek and a character device
   cannot.  That exception is a subclass of `OSError`, so the
   `except OSError` meant for "there is no terminal" would have caught
   it, reported no terminal, and **never asked anybody anything,
   anywhere**, while every test that did not use a real terminal passed.
   Two handles, one for reading and one for writing.
2. **A prompt can only be tested with a pseudoterminal**, and only
   `os.login_tty` makes the slave the child's *controlling* terminal,
   which is what `/dev/tty` resolves to.  Inheriting the descriptor is
   not enough: a child started with `start_new_session` alone reports
   `No such device or address`.  `login_tty` also puts the child's own
   output on the terminal, so nothing comes back through pipes.  It runs
   in a small launcher after `exec` rather than in `preexec_fn`, which
   `ruff` flagged and which would risk deadlocking a process that has
   threads -- and this suite has a server thread.
3. **The first cut only verified on a cache miss**, so an author whose
   cache was warm could never regenerate the approvals.  The request
   record now names the wheels as well as the trees, and `write` works
   from a warm cache.  Verification still happens only when something is
   fetched, for the reason in 6.6.12.
4. **`came along` had never executed.**  Tracing child processes found
   it: no wheel the suite built had a dependency, so `pip` never pulled
   anything along and the distinction that 6.6.4 rests on was
   unreachable.  `build_wheel` takes `requires` now, the index publishes
   `needy`, which needs `widget`, and two tests watch the two kinds
   being told apart.  The same shape of gap as the `.data` tree and the
   wheel tag matcher: fixtures too simple to reach the interesting
   branch.

82 tests, up from 62 at the start of the step.  `alt_venv.py` reaches
97% with child processes traced, and 74% without, which is the
measurement being blind rather than the code being untested: every
approval test is a child program.

What this step does not cover: the project's own `README.md`, which
still describes the Scavenger Hunt and still has its security section
marked TBD.  Explaining any of this to a stranger is Step 6.10, and the
sub-items above are the outline it should follow.
