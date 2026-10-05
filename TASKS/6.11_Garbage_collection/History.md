# 6.11 Garbage collection: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.11 of `LOGBOOK.md` on 2026-10-04.

* Step 6.11: Garbage collection.  Cull packages that have not been used
  for a while.  Not by access time: nearly every Linux filesystem
  mounts `relatime`, so `atime` updates at most once a day and not on
  ordinary reads, and `noatime` switches it off altogether, so culling
  on it would delete packages in daily use.  `install` is the only
  thing that reads the cache, so have it record use in a sidecar file
  and cull on that.

  Two kinds of litter arrive here from Step 6.4.2.  A program killed
  mid-unpack leaves an `unpacking-` directory under `pending/`, and a
  killed download leaves its own temporary directory beside it.  Neither
  is importable and neither is a correctness problem, so culling is the
  whole of the fix; the `unpacking-` prefix is there to make them
  identifiable.  A tree in `versions/` that no request record names any
  longer is the third kind, and arrives from Step 6.3.13.
  * 6.11.1 - Designed 2026-09-29, and designed **for testability**, at
    Wayne's insistence: where two designs would work, the one that is
    easier to test wins, because the test suite is the product.  Written
    as a plan because Step 6.10's `README.md` forced the decisions early
    -- describing behaviour to a stranger is what exposed which parts do
    not exist yet.

    * **Deciding is separate from deleting.**  `litter()` and
      `stale(days)` each return a list of paths and remove nothing;
      `cull(days)` removes what they name and returns what it removed.
      Most tests then assert on lists and never delete anything, and a
      dry run is free, which is a feature a person actually wants: *what
      would you remove?*
    * **File times are the clock, and `os.utime` is the test lever.**  No
      injected clock, no mocking, no sleeping: a test back-dates a stamp
      by two hundred days and asks whether the tree is stale.  Exact
      rather than approximate.  The same trick already tests that the
      cache `README.md` is not rewritten needlessly.
    * **The request records are the evidence of use.**  Each install
      touches its record, warm or cold; a tree is stale when no record
      naming it has been touched inside the threshold.  No new directory,
      nothing written inside a package tree, and two programs sharing a
      tree means the freshest record wins.  It reuses the walk 6.3.13
      needs anyway.
    * **Thresholds are parameters with module level defaults**, so a test
      passes `days=0` or an absurdly large number and gets both extremes
      without touching the environment.  An environment variable can come
      later if anybody asks.
    * **Litter first, because it needs no policy and cannot be wrong.**
      Anything under `pending/`, and any tree no record names at all,
      is unreachable by definition.  The test is: make a mess, cull,
      assert the mess is gone and the good tree is untouched.
    * **The daily gate is its own predicate.**  `due()` reads the mtime
      of a `last_cull` stamp and `install` culls only when it says so.
      Tests drive `due()` directly, and the install path needs one test
      that a second install the same day culls nothing.
    * **Two safety invariants, a test each**, because they are how this
      feature would bite: nothing stamped during this run is ever
      removed, and a tree vanishing mid-cull because another process got
      there first is not an error.
    * **`wheels/` is left alone** for now, with a test saying so, because
      those wheels are what makes `ALT_VENV_APPROVE=write` work from a
      warm cache; a later size optimisation must not quietly break the
      author's flow.

    Order of work: litter and the daily gate first, which is a small
    honest half, then the age based cull.  The `README.md` already says
    the automatic clean up is designed and not yet written, so it becomes
    true rather than needing a correction.
  * 6.11.2 - The litter half is built, 2026-09-29, and building it
    corrected the plan above on one point: **litter does need a
    threshold.**  6.11.1 said it needed no policy because unreachable
    things are unreachable at any age, and that is true of reachability
    and false of concurrency.  Another program's download is sitting in
    `pending/` right now, and a tree is renamed into `versions/` a moment
    *before* the record naming it is written -- so a sweep with no grace
    period would delete a running program's work, and would do it most
    often on a busy machine.  `CULL_GRACE` is a day: far longer than
    either window, short enough that a crashed run's leftovers do not
    accumulate.

    Three methods, deciding kept apart from deleting as designed.
    `litter(grace)` returns what is unreachable and old enough --
    anything under `pending/`, and any `versions/` tree that no request
    record names -- and removes nothing.  `cull(grace)` removes what that
    names, tolerates a path another sweep took first, and stamps
    `last_cull` even when it found nothing, so an empty cache is not
    swept again a second later.  `due(interval)` compares that stamp
    against now, treating an absent or unreadable stamp as due.
    `provide` sweeps when due, just before fetching: the cost is
    invisible beside a download, and everything this program is about to
    create is younger than the grace period and therefore safe.

    Ten tests, and `os.utime` is the clock throughout, as planned: a test
    back-dates a directory by twice the grace period and asks whether it
    is litter.  Nothing sleeps.  The invariants each have one: a young
    download is spared, a tree a record names survives at a hundred times
    the grace period, a path that vanishes mid-sweep is not an error, and
    a second install on the same day does not sweep again -- watched
    through the stamp's modification time, which is the observable part.
  * 6.11.3 - The age based half is built the same day, and **no pseudo
    clock was needed.**  Wayne offered an environment variable to fake
    the time, on the grounds that tricks in aid of testing are fair;
    declined, because the thresholds are already parameters, so a test
    asks for `days=0.0` or `days=10**9` and gets both extremes at full
    speed, and `os.utime` covers the cases where age itself is the
    subject.  The reason to avoid the variable specifically: a
    time-shifting value loose in somebody's environment would make every
    package look ancient and be swept, which is a footgun that ships.  If
    real time travel is ever wanted, a module level `NOW = time.time`
    that a test patches in process is the shape to use.

    **Age applies to request records and nothing else, and it means
    *unused* rather than *old*.**  `remember` touches a record on every
    hit, warm or cold, so a package fetched two years ago and used this
    morning is not stale; that has its own test.  `stale(days)` names
    records nothing has used for `CULL_DAYS`, which is 180 days because
    the cost of being wrong is one download and the cost of being right
    is a little disk, and those are not symmetrical.

    `cull` removes stale records first and then sweeps litter, so the two
    halves are one mechanism: dropping a record leaves its trees and
    wheels spoken for by nobody, and the litter pass collects them in the
    same sweep.  *Unused* is expressed once, about records; *unreachable*
    once, about everything else.  A tree two records name survives until
    the last of them goes, which is tested by asking for `widget` alone
    and then beside `sprocket`.
  * 6.11.4 - Wheels are collected after all, which **reverses 6.11.1's
    decision** to leave `wheels/` alone, and the reason is that 6.11.3
    created it: once records age out, their wheels become the only thing
    in the cache that nothing will ever look at again and nothing will
    ever remove.  The rule is now symmetric -- a wheel no record names is
    litter, exactly like a tree -- and the author flow the old decision
    was protecting is still safe, because a live record protects its
    wheels, so `ALT_VENV_APPROVE=write` still works from a warm cache.

    `cull` grew a two line branch for it, since a kept wheel is a file
    where everything else swept is a directory.  The test that pinned the
    old decision was replaced by three: an unreferenced old wheel is
    collected, a referenced ancient one is not, and a young unreferenced
    one is spared by the same grace period as everything else -- a wheel
    is renamed into `wheels/` a moment before the record naming it is
    written.
