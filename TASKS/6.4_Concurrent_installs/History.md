# 6.4 Concurrent installs: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.4 of `LOGBOOK.md` on 2026-10-04.

* Step 6.4: Concurrent installs.  Mostly answered by Step 6.3's
  construction rather than by a mechanism of its own, because nothing
  installs into a shared directory any more.  Done: a download directory
  per call, so two programs never share a staging area; unpacking inside
  `pending/` and renaming into `versions/`, where `ENOTEMPTY` makes the
  loser take the winner's tree; one record file per request, so no write
  can lose another's; and `mkdir(exist_ok=True)` throughout.
  * 6.4.1 - `repair_module_layout` had a real race, found 2026-09-26 by
    asking this question: two programs both read the module and both
    removed it, and the second raised `FileNotFoundError` out of a
    constructor.  `unlink(missing_ok=True)` now, with a test that makes
    the read delete the file as a rival would have.
  * 6.4.2 - Carried to Step 6.11 rather than left open here: a program
    killed mid-unpack leaves an `unpacking-` directory under
    `pending/`, and a killed download leaves its own.  Neither is
    importable, so neither is a correctness problem; they only
    accumulate, which is culling work.
  * 6.4.3 - Done 2026-09-26, and it took three tries to make it mean
    anything.  `test_four_processes_share_one_cache` runs four real
    programs against one cache and checks that one of everything comes
    out, with the index made `slow` so the fetches overlap.  But
    deleting the lost race recovery did not make it fail: the window
    between asking whether a tree exists and renaming one into place is
    a millisecond or two, and four processes drift further apart than
    that while `pip` runs.  Moving the delay from the project page to
    the wheel did not help either.
  * 6.4.4 - What worked was a barrier.
    `test_four_processes_collide_on_one_unpack` has each process
    download first, wait until every one of them has arrived, and only
    then unpack, which puts them inside the window deliberately.  With
    four racers, deleting the recovery was caught two runs in three and
    then none in five, which is variance rather than a test.  With
    eight it was caught six times out of six, and the correct code
    passes every time.  Both tests are worth keeping: the first shows
    the outcome under honest concurrency, the second exercises the
    race.
  * 6.4.5 - The lesson, which cost most of the time here: a concurrency
    test that passes proves nothing until the fix it guards has been
    removed and the test has been seen to fail.  Timing tests are
    especially good at passing for no reason.
