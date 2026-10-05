# 6.10 `README.md` documentation: History

<!-- --------------------------- 79 characters ---------------------------- -->

Moved here from Step 6.10 of `LOGBOOK.md` on 2026-10-04.

* Step 6.10: `README.md` documentation.  Two different files carry that
  name and they are for different readers, so each has its own
  sub-items below and neither is finished by writing the other.  The
  project's `README.md` is the page a stranger lands on after a program
  tells them to; `~/.alt_venv/README.md` is what somebody finds inside
  the cache directory and wonders about.
  * 6.10.6 - Drafted 2026-09-28, both files, and Wayne's to edit: the
    prose is the product's face and a draft from Claude is a starting
    point rather than an answer.  `hg revert` undoes it in one command.

    The project's `README.md` keeps the opening -- a person arrives here
    annoyed, and the author chose this over a virtual environment -- and
    replaces the Scavenger Hunt with what the code does: a **What Just
    Happened** section showing the real listing and the real
    `[y/N/?]` question, a **Security** section written from 6.6's
    sub-items as two lists, what it protects against and what it plainly
    does not, and a **For Program Authors** section carrying the PEP 723
    shape with its `# noqa: BLE001` and `# type: ignore` comments
    explained.  Everything in it is something this project measured.

    The cache's `README.md` now describes the versioned layout it
    predated: `versions/`, `wheels/`, `requests/` and `pending/`, one
    line each, with the litter note for `pending/`.  And it is written
    **only when it would change**, which retires 6.10.5's complaint that
    making an object wrote a file; a stale copy is still replaced, so
    editing the docstring still reaches an existing cache.  Four tests.
  * 6.10.7 - Writing this step out of order paid for itself, twice over,
    and that is worth recording rather than apologising for.  Wayne
    rewrote the project's `README.md` from scratch on 2026-09-29 and we
    went through it line by line, and **describing the behaviour to a
    stranger is what exposed the decisions**.  Four things came out of it
    that specification alone had not produced:

    * The consent prompt gained a fourth answer, `[y/n/a/?]`, where `a`
      means approve from now on and leaves a marker in the cache.  Wayne
      wanted a reader to understand that code is being downloaded without
      being nagged about it forever; the letter and the marker file did
      not exist as an idea until the prompt had to be explained.
    * Garbage collection got designed, in 6.11.1, because *nothing ages
      out* was an uncomfortable sentence to write down.
    * `AltVEnv` never needs `sudo` -- which had to be checked before it
      could be claimed, and which contradicted the `apt install` line two
      paragraphs above it until a qualifier was added.
    * What a person sees when `pip` is missing got measured, because
      Wayne asked.  Python's own `No module named pip` is precise and our
      line beneath it is noise; see 6.13.
    * A definition of *wheel*, because most Python users have never
      needed the word, and the README used it to make its central claim.

    The general lesson, which the rest of Task 6 should expect: the steps
    still open are precisely the ones the `README.md` could not describe
    honestly.  Describing a thing is a cheap way to find out whether it
    exists.

  * 6.10.8 - What the project's `README.md` still lacks, as of 2026-09-29,
    so that the list is somewhere other than a conversation.  Grouped by
    who needs it, and the first group is the one that would embarrass us.

    **Missing and depended upon by a decision not yet made:**

    * **The download prompt.**  What is shown, that `?` lists the
      packages, that the default is no, that it is asked once per cache
      rather than once per run, and that a program with no terminal --
      `cron`, a build, a double clicked launcher -- proceeds without
      asking.  Waiting on the `[y/n/a/?]` letter and its marker file.
    * **The security section itself.**  Wayne's rewrite dropped the old
      `## Security Issues of Executing Unvetted Code` heading along with
      the Scavenger Hunt, so the page currently says **nothing** about
      the subject the whole feature rests on.  6.10.2 and 6.10.4 are its
      outline: what an approvals file guarantees, what a listing merely
      notifies, and the two things the mechanism cannot do -- a malicious
      author and a typosquat the author fell for.

    **Missing and ready to write:**

    * **The real bootstrap**, copy and pasteable.  The layout sketch at
      the top of the file is schematic and says so in a comment; an
      author cannot use the page as it stands.  This is the single most
      important omission.
    * **`uv` compatibility.**  The same file runs under `uv run` with the
      bootstrap never executing, which is the strongest argument for
      having used the standard block.  One sentence.
    * **The author's side of approvals**: run once with the writer, commit
      the `.altvenv` file beside the program, and recipients get those
      exact wheels or a refusal.
    * **Version constraints.**  `"requests<3"` works because it is a PEP
      508 requirement handed to `pip`, and two programs wanting different
      versions each get their own directory.
    * **`PIP_INDEX_URL`**, for a private index or a mirror, which is also
      how every test in this project fetches.
    * **What the messages mean**: the failed fetch, the Python floor
      refusal, and what happens with no network on a warm cache.
    * **Status and scope**: experimental; measured on Linux with CPython
      3.12; Windows, macOS and PyPy **untested**, which matters now that
      the page speaks to Windows readers; concurrent use tested; MIT-0;
      and a pointer here, to `LOGBOOK.md`, for anybody wanting the
      reasoning rather than the instructions.
    * **Where to report a problem**, once there is somewhere to report it.

  * 6.10.9 - Requirement forms, measured 2026-09-30 before being
    documented, because the `README.md` was about to claim that anything
    `pip` understands works.  Against the local index, all of these
    resolve correctly through `install()`: `sprocket>=1.0,<2`,
    `sprocket~=1.0.0`, `sprocket!=2.0.0`, `sprocket===1.0.0`,
    `sprocket>1.0.0`, `widget[extra]`, and environment markers both true
    and false.  Three tests pin the constraint forms and the two marker
    outcomes.

    **A defect fell out of the false marker.**
    `"widget; sys_platform == 'win32'"` on Linux printed
    `1 requested, 0 downloaded into ...` followed by an empty list, and on
    a terminal it would have **asked a person whether to install no
    packages at all**.  Nothing arriving is a real answer and not a
    failure -- a platform conditional dependency is a normal thing to
    write -- so `install` now returns quietly when the download brings
    back nothing.  Two tests: the excluded case says nothing whatever,
    and the same requirement with a true marker still installs.
  * 6.10.10 - The `README.md` as it stands on 2026-09-30, recorded because
    Wayne is about to reorganise it and the next session will not have
    this conversation.  Sections in order: Introduction; *How an `AltVEnv`
    Enabled Program Works* with a 34 line complete program listed with
    `01:` style line numbers and a bullet per line group; *The Bootstrap,
    Which You Do Not Edit* -- Wayne's framing, the try block is
    boilerplate -- with a *For The Curious* subsection holding the
    pasteable copy and the notes on it; *Saying Exactly What You Want*, on
    requirement forms and markers; *What You Need*; *Where Things Land*;
    *Being Asked Before Anything Is Downloaded*; *What This Protects You
    Against, And What It Does Not*.

    The reorganisation Wayne intends: the file is what PyPI shows as a
    project's front page, so the top has to **sell** the package to a
    stranger who found it by accident, and the manual follows.  See
    6.10.11 for what that changes.
  * 6.10.11 - Advice on selling first, written 2026-09-30 so that the
    intent survives a `/clear`:

    * The first fifteen lines are the whole of the sale.  PyPI shows the
      project name and summary itself, so the page can open on the
      problem in a reader's own words -- a single file program that needs
      `requests` -- rather than on a heading that repeats the name.
    * The strongest trust signal costs nothing and belongs near the top:
      **when not to use this.**  `uv run` is better whenever the people
      running the program can install `uv`; `zipapp` is better when there
      is no network; a virtual environment is better for a project rather
      than a script.  A page that says so is believed about everything
      else.
    * Four honesty constraints must survive the rewrite, because hiding
      any of them converts a sale into a support burden: `pip` must be
      preinstalled, the project is experimental, packages are fetched and
      run from an index, and everything has been measured on Linux with
      CPython 3.12 only.
    * The numbered walkthrough is worth keeping and belongs in the manual
      half, not the sale.  It is unusual in a way that helps a reader who
      has decided to commit, and it is noise to one who has not.
    * Two PyPI rendering facts: relative links break, since there is no
      repository context, and HTML comments are not rendered, so the
      `<!-- Claude: ... -->` notes can stay.

  * 6.10.1 - The project's `README.md` still describes the Scavenger
    Hunt, at lines 17 and 27, which nothing implements any more: nobody
    is sent to visit web pages and paste titles back.  What replaced it
    is that the author approves once, and the recipient is told and
    asked at most once per cache.
  * 6.10.2 - `## Security Issues of Executing Unvetted Code` is still
    marked TBD, and it is the section the whole feature rests on.  The
    sub-items of Step 6.6 are its outline, and 6.6.1 in particular: the
    claim has to be narrow to be true, because a malicious author gets
    no protection at all and a typosquat very little.
  * 6.10.3 - Habituation deserves an answer here, per 6.6.7.  The
    mitigation is real and worth stating: the question is asked once per
    cache, not once per run, and an approvals file removes it entirely.
  * 6.10.4 - The project's `README.md` should say plainly that an
    approvals file is how a guarantee is had, where a listing is only a
    notification, and that a program started by `cron` or a build has
    nobody to ask and so proceeds.
  * 6.10.5 - The cache's `~/.alt_venv/README.md` is the other file, and
    `AltVEnv.__init__` writes it from its own docstring.  What it should
    say needs discussing, and it has to describe the versioned layout of
    Step 6.3, which it predates.  Note the current behaviour: it is
    rewritten on every construction rather than only when absent, which
    makes writing a file a side effect of making an object and will
    surprise somebody.
