# Logbook Notes

<!-- ----------------------------79 characters----------------------------- -->

Decisions about how `LOGBOOK.md` itself works, made while converting it
to the task and issue format.  They are collected here so that Wayne can
propagate them back into `claude_notes.md`, which is the general write-up
and lives in its own repository.  Once a decision has been propagated it
can be deleted from this file.

## Various thoughts

Each issue may end with a `Various thoughts:` section.  It replaces the
older `Wayne's current thoughts:`, which assumed a single reviewer.

* **Multiple reviewers, named.**  Every thought is tagged with a
  reviewer's first name.  Two reviewers sharing a first name are
  disambiguated with a trailing digit, `Bill1` and `Bill2`.  That digit
  is a different namespace from the one that disambiguates colliding
  issue names, and the two never interact.

* **Claude is a reviewer like any other.**  It is named `Claude` and
  uses the same format.  Nothing marks it out as non-human.

* **Every thought is dated**, as `Name (YYYY-MM-DD):`.  Thoughts
  accumulate over months and go stale silently otherwise.  The case
  that prompted this: an issue carried "We'll start getting answers in
  Experiment 2" with no date, so nothing said whether it was still
  pending or long since answered.

* **Oldest first.**  The section reads as a thread, and the newest
  thought lands next to where the following one gets written.  This is
  the opposite of `### Closed Issues`, which is newest first, because
  that one is a log rather than a discussion.

* **Nobody edits somebody else's thought.**  Claude appends its own and
  never rewrites or deletes another reviewer's.  A thought that turns
  out to be wrong is answered by a later thought saying so, not by
  correcting the original.

* **Omit the section when it is empty.**  No thoughts means no heading,
  rather than a heading over an empty bullet.

* **The body and the thoughts stay distinct.**  The issue body is the
  checkable statement of the problem, written by Claude.  Thoughts are
  opinions and dispositions.  Now that Claude may have thoughts too,
  the temptation is to put the same analysis in both places.

An example of the resulting shape:

```
  Various thoughts:
  * Wayne (2026-09-21): We are going to die without the network to
    fetch the package.  We need to at least let the user know.
  * Claude (2026-09-24): `include()` now raises `RuntimeError` with
    pip's stderr, so the second stage does this.  The twelve bootstrap
    cases still do not.
```

## Issue priorities are not only about the bootstrap

Priority 0 used to be defined as "it can break the bootstrap once the
bootstrap is out in the wild."  That is an example rather than a
definition: a security hole is also a 0, and so is anything else that
must be avoided at all costs.  The definition now leads with the cost
and gives the escaped-code case and the security case as instances.

## A log book carries more than the template enumerates

The template in `claude_notes.md` shows `Goals`, then tasks, then issues.
A real log book needs background as well, and this one carries three
sections between the goals and the first task:

* `## Problem Statement` -- what is actually wrong, including the three
  categories of Python module that the whole project turns on.
* `## Initial Thoughts` -- considerations raised early that frame later
  decisions without being acted on.  The escape hatch of shipping the
  interpreter inside a Snap or a container lives here, because naming it
  keeps it a conscious choice rather than an oversight.
* `## Prior Art` -- what already solves this, and what each solution
  still asks of the user.

The ordering matters in one place.  `Goals` comes before
`Initial Thoughts`, because the escape hatch is a way of declining the
goal, and it reads oddly before the goal has been stated.

The section spelled `Goal` was renamed `Goals` on 2026-09-24 to match
the template.

## Changing a decision recorded inside a closed task

`LOGBOOK.md` is the history of the project.  Notes from the future are
scribbled into it rather than used to rewrite what it says.  A closed
task is therefore never edited; it is annotated.

An annotation is wrapped in curly braces and names the task that changed
things:

```
{Task 7 dropped the requirement for `pip`, so the conclusion below
describes what was believed here rather than what holds now.}
```

The rules:

* Curly braces, because Markdown leaves them alone, they survive a
  `grep`, and nothing else in the file uses them in prose.
* The annotation comes immediately before the text it qualifies, on its
  own line or lines, so it reads as a foreword rather than an
  afterthought.
* It names a task, not a date.  The task's own heading carries the date.
* One or two sentences.  An annotation that wants a paragraph is a sign
  the material belongs in the newer task instead.

Typos, spelling and grammar are the exception: those are fixed in place
on a closed task, with no annotation.  The rule protects what the task
claimed, not how badly it was typed.

The original wording stays readable as a record of what was believed at
the time, the annotation says where to look for what replaced it, and
the closed task keeps its integrity.  This is why standing decisions do
not need to be lifted out of closed tasks into a section of their own.

## A task heading names the task, not the experiment

Tasks 2 and 3 were called Experiment 1 and Experiment 2 while they ran,
which left the headings carrying two numbering schemes that were
permanently off by one.  The headings now name the work in title case --
`## Task 2: Create the Bootstrap Code` -- and each of those two task
bodies opens with one line saying what the task used to be called, since
a dozen references elsewhere still use the old names.  Annotate, do not
rewrite.

