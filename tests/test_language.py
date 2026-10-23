import unittest
from unittest.mock import patch

from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
from tests.fixture_runner import assert_program_result, run_python


def run_compiled(source_text, assertions="", module_name="inspection"):
  """
  Compile and inspect new bytecode in a disposable child interpreter.
  """

  script = (
    "from pyindo.compiler import compile_source\n"
    f"namespace = {{'__name__': {module_name!r}}}\n"
    f"code = compile_source({source_text!r}, filename='example.pyind')\n"
    "exec(code, namespace)\n"
    f"{assertions}\n"
  )

  return run_python(script)


class LanguageTests(unittest.TestCase):
  def test_excessive_flat_expression_complexity_has_a_located_error(self):
    source = "fungsi utama(): apapun { hasilkan 1" + " + 1" * 1200 + "; }"

    with self.assertRaisesRegex(PyIndoError, "complexity exceeds compiler limit") as raised:
      compile_source(source)

    self.assertIsNotNone(raised.exception.span)

  def test_parameters_locals_constants_and_returns(self):
    source = """fungsi jumlah(a: apapun, b: apapun): apapun {
  konstanta extra: apapun = 10;
  variabel total: apapun = a + b;
  total = total + extra;
  hasilkan total;
  tampilkan("unreachable");
}
fungsi kosong(): apapun { hasilkan; }
fungsi lanjut(): apapun {}
fungsi utama(): apapun {}
"""
    assertions = (
      "assert namespace['jumlah'](2, 3) == 15\n"
      "assert namespace['kosong']() is None\n"
      "assert namespace['lanjut']() is None\n"
      "assert namespace['jumlah'](0, 0) == 10"
    )

    assert_program_result(run_compiled(source, assertions), "")

  def test_local_names_are_isolated_between_functions_and_calls(self):
    source = """fungsi first(value: apapun): apapun { variabel total: apapun = value + 1; hasilkan total; }
fungsi second(value: apapun): apapun { variabel total: apapun = first(value) + first(2); hasilkan total; }
fungsi utama(): apapun { tampilkan(second(10), first(0)); }
"""

    assert_program_result(run_compiled(source, module_name="__main__"), "141")

  def test_arithmetic_precedence_and_comparisons(self):
    cases = [
      ("2 + 3 * 4", 14), ("20 - 5 - 3", 12), ("2 ** 3 ** 2", 512),
      ("-2 ** 2", -4), ("2 ** -2", 0.25), ("+3", 3), ("-7 / 2", -3.5),
      ("-7 % 2", 1), ("0 + 0", 0), ("1.25 * 2", 2.5),
      ("1 + 2 == 3", True), ("1 | 2 & 3 << 1", 3),
      ("8 >> 2", 2), ("1 < 2", True), ("2 <= 2", True), ("2 > 1", True),
      ("2 >= 3", False), ("2 bukan 3", True), ("2 adalah 2", True),
    ]
    source = "\n".join(
      f"fungsi case_{index}(): apapun {{ hasilkan {expression}; }}"
      for index, (expression, _) in enumerate(cases)
    ) + "\nfungsi utama(): apapun {}"
    assertions = "\n".join(
      f"assert namespace['case_{index}']() == {expected!r}"
      for index, (_, expected) in enumerate(cases)
    )

    assert_program_result(run_compiled(source, assertions), "")

  def test_all_definitions_precede_entrypoint_execution(self):
    source = 'fungsi utama(): apapun { tampilkan(helper(2, 3)); } fungsi helper(a: apapun, b: apapun): apapun { hasilkan a + b; }'

    assert_program_result(run_compiled(source), "")
    assert_program_result(run_compiled(source, module_name="__main__"), "5")

  def test_entrypoint_return_is_recorded_without_exiting_library_execution(self):
    source = "fungsi utama(): apapun { hasilkan 1337; tampilkan(1); }"

    assertions = "assert namespace['<pyindo:entrypoint_result>'] == 1337\nassert namespace['utama']() == 1337"
    assert_program_result(run_compiled(source, assertions, module_name="__main__"), "")

  def test_intrinsic_print_has_a_value_and_preserves_concatenation(self):
    source = """fungsi empty(): apapun { hasilkan tampilkan(); }
fungsi utama(): apapun { tampilkan("a", 2, benar); }
"""

    assert_program_result(run_compiled(source, "assert namespace['empty']() is None"), "")
    assert_program_result(run_compiled(source, module_name="__main__"), "a2True")

  def test_backend_names_are_safe_as_locals(self):
    source = 'fungsi utama(): apapun { variabel print: apapun = 1; variabel __name__: apapun = 2; tampilkan("ok"); }'

    assert_program_result(run_compiled(source, module_name="__main__"), "ok")

  def test_functions_have_ordered_slots_flags_and_source_metadata(self):
    source = """fungsi helper(a: apapun, b: apapun): apapun {
  variabel result: apapun = a + b;
  hasilkan result;
  variabel unused: apapun = 0;
}
fungsi utama(): apapun {}
"""
    assertions = """import dis
from bytecode import CompilerFlags
helper = namespace['helper']
assert helper.__name__ == helper.__qualname__ == 'helper'
assert helper.__code__.co_filename == 'example.pyind'
assert helper.__code__.co_firstlineno == 1
assert helper.__code__.co_varnames == ('a', 'b', 'result', 'unused')
assert helper.__code__.co_argcount == 2
assert helper.__code__.co_posonlyargcount == helper.__code__.co_kwonlyargcount == 0
assert helper.__code__.co_flags & 3 == 3
assert not code.co_flags & CompilerFlags.OPTIMIZED
opnames = {instruction.opname for instruction in dis.get_instructions(helper)}
assert 'LOAD_FAST_CHECK' in opnames and 'STORE_FAST' in opnames
assert helper(2, 3) == 5
"""

    assert_program_result(run_compiled(source, assertions), "")

  def test_unsupported_runtime_is_checked_before_parsing(self):
    with patch("pyindo.compiler.ensure_supported_runtime", side_effect=RuntimeError("unsupported")):
      with patch("pyindo.syntax.parse_module") as parse_module:
        with self.assertRaisesRegex(RuntimeError, "unsupported"):
          compile_source("fungsi utama(): apapun {}")

        parse_module.assert_not_called()

  def test_nested_branches_resume_in_the_correct_block(self):
    source = """fungsi pilih(a: apapun, b: apapun): apapun {
  jika (a) {
    jika (b) { tampilkan("tt"); } selainnya { tampilkan("tf"); }
    tampilkan("inside");
  } selainnya jika (b) { tampilkan("ft"); }
  selainnya { tampilkan("ff"); }
  jika (salah) {} selainnya {}
  tampilkan("after");
}
fungsi utama(): apapun { pilih(benar, salah); pilih(salah, benar); pilih(salah, salah); pilih(benar, benar); }
"""

    assert_program_result(
      run_compiled(source, module_name="__main__"),
      "tfinsideafterftafterffafterttinsideafter",
    )

  def test_conditions_accept_general_truthy_values(self):
    source = """fungsi pilih(value: apapun): apapun {
  jika (value) { hasilkan "T"; } selainnya { hasilkan "F"; }
}
fungsi utama(): apapun { tampilkan(pilih(0), pilih(1), pilih(""), pilih("yes")); }
"""

    assert_program_result(run_compiled(source, module_name="__main__"), "FTFT")

  def test_self_and_mutual_recursion_have_independent_frames(self):
    source = """fungsi utama(): apapun { tampilkan(faktorial(5), genap(10), ganjil(10)); }
fungsi faktorial(n: apapun): apapun {
  jika (n <= 1) { hasilkan 1; }
  hasilkan n * faktorial(n - 1);
}
fungsi genap(n: apapun): apapun { jika (n == 0) { hasilkan benar; } hasilkan ganjil(n - 1); }
fungsi ganjil(n: apapun): apapun { jika (n == 0) { hasilkan salah; } hasilkan genap(n - 1); }
"""

    assert_program_result(run_compiled(source, module_name="__main__"), "120TrueFalse")

  def test_nested_call_arguments_evaluate_once_left_to_right(self):
    helpers = """fungsi tandai(teks: apapun): apapun { tampilkan(teks); hasilkan teks; }
fungsi gabung(a: apapun, b: apapun): apapun { hasilkan a + b; }
"""

    for expression in ('gabung(tandai("A"), tandai("B"))', '"${gabung(tandai("A"), tandai("B"))}"'):
      with self.subTest(expression=expression):
        source = helpers + f"fungsi utama(): apapun {{ tampilkan({expression}); }}"
        assert_program_result(run_compiled(source, module_name="__main__"), "ABAB")

  def test_interpolation_preserves_escapes_unicode_and_inner_strings(self):
    source = r'''fungsi identity(value: apapun): apapun { hasilkan value; }
fungsi utama(): apapun {
  variabel value: apapun = 3;
  tampilkan("café ☕ ${value + 1}|\${value}|\\${value}|${identity("}")}|// /* () ,");
}'''

    assert_program_result(run_compiled(source, module_name="__main__"), "café ☕ 4|${value}|\\3|}|// /* () ,")

  def test_interpolation_positions_use_utf8_byte_columns(self):
    source = 'fungsi utama(): apapun { tampilkan("café ☕ ${1 + 2}"); }'
    expression_start = source.index("1 + 2")
    start_column = len(source[:expression_start].encode("utf-8"))
    end_column = start_column + len("1 + 2")
    assertions = (
      f"assert (1, 1, {start_column}, {end_column}) "
      "in list(namespace['utama'].__code__.co_positions())"
    )

    assert_program_result(run_compiled(source, assertions), "")

  def test_returning_branch_allows_initialized_fallthrough_local(self):
    source = """fungsi pilih(flag: apapun): apapun {
  jika (flag) { hasilkan 1; } selainnya { variabel result: apapun = 2; }
  hasilkan result;
}
fungsi utama(): apapun { tampilkan(pilih(benar), pilih(salah)); }
"""

    assert_program_result(run_compiled(source, module_name="__main__"), "12")

  def test_default_return_and_boolean_formatting(self):
    source = 'fungsi empty(): apapun {} fungsi utama(): apapun { tampilkan("${empty()}|${benar}|${salah}"); }'

    assert_program_result(run_compiled(source, module_name="__main__"), "None|True|False")
