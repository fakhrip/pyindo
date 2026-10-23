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

  def test_for_header_slots_are_optional_but_separators_are_required(self):
    for initializer in ("", "variabel index = 0"):
      for condition in ("", "benar"):
        for update in ("", "index++"):
          source = f"fungsi utama() {{ untuk ({initializer}; {condition}; {update}) {{}} }}"
          node = parse_module(source).functions[0].body[0]

          self.assertEqual(node.initializer is None, initializer == "")
          self.assertEqual(node.condition is None, condition == "")
          self.assertEqual(node.update is None, update == "")

    for header in ("variabel index = 0 index < 2; index++", ";; variabel index = 1", "variabel index: desimal = 0;;", ";; index++, index++"):
      with self.subTest(header=header):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ untuk ({header}) {{}} }}")

  def test_for_execution_order_and_zero_iterations(self):
    for initial, expected in ((0, "ICBUCBUCA"), (2, "ICA")):
      with self.subTest(initial=initial):
        source = f"""fungsi mark(text) {{ tampilkan(text); }}
fungsi condition(index) {{ tampilkan("C"); hasilkan index < 2; }}
fungsi update(index) {{ tampilkan("U"); hasilkan index + 1; }}
fungsi utama() {{
  variabel index = {initial};
  untuk (mark("I"); condition(index); index = update(index)) {{ mark("B"); }}
  mark("A");
}}"""

        assert_program_result(run_source(source), expected)

  def test_for_continue_runs_update_once(self):
    source = """fungsi update(index) { tampilkan(index); hasilkan index + 1; }
fungsi utama() {
  untuk (variabel index = 0; index < 4; index = update(index)) { lewati; }
}
"""

    assert_program_result(run_source(source), "0123")

  def test_for_break_and_return_skip_update(self):
    source = """fungsi update() { tampilkan("unexpected"); }
fungsi probe() { untuk (;;) { hasilkan 7; } }
fungsi utama() {
  untuk (;; update()) { berhenti; }
  tampilkan(probe());
}
"""

    assert_program_result(run_source(source), "7")

  def test_for_initializer_is_visible_after_zero_iterations(self):
    source = "fungsi utama() { untuk (variabel index = 0; salah; index++) {} tampilkan(index); }"

    assert_program_result(run_source(source), "0")
    self.assert_rejected("fungsi utama() { untuk (index = 0; salah;) {} }")
    self.assert_rejected("fungsi utama() { untuk (variabel index = index; salah;) {} }")
    self.assert_rejected("fungsi utama() { variabel index = 0; untuk (variabel index = 0; salah;) {} }")
    self.assert_rejected("fungsi utama() { untuk (variabel index = 0; salah;) { variabel index = 1; } }")
    self.assert_rejected("fungsi utama() { untuk (;;) { variabel value = 1; berhenti; } tampilkan(value); }")

  def test_empty_continue_state_is_a_real_update_path(self):
    source = """fungsi utama() {
  untuk (; salah; value++) {
    jika (benar) { lewati; }
    variabel value = 0;
  }
}"""

    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module(source))

  def test_dead_declarations_cannot_authorize_a_live_update(self):
    source = """fungsi probe(flag) {
  untuk (variabel index = 0; index < 1; index += step) {
    jika (flag) { lewati; } selainnya { hasilkan; }
    variabel step = 1;
  }
}
fungsi utama() {}
"""

    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module(source))

  def test_dead_nested_continues_do_not_poison_update_joins(self):
    source = """fungsi probe(flag) {
  untuk (variabel index = 0; index < 1; index += step) {
    jika (flag) {
      hasilkan 8;
      jika (benar) { lewati; } selainnya { lewati; }
    }
    variabel step = 1;
  }
  hasilkan 9;
}
fungsi utama() { tampilkan(probe(salah), probe(benar)); }
"""

    assert_program_result(run_source(source), "98")

  def test_breaking_paths_do_not_weaken_live_update_initialization(self):
    source = """fungsi probe(flag) {
  untuk (variabel index = 0; index < 1; index += step) {
    jika (flag) { berhenti; }
    variabel step = 1;
  }
  hasilkan 9;
}
fungsi utama() { tampilkan(probe(benar), probe(salah)); }
"""

    assert_program_result(run_source(source), "99")

  def test_unreachable_update_uses_diagnostic_cursor_and_checks_constants(self):
    source = """fungsi utama() {
  untuk (variabel index = 0; index < 1; index += step) {
    berhenti;
    variabel step = 1;
  }
  tampilkan("A");
}
"""

    assert_program_result(run_source(source), "A")
    self.assert_rejected("fungsi utama() { untuk (konstanta limit = 2; benar; limit++) { berhenti; } }")

  def test_inner_loop_exits_do_not_escape_to_outer_update(self):
    source = """fungsi utama() {
  untuk (variabel index = 0; index < 1; index += step) {
    selama (salah) { lewati; }
    selama (benar) { berhenti; }
    variabel step = 1;
  }
  tampilkan(index);
}
"""

    assert_program_result(run_source(source), "1")

  def test_nested_for_continue_targets_its_own_update(self):
    source = """fungsi utama() {
  untuk (variabel outer = 0; outer < 2; outer++) {
    untuk (variabel inner = 0; inner < 3; inner++) {
      jika (inner == 1) { lewati; }
      jika (inner == 2) { berhenti; }
      tampilkan(outer, inner);
    }
  }
}
"""

    assert_program_result(run_source(source), "0010")
