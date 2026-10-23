import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pyindo import runtime


class RuntimeTests(unittest.TestCase):
  def test_accepts_cpython_315_patch_releases(self):
    for version in ((3, 15, 0), (3, 15, 1), (3, 15, 9)):
      with self.subTest(version=version):
        with patch.object(runtime.sys, "version_info", version):
          runtime.ensure_supported_runtime()

  def test_rejects_other_minor_versions(self):
    for version in ((3, 12, 14), (3, 14, 9), (3, 16, 0)):
      with self.subTest(version=version):
        with patch.object(runtime.sys, "version_info", version):
          with self.assertRaisesRegex(RuntimeError, "CPython 3.15"):
            runtime.ensure_supported_runtime()

  def test_rejects_other_implementations(self):
    with patch.object(runtime.sys, "version_info", (3, 15, 1)):
      with patch.object(runtime.sys, "implementation", SimpleNamespace(name="pypy")):
        with self.assertRaisesRegex(RuntimeError, "pypy"):
          runtime.ensure_supported_runtime()

  def test_cli_checks_version_before_importing_assembler(self):
    compiler_path = Path(__file__).resolve().parents[1] / "main.py"
    script = (
      "import runpy, sys; "
      "sys.version_info = (3, 14, 9); "
      "sys.modules['bytecode'] = None; "
      f"runpy.run_path({str(compiler_path)!r}, run_name='__main__')"
    )

    completed_process = subprocess.run(
      [sys.executable, "-c", script],
      capture_output=True,
      text=True,
      encoding="utf-8",
      timeout=10,
    )

    self.assertEqual(completed_process.returncode, 64)
    self.assertIn("CPython 3.15", completed_process.stderr)
    self.assertNotIn("Traceback", completed_process.stderr)
