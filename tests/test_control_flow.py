import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import (
  REPOSITORY_PATH,
  assert_program_result,
  run_program,
  run_python,
)


class ControlFlowTests(unittest.TestCase):
  def test_repeated_calls_continue_to_the_next_statement(self):
    source_text = """fungsi helper() {
  tampilkan("helper");
}
fungsi utama() {
  helper();
  helper();
  tampilkan("after");
}
"""

    with tempfile.TemporaryDirectory() as temporary_directory:
      source_path = Path(temporary_directory) / "calls.pyind"
      source_path.write_text(source_text, encoding="utf-8")

      assert_program_result(run_program(source_path), "helperhelperafter")

  def test_a_helper_can_call_another_helper_and_continue(self):
    source_text = """fungsi first() {
  tampilkan("one");
}
fungsi second() {
  first();
  tampilkan("two");
}
fungsi utama() {
  second();
  tampilkan("end");
}
"""

    with tempfile.TemporaryDirectory() as temporary_directory:
      source_path = Path(temporary_directory) / "nested_calls.pyind"
      source_path.write_text(source_text, encoding="utf-8")

      assert_program_result(run_program(source_path), "onetwoend")

  def test_helper_has_function_metadata_and_returns_none_repeatedly(self):
    source_text = 'fungsi helper() { tampilkan("h"); } fungsi utama() {}\0'
    script = (
      "from pyindo.parser import parse_program; "
      "from pyindo.compiler import compile_bytecodes; "
      f"instructions, chunks = parse_program({source_text!r}); "
      "namespace = {'__name__': 'inspection'}; "
      "exec(compile_bytecodes(instructions).to_code(), namespace); "
      "helper = namespace['helper']; "
      "assert helper.__name__ == 'helper'; "
      "assert helper() is None; assert helper() is None; "
      "print('done')"
    )

    assert_program_result(run_python(script), "hhdone\n")

  def test_current_if_else_fixtures_and_following_code(self):
    for stem in ("simple_if_else", "complex_if"):
      with self.subTest(fixture=stem):
        source_path = REPOSITORY_PATH / "tests" / "success" / f"{stem}.pyind"
        expected_output = source_path.with_suffix(".output").read_text(encoding="utf-8")

        assert_program_result(run_program(source_path), expected_output)

  def test_conditional_jumps_accept_general_truthy_values(self):
    for value, expected_output in ((0, "false\n"), (1, "true\n"), ("", "false\n"), ("yes", "true\n")):
      with self.subTest(value=value):
        script = (
          "from bytecode import Instr, Label; "
          "from pyindo.compiler import condition, compile_bytecodes; "
          "false_label, end_label = Label(), Label(); "
          f"instructions = condition([Instr('LOAD_CONST', {value!r})], "
          "[Instr('LOAD_CONST', 'true'), Instr('STORE_NAME', 'result')], "
          "[false_label, Instr('LOAD_CONST', 'false'), Instr('STORE_NAME', 'result')], "
          "'jika', end_label, false_label); "
          "instructions.append(end_label); "
          "namespace = {}; exec(compile_bytecodes(instructions).to_code(), namespace); "
          "print(namespace['result'])"
        )

        assert_program_result(run_python(script), expected_output)
