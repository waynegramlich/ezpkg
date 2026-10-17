# 7.9 Ask before the first download

On a stranger's first run the bootstrap fetches `pip` and `ezpkg`
before anybody is asked anything, and `pip install`'s own lines
(`Looking in links`, `Processing`, `Installing collected packages`,
`Successfully installed`) are the first thing they see, with nothing
to explain them (Wayne, 2026-10-16: "totally confusing").

## Agreed (Wayne, 2026-10-16)

1. **Downloading silently is fine; running downloaded code without
   asking is not.**  The bootstrap is exempt, since the author put it
   there, so it asks nothing.  `EZPkg`'s download prompt, before any of
   the program's packages is used, is the question.
2. **Capture `pip`'s output** (`capture_output=True, text=True`) and
   hand the result to `EZPkg.__init__()`, along with the bootstrap's
   name and needed version (`T.eui`), so that `EZPkg` knows the most,
   soonest.  `EZPkg` explains what happened and can show `pip`'s lines
   afterwards.
3. **A failed install keeps `pip`'s reason** (such as `ERROR: No
   matching distribution found for ezpkg`), which a bare
   `CalledProcessError` would lose.
4. **The bootstrap name does not matter;** it will be renamed at
   deployment anyway.
5. Needs `T.eui` first: a new bootstrap breaks every older cached
   `ezpkg` until `ezpkg` can update itself.
