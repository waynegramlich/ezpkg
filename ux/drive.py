#!/usr/bin/env python3
"""Drive the UX steps on a real terminal, and write a transcript.

Each step edits `prog.py`'s imports, runs it (the project's `ezpkg.py`
on `PYTHONPATH`, a home of its own, a private `pip.whl` fetched from
pypi.org at the start), on a pseudoterminal, so `ezpkg`'s questions are asked as
they are of a person.  Each question is answered from the step's
script, in order, and checked against the text it expects; a download
question ("... and run prog.py?") is answered `y` wherever it comes,
since whether one comes depends on what this Python already has.
Then the step's checks run on what was printed and on `prog.py`.

Everything happens in a fresh temporary copy, starting from the
project's `quick_start.py`, so nothing of the project's or of `~/.ezpkg`
is touched.

Usage: `ux/drive.py [--keep] [--until STEP] [OUTPUT]`.  OUTPUT defaults
to `ux/drive_output.txt` (ignored by git and hg); it is written as the
steps run, each step framed by `^` and `v` lines.
`--keep` leaves the temporary copy, and says where; `--until 1.4`
stops after the step whose name starts `1.4 `.

Each step's output is also written on its own, without the frame, as
`ux/uxNN_NAME.txt` (`NN` the step's place, from `01`).  Wayne edits
those into the output he wants and commits them, so after a rerun
`git diff ux/` shows where the real output departs from the agreed.
A rerun overwrites them; commit first.
"""

import dataclasses
import os
import pty
import re
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

UX: Path = Path(__file__).resolve().parent
PROJECT: Path = UX.parent
sys.path.insert(0, str(PROJECT))
import ezpkg

WIDTH: int = 79
IDLE_SECONDS: float = 180.0
STEP_SECONDS: float = 900.0
# A question ends the output with its answers in brackets.
QUESTION: re.Pattern[str] = re.compile(r"\[[^\[\]\n]*=>[^\[\]\n]*\] $")
DOWNLOAD: str = "and run prog.py? ["
CONTROL_C: str = "\x03"


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


def forget_answers(work: Path) -> None:
    """Remove the program's development record (undoes `a` and `d`)."""
    for record in (work / "home" / ".ezpkg" / "develop").glob("*.json"):
        record.unlink()


def first_run_again(work: Path) -> None:
    """Make the next run a first one: Quick Start, empty cache but `pip`."""
    shutil.copy2(PROJECT / "quick_start.py", work / "prog.py")
    cache: Path = work / "home" / ".ezpkg"
    for item in cache.iterdir():
        if item.name != "pip.whl":
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()


