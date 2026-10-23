import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


REPOSITORY_PATH = Path(__file__).resolve().parents[1]
COMPILER_PATH = REPOSITORY_PATH / "main.py"
PROCESS_TIMEOUT_SECONDS = 10


def discover_pairs(fixture_directory: Path) -> list[tuple[Path, Path]]:
  """
  Pair source and expected-output fixtures by their shared filename stem.

  Return pairs in filename order. Raise ValueError for either kind of
  orphan so a missing fixture cannot silently reduce the test coverage.
  """

  source_paths = {path.stem: path for path in fixture_directory.glob("*.pyind")}
  output_paths = {path.stem: path for path in fixture_directory.glob("*.output")}
  orphaned_stems = source_paths.keys() ^ output_paths.keys()

  if orphaned_stems:
    raise ValueError(f"Unpaired fixtures: {', '.join(sorted(orphaned_stems))}")

  return [
    (source_paths[stem], output_paths[stem])
    for stem in sorted(source_paths)
  ]


def run_program(
  source_path: Path, options: Sequence[str] = ()
) -> subprocess.CompletedProcess[str]:
  """
  Run the compiler with this test session's interpreter in a child process.

  Capture UTF-8 output and the exit status without a shell. A hung child
  is terminated by subprocess.run and raises TimeoutExpired after 10 seconds.
  """

  return subprocess.run(
    [sys.executable, str(COMPILER_PATH), str(source_path), *options],
    cwd=REPOSITORY_PATH,
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=PROCESS_TIMEOUT_SECONDS,
  )


def run_python(script: str) -> subprocess.CompletedProcess[str]:
  """
  Execute a backend probe in an isolated interpreter and capture its result.

  A bytecode stack mistake can crash a process, so compiler probes never
  execute newly assembled code inside the unittest runner itself.
  """

  return subprocess.run(
    [sys.executable, "-c", script],
    cwd=REPOSITORY_PATH,
    capture_output=True,
    text=True,
    encoding="utf-8",
    timeout=PROCESS_TIMEOUT_SECONDS,
  )


def run_source(
  source_text: str, options: Sequence[str] = ()
) -> subprocess.CompletedProcess[str]:
  """
  Run an inline UTF-8 program from a system temporary directory.

  Keep generated sources and optional disassembly outside the repository,
  and wait for the child before removing its input directory.
  """

  with tempfile.TemporaryDirectory() as temporary_directory:
    source_path = Path(temporary_directory) / "program.pyind"
    source_path.write_text(source_text, encoding="utf-8")

    return run_program(source_path, options)


def assert_program_result(
  completed_process: subprocess.CompletedProcess[str],
  expected_output: str,
  expected_status: int = 0,
) -> None:
  """
  Check a fixture's output, exit status, and absence of unexpected stderr.

  Raise AssertionError on a mismatch. Whitespace remains significant;
  subprocess text mode and fixture reads normalize only line endings.
  """

  if completed_process.returncode != expected_status:
    raise AssertionError(
      f"Expected exit {expected_status}, got {completed_process.returncode}.\n"
      f"stdout: {completed_process.stdout!r}\nstderr: {completed_process.stderr!r}"
    )

  if completed_process.stdout != expected_output:
    raise AssertionError(
      f"Expected output: {expected_output!r}\n"
      f"Actual output: {completed_process.stdout!r}"
    )

  if completed_process.stderr:
    raise AssertionError(f"Unexpected stderr: {completed_process.stderr!r}")
