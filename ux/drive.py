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
# An answer that is never typed, for a question nobody is there to answer.
WAIT: str = "\x00wait"


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
    * `environment` (`dict[str, str]`):
      More environment for the run, such as `EZPKG_ANSWER_SECONDS`.
    * `mode` (`str`):
      `end-user` (no `prog.py.toml`, and `ezpkg` must not edit
      `prog.py`), `developer` (a `prog.py.toml`), or `gone` when
      `~/.ezpkg` must have been removed.
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
    environment: dict[str, str] = dataclasses.field(default_factory=dict)
    mode: str = "end-user"


def first_run_again(work: Path) -> None:
    """Make the next run a first one: the Quick Start, and no cache."""
    shutil.copy2(PROJECT / "quick_start.py", work / "prog.py")
    shutil.rmtree(work / "home" / ".ezpkg", ignore_errors=True)


def developer_first_run(work: Path) -> None:
    """Make the next run a developer's first: an empty `prog.py.toml`."""
    first_run_again(work)
    (work / "prog.py.toml").write_text("", encoding="utf-8")


def second_program(work: Path) -> None:
    """Put a second program beside `prog.py`, using the same packages."""
    shutil.copy2(PROJECT / "quick_start.py", work / "second.py")


def version_two(work: Path) -> None:
    """Replace `prog.py` with the author's version 2, as if emailed.

    It needs one more package, `tabulate`, which its author declared,
    since an end user's program is never edited.
    """
    text: str = (PROJECT / "quick_start.py").read_text(encoding="utf-8")
    text = text.replace('"cowsay"]', '"cowsay", "tabulate"]', 1)
    text = text.replace(
        "import cowsay  # type: ignore[import-not-found]  # For mypy.\n",
        "import cowsay  # type: ignore[import-not-found]  # For mypy.\n"
        "import tabulate  # type: ignore[import-not-found]  # For mypy.\n",
        1)
    text = text.replace('cowsay.cow("EZPkg works!")',
                        'cowsay.cow("Version 2 of prog.py, with tabulate!")',
                        1)
    (work / "prog.py").write_text(text, encoding="utf-8")


