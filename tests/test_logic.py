import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_python, run_source


class LogicTests(unittest.TestCase):
  def test_logical_aliases_preserve_operands_and_identity(self):
    source = """fungsi pilih_dan(a, b) { hasilkan a dan b; }
fungsi pilih_atau(a, b) { hasilkan a atau b; }
fungsi simbol_dan(a, b) { hasilkan a && b; }
fungsi simbol_atau(a, b) { hasilkan a || b; }
fungsi utama() { tampilkan(0 dan 7, 1 dan 7, "" atau "cadangan"); }
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "for name in ('pilih_dan', 'simbol_dan'):\n"
      "  left, right = [], object()\n"
      "  assert namespace[name](left, right) is left\n"
      "  assert namespace[name]([1], right) is right\n"
      "for name in ('pilih_atau', 'simbol_atau'):\n"
      "  left, right = [1], object()\n"
      "  assert namespace[name](left, right) is left\n"
      "  assert namespace[name]([], right) is right\n"
    )

    assert_program_result(run_python(script), "")
    assert_program_result(run_source(source), "07cadangan")

  def test_nested_logic_matches_python_truthiness_and_operand_identity(self):
    expressions = [
      ("a dan b dan c", "a and b and c"),
      ("(a dan b) dan c", "(a and b) and c"),
      ("a dan (b dan c)", "a and (b and c)"),
      ("a || b atau c", "a or b or c"),
      ("(a atau b) atau c", "(a or b) or c"),
      ("a atau (b atau c)", "a or (b or c)"),
      ("(a atau b) dan c", "(a or b) and c"),
      ("(a dan b) atau c", "(a and b) or c"),
      ("a dan (b atau c)", "a and (b or c)"),
      ("a atau (b dan c)", "a or (b and c)"),
    ]
    # A repeated truth test flips these host objects, exposing duplicate checks.
    cases = []

    for expression, reference in expressions:
      condition_result = f"True if ({reference}) else False"
      cases.extend([
        (f"hasilkan {expression};", reference),
        (f"hasilkan tidak ({expression});", f"not ({reference})"),
        (f"jika ({expression}) {{ hasilkan benar; }} hasilkan salah;", condition_result),
        (
          f"jika (tidak ({expression})) {{ hasilkan benar; }} hasilkan salah;",
          f"True if not ({reference}) else False",
        ),
        (f"selama ({expression}) {{ hasilkan benar; }} hasilkan salah;", condition_result),
        (f"untuk (; {expression};) {{ hasilkan benar; }} hasilkan salah;", condition_result),
      ])

    source = "\n".join(
      f"fungsi probe_{index}(a, b, c) {{ {body} }}"
      for index, (body, _) in enumerate(cases)
    ) + "\nfungsi utama() {}"
    references = [reference for _, reference in cases]
    script = (
      "from itertools import product\n"
      "from pyindo.compiler import compile_source\n"
      "class TruthProbe:\n"
      "  def __init__(self, initial):\n"
      "    self.initial, self.count = initial, 0\n"
      "  def __bool__(self):\n"
      "    self.count += 1\n"
      "    return self.initial if self.count == 1 else not self.initial\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      f"for index, reference in enumerate({references!r}):\n"
      "  for initial_values in product((False, True), repeat=3):\n"
      "    expected_values = [TruthProbe(value) for value in initial_values]\n"
      "    actual_values = [TruthProbe(value) for value in initial_values]\n"
      "    expected = eval(reference, {}, dict(zip('abc', expected_values)))\n"
      "    actual = namespace[f'probe_{index}'](*actual_values)\n"
      "    if type(expected) is bool:\n"
      "      assert actual is expected, (reference, initial_values)\n"
      "    else:\n"
      "      selected = next(i for i, value in enumerate(expected_values) if value is expected)\n"
      "      assert actual is actual_values[selected], (reference, initial_values)\n"
      "    assert [value.count for value in actual_values] == [\n"
      "      value.count for value in expected_values\n"
      "    ], (reference, initial_values)\n"
    )

    assert_program_result(run_python(script), "")

  def test_rhs_effects_are_short_circuited(self):
    source = """fungsi tandai() { tampilkan("R"); hasilkan 9; }
fungsi utama() {
  tampilkan(0 dan tandai(), "a" atau tandai());
  tampilkan(1 && tandai(), "" || tandai());
}
"""

    assert_program_result(run_source(source), "0aRR99")

  def test_negation_returns_exact_booleans(self):
    source = """fungsi negasi(value) { hasilkan tidak value; }
fungsi simbol(value) { hasilkan !value; }
fungsi kosong() {}
fungsi utama() { tampilkan(tidak kosong(), !!benar, tidak 1 == 2); }
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "for name in ('negasi', 'simbol'):\n"
      "  for value in (0, 1, '', 'yes', None):\n"
      "    result = namespace[name](value)\n"
      "    assert type(result) is bool and result == (not value)\n"
    )

    assert_program_result(run_python(script), "")
    assert_program_result(run_source(source), "TrueTrueTrue")

  def test_precedence_comparisons_and_complete_word_aliases(self):
    source = """fungsi utama() {
  variabel dana = 7;
  variabel ataupun = 8;
  variabel tidak_sama = 9;
  tampilkan(benar atau salah dan salah, 1 < 2 dan 3 < 4, !1 == 2);
  tampilkan(dana, ataupun, tidak_sama, "${0 || 3 && 4}");
}
"""

    assert_program_result(run_source(source), "TrueTrueTrue7894")

    for expression in ("1 < 2 < 3", "1 + tidak benar", "1 == !salah", "1 &&"):
      with self.subTest(expression=expression):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ hasilkan {expression}; }}")

  def test_skipped_rhs_still_receives_static_validation(self):
    sources = [
      "fungsi utama() { tampilkan(salah dan missing()); }",
      "fungsi helper(value) {} fungsi utama() { tampilkan(benar atau helper()); }",
      "fungsi utama() { tampilkan(benar atau value); variabel value = 1; }",
    ]

    for source in sources:
      with self.subTest(source=source):
        completed = run_source(source)

        self.assertEqual(completed.returncode, 70)
        self.assertTrue(completed.stdout.startswith("Error: "))
        self.assertEqual(completed.stderr, "")

  def test_logical_interpolation_keeps_utf8_positions(self):
    source = 'fungsi utama() { tampilkan("café ☕ ${0 atau 7}"); }'
    expression = parse_module(source).functions[0].body[0].call.arguments[0].parts[1]

    self.assertEqual(source[expression.span.start:expression.span.end], "0 atau 7")
    start_column = len(source[:expression.span.start].encode("utf-8"))
    end_column = len(source[:expression.span.end].encode("utf-8"))
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      f"assert (1, 1, {start_column}, {end_column}) in namespace['utama'].__code__.co_positions()"
    )

    assert_program_result(run_python(script), "")
