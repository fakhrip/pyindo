import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_python, run_source


class UpdateTests(unittest.TestCase):
  def test_all_augmented_operators_match_existing_binary_results(self):
    cases = [
      ("+", 5, 0, 5), ("-", 5, 2, 3), ("*", 5, 0, 0), ("/", 7, 2, 3.5),
      ("%", 7, 3, 1), ("**", 2, 3, 8), ("&", 7, 3, 3), ("|", 4, 1, 5),
      ("<<", 3, 2, 12), (">>", 8, 2, 2),
    ]
    source = "\n".join(
      f"fungsi case_{index}(value: apapun): apapun {{ value {operator}= {right}; hasilkan value; }}"
      for index, (operator, _, right, _) in enumerate(cases)
    ) + "\nfungsi utama(): apapun {}"
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
    ) + "\n".join(
      f"assert namespace['case_{index}']({left}) == {expected!r}"
      for index, (_, left, _, expected) in enumerate(cases)
    )

    assert_program_result(run_python(script), "")

  def test_postfix_updates_are_stack_neutral_statements(self):
    source = """fungsi utama(): apapun {
  variabel value: apapun = 0;
  value++;
  value++;
  value--;
  tampilkan("${value}");
  value += 2;
  tampilkan(value);
}
"""

    assert_program_result(run_source(source), "13")

  def test_update_rhs_runs_once(self):
    source = """fungsi right(): apapun { tampilkan("R"); hasilkan 3; }
fungsi utama(): apapun { variabel value: apapun = 2; value += right(); tampilkan(value); }
"""

    assert_program_result(run_source(source), "R5")

  def test_targets_must_be_initialized_mutable_names(self):
    bodies = [
      "missing += 1;", "value++; variabel value: apapun = 1;",
      "konstanta value: apapun = 1; value++;", "konstanta value: apapun = 1; value -= 1;",
      "konstanta value: apapun = 1; hasilkan; value--;",
    ]

    for body in bodies:
      with self.subTest(body=body):
        completed = run_source(f"fungsi utama(): apapun {{ {body} }}")

        self.assertEqual(completed.returncode, 70)
        self.assertTrue(completed.stdout.startswith("Error: "))
        self.assertEqual(completed.stderr, "")

  def test_updates_are_not_expressions_or_compound_targets(self):
    bodies = [
      "++value;", "--value;", "hasilkan value++;", "tampilkan(value++);",
      "jika (value++) {}", "value[0] += 1;", "value.item++;",
      "value++, value++;", "value += ;",
    ]

    for body in bodies:
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama(): apapun {{ variabel value: apapun = 1; {body} }}")
