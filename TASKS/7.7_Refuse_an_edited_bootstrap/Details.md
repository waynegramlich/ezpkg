# 7.7 Refuse an edited bootstrap

If a program's bootstrap has **ever** been modified, `EZPkg` detects
it, says where it changed, and stops until it is fixed (Wayne,
2026-10-16).  An edited bootstrap is code nobody here wrote, running
before `EZPkg` gets control, so nothing after it can be vouched for.
Today an edit is reported only under `EZPKG_BOOTSTRAP=check`.

## What Is Agreed

1. **Detect, then stop.**  The bootstrap has already run by the time
   `EZPkg` sees it, so this cannot prevent anything; it refuses to go
   on.  `install()` exits non-zero.  The person who edits a bootstrap
   is almost always the author, who runs the program before sending
   it, so the refusal reaches the one person who can fix it.
2. **Say where.**  `ezpkg.py` carries the text of every published
   bootstrap, not just its fingerprint, and compares the program's
   bootstrap token by token against the nearest one, naming the line
   and what differs, then how to replace it:

   ```
   ezpkg: prog.py line 33: the bootstrap has been edited:
       "choose pipxxx"  (nopip6 has "choose pip")
   Replace lines 21-56 with the bootstrap from https://pypi.org/project/ezpkg/
   ```
3. **The names must match.**  The name the bootstrap gives itself
   (`bootstrap="nopip6"`) must be the one its fingerprint belongs to.
4. **Only what `EZPkg` can reach.**  The checks run once `EZPkg` is
   running; a bootstrap too broken to get there fails on its own, and
   it was warned three times not to edit the code.  The check is in
   `ezpkg.py`, so it covers every bootstrap ever published, old ones
   included.  Done before `T.utpat`, so that no edited bootstrap goes
   unnoticed from the first real release.
5. README's "Never edit the bootstrap" paragraph says so.

## Still To Discuss

What is allowed through:
* Layout and comments (re-indenting, re-wrapping, an added `# noqa`),
  which the fingerprint already ignores.  A bootstrap indented inside
  an `if` is legitimate.
* A stale but unedited bootstrap (`nopip5`): published and unmodified.
  `EZPKG_BOOTSTRAP=check` still reports it as stale.
* No bootstrap at all (`uv run`, a `zipapp` export, a program calling
  `EZPkg` directly).  Proposed rule: a call with `bootstrap="..."` must
  come from a recognised bootstrap; one without it is not checked.
