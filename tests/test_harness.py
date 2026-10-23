import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import fixture_runner


class FixtureHarnessTests(unittest.TestCase):
  def test_pairs_fixtures_by_stem(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      fixture_directory = Path(temporary_directory)
      for filename in ("b.output", "a.pyind", "a.output", "b.pyind"):
        (fixture_directory / filename).write_text("", encoding="utf-8")

      fixture_pairs = fixture_runner.discover_pairs(fixture_directory)

      self.assertEqual(
        [(source.name, output.name) for source, output in fixture_pairs],
        [("a.pyind", "a.output"), ("b.pyind", "b.output")],
      )

  def test_rejects_orphaned_sources_and_outputs(self):
    for filename in ("orphan.pyind", "orphan.output"):
      with self.subTest(filename=filename):
        with tempfile.TemporaryDirectory() as temporary_directory:
          fixture_directory = Path(temporary_directory)
          (fixture_directory / filename).write_text("", encoding="utf-8")

          with self.assertRaisesRegex(ValueError, "orphan"):
            fixture_runner.discover_pairs(fixture_directory)

  def test_keeps_exit_status_stderr_and_path_arguments(self):
    with tempfile.TemporaryDirectory(prefix="pyindo ruang ") as temporary_directory:
      compiler_path = Path(temporary_directory) / "compiler.py"
      source_path = Path(temporary_directory) / "bahasa Indonesia.pyind"
      compiler_path.write_text(
        "import sys\n"
        "print(sys.argv[1])\n"
        "print('expected', end='')\n"
        "print('failure', file=sys.stderr)\n"
        "sys.exit(1)\n",
        encoding="utf-8",
      )

      with patch.object(fixture_runner, "COMPILER_PATH", compiler_path):
        completed_process = fixture_runner.run_program(source_path)

      self.assertEqual(completed_process.returncode, 1)
      self.assertEqual(completed_process.stdout, f"{source_path}\nexpected")
      self.assertEqual(completed_process.stderr, "failure\n")

      with self.assertRaises(AssertionError):
        fixture_runner.assert_program_result(completed_process, "expected")

  def test_preserves_output_whitespace(self):
    completed_process = subprocess.CompletedProcess([], 0, "  halo\n\n", "")

    fixture_runner.assert_program_result(completed_process, "  halo\n\n")

    with self.assertRaises(AssertionError):
      fixture_runner.assert_program_result(completed_process, "halo\n")

  def test_times_out_hung_children(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      compiler_path = Path(temporary_directory) / "hung.py"
      compiler_path.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")

      with patch.object(fixture_runner, "COMPILER_PATH", compiler_path):
        with patch.object(fixture_runner, "PROCESS_TIMEOUT_SECONDS", 0.1):
          with self.assertRaises(subprocess.TimeoutExpired):
            fixture_runner.run_program(Path("unused.pyind"))

  def test_runner_returns_failure_for_a_failing_suite(self):
    runner_path = Path(__file__).resolve().parents[1] / "test.py"

    with tempfile.TemporaryDirectory() as temporary_directory:
      test_directory = Path(temporary_directory)
      (test_directory / "test_failure.py").write_text(
        "import unittest\n"
        "class FailingTest(unittest.TestCase):\n"
        "  def test_failure(self):\n"
        "    self.fail('intentional fixture mismatch')\n",
        encoding="utf-8",
      )
      script = (
        "import importlib.util, pathlib, sys; "
        f"spec = importlib.util.spec_from_file_location('runner', {str(runner_path)!r}); "
        "runner = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(runner); "
        f"sys.exit(runner.main(pathlib.Path({str(test_directory)!r})))"
      )
      completed_process = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
      )

    self.assertEqual(completed_process.returncode, 1)
    self.assertIn("intentional fixture mismatch", completed_process.stderr)
    self.assertIn("FAILED", completed_process.stderr)