BASE: list[str] = ["ezpkg", "cowsay"]
WORKS: str = "EZPkg works!"
# The end user's steps (Wayne's list, 2026-10-19), then the developer's
# (`T.abfd`, S1.4a; 2.1-2.3 first, the rest once Wayne has seen them).
STEPS: list[Step] = [
    Step("1.1 First run",
         "A stranger's first run, answered y: the packages listed, then "
         "the cow.",
         None, [(DOWNLOAD, "y")],
         present=["are retained", "now retained", "manages", WORKS],
         absent=["Traceback", "exclude-newer"], declared=BASE),
    Step("1.2 Later runs",
         "The same program again: nothing asked, nothing said, the cow.",
         None, present=[WORKS], absent=[DOWNLOAD, "now retained",
                                        "Traceback"], declared=BASE),
    Step("1.3 A second program",
         "second.py, whose packages are already stored: still asked "
         "once, y.",
         None, [(DOWNLOAD.replace("prog.py", "second.py"), "y")],
         present=["answer `n` and `second.py` will not run", WORKS],
         absent=["will simply go away", "Traceback"], before=second_program,
         command=["second.py"]),
    Step("1.4 Version 2",
         "The author sends a newer prog.py needing tabulate: fetched "
         "silently, and it runs.",
         None, present=["Version 2 of prog.py, with tabulate!"],
         absent=[DOWNLOAD, "Traceback"], before=version_two,
         declared=[*BASE, "tabulate"]),
    Step("1.5 remove.py",
         "python3 ~/.ezpkg/remove.py: everything is gone.",
         None, command=["home/.ezpkg/remove.py"], present=["Removed"],
         absent=["Traceback"], mode="gone"),
    Step("1.6 Explain",
         "A first run again, answered ?, then y: the packages explained, "
         "then the question again.",
         None, [(DOWNLOAD, "?"), (DOWNLOAD, "y")],
         present=["Software packages are code from PyPI", "Version 2"],
         absent=["Traceback"], declared=[*BASE, "tabulate"]),
    Step("1.7 Bare Enter",
         "A first run answered with Enter twice, then y: just asked again.",
         None, [(DOWNLOAD, ""), (DOWNLOAD, ""), (DOWNLOAD, "y")],
         present=[WORKS], absent=["Please answer", "Traceback"],
         before=first_run_again, declared=BASE),
    Step("1.8 A typo",
         "A first run answered x, then y: asked again.",
         None, [(DOWNLOAD, "x"), (DOWNLOAD, "y")],
         present=["Please answer", WORKS], absent=["Traceback"],
         before=first_run_again, declared=BASE),
    Step("1.9 No",
         "A first run answered n: ~/.ezpkg is removed.",
         None, [(DOWNLOAD, "n")],
         present=["Declined, so `~/.ezpkg` has been removed"],
         absent=["Traceback", WORKS], before=first_run_again,
         mode="gone"),
    Step("1.10 Control-C",
         "A first run, interrupted at the question: ~/.ezpkg is removed.",
         None, [(DOWNLOAD, CONTROL_C)],
         present=["Interrupted, so `~/.ezpkg` has been removed"],
         absent=["Traceback", WORKS], before=first_run_again,
         mode="gone"),
    Step("1.11 Control-D",
         "A first run answered with Control-D (end of input).",
         None, [(DOWNLOAD, CONTROL_D)],
         absent=["Traceback", WORKS], before=first_run_again,
         mode="gone"),
    Step("1.12 No answer",
         "A first run nobody answers (5 minutes, shortened here to 3 "
         "seconds): no.",
         None, [(DOWNLOAD, WAIT)],
         present=["No answer in 3 seconds, so: no."],
         absent=["Traceback", WORKS], before=first_run_again,
         environment={"EZPKG_ANSWER_SECONDS": "3"}, mode="gone"),
    Step("2.1 Becoming the developer",
         "touch prog.py.toml, then a first run: the file is filled in, "
         "nothing is asked, and the cow.",
         None, present=["was empty, so `ezpkg` filled it", WORKS],
         absent=[DOWNLOAD, "Traceback"], before=developer_first_run,
         declared=BASE, mode="developer"),
    Step("2.2 A new import",
         "import tabulate added: an entry with a range, silently, then "
         "the cow.",
         ["tabulate"], present=[WORKS], absent=[DOWNLOAD, "Traceback",
                                            "changed again"],
         declared=[*BASE, "tabulate"], mode="developer"),
    Step("2.3 An import removed",
         "import tabulate taken out again: its entry goes, silently.",
         [], present=[WORKS], absent=[DOWNLOAD, "Traceback",
                                            "changed again"],
         declared=BASE, mode="developer"),
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
                      command: list[str] | None = None,
                      extra: dict[str, str] | None = None
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
                       PIP_FIND_LINKS=str(work / "links"), **(extra or {}))
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
        if "and run `" in asked and not (waiting
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
        if reply == WAIT:
            continue
        os.write(master, reply.encode() if reply in (CONTROL_C, CONTROL_D)
                 else (reply + "\n").encode())
    os.close(master)
    status: int = os.waitpid(pid, 0)[1]
    problems += [f"never asked the question with {text!r}"
                 for text, _ in waiting]
    return (shown.replace("\r\n", "\n").replace("\r", ""), problems,
            os.waitstatus_to_exitcode(status))


def check(step: Step, shown: str, program: Path, ran: str) -> list[str]:
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
    developing: bool = program.with_name("prog.py.toml").exists()
    if developing != (step.mode == "developer"):
        problems.append(f"mode is {'developer' if developing else 'end-user'}"
                        f", expected {step.mode}")
    if step.mode == "end-user" and text != ran:
        problems.append("ezpkg edited an end user's prog.py")
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
                                                step.command,
                                                step.environment)
    problems += check(step, shown, work / "prog.py", ran)
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
