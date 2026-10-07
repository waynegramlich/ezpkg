# 5 A real package server: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Task 5 of `LOGBOOK.md` on 2026-10-04.

## Task 5: A Real Package Server  (CLOSED 2026-09-25)

The primary purpose of this task is to do end-to-end testing of the bootstrap
code with a real package server.  A proposed list of steps list belows:

* Step 5.1: Select a package server.  This is a research task.  No coding.

* Step 5.2: Serve the existing tree over HTTP.  A `ThreadingHTTPServer`
  bound to `127.0.0.1` on port 0, so that the operating system assigns
  the port and the test reads it back rather than colliding with a stale
  server; a daemon thread; torn down through `addClassCleanup`, which is
  also what makes a control-C leave nothing behind.  Prove it by pointing
  `PIP_INDEX_URL` at `http://127.0.0.1:<port>/` and re-running the tests
  that pass today over `file://` -- the same assertions, a different
  transport.  Measured 2026-09-25: `pip` reaches a plain HTTP loopback
  index with no `--trusted-host` and no TLS.

* Step 5.3: Settle cases 3 and 12.  They fetch
  `https://pypi.org/pypi/{PACKAGE}/json` with bare `urllib`, which knows
  nothing of `PIP_INDEX_URL`, so they are the one real gap: either serve
  that JSON shape from the same server, or teach both cases the simple
  API instead.

* Step 5.4: The failure cases carried over from Task 3.  A truncated
  wheel, a missing `index.html`, and a 500 from the index.  All three are
  cheap once a server exists, because a server can be told to misbehave
  where a directory cannot.

* Step 5.5: Run every `bootstrap.py` case against the server end to end,
  asserting that `alt_venv` lands in the cache and imports.  This is
  the test the task exists for.

* Step 5.6: TLS, which nothing has exercised yet.  Two questions: does a
  case refuse a certificate it cannot verify, and does it succeed once
  the certificate is trusted?  `pip` reads `PIP_CERT` and `urllib` reads
  `SSL_CERT_FILE`, both environment variables, so no case body changes.
  This does not settle the `ca-certificates` dependency from Task 3,
  which is about trusting the public authorities well enough to reach
  the real PyPI; a private certificate tests the opposite.

* Step 5.7: Test suite coverage, measured with the standard library
  `trace` rather than `coverage`, so that the suite needs nothing
  installed.

### Step 5.1: Select a package server (research only)

`build_index` in `alt_venv_test.py` already emits a complete PEP
503 tree, so the question was whether any server buys anything that
`http.server` over that tree does not.  The criterion is that the test
suite run with nothing installed beyond `python3-pip`, since a suite
needing `pip install` to test a bootstrap that exists because one
cannot `pip install` argues against itself.  Dependency counts come
from `pip install --dry-run --report`.

* `devpi-server` -- rejected: 43 dependencies, one of them the compiled
  `argon2-cffi-bindings`, which is the `.so` problem of `I.nicav`.
* `simpleindex` -- rejected: 14 dependencies, including `pydantic`,
  `uvicorn` and `starlette`, to serve a static file tree.
* `pypiserver` -- rejected: 4 dependencies, and its JSON route is
  `/:project/json` returning the legacy `info`/`releases` shape, so
  cases 3 and 12 would need a translating shim and a path rewrite.
* `http.server` -- **selected**: 0 dependencies, and a
  `ThreadingHTTPServer` on port 0 serving the existing tree installed
  `alt_venv` through `PIP_INDEX_URL` with returncode 0.  The
  handler is about 35 lines, including the 12 that synthesize
  `/pypi/{PACKAGE}/json` in the shape case 3 already parses.

Not settled here: `http.server` has no TLS, so Step 5.6 will need
`ssl.SSLContext.wrap_socket` on the listening socket.  No alternative
above supplies a trusted certificate either.

### Step 5.2: Serve the existing tree over HTTP

`serve_index` in `alt_venv_test.py` publishes the tree that
`build_index` already produced, and both test classes now reach it
through `PIP_INDEX_URL` over a socket instead of over `file://`.  The
15 existing tests pass unchanged, which was the point: same
assertions, different transport.