BASE: list[str] = ["ezpkg", "cowsay"]
STEPS: list[Step] = [
    Step("1.1 Baseline",
         "The Quick Start as it is: a download question, then the cow.",
         [], present=["EZPkg works!"],
         absent=["exclude-newer", "dependencies", "Traceback"],
         declared=BASE),
    Step("1.2 Batch y",
         "Two new imports: one question, y, and no second approval.",
         ["requests", "yaml"], [("Update them?", "y")],
         present=["2 entries in `dependencies`", "and its mypy comment",
                  "EZPkg works!"],
         absent=["Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml"]),
    Step("1.3 Batch i, with keep",
         "Both imports removed: i, then k for requests, y for PyYAML.",
         [], [("Update them?", "i"), ('"requests', "k"),
              ('"PyYAML', "y"), ("Make these changes?", "y")],
         present=['kept "requests" as unimported', 'removed "PyYAML'],
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
         present=['no package "bogus_pkg_xyzzy" is on the index',
                  "2 entries in `dependencies`"],
         declared=[*BASE, "requests", "pyyaml", "rich"]),
    Step("1.6 One change",
         "One new import: the old single question and approval, no batch.",
         ["yaml", "rich", "attrs"],
         [('Add "attrs"?', "y"), ("Make these changes?", "y")],
         present=["disagree"], absent=["Update them?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs"]),
    Step("1.7 Always, with a Really? n",
         "a, then n to Really? goes back; a, y updates without approval.",
         ["yaml", "rich", "attrs", "click", "tabulate"],
         [("Update them?", "a"), ("Really update", "n"),
          ("Update them?", "a"), ("Really update", "y")],
         present=["To be asked again, delete"],
         absent=["Make these changes?", "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click",
                   "tabulate"]),
    Step("1.8 Always applies a single change",
         "One import removed after a: done with no question at all.",
         ["yaml", "rich", "attrs", "click"],
         present=['removed "tabulate'],
         absent=["Update them?", "Remove it?", "Make these changes?",
                 "Traceback"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click"]),
    Step("1.9 Don't ask again",
         "a forgotten; two changes answered d, y: nothing changes.",
         ["yaml", "rich", "attrs", "tabulate"],
         [("Update them?", "d"), ("Really never", "y")],
         present=["Really never ask about prog.py again?",
                  "No module named 'tabulate'"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click"],
         before=forget_answers),
    Step("1.9b Don't ask again, one more change",
         "After d, a change is only named: no question, no edit.",
         ["yaml", "rich", "tabulate"],
         present=["disagree"], absent=["Update them?", "Remove it?"],
         declared=[*BASE, "requests", "pyyaml", "rich", "attrs", "click"]),
    Step("1.10 Control-C at the download question",
         "A first run, interrupted at the question: what does it print?",
         None, [("and run prog.py?", CONTROL_C)],
         absent=["Traceback", "EZPkg works!"], before=first_run_again),
    Step("1.11 After Control-C",
         "The same first run again: asked again, y, and the cow.",
         None, present=["EZPkg works!"], absent=["Traceback"],
         declared=BASE),
]


def with_imports(text: str, names: list[str]) -> str:
    """Return `prog.py` with exactly these imports below `import cowsay`."""
    lines: list[str] = text.splitlines(keepends=True)
    start: int = next(index for index, line in enumerate(lines)
                      if line.startswith("# Part 4"))
    end: int = next(index for index, line in enumerate(lines)
                    if line.startswith("# Part 5"))
    region: list[str] = [line for line in lines[start:end]
                         if not line.startswith("import ")
                         or line.startswith("import cowsay")]
    at: int = next(index for index, line in enumerate(region)
                   if line.startswith("import cowsay")) + 1
    region[at:at] = [f"import {name}\n" for name in names]
    return "".join(lines[:start] + region + lines[end:])


def run_on_a_terminal(work: Path, script: list[tuple[str, str]]
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
    environment.update(HOME=str(work / "home"), PYTHONPATH=str(PROJECT))
    python: str = shutil.which("python3") or sys.executable
    pid: int
    master: int
    pid, master = pty.fork()
    if pid == 0:
        os.chdir(work)
        os.execve(python, [python, "prog.py"], environment)

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
        os.write(master, reply.encode() if reply == CONTROL_C
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
    if step.kept is not None and ezpkg.unimported(text) != step.kept:
        problems.append(f"unimported is {ezpkg.unimported(text)}, "
                        f"expected {step.kept}")
    return problems


def main() -> int:
    """Run every step, writing the transcript as it goes."""
    arguments: list[str] = sys.argv[1:]
    keep: bool = "--keep" in arguments
    arguments = [one for one in arguments if one != "--keep"]
    until: str = ""
    if "--until" in arguments[:-1]:
        at: int = arguments.index("--until")
        until = arguments[at + 1]
        del arguments[at:at + 2]
    if len(arguments) > 1 or (arguments and arguments[0].startswith("-")):
        print("usage: ux/drive.py [--keep] [--until STEP] [OUTPUT]",
              file=sys.stderr)
        return 2
    output: Path = Path(arguments[0]) if arguments else UX / "drive_output.txt"

    # A fresh copy: the Quick Start, a home with only a private `pip`.
    work: Path = Path(tempfile.mkdtemp(prefix="drive-"))
    shutil.copy2(PROJECT / "quick_start.py", work / "prog.py")
    cache: Path = work / "home" / ".ezpkg"
    cache.mkdir(parents=True)
    # The bootstrap never fetches `pip` when `ezpkg` is importable, and
    # this Python's own `pip` may be old, so fetch the newest wheel.
    fetched: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "pip", "download", "--quiet", "--no-deps",
         "--only-binary", ":all:", "--dest", str(work), "pip"],
        capture_output=True, text=True, check=False)
    wheels: list[Path] = sorted(work.glob("pip-*.whl"))
    if fetched.returncode or not wheels:
        print(f"drive: cannot fetch pip.whl:\n{fetched.stderr}",
              file=sys.stderr)
        return 1
    wheels[-1].rename(cache / "pip.whl")

    results: list[tuple[str, list[str]]] = []
    with open(output, "w", encoding="utf-8") as transcript:
        def write(text: str) -> None:
            transcript.write(text)
            transcript.flush()
        write(f"drive: {time.strftime('%Y-%m-%d %H:%M:%S')}, ezpkg "
              f"{ezpkg.__version__} from {PROJECT}, in {work}\n\n")
        step: Step
        for step in STEPS:
            print(f"drive: {step.name} ...", file=sys.stderr, flush=True)
            if step.before is not None:
                step.before(work)
            if step.imports is not None:
                program: Path = work / "prog.py"
                program.write_text(with_imports(program.read_text(),
                                                step.imports))
            shown: str
            problems: list[str]
            status: int
            shown, problems, status = run_on_a_terminal(work, step.script)
            problems += check(step, shown, work / "prog.py")
            body: str = (step.name + "\n" + step.description + "\n"
                         + "-" * WIDTH + "\n" + shown
                         + ("" if shown.endswith("\n") else "\n"))
            write("^" * WIDTH + "\n" + body + "v" * WIDTH + "\n")
            UX.mkdir(exist_ok=True)
            title: str = re.sub(r"\W+", "_", step.name.split(" ", 1)[1])
            (UX / f"ux{len(results) + 1:02d}_{title.strip('_')}.txt"
             ).write_text(body, encoding="utf-8")
            write(f"{step.name}: {'PASS' if not problems else 'FAIL'} "
                  f"(exit {status})\n")
            for problem in problems:
                write(f"    {problem}\n")
            write("\n")
            results.append((step.name, problems))
            if until and step.name.startswith(until + " "):
                break
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
