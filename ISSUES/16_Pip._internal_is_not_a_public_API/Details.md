# 16 `pip._internal` is not a public API

(CLOSED 2026-10-01)  Six of the twelve cases import it.  The pip documentation
says in as many words not to, and the module path has moved before.  This is
code pasted into programs and never updated afterwards, so when it breaks it
breaks on some other person's machine, at their pip version, with no one around
to fix it.

Since this issue was written, case 11 was added to close the gap it
creates.  Avoiding `pip._internal` rules out cases 1, 4, 5, 6, 8
and 9, which left the "no pip but `venv` present" branch with no
answer at all, because case 4 was its only mechanism.  Case 11
reaches the same manufactured pip by running the venv's own
interpreter as a child process, and measures identically to case 4
on every column: 5 imports, 26 lines, 30 pasted, 1790 KB.  The
surviving set is therefore cases 2, 3, 7, 10 and 11, and nothing is
lost by discarding the rest.

Various thoughts:
* Wayne (2026-09-22): In general, this seems quite bad.  I'd very much like
  to avoid using `pip._internal`.  I'd very much dislike using this interface
  since the bootstrap code in theory could be replicated a large number of
  places.  I will point out that the reason why we have 10 bootstrap code
  candidates gives us some flexibility dealing with this issue.
* Wayne (2026-10-01): Closed, because we are downloading `pip`, and the
  cases that import `pip._internal` are going away.