* The handler subclasses `SimpleHTTPRequestHandler` only to silence
  the request log.  The base class already serves a directory's
  `index.html`, which is exactly what a PEP 503 tree asks for.
* Port 0, so the operating system assigns the port and the caller
  reads it back.  A fixed port would collide with a server left by an
  interrupted run, and that failure would read as a packaging bug.
* A daemon thread is what makes control-C clean.  Measured
  2026-09-25: `SIGINT` to a test process ended it in 0.032 s and the
  port was refusing connections immediately afterwards.
* `tearDownClass` calls `shutdown` and `server_close` before the tree
  is removed, and the server starts last in `setUpClass` so that
  nothing can fail after it is up.

Not done here: cases 3 and 12 still cannot be tested, because they
want `/pypi/{PACKAGE}/json` rather than the simple API.  That is Step
5.3.

### Step 5.3: Settle cases 3 and 12

Cases 3 and 12 read PyPI's JSON API with `urllib`, which knows nothing
of `PIP_INDEX_URL`, so they were the two cases no local index could
reach.  They are now tested, and the choice was to serve the JSON
rather than to convert them to the simple API.  That keeps what the
cases measure -- a bootstrap needing neither `pip` nor `venv` -- which
converting them would have thrown away.

* `bootstrap.py` gained `JSON_API`, read from `BOOTSTRAP_JSON_API` and
  defaulting to `https://pypi.org/pypi`.  This copies what `PACKAGE`
  and `BOOTSTRAP_PACKAGE` already do, and for the same reason: the
  harness aims a case at a local server without editing a case body.
* The `paste` column did not move.  The substitution costs no lines,
  and `measure_source` still reports 5 imports and 45 lines for case 3
  and 7 and 51 for case 12, which is what the Task 2 table says.  No
  remeasurement was needed after all.
* `_IndexHandler` answers `/pypi/{project}/json` from the tree, in the
  modern `{"urls": [...]}` shape that those two cases parse, and 404s
  a project the index does not hold.  The payload is the subset they
  read rather than all of PyPI's, since the rest cannot be checked.
* Both cases now run end to end: three new tests take the suite to 18,
  and pointing `BOOTSTRAP_JSON_API` at a dead port fails them, so they
  are measuring the fetch and not passing vacuously.

### Step 5.4: The failure cases

A directory index cannot misbehave, which is why these went untested
through Tasks 2 and 3.  `_IndexServer` now carries a `faults` table
that maps a path suffix to what should go wrong, and a test adds an
entry through `inject`, which registers the removal as a cleanup first
so that a failing assertion cannot leave the fault in place.

* Four faults exist.  `missing` answers 404, `error` answers 500,
  `hang` waits three seconds and then answers correctly, and
  `truncate` sends the first half of the file with a `Content-Length`
  that agrees with the half.
* `truncate` is the one worth having.  The download looks complete at
  every layer below the archive, so nothing but unzipping catches it.
  `pip` refuses the install, and case 3, which unzips the wheel
  itself, fails inside `zipfile`.
* Five tests take the suite to 23.  Neutering `inject` makes all five
  fail, so they measure the faults rather than passing for free.
* A hung connection turned out to be in scope after all, for `pip`:
  `PIP_TIMEOUT` and `PIP_RETRIES` bound the wait, so the test costs a
  second rather than a minute.  It stays out of scope for cases 3 and
  12, whose `urlopen` timeouts are literals of 30 and 60 seconds
  inside counted case bodies.  Steering those would want a third
  harness constant beside `PACKAGE` and `JSON_API`.
* `_IndexServer.handle_error` swallows `ConnectionError` and nothing
  else.  A client that times out hangs up mid-answer, and the base
  class prints a traceback for that, which looked like a failure in
  the middle of a passing run.

### Step 5.5: Every case, end to end

`test_every_case_bootstraps` runs all twelve cases against our own
server and asserts that each one lands `alt_venv` in the cache and
imports it.  All twelve pass.  That is the claim Task 5 was opened to
establish.

