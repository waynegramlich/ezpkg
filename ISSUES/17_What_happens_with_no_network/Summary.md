# Summary of `I.whwnn` What happens with no network?

Undefined in all twelve cases.  Should the bootstrap fail, or fall back to
whatever the system already provides?

Last thought: Claude (2026-09-26): Closed. Step 6.1 of Task 6 wrapped the fetch
so that a failed one exits with a single line naming the package and the
underlying error, and no traceback. Cases 3 and 12 give exactly one line; the
ten `pip` cases give three or four, the extra lines being pip's own
diagnostics, which are kept because they are more specific than ours.
`test_a_failed_fetch_is_one_line` holds it. The fall back alternative was
declined by Wayne on 2026-09-22.
