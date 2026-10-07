# 6.1 Error on a failed fetch: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.1 of `LOGBOOK.md` on 2026-10-04.

* Step 6.1: Generate error on bootstrap fetch error (`I.whwnn`):
  * The new bootstrap diagnoses a failed fetch, which closes `I.whwnn`.
  * Measured 2026-09-25 against a dead port: case 6 ends in
   `RuntimeError: pip failed` after ten lines of traceback and never
    mentions the network, and case 3 buries `Connection refused` under 47.
    Neither is an error message.
  * Wrap the fetch once in the shared region and `raise SystemExit` naming
    the package, the destination and the underlying error.  `SHARED_LINES`
    then goes from 4 to 7 and every `paste` figure rises by three, which
    makes this the first change to move that column.  A `sys.excepthook`
    would be shorter and is rejected: the bootstrap sits at the top of
    somebody else's program and must not leave a global hook mangling
    their tracebacks.

### Step 6.1: Error on a failed fetch

A failed fetch now exits with one line instead of a traceback, which
closes `I.whwnn`.  Measured against a dead port, before and after:

| case        | before                    | after                     |
| ----------- | ------------------------- | ------------------------- |
| 3, `urllib` | 47 lines, traceback       | 1 line, no traceback      |
| 6, `pip`    | 10 lines, `pip failed`    | 4 lines, no traceback     |

* Only cases 3 and 12 give exactly one line.  The ten `pip` cases give
  three or four, and the extra lines are pip's own diagnostics, which
  are kept deliberately: `ERROR: Could not find a version that
  satisfies the requirement` is more specific than anything we would
  say in its place.
* The wrapper sits at the entry point rather than around each case, so
  no case body had to be re-indented; 300 lines shifting four columns
  would have pushed many past 79.  A pasted case carries the same three
  lines around its own body, which is why `SHARED_LINES` went from 4 to
  7 and every `paste` figure rose by three.  This is the first change to
  move that column, and the Task 2 and Task 5 charts carry annotations
  saying so.
* `except Exception` needed `# noqa: BLE001`.  The blind catch is the
  entire point, so it is silenced with a reason rather than narrowed to
  a tuple that would miss something.  `Exception` rather than
  `BaseException`, so a control-C still reads as a control-C.
* `test_a_truncated_wheel_fails_case_3` broke, correctly: it had been
  asserting the word `zipfile` from the traceback that this step
  removes.  It now reads the message.