* The case list is read from `bootstrap.MECHANISMS` rather than copied
  into the test, so a thirteenth case cannot quietly go untested.
* Four assertions per case: `pip` or `urllib` exited zero, the printed
  module name matches, the version matches `alt_venv.__version__`,
  and the file it was imported from lies under `.alt_venv`.  The
  last one is what distinguishes a real fetch from an accidental
  import of the copy in this directory.
* The suite went from 13.8 s to 40.3 s.  The twelve cases cost about
  26 s of that, nearly all of it building virtual environments.
* Every run in that test is cold, because each case gets a fresh
  `HOME`, so the warm path needed a test of its own.
  `test_every_case_bootstraps_repeatedly` is it: one cache per case,
  three runs through it, all twelve passing.  Three rather than two
  because the repair that `I.cctfd` needed has to be idempotent, and an
  earlier version of it passed two runs and broke the cache on the
  third.  `I.cctfd` is closed.

### Step 5.6: TLS

The one thing a directory index could never test.  `make_certificate`
shells out to `openssl` for a throwaway self signed certificate, and
`serve_index` wraps the listening socket when it is handed one.  Both
questions are answered, and the first is the one that mattered.

* **Every case refuses a certificate it cannot verify**, and fails over
  the certificate rather than for some unrelated reason.  Case 3, which
  uses `urllib`, reports
  `[SSL: CERTIFICATE_VERIFY_FAILED] ... self-signed certificate`; case
  6, which uses `pip`, reports `SSLCertVerificationError`.  Nothing
  falls back to plain HTTP and nothing accepts an unknown issuer.  Had
  one done so, it would have been a priority 0 issue: pasted code on a
  stranger's machine handing their program's contents to whoever
  controls the network.
* Every case succeeds once the certificate is trusted, which is what
  makes the refusal a real check rather than TLS being broken outright.
  `SSL_CERT_FILE` is what `urllib` honours, through OpenSSL's own
  default verify paths, and `PIP_CERT` is what `pip` honours.  Both are
  environment variables, so no case gained a line and the `paste`
  column did not move.
* `openssl` is a program rather than a Python package, so it costs the
  suite no dependency under the Step 5.1 criterion.  A machine without
  it skips these tests rather than failing them.  The certificate lasts
  ten years and carries `subjectAltName=IP:127.0.0.1`, because Python
  has ignored `commonName` since 3.7.
* `handle_error` now swallows `ssl.SSLError` as well as
  `ConnectionError`.  A refused handshake is exactly what the negative
  test provokes, and the base class prints a traceback for it.

`ALT_VENV_TEST` chooses how much of this runs.  Unset or `FAST`,
which is the usual way, exercises cases 3, 6, 11 and 12 -- one case per
distinct mechanism, plus the one whose second run used to fail.
`COMPLETE` exercises all twelve.  An unrecognised value raises rather
than quietly running the fast tests.  Measured 2026-09-25: 29 tests in
50.9 s fast, 193.3 s complete, both passing.

One thing is still unsettled, and it is the last of the Task 3
leftovers.  Task 3 concluded that a bootstrap needs `python3-pip` plus
a TLS trust store, and that conclusion is about trusting the public
certificate authorities well enough to reach the real PyPI.  A private
certificate tests the opposite, that the system trust store can be
overridden, so nothing here confirms it.  Confirming it needs a fetch
from the real index, which is a test with a network dependency and
belongs with the work on `alt_venv.py` rather than here.

### Step 5.7: Coverage

`alt_venv_coverage.py` measures the suite with the standard
library `trace`.  `coverage` would have been a `pip install`, and a
suite for a project about packages that are not preinstalled should not
need a package fetched; the same criterion chose `http.server` in Step
5.1.  Where it ended up, on the fast suite:

| module                   | lines | before | after |
| ------------------------ | ----- | ------ | ----- |
| `bootstrap.py`           |   407 |     7% |    7% |
| `alt_venv.py`       |    65 |    60% |   98% |
| `alt_venv_test.py`  |   590 |    87% |   99% |

