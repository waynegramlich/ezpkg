# 6.13 Messages: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.13 of `LOGBOOK.md` on 2026-10-04.

* Step 6.13: Messages.  When should anything be said: on creating the
  directory, on each download, on a stale bootstrap?  One constraint is
  hard.  A library must never write to standard output, because the
  host program's output may be piped or parsed.  `logging` with a
  `NullHandler` lets the host decide.  One line on standard error when a
  download actually starts is still worth it, because several seconds
  of silence looks like a hang.

  A pointer to the `README.md` belongs in the failed fetch message from
  Step 6.1, and costs one `paste` line: the URL in a shared constant
  keeps the `raise` on one source line at 73 columns, where inlining it
  is 121 and wrapping it costs two, so `SHARED_LINES` would go from 7
  to 8.  Not done, because the URL depends on the repository name.
  * 6.13.1 - **Who writes what, and where**, surveyed 2026-10-01, which
    Wayne set as the first thing to know before deciding anything.  By
    reading `alt_venv.py` and `nopip3`, and by running `nopip3` cold with
    its two output streams kept apart.

    | Writer | Stream | When |
    |--------|--------|------|
    | `nopip3`'s `pip install` | **standard output** | first run only |
    | `nopip3`'s `pip install` | standard error | when it fails |
    | `nopip3`'s `except` | standard error, exit 1 | any failure |
    | `AltVEnv.announce` | standard error | every fetch |
    | `AltVEnv.gate` | standard error | `ALT_VENV_APPROVE=write` |
    | `AltVEnv.consent` | `/dev/tty`, not a stream | approvals and a terminal |
    | `AltVEnv.download` | captured; text goes into the exception | always |
    | `AltVEnv.refresh_pip` | captured and dropped | weekly |
    | `AltVEnv`'s exceptions | the caller's to catch | failures |

    The one surprise is the first row.  `pip` writes its progress --
    `Collecting coverage`, `Downloading ...`, `Successfully installed
    ...`, five lines -- to the program's own standard output, so the
    first run of a program whose output is piped or parsed gets those
    lines mixed into it.  `announce`'s own docstring says a library
    must never do this.  `stdout=2` on that `subprocess.run` would send
    them to standard error, and it fits inside 79 columns, so it costs
    no line.  Recommended for 6.13; not done, because 6.13 is Wayne's
    to decide.

    The other open question for 6.13 is the last row: `install()` raises
    on a failed fetch, so a program that does not catch it ends in a
    traceback, where `nopip3` itself ends in one line.
