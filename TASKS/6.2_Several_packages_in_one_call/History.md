# 6.2 Several packages in one call: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.2 of `LOGBOOK.md` on 2026-10-04.

* Step 6.2: Several packages in one call, and what to do about bad
  requirements.  `install` takes one requirement or a list, costs one
  `pip` invocation for the set so that `pip` resolves them together,
  and is what makes Step 6.3's freshness check affordable.
  * 6.2.1 - `pip._internal` buys nothing here, measured 2026-09-26.
    `pip._internal.cli.main.main` **returns 1** for a missing package
    and raises nothing: it catches its own exceptions and converts them
    to exit codes exactly as the command line does.  The thirteen typed
    exceptions exist, but catching them means driving the resolver
    directly, which is far deeper into private API than the cases that
    got `0pinpa` filed, for the same stderr text we already have.
  * 6.2.2 - Exit codes carry one useful bit.  A missing package, an
    impossible version, a malformed requirement and a dead index all
    exit 1; only a bad option exits 2.  So 2 means we handed `pip` a
    bad command line, which is our bug or the caller's `argv`, and
    deserves a different exception.  `NO_MATCHES_FOUND = 23` exists in
    pip's status codes but `install` never returns it.
  * 6.2.3 - Parse pip's text for the message, never for the behaviour.
    Matching `No matching distribution found` to add "check the
    spelling?" is fine, because a rephrasing costs a hint and nothing
    else.  Branching control flow on it breaks on a pip upgrade, which
    is `0pinpa`'s failure mode reached through text instead of imports.
  * 6.2.4 - Validate locally what can be validated locally.  A
    requirement beginning with `-` is the one that matters: it would be
    read as an option, so `install("--index-url=...")` could repoint
    the fetch at somebody else's index, which belongs with Step 6.6.
    Requirement syntax is not ours to check: measured 2026-09-26, `pip`
    rejects `bad name with spaces` in 0.59 s with
    `ERROR: Invalid requirement`, locally, without touching the
    network, so reimplementing PEP 508 would only add a way to
    disagree with it.  What is left is that two entries must not claim
    the same import name, since `pip` cannot know our import names and
    one module would be returned twice.
  * 6.2.5 - What cannot be checked locally is whether `reqeusts`
    exists; only the index knows, so that error has to come from `pip`
    and is surfaced with pip's own words.  The one discrimination that
    really matters, first fetch versus staleness check in 6.3.8, comes
    from whether the cache is populated, which is known locally.

### Step 6.2: Several packages in one call

`include` became `install`, which takes one requirement or a list and
spends one `pip` invocation on the set.

* The API is `install("coverage")` returning a module, and
  `install(["coverage", "pytest>=7.0,<8"])` returning one module per
  requirement in order, so `cov, pt = ...` unpacks.  A
  `(import_name, requirement)` pair covers the packages whose two names
  differ, which replaces the old `distribution` argument.
* PEP 508 already carries version constraints, so no new structure was
  needed for them.  `argv` became per-call rather than per-package,
  since one invocation serves the whole set.
* Two `@overload` stubs give the varying return type.  `Requirements` is
  spelled `list | tuple` rather than `Sequence`, because a `str` is
  itself a `Sequence[str]` and the overloads would otherwise overlap.
  Docstrings on overload stubs are legal but pointless: only the
  implementation's survives, since each `def` rebinds the name.
* The one-invocation claim is counted rather than inferred.
  `test_install_runs_pip_once_for_the_set` wraps `subprocess.run`, lets
  the genuine one do the work, and asserts exactly one call carrying
  both requirements.
* The test index now publishes `sprocket` at 1.0.0 and 2.0.0, because
  one version per project makes every constraint pass trivially.  Four
  constraints are checked against both: `sprocket<2` and
  `sprocket!=2.0.0` take 1.0.0, `sprocket>=2` takes 2.0.0, and a bare
  `sprocket` takes the newest.
* 48 tests, up from 39 at the start of the step.
