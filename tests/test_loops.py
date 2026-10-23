import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_source


class LoopTests(unittest.TestCase):
  def assert_rejected(self, source):
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module(source))

  def test_while_zero_one_and_many_iterations(self):
    for count, expected in ((0, "A"), (1, "0A"), (3, "012A")):
      with self.subTest(count=count):
        source = f"""fungsi utama() {{
  variabel index = 0;
  selama (index < {count}) {{ tampilkan(index); index++; }}
  tampilkan("A");
}}"""

        assert_program_result(run_source(source), expected)

    assert_program_result(run_source('fungsi utama() { selama (salah) {} tampilkan("A"); }'), "A")

  def test_while_conditions_accept_general_truthiness(self):
    source = """fungsi probe(value) {
  selama (value) { tampilkan("T"); value = 0; }
  tampilkan("A");
}
fungsi utama() { probe(0); probe(1); probe(""); probe("yes"); }
"""

    assert_program_result(run_source(source), "ATAATA")

  def test_while_continue_rechecks_condition_and_break_exits(self):
    source = """fungsi utama() {
  variabel index = 0;
  selama (index < 4) {
    index++;
    jika (index == 2) { lewati; }
    tampilkan(index);
    jika (index == 3) { berhenti; }
  }
  tampilkan("A");
}
"""

    assert_program_result(run_source(source), "13A")

  def test_nested_while_control_targets_the_nearest_loop(self):
    source = """fungsi utama() {
  variabel outer = 0;
  selama (outer < 2) {
    variabel inner = 0;
    selama (inner < 3) {
      inner++;
      jika (inner == 1) { lewati; }
      jika (inner == 3) { berhenti; }
      tampilkan(outer, inner);
    }
    outer++;
  }
  tampilkan("A");
}
"""

    assert_program_result(run_source(source), "0212A")

  def test_return_exits_the_function_from_inside_a_loop(self):
    source = """fungsi probe() {
  selama (benar) { jika (benar) { hasilkan 7; } }
  tampilkan("unreachable");
}
fungsi utama() { tampilkan(probe()); }
"""

    assert_program_result(run_source(source), "7")

  def test_loop_body_declarations_do_not_initialize_post_loop_reads(self):
    self.assert_rejected("fungsi utama() { selama (salah) { variabel value = 1; } tampilkan(value); }")
    self.assert_rejected("fungsi utama() { variabel value = 0; selama (salah) { variabel value = 1; } }")
    self.assert_rejected("fungsi utama() { selama (benar) { konstanta value = 1; value++; berhenti; } }")

  def test_constant_declaration_can_execute_on_each_iteration(self):
    source = """fungsi utama() {
  variabel index = 0;
  selama (index < 3) { konstanta snapshot = index; tampilkan(snapshot); index++; }
}
"""

    assert_program_result(run_source(source), "012")

  def test_loop_control_outside_a_loop_is_rejected_even_when_unreachable(self):
    for statement in ("berhenti;", "lewati;"):
      with self.subTest(statement=statement):
        self.assert_rejected(f"fungsi utama() {{ {statement} }}")
        self.assert_rejected(f"fungsi utama() {{ hasilkan; {statement} }}")
        self.assert_rejected(f"fungsi helper() {{ {statement} }} fungsi utama() {{ selama (salah) {{ helper(); }} }}")

  def test_while_requires_a_condition_and_braced_body(self):
    for body in ("selama () {}", "selama benar {}", "selama (benar) maka berhenti;", "selama (salah) {} selainnya {}"):
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ {body} }}")