Nine tests were added, taking the suite from 29 to 38 and from 50.9 s
to 56.5 s.  Tracing itself costs almost nothing, which is its own
finding: nearly all of the work happens in child processes, where the
tracer cannot reach.

* **`alt_venv.py` is effectively complete.**  The gap was that
  `repair_module_layout` and `install` were exercised only through
  child interpreters, so their bodies were never measured.  Calling
  them in process, with `__file__` or `PIP_INDEX_URL` patched, covered
  both.  The last uncovered line can never be reported: it runs only
  when `__file__` is `None`, and `trace.Trace.globaltrace_lt` decides
  what to follow by reading `frame.f_globals.get("__file__")`, so the
  state that reaches the line is the state that turns tracing off.
  98% here means 100%.
* **Threads have to be instrumented separately**, and this was the
  single biggest correction.  `trace` follows only the thread it starts
  in, so every request handler looked dead however many requests went
  through it.  `threading.settrace` moved the harness from 88% to 99%.
* **The one real gap tracing found** was `make_certificate`'s two
  failure returns and the skip they trigger: the path that runs on a
  machine with no `openssl`, where a fault would make the TLS tests
  error instead of skip, and where it would be hardest to diagnose.
  Three tests cover it now, one of them using `/bin/false` as a
  stand-in for a failing `openssl` so that nothing mocks `subprocess`.
* **Hit counts said more than percentages.**  `do_GET` ran 54 times,
  `fault` returned a fault 5 times and `None` 49, `send_fault` covered
  `missing`, `error` and `hang` once each and `truncate` twice, and
  `send_json` answered ten times and 404ed once.  That `hang` alone
  falls through to a correct answer is visible in the counts: the
  post-fault `return` fires four times, not five.
* **`bootstrap.py`'s 7% is an artefact** of the twelve cases running as
  children, and measures only the module level code that an import
  executes.  The cases are covered by Steps 5.5 and the repeat test.
  Driving `main()` in process would mean twelve cases mutating
  `sys.path`, `HOME` and `sys.modules` inside the runner, which is why
  they are children in the first place.
* Five uncovered lines remain in the harness, all accounted for and
  none worth closing: `super().handle_error`, which never firing is
  the healthy state; the `openssl` absent skip, untestable while
  `openssl` is present; and `main` with its `unittest.main`, which the
  coverage runner bypasses by calling `unittest.main(module=...)`.

### Task 5 Summary

All twelve `bootstrap.py` cases now fetch `alt_venv` from a
package server this project controls, import it, and do it again on a
second and third run without fetching anything.  That was the whole
point of the task.

The server is `http.server` over the PEP 503 tree the test suite
already built, chosen in Step 5.1 because the alternatives cost between
4 and 43 dependencies and bought nothing.  It serves the JSON API that
cases 3 and 12 read, it can be told to misbehave, and it can speak TLS.
None of that cost a single case a line of pasted code: `JSON_API`, the
`I.cctfd` repair and the whole of TLS are steered from outside the case
bodies, so every `paste` figure is what Task 2 measured.

Three things were learned rather than assumed.  Pointing the cases at
the package this project ships, instead of at `coverage`, immediately
exposed `I.cctfd`: the guard every case uses asks whether the package is
a directory, a single module install is not one, and case 11 deletes
the `pip` it would need to fetch again.  Every case fails closed on a
certificate it cannot verify, which nothing had ever checked and which
would have been a priority 0 defect had it gone the other way.  And
tracing the suite found that its own server was invisible to the
tracer, because `trace` follows only the thread it starts in.

What is not settled: Task 3's conclusion that a bootstrap needs
`python3-pip` plus a TLS trust store is about trusting the public
certificate authorities well enough to reach the real PyPI, and a
private certificate tests the opposite.  Confirming it needs a fetch
from the real index.

The final measurement follows.  The Task 2 chart stays as it was,
because it measured `coverage` from PyPI and this one measures
`alt_venv` from `127.0.0.1`.

