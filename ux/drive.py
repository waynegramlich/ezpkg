#!/usr/bin/env python3
"""Drive the UX steps on a real terminal, and write a transcript.

Each step edits `prog.py`'s imports and runs it on a pseudoterminal,
so `ezpkg`'s questions are asked as they are of a person.  The first
run is a stranger's: a home of its own, and the bootstrap fetches `pip`
from pypi.org and installs `ezpkg` from a wheel of the project's
`ezpkg.py` (`PIP_FIND_LINKS`), as it will from pypi.org.  Each question is answered from the step's
script, in order, and checked against the text it expects; a download
question ("... and run prog.py?") is answered `y` wherever it comes,
since whether one comes depends on what this Python already has.
Then the step's checks run on what was printed and on `prog.py`.

Everything happens in a fresh temporary copy, starting from the
project's `quick_start.py`, so nothing of the project's or of `~/.ezpkg`
is touched.

Usage: `ux/drive.py [--keep] [--until STEP | --only STEP...]
[--ux-dir DIR] [OUTPUT]`.  OUTPUT defaults to `ux/drive_output.txt`
(ignored by git and hg); it is written as the steps run, each step
framed by `^` and `v` lines.  `--keep` leaves the temporary copy, and
says where; `--until 1.4` stops after the step numbered `1.4`.

`--only 1.4 1.6` runs just those steps.  The copy after every step run
is kept in `ux/.snapshots/NN/` (ignored), so a step starts from the
snapshot of the step before it; without one, the steps before it run
first as setup, not written to ux files and not counted.  Snapshots
are thrown away when `drive.py`, `ezpkg.py`, `quick_start.py` or
`ezpkg_test.py` changes.  A snapshot goes back to the temporary path
it was taken at, since the cache records absolute paths.
`--ux-dir DIR` writes the per-step files there instead of `ux/`.

Each step also leaves `prog.py` as it ran, `ux/uxNN_prog.py`, and, when
`ezpkg` edited it, as `ezpkg` left it, `ux/uxNN_prog_after.py`; the
step's third line names both.  So `diff ux10_prog_after.py
ux11_prog.py` is the step's own edit, and `diff ux11_prog.py
ux11_prog_after.py` is `ezpkg`'s.

Each step's output is also written on its own, without the frame, as
`ux/uxNN_NAME.txt` (`NN` the step's place, from `01`).  Wayne edits
those into the output he wants and commits them, so after a rerun
`git diff ux/` shows where the real output departs from the agreed.
A rerun overwrites them; commit first.
"""

import dataclasses
import hashlib
import json
import os
import pty
import re
import select
import shutil
import signal
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

UX: Path = Path(__file__).resolve().parent
PROJECT: Path = UX.parent
SNAPSHOTS: Path = UX / ".snapshots"
sys.path.insert(0, str(PROJECT))
import ezpkg
import ezpkg_test

WIDTH: int = 79
IDLE_SECONDS: float = 180.0
STEP_SECONDS: float = 900.0
# A question ends the output with its answers in brackets.
QUESTION: re.Pattern[str] = re.compile(
    r"(\[[^\[\]\n]*=>[^\[\]\n]*\]:?|Enter to skip\):) $")
DOWNLOAD: str = "and run `prog.py`?"
CONTROL_C: str = "\x03"
CONTROL_D: str = "\x04"


