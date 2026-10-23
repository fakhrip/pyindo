import unittest

from tests.fixture_runner import (
  REPOSITORY_PATH,
  assert_program_result,
  run_program,
  run_python,
)


class BytecodeTests(unittest.TestCase):
  def test_binary_operations_execute_with_python_semantics(self):
    cases = [
      ("+", 2, 3, "5"),
      ("-", 8, 3, "5"),
      ("*", 6, 7, "42"),
      ("/", 7, 2, "3.5"),
      ("%", 7, 2, "1"),
      ("&", 6, 3, "2"),
      ("|", 4, 3, "7"),
      ("<<", 3, 2, "12"),
      (">>", 12, 2, "3"),
      ("**", 2, 5, "32"),
      ("/", -7, 2, "-3.5"),
      ("%", -7, 2, "1"),
      ("+", 0, 0, "0"),
      ("*", 9, 0, "0"),
    ]

    for operation, left_operand, right_operand, expected_value in cases:
      with self.subTest(operation=operation, operands=(left_operand, right_operand)):
        script = (
          "from bytecode import Instr; "
          "from pyindo.compiler import math_operation, compile_bytecodes; "
          f"instructions = math_operation(({left_operand!r}, int), "
          f"({right_operand!r}, int), {operation!r}); "
          "assert any(instruction.name == 'BINARY_OP' for instruction in instructions); "
          "instructions.append(Instr('STORE_NAME', 'result')); "
          "namespace = {}; "
          "exec(compile_bytecodes(instructions).to_code(), namespace); "
          "print(repr(namespace['result']))"
        )

        assert_program_result(run_python(script), expected_value + "\n")

  def test_assembles_a_module_with_source_metadata_and_fallthrough(self):
    script = (
      "from bytecode import Instr; "
      "from pyindo.compiler import compile_bytecodes; "
      "code = compile_bytecodes([Instr('LOAD_CONST', 42), "
      "Instr('STORE_NAME', 'answer')], filename='contoh.pyind').to_code(); "
      "namespace = {}; exec(code, namespace); "
      "print(code.co_filename, code.co_name, namespace['answer'])"
    )

    assert_program_result(run_python(script), "contoh.pyind <module> 42\n")

  def test_print_and_interpolation_preserve_existing_output(self):
    for stem in ("hello_world", "multiple_print", "format_print", "multiline_comment"):
      with self.subTest(fixture=stem):
        source_path = REPOSITORY_PATH / "tests" / "success" / f"{stem}.pyind"
        expected_output = source_path.with_suffix(".output").read_text(encoding="utf-8")

        assert_program_result(run_program(source_path), expected_output)

  def test_print_helper_decodes_escapes_without_adding_a_newline(self):
    script = (
      "from pyindo.compiler import compile_bytecodes, format_print; "
      "from pyindo.types import LiteralString; "
      r"instructions = format_print([(r'baris\nbaru\t!', LiteralString)], 1, True); "
      "exec(compile_bytecodes(instructions).to_code())"
    )

    assert_program_result(run_python(script), "baris\nbaru\t!")