```
date        : 2026-09-25 19:12
python      : 3.12.3 at /usr/bin/python3
platform    : linux
inside venv : False
package     : alt_venv
index       : local, http
repetitions : 3; cold and warm are medians

+------+-----------------+---------+-------+-------+--------+--------+--------+
| case | mechanism       | imports | lines | paste | cold   | warm   | size   |
+------+-----------------+---------+-------+-------+--------+--------+--------+
| 1    | venv(pip), pip  | 4       | 20    | 24    | 4.42 s | 0.09 s | 15275  |
|      | in process      |         |       |       |        |        |        |
| 2    | venv(pip), pip  | 4       | 20    | 24    | 4.45 s | 0.10 s | 15275  |
|      | subprocess      |         |       |       |        |        |        |
| 3    | no venv, stdlib | 5       | 45    | 49    | 0.13 s | 0.10 s | 52     |
|      | wheel           |         |       |       |        |        |        |
| 4    | venv(pip), then | 5       | 26    | 30    | 4.38 s | 0.10 s | 84     |
|      | delete pip      |         |       |       |        |        |        |
| 5    | venv(no pip),   | 4       | 20    | 24    | 1.23 s | 0.10 s | 84     |
|      | pip in proc     |         |       |       |        |        |        |
| 6    | no venv, pip in | 1       | 11    | 15    | 1.23 s | 0.09 s | 56     |
|      | process         |         |       |       |        |        |        |
| 7    | no venv, pip    | 1       | 11    | 15    | 1.33 s | 0.08 s | 56     |
|      | subprocess      |         |       |       |        |        |        |
| 8    | no venv, pip    | 2       | 15    | 19    | 2.76 s | 0.09 s | 56     |
|      | from wheel      |         |       |       |        |        |        |
| 9    | as 6 plus --no- | 1       | 11    | 15    | 1.27 s | 0.09 s | 56     |
|      | compile         |         |       |       |        |        |        |
| 10   | as 7 plus --no- | 1       | 11    | 15    | 1.36 s | 0.09 s | 56     |
|      | compile         |         |       |       |        |        |        |
| 11   | as 4 but        | 5       | 26    | 30    | 3.88 s | 0.10 s | 84     |
|      | subprocess      |         |       |       |        |        |        |
| 12   | venv(no pip),   | 7       | 51    | 55    | 0.15 s | 0.11 s | 80     |
|      | stdlib wheel    |         |       |       |        |        |        |
+------+-----------------+---------+-------+-------+--------+--------+--------+

All cases succeeded.
```

{Step 6.1 of Task 6 wrapped the fetch in a three line `try` on
2026-09-26, so every `paste` figure above is now three higher: 27, 27,
52, 33, 27, 18, 18, 22, 18, 18, 33 and 58 for cases 1 to 12.  The
wrapper turns a failed fetch into one line of diagnosis instead of a
traceback, which is the `I.whwnn` issue.}

What the remeasurement says:

* All twelve cases fetch `alt_venv` from our own server and import
  it, with no failures.  That is the thing Task 5 exists to establish.
* `imports`, `lines` and `paste` are identical to the Task 2 chart in
  every row.  Neither `JSON_API` nor the `I.cctfd` repair cost a case a
  line, because both live outside the pasted case bodies.
* Warm is now genuinely warm: 0.08 to 0.11 s everywhere, against 1.20
  to 2.76 s before `I.cctfd` was fixed.  The guard now trips, so a
  second run inserts a path and imports rather than fetching again.
  Case 11, which failed on every warm run, passes.
* Sizes rose by 16 KB per case, which is the `README.md` the
  constructor writes plus the directory the repair creates.  The
  constructor did not run at all before, because `bootstrap.py` only
  imported the module.
* Against the Task 2 chart, sizes are still smaller by a factor of
  about 20 outside the venv-with-pip cases, because `alt_venv` is
  one pure Python module where `coverage` ships compiled extensions.
  The 15275 KB of cases 1 and 2 is almost entirely the `pip` they keep.

(CLOSED 2026-09-25)
