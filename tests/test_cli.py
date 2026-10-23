import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import (
  COMPILER_PATH,
  REPOSITORY_PATH,
  assert_program_result,
  run_program,
  run_python,
  run_source,
)


class CliTests(unittest.TestCase):
  def test_no_input_and_unknown_options_report_usage(self):
    source_path = REPOSITORY_PATH / "tests" / "success" / "hello_world.pyind"

    for arguments in ([], ["-unknown"], ["-D"], [str(source_path), "-unknown"]):
      with self.subTest(arguments=arguments):
        completed_process = subprocess.run(
          [sys.executable, str(COMPILER_PATH), *arguments],
          capture_output=True,
          text=True,
          encoding="utf-8",
          timeout=10,
        )

        self.assertEqual(completed_process.returncode, 64)
        self.assertIn("Usage:", completed_process.stdout)
        self.assertEqual(completed_process.stderr, "")

  def test_missing_input_reports_a_portable_exit_status(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      source_path = Path(temporary_directory) / "missing.pyind"
      completed_process = run_program(source_path)

    self.assertEqual(completed_process.returncode, 66)
    self.assertIn("Could not open file:", completed_process.stdout)
    self.assertEqual(completed_process.stderr, "")

  def test_parser_error_keeps_its_diagnostic_without_a_traceback(self):
    source_path = REPOSITORY_PATH / "tests" / "error" / "no_semicolon.pyind"
    expected_output = source_path.with_suffix(".output").read_text(encoding="utf-8")

    assert_program_result(run_program(source_path), expected_output, 70)


  def test_malformed_condition_stays_inside_the_compilation_error_boundary(self):
    with tempfile.TemporaryDirectory() as temporary_directory:
      source_path = Path(temporary_directory) / "empty_condition.pyind"
      source_path.write_text("fungsi utama() { jika () {} }", encoding="utf-8")

      completed_process = run_program(source_path)

    self.assertEqual(completed_process.returncode, 70)
    self.assertEqual(
      completed_process.stdout,
      "Error: Expecting expression but got ')' (on line number 1)",
    )
    self.assertEqual(completed_process.stderr, "")

  def test_main_can_be_called_repeatedly_without_changing_sys_argv(self):
    source_path = REPOSITORY_PATH / "tests" / "success" / "hello_world.pyind"
    script = (
      "import sys; from main import main; "
      "original_arguments = list(sys.argv); "
      f"assert main([{str(source_path)!r}]) == 0; "
      f"assert main([{str(source_path)!r}]) == 0; "
      "assert sys.argv == original_arguments"
    )

    assert_program_result(run_python(script), "halo dunia!halo dunia!")

  def test_utf8_source_and_path_with_spaces(self):
    with tempfile.TemporaryDirectory(prefix="pyindo ruang ") as temporary_directory:
      source_path = Path(temporary_directory) / "bahasa é.pyind"
      source_path.write_text(
        'fungsi utama() { tampilkan("Selamat datang, café ☕"); }\n',
        encoding="utf-8",
      )

      assert_program_result(run_program(source_path), "Selamat datang, café ☕")

  def test_debug_output_never_replaces_source_and_includes_helpers(self):
    source_text = (
      'fungsi helper() { tampilkan("h"); }\n'
      'fungsi utama() { helper(); }\n'
    )

    for filename in ("example.pyind", "example", "example.dis"):
      with self.subTest(filename=filename):
        with tempfile.TemporaryDirectory() as temporary_directory:
          source_path = Path(temporary_directory) / filename
          source_path.write_text(source_text, encoding="utf-8")
          original_bytes = source_path.read_bytes()

          assert_program_result(run_program(source_path, ("-D",)), "h")

          disassembly_path = source_path.with_suffix(".dis")
          if disassembly_path == source_path:
            disassembly_path = source_path.with_name(source_path.name + ".dis")

          disassembly = disassembly_path.read_text(encoding="utf-8")

          self.assertEqual(source_path.read_bytes(), original_bytes)
          self.assertIn("RESUME", disassembly)
          self.assertIn("helper", disassembly)
          self.assertIn("utama", disassembly)
          self.assertIn("Disassembly of", disassembly)
          self.assertIn(str(source_path), disassembly)
          self.assertFalse(source_path.with_suffix(".pyc").exists())

  def test_optimization_option_preserves_program_behavior(self):
    for stem in ("hello_world", "function_call", "simple_if_else"):
      with self.subTest(fixture=stem):
        source_path = REPOSITORY_PATH / "tests" / "success" / f"{stem}.pyind"
        expected_output = source_path.with_suffix(".output").read_text(encoding="utf-8")

        assert_program_result(run_program(source_path, ("-O",)), expected_output)

  def test_module_name_access_does_not_require_optimized_scope_flags(self):
    script = (
      "from bytecode import CompilerFlags, Instr; "
      "from pyindo.compiler import compile_bytecodes; "
      "instructions = [Instr('LOAD_CONST', 42), Instr('STORE_NAME', 'answer'), "
      "Instr('LOAD_NAME', 'answer'), Instr('STORE_NAME', 'copy')]; "
      "compiled = compile_bytecodes(instructions); "
      "assert not compiled.flags & CompilerFlags.OPTIMIZED; "
      "namespace = {}; exec(compiled.to_code(), namespace); "
      "print(namespace['copy'])"
    )

    assert_program_result(run_python(script), "42\n")

  def test_nested_code_objects_keep_the_source_filename(self):
    source_text = 'fungsi helper() {} fungsi utama() {}\0'
    script = (
      "from types import CodeType; "
      "from pyindo.parser import parse_program; "
      "from pyindo.compiler import compile_bytecodes; "
      f"instructions, chunks = parse_program({source_text!r}); "
      "code = compile_bytecodes(instructions, filename='source.pyind').to_code(); "
      "helper_code = next(value for value in code.co_consts if isinstance(value, CodeType)); "
      "print(helper_code.co_filename, helper_code.co_name)"
    )

    assert_program_result(run_python(script), "source.pyind helper\n")

  def test_entrypoint_return_does_not_choose_the_cli_status(self):
    assert_program_result(run_source("fungsi utama() { hasilkan 1337; }"), "")

  def test_source_complexity_limit_has_a_structured_diagnostic(self):
    source = "fungsi utama() { hasilkan 1" + " + 1" * 1200 + "; }"

    assert_program_result(
      run_source(source),
      "Error: Source complexity exceeds compiler limit (on line number 1)",
      70,
    )

  def test_optimization_preserves_the_new_language(self):
    source = """fungsi utama() {
  variabel value = jumlah(2, 3);
  jika (value > 0) { tampilkan("${value}"); }
}
fungsi jumlah(a, b) { hasilkan a + b; }
"""

    assert_program_result(run_source(source, ("-O",)), "5")

  def test_invalid_new_language_syntax_has_a_located_user_error(self):
    for body in (
      "variabel value = value;", "missing();", "hasilkan 1 < 2 < 3;",
      "untuk (variabel i: desimal = 0; i < 2; i++) {}", "tampilkan(\"${}\");",
    ):
      with self.subTest(body=body):
        completed_process = run_source(f"fungsi utama() {{ {body} }}")

        self.assertEqual(completed_process.returncode, 70)
        self.assertTrue(completed_process.stdout.startswith("Error: "))
        self.assertIn("(on line number 1)", completed_process.stdout)
        self.assertEqual(completed_process.stderr, "")