@dataclasses.dataclass
class Step:
    """One UX step.

    Attributes:
    * `name`, `description` (`str`):
      Shown above its output.
    * `imports` (`list[str] | None`):
      The modules imported below `import cowsay`, or `None` to leave
      `prog.py` as it is.
    * `script` (`list[tuple[str, str]]`):
      Each expected question (a piece of its text) and the answer.
    * `present`, `absent` (`list[str]`):
      Text the output must, or must not, contain.
    * `declared` (`list[str] | None`):
      The package names `dependencies` must then list, in order.
    * `kept` (`list[str] | None`):
      What `[tool.ezpkg] unimported` must then list.
    * `before` (`Callable[[Path], None] | None`):
      Run on the copy first, such as removing a record.
    * `command` (`list[str] | None`):
      What to run with Python instead of `prog.py`, such as the
      cache's `remove.py`, relative to the copy.
    * `mode` (`str`):
      The program's mode afterwards, `end-user` until it has changed
      and `developer` from then on (`EZPkg.developing`), or `gone`
      when `~/.ezpkg` must have been removed.
    """

    name: str
    description: str
    imports: list[str] | None
    script: list[tuple[str, str]] = dataclasses.field(default_factory=list)
    present: list[str] = dataclasses.field(default_factory=list)
    absent: list[str] = dataclasses.field(default_factory=list)
    declared: list[str] | None = None
    kept: list[str] | None = None
    before: Callable[[Path], None] | None = None
    command: list[str] | None = None
    mode: str = "developer"


def first_run_again(work: Path) -> None:
    """Make the next run a first one: the Quick Start, and no cache."""
    shutil.copy2(PROJECT / "quick_start.py", work / "prog.py")
    shutil.rmtree(work / "home" / ".ezpkg", ignore_errors=True)


