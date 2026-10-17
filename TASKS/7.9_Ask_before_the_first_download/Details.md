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

## The Download Prompt (Wayne, 2026-10-16)

From Wayne's dogfood of `run_testpypi --clean > output 2>&1`: most of
what a first run prints is confusing.  At most three lines, with the
onus on the program's author:

```
prog.py needs 3 software packages, chosen by its author and now downloaded.
If you do not trust the author of prog.py, answer n and nothing is installed.
Install them into ~/.ezpkg? [y=>Yes/n=>No/a=>Always/?=>Explanation]
```

* Promise nothing `EZPkg` cannot know ("the packages it needs", not
  "the correct software").
* Name the program (though for some programs that helps little).
* The package names, versions and `pip`'s captured lines go under `?`.
* "Where" stays in the question, so it can be undone.
* The answer is echoed with the question, so redirected output tells
  the whole story.
* A "no" ends with `ezpkg: nothing was installed, so prog.py stops
  here.`, not today's `fetch packages failed: RuntimeError('declined:
  ...')`.
* README "Download Prompt" is rewritten to match.

## Keep or Delete (Wayne, 2026-10-16)

The packages are already downloaded when the question is asked, so it
asks whether to keep them:

```
prog.py needs 3 software packages, chosen by its author and now downloaded.
If you do not trust the author of prog.py, answer n and they are deleted.
Keep them in ~/.ezpkg and run prog.py? [y=>Yes/n=>No/a=>Always/?=>Explanation]
```

* `y`: `ezpkg: 3 packages stored in ~/.ezpkg.`  On Windows the full
  path is shown, since Windows has no `~`.
* `n` on a first run: `~/.ezpkg` is deleted entirely, `pip.whl` and
  `ezpkg` included; it never happened.  `EZPkg.__init__()` knows it is
  a first run from the captured `pip` result the bootstrap hands it.
* `n` on any other run: only the new downloads are deleted.
* If in doubt, delete: anything deleted is simply fetched again.  A
  second program starting at the same moment is unlikely but
  possible; how to handle it is not settled.
* "Software package" is the phrase; `?` explains it in one line (a
  piece of code from PyPI, the Python Package Index, that the program
  uses).