BASE: list[str] = ["ezpkg", "cowsay"]
STEPS: list[Step] = [
    Step("1.1 Baseline",
         "The Quick Start as it is: a download question, then the cow.",
         [], present=["EZPkg works!"],
         absent=["exclude-newer", "dependencies", "Traceback"],
         declared=BASE, mode="end-user"),
    Step("1.1b Not working on it",
         "An end-user's copy changed, answered n: no edit, only a warning.",
         ["tabulate"], [("Are you working on", "n")],
         present=["No module named 'tabulate'", "not in Python or `ezpkg`"],
         absent=["Update them?", "Add \"tabulate\"?"],
         declared=BASE, mode="end-user"),
    Step("1.1c Not working on it, run again",
         "Still broken, so asked again; n again, and the same explanation.",
         None, [("Are you working on", "n")],
         present=["not in Python or `ezpkg`"],
         absent=["disagree", "Update them?", "not importable here"],
         declared=BASE, mode="end-user"),
    Step("1.2 Batch y",
         "Two new imports: one question, y, and no second approval.",
         ["requests", "yaml"],
         [("Are you working on", "y"), ("Update them?", "y")],
         present=["2 entries in `dependencies`", "mypy   import requests",
                  "EZPkg works!"],
         absent=["Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml"]),
    Step("1.3 Batch i, with keep",
         "Both imports removed: i, then k for requests, y for PyYAML.",
         [], [("Update them?", "i"), ('"requests', "k"),
              ("What needs `requests`?", "the sync script"),
              ('"PyYAML', "y"), ("Make these changes?", "y")],
         present=['"requests", # Needed by the sync script.',
                  'remove "PyYAML'],
         absent=["Traceback"],
         declared=[*BASE, "requests"], kept=["requests"]),
    Step("1.4 Batch n",
         "Two more imports, answered n: nothing changes.",
         ["yaml", "rich"], [("Update them?", "n")],
         declared=[*BASE, "requests"]),
    Step("1.4b Batch n, run again",
         "Nothing changed since the n, so nothing is asked.",
         None, absent=["Update them?", "disagree"],
         declared=[*BASE, "requests"]),
    Step("1.5 A misspelt import in a batch",
         "A third import nobody publishes: named, not counted, not added.",
         ["yaml", "rich", "bogus_pkg_xyzzy"], [("Update them?", "y")],
         present=['no package "bogus_pkg_xyzzy"',
                  "2 entries in `dependencies`"],
         declared=[*BASE, "requests", "pyyaml", "rich"]),
    Step("1.6 One change",
         "One new import: listed and asked like a batch, in the singular.",
         ["yaml", "rich", "attrs"], [("Update it?", "y")],
         present=["1 entry in `dependencies`"],
         absent=["Make these changes?", "disagree", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs"]),
    Step("1.7 Auto",
         "a, asked once: updated now, and from then on without asking.",
         ["yaml", "rich", "attrs", "click", "tabulate"],
         [("Update them?", "a")],
         present=["To be asked again, delete"],
         absent=["Really", "Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click",
                   "tabulate"]),
    Step("1.8 Auto removes an import",
         "import tabulate removed, in Auto mode: no question, one line.",
         ["yaml", "rich", "attrs", "click"],
         present=['ezpkg: removed "tabulate'],
         absent=["Update", "Remove it?", "Make these changes?",
                 "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click"]),
    Step("1.9 Auto adds an import",
         "import tabulate back, in Auto mode: one line, then the cow; "
         "its 0.10.0 is still stored, so no download question.",
         ["yaml", "rich", "attrs", "click", "tabulate"],
         present=['ezpkg: added "tabulate', "EZPkg works!"],
         absent=["Update", "Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click",
                   "tabulate"]),
    Step("1.9b Auto adds a new package",
         "import humanize, never fetched before, in Auto mode: one line, "
         "the download question, the cow.",
         ["yaml", "rich", "attrs", "click", "tabulate", "humanize"],
         present=['ezpkg: added "humanize', DOWNLOAD, "EZPkg works!"],
         absent=["Update", "Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click",
                   "tabulate", "humanize"]),
    Step("1.10 Control-C at the download question",
         "A first run, interrupted at the question: ~/.ezpkg is removed.",
         None, [(DOWNLOAD, CONTROL_C)],
         present=["Interrupted, so `~/.ezpkg` has been removed"],
         absent=["Traceback", "EZPkg works!"], before=first_run_again,
         mode="gone"),
    Step("1.11 After Control-C",
         "The same first run again: as ux01, pip and ezpkg listed too.",
         None, present=["3 package(s)", "(used by `ezpkg`)", "EZPkg works!"],
         absent=["Traceback"], declared=BASE, mode="end-user"),
    Step("1.12 No on a later run",
         "A change needing humanize, answered n at the download question: "
         "only it is removed.",
         ["humanize"], [("Are you working on", "y"), ("Update it?", "y"),
                        (DOWNLOAD, "n")],
         present=["Declined, so the new software package(s) have been"],
         absent=["Traceback", "EZPkg works!"], declared=BASE),
    Step("1.13 No on a first run",
         "A first run answered n: ~/.ezpkg is removed.",
         None, [(DOWNLOAD, "n")],
         present=["Declined, so `~/.ezpkg` has been removed"],
         absent=["Traceback", "EZPkg works!"], before=first_run_again,
         mode="gone"),
    Step("1.14 Explain",
         "A first run answered ?, then y: the packages explained, the "
         "question again.",
         None, [(DOWNLOAD, "?"), (DOWNLOAD, "y")],
         present=["Software packages are code from PyPI", "EZPkg works!"],
         absent=["Traceback"], before=first_run_again, declared=BASE,
         mode="end-user"),
    Step("1.15 A typo",
         "A first run answered x, then y: asked again.",
         None, [(DOWNLOAD, "x"), (DOWNLOAD, "y")],
         present=["EZPkg works!"], absent=["Traceback"],
         before=first_run_again, declared=BASE, mode="end-user"),
    Step("1.16 Bare Enter",
         "A first run answered with Enter alone, then y.",
         None, [(DOWNLOAD, ""), (DOWNLOAD, "y")],
         present=["EZPkg works!"], absent=["Traceback"],
         before=first_run_again, declared=BASE, mode="end-user"),
    Step("1.17 Control-D",
         "A first run answered with Control-D (end of input).",
         None, [(DOWNLOAD, CONTROL_D)],
         absent=["Traceback", "EZPkg works!"], before=first_run_again,
         mode="gone"),
    Step("1.18 Always",
         "A first run answered a: kept, and never asked again.",
         None, [(DOWNLOAD, "a")],
         present=["without asking", "remove.py", "EZPkg works!"],
         absent=["Traceback", "rm -rf"],
         before=first_run_again, declared=BASE, mode="end-user"),
    Step("1.19 Always, a later download",
         "After a, a change needing humanize: no download question.",
         ["humanize"], [("Are you working on", "y"), ("Update it?", "y")],
         present=["EZPkg works!"], absent=[DOWNLOAD, "Traceback"],
         declared=[*BASE, "humanize"]),
    Step("1.20 Silently",
         "A first run answered s: a note, then the cow, and no list.",
         None, [(DOWNLOAD, "s")],
         present=["silently", "remove.py", "EZPkg works!"],
         absent=["Traceback", "now installed"], before=first_run_again,
         declared=BASE, mode="end-user"),
    Step("1.21 Silently, a later download",
         "After s, a change needing humanize: no download question, no "
         "list.",
         ["humanize"], [("Are you working on", "y"), ("Update it?", "y")],
         present=["EZPkg works!"],
         absent=[DOWNLOAD, "now installed", "Traceback"],
         declared=[*BASE, "humanize"]),
    Step("1.22 remove.py",
         "python3 ~/.ezpkg/remove.py: the cache is gone.",
         None, command=["home/.ezpkg/remove.py"], present=["Removed"],
         absent=["Traceback"], mode="gone"),
    Step("1.23 After remove.py",
         "The program again: a first run, asked as in ux01.",
         None, present=["(used by `ezpkg`)", "EZPkg works!"],
         absent=["Traceback"], declared=[*BASE, "humanize"],
         mode="end-user"),
]


def with_imports(text: str, names: list[str]) -> str:
    """Return `prog.py` with exactly these imports below `import cowsay`.

    An import already there keeps its line, comments included (such as
    the `# type: ignore` that `ezpkg` adds), so only the step's own edit
    shows in a diff.
    """
    lines: list[str] = text.splitlines(keepends=True)
    start: int = next(index for index, line in enumerate(lines)
                      if line.startswith("# Part 4"))
    end: int = next(index for index, line in enumerate(lines)
                    if line.startswith("# Part 5"))
    existing: dict[str, str] = {
        line.split()[1]: line for line in lines[start:end]
        if line.startswith("import ")}
    region: list[str] = [line for line in lines[start:end]
                         if not line.startswith("import ")
                         or line.startswith("import cowsay")]
    at: int = next(index for index, line in enumerate(region)
                   if line.startswith("import cowsay")) + 1
    region[at:at] = [existing.get(name, f"import {name}\n")
                     for name in names]
    return "".join(lines[:start] + region + lines[end:])


def run_on_a_terminal(work: Path, script: list[tuple[str, str]],
                      command: list[str] | None = None
                      ) -> tuple[str, list[str], int]:
    """Run `prog.py` on a pseudoterminal, answering its questions.

    Returns:
    * (`tuple[str, list[str], int]`): What the terminal showed, the
      problems with the questions, and the exit status.
    """
    environment: dict[str, str] = {
        key: value for key, value in os.environ.items()
        if not key.startswith(("PIP_", "EZPKG_"))
        and key not in ("PYTHONPATH", "VIRTUAL_ENV", "CI")}
    environment.update(HOME=str(work / "home"),
                       PIP_FIND_LINKS=str(work / "links"))
    python: str = shutil.which("python3") or sys.executable
    pid: int
    master: int
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(work)
        os.execve(python, [python, *(command or ["prog.py"])],
                  environment)

    # Read, and answer each question as it is asked.
    shown: str = ""
    seen: int = 0
    problems: list[str] = []
    waiting: list[tuple[str, str]] = list(script)
    started: float = time.monotonic()
    last: float = started
    while True:
        ready: list[int] = select.select([master], [], [], 1.0)[0]
        now: float = time.monotonic()
        if ready:
            try:
                chunk: bytes = os.read(master, 65536)
            except OSError:
                break
            if not chunk:
                break
            shown += chunk.decode("utf-8", "replace")
            last = now
        elif now - last > IDLE_SECONDS or now - started > STEP_SECONDS:
            problems.append(f"nothing for {IDLE_SECONDS:.0f} s; stopped")
            os.kill(pid, signal.SIGKILL)
            break
        fresh: str = shown[seen:].replace("\r", "")
        if not QUESTION.search(fresh):
            continue
        asked: str = fresh[-400:]
        seen = len(shown)
        reply: str
        if DOWNLOAD in asked and not (waiting
                                      and waiting[0][0] in asked):
            reply = "y"
        elif waiting and waiting[0][0] in asked:
            reply = waiting.pop(0)[1]
        else:
            question: str = asked.strip().splitlines()[-1]
            problems.append(
                f"unexpected question {question!r}"
                + (f", expected one with {waiting[0][0]!r}"
                   if waiting else ""))
            reply = CONTROL_C
        os.write(master, reply.encode() if reply in (CONTROL_C, CONTROL_D)
                 else (reply + "\n").encode())
    os.close(master)
    status: int = os.waitpid(pid, 0)[1]
    problems += [f"never asked the question with {text!r}"
                 for text, _ in waiting]
    return (shown.replace("\r\n", "\n").replace("\r", ""), problems,
            os.waitstatus_to_exitcode(status))


def check(step: Step, shown: str, program: Path) -> list[str]:
    """Return what is wrong with a step's output and `prog.py`."""
    flat: str = " ".join(shown.split())
    problems: list[str] = []
    problems += [f"missing {text!r}" for text in step.present
                 if " ".join(text.split()) not in flat]
    problems += [f"unwanted {text!r}" for text in step.absent
                 if " ".join(text.split()) in flat]
    text: str = program.read_text()
    if step.declared is not None:
        metadata = ezpkg.script_metadata(text) or {}
        names: list[str] = [ezpkg.normal_name(ezpkg.requirement_name(one))
                            for one in metadata.get("dependencies", [])]
        if names != step.declared:
            problems.append(f"dependencies are {names}, expected "
                            f"{step.declared}")
    if step.mode == "gone":
        if (program.parent / "home" / ".ezpkg").exists():
            problems.append("~/.ezpkg is still there")
        return problems
    modes: list[str] = []
    record: Path
    for record in (program.parent / "home" / ".ezpkg" / "develop").glob(
            "*.json"):
        try:
            modes.append(json.loads(record.read_text()).get("mode", ""))
        except (OSError, ValueError):
            modes.append("unreadable")
    if modes != [step.mode]:
        problems.append(f"mode is {modes}, expected [{step.mode!r}]")
    # Kept entries are now the commented ones (S3.2a, S3.4).
    kept: list[str] = list(ezpkg.dependency_comments(text))
    if step.kept is not None and kept != step.kept:
        problems.append(f"kept is {kept}, expected {step.kept}")
    return problems


def key() -> str:
    """Return what a snapshot must match: the files that make a step."""
    digest = hashlib.sha256()
    name: str
    for name in ("ux/drive.py", "ezpkg.py", "quick_start.py",
                 "ezpkg_test.py"):
        digest.update((PROJECT / name).read_bytes())
    return digest.hexdigest()


def snapshot(index: int, work: Path) -> None:
    """Keep the copy as it is after step `index` (from 0)."""
    place: Path = SNAPSHOTS / f"{index + 1:02d}"
    shutil.rmtree(place, ignore_errors=True)
    shutil.copytree(work, place / "work", symlinks=True)
    (place / "path").write_text(str(work), encoding="utf-8")


def restorable(index: int, work: Path) -> bool:
    """Say whether the snapshot after step `index` can be restored.

    A snapshot goes back where it was taken, since the cache records
    absolute paths; that place must be free, or be the copy itself.
    """
    place: Path = SNAPSHOTS / f"{index + 1:02d}"
    if not (place / "path").exists() or not (place / "work").is_dir():
        return False
    path: Path = Path((place / "path").read_text(encoding="utf-8"))
    return path == work or not path.exists()


def restore(index: int, work: Path) -> Path:
    """Replace the copy with the snapshot after step `index`; return it."""
    place: Path = SNAPSHOTS / f"{index + 1:02d}"
    path: Path = Path((place / "path").read_text(encoding="utf-8"))
    shutil.rmtree(work, ignore_errors=True)
    shutil.copytree(place / "work", path, symlinks=True)
    return path


def run_step(step: Step, work: Path
             ) -> tuple[str, list[str], int, str]:
    """Run one step on the copy.

    Returns:
    * (`tuple[str, list[str], int, str]`): What the terminal showed,
      the problems, the exit status and `prog.py` as it ran.
    """
    if step.before is not None:
        step.before(work)
    if step.imports is not None:
        program: Path = work / "prog.py"
        program.write_text(with_imports(program.read_text(),
                                        step.imports))
    ran: str = (work / "prog.py").read_text(encoding="utf-8")
    shown: str
    problems: list[str]
    status: int
    shown, problems, status = run_on_a_terminal(work, step.script,
                                                step.command)
    problems += check(step, shown, work / "prog.py")
    return shown, problems, status, ran


def numbered(name: str) -> str:
    """Return a step's number, such as `1.4b`."""
    return name.split(" ", 1)[0]


USAGE: str = ("usage: ux/drive.py [--keep] [--until STEP | --only STEP...]"
              " [--ux-dir DIR] [OUTPUT]")


def main() -> int:
    """Run the steps, writing the transcript as it goes."""
    arguments: list[str] = sys.argv[1:]
    keep: bool = "--keep" in arguments
    arguments = [one for one in arguments if one != "--keep"]
    until: str = ""
    if "--until" in arguments[:-1]:
        at: int = arguments.index("--until")
        until = arguments[at + 1]
        del arguments[at:at + 2]
    ux: Path = UX
    if "--ux-dir" in arguments[:-1]:
        at = arguments.index("--ux-dir")
        ux = Path(arguments[at + 1])
        del arguments[at:at + 2]
    only: list[str] = []
    if "--only" in arguments:
        at = arguments.index("--only")
        end: int = at + 1
        while (end < len(arguments)
               and re.fullmatch(r"\d+(\.\d+)*[a-z]?", arguments[end])):
            end += 1
        only = arguments[at + 1:end]
        del arguments[at:end]
    known: list[str] = [numbered(step.name) for step in STEPS]
    if ((until and only) or "--only" in arguments
            or any(one not in known for one in only)
            or len(arguments) > 1
            or (arguments and arguments[0].startswith("-"))):
        print(USAGE, file=sys.stderr)
        return 2
    output: Path = Path(arguments[0]) if arguments else UX / "drive_output.txt"
    chosen: list[int] = (
        [known.index(one) for one in only] if only
        else list(range(next((index for index, number in enumerate(known)
                              if number == until), len(STEPS) - 1) + 1)))
    chosen.sort()

    # Snapshots from other code are of no use.
    wanted: str = key()
    if (not (SNAPSHOTS / "key").exists()
            or (SNAPSHOTS / "key").read_text(encoding="utf-8") != wanted):
        shutil.rmtree(SNAPSHOTS, ignore_errors=True)
        SNAPSHOTS.mkdir(parents=True)
        (SNAPSHOTS / "key").write_text(wanted, encoding="utf-8")

    # A fresh copy: the Quick Start, an empty home, and the project's
    # `ezpkg` as the wheel pypi.org will one day serve.
    work: Path = Path(tempfile.mkdtemp(prefix="drive-"))
    shutil.copy2(PROJECT / "quick_start.py", work / "prog.py")
    (work / "home").mkdir()
    built: Path = ezpkg_test.release_wheel(
        work / "build", distribution="ezpkg", version=ezpkg.__version__)
    (work / "links").mkdir()
    shutil.copy2(built, work / "links" / built.name)

    results: list[tuple[str, list[str]]] = []
    done: int = -1  # The last step whose effects the copy holds.
    with open(output, "w", encoding="utf-8") as transcript:
        def write(text: str) -> None:
            transcript.write(text)
            transcript.flush()
        write(f"drive: {time.strftime('%Y-%m-%d %H:%M:%S')}, ezpkg "
              f"{ezpkg.__version__} from {PROJECT}, in {work}\n\n")
        index: int
        for index in chosen:
            # Bring the copy to just after the step before: from the
            # latest usable snapshot, then the rest run quietly.
            latest: int = next((one for one in range(index - 1, done, -1)
                                if restorable(one, work)), done)
            if latest > done:
                work = restore(latest, work)
                done = latest
                write(f"drive: restored the copy after "
                      f"{STEPS[latest].name}, in {work}\n\n")
            for setup in range(done + 1, index):
                print(f"drive: {STEPS[setup].name} (setup) ...",
                      file=sys.stderr, flush=True)
                problems: list[str] = run_step(STEPS[setup], work)[1]
                snapshot(setup, work)
                write(f"{STEPS[setup].name}: setup, "
                      f"{'PASS' if not problems else 'FAIL'}\n")
                for problem in problems:
                    write(f"    {problem}\n")
            step: Step = STEPS[index]
            print(f"drive: {step.name} ...", file=sys.stderr, flush=True)
            shown: str
            status: int
            ran: str
            shown, problems, status, ran = run_step(step, work)
            snapshot(index, work)
            done = index

            # `prog.py` as the step ran it, and as `ezpkg` left it.
            ux.mkdir(parents=True, exist_ok=True)
            before: Path = ux / f"ux{index + 1:02d}_prog.py"
            after: Path = ux / f"ux{index + 1:02d}_prog_after.py"
            before.write_text(ran, encoding="utf-8")
            left: str = (work / "prog.py").read_text(encoding="utf-8")
            if left == ran:
                after.unlink(missing_ok=True)
                files: str = f"`{before.name}`, left unchanged by `ezpkg`."
            else:
                after.write_text(left, encoding="utf-8")
                files = (f"`{before.name}`, changed by `ezpkg` into "
                         f"`{after.name}`.")
            body: str = (step.name + "\n" + step.description + "\n"
                         + "prog.py: " + files + "\n"
                         + "-" * WIDTH + "\n" + shown
                         + ("" if shown.endswith("\n") else "\n"))
            write("^" * WIDTH + "\n" + body + "v" * WIDTH + "\n")
            title: str = re.sub(r"\W+", "_", step.name.split(" ", 1)[1])
            # The copy's name changes every run, so it is left out.
            (ux / f"ux{index + 1:02d}_{title.strip('_')}.txt"
             ).write_text(body.replace(str(work), "/tmp/drive-..."),
                          encoding="utf-8")
            write(f"{step.name}: {'PASS' if not problems else 'FAIL'} "
                  f"(exit {status})\n")
            for problem in problems:
                write(f"    {problem}\n")
            write("\n")
            results.append((step.name, problems))
        failed: list[str] = [name for name, problems in results if problems]
        write(f"drive: {len(results) - len(failed)} of {len(results)} "
              f"passed" + (f"; failed: {', '.join(failed)}" if failed
                           else "") + "\n")
    if keep:
        print(f"drive: the copy is kept in {work}", file=sys.stderr)
    else:
        shutil.rmtree(work, ignore_errors=True)
    print(f"drive: transcript in {output}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
