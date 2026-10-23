import tempfile
import unittest
from pathlib import Path

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_program, run_python, run_source


CONTROL_FLOW_PROGRAM = """fungsi utama(): apapun {
  variabel total: apapun = 0;

  untuk (variabel angka: apapun = 0; angka < 6; angka++) {
    jika (angka adalah 2) maka lewati;
    jika (angka adalah 5) maka berhenti;
    total += angka;
  }

  variabel sisa: apapun = 2;

  selama (sisa > 0 dan total > 0) {
    sisa -= 1;
  }

  cetak(total);
}

fungsi cetak(nilai: apapun): apapun {
  tampilkan(nilai);
}
"""


class LoopTests(unittest.TestCase):
  def assert_rejected(self, source):
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module(source))

  def test_while_zero_one_and_many_iterations(self):
    for count, expected in ((0, "A"), (1, "0A"), (3, "012A")):
      with self.subTest(count=count):
        source = f"""fungsi utama(): apapun {{
  variabel index: apapun = 0;
  selama (index < {count}) {{ tampilkan(index); index++; }}
  tampilkan("A");
}}"""

        assert_program_result(run_source(source), expected)

    assert_program_result(run_source('fungsi utama(): apapun { selama (salah) {} tampilkan("A"); }'), "A")

  def test_while_conditions_accept_general_truthiness(self):
    source = """fungsi probe(value: apapun): apapun {
  selama (value) { tampilkan("T"); value = 0; }
  tampilkan("A");
}
fungsi utama(): apapun { probe(0); probe(1); probe(""); probe("yes"); }
"""

    assert_program_result(run_source(source), "ATAATA")

  def test_while_continue_rechecks_condition_and_break_exits(self):
    source = """fungsi utama(): apapun {
  variabel index: apapun = 0;
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
    source = """fungsi utama(): apapun {
  variabel outer: apapun = 0;
  selama (outer < 2) {
    variabel inner: apapun = 0;
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
    source = """fungsi probe(): apapun {
  selama (benar) { jika (benar) { hasilkan 7; } }
  tampilkan("unreachable");
}
fungsi utama(): apapun { tampilkan(probe()); }
"""

    assert_program_result(run_source(source), "7")

  def test_loop_body_declarations_do_not_initialize_post_loop_reads(self):
    self.assert_rejected("fungsi utama(): apapun { selama (salah) { variabel value: apapun = 1; } tampilkan(value); }")
    self.assert_rejected("fungsi utama(): apapun { variabel value: apapun = 0; selama (salah) { variabel value: apapun = 1; } }")
    self.assert_rejected("fungsi utama(): apapun { selama (benar) { konstanta value: apapun = 1; value++; berhenti; } }")

  def test_constant_declaration_can_execute_on_each_iteration(self):
    source = """fungsi utama(): apapun {
  variabel index: apapun = 0;
  selama (index < 3) { konstanta snapshot: apapun = index; tampilkan(snapshot); index++; }
}
"""

    assert_program_result(run_source(source), "012")

  def test_loop_control_outside_a_loop_is_rejected_even_when_unreachable(self):
    for statement in ("berhenti;", "lewati;"):
      with self.subTest(statement=statement):
        self.assert_rejected(f"fungsi utama(): apapun {{ {statement} }}")
        self.assert_rejected(f"fungsi utama(): apapun {{ hasilkan; {statement} }}")
        self.assert_rejected(f"fungsi helper(): apapun {{ {statement} }} fungsi utama(): apapun {{ selama (salah) {{ helper(); }} }}")

  def test_while_requires_a_condition_and_braced_body(self):
    for body in ("selama () {}", "selama benar {}", "selama (benar) maka berhenti;", "selama (salah) {} selainnya {}"):
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama(): apapun {{ {body} }}")

  def test_for_header_slots_are_optional_but_separators_are_required(self):
    for initializer in ("", "variabel index: apapun = 0"):
      for condition in ("", "benar"):
        for update in ("", "index++"):
          source = f"fungsi utama(): apapun {{ untuk ({initializer}; {condition}; {update}) {{}} }}"
          node = parse_module(source).functions[0].body[0]

          self.assertEqual(node.initializer is None, initializer == "")
          self.assertEqual(node.condition is None, condition == "")
          self.assertEqual(node.update is None, update == "")

    for header in ("variabel index: apapun = 0 index < 2; index++", ";; variabel index: apapun = 1", "variabel index: himpunan<> = 0;;", ";; index++, index++"):
      with self.subTest(header=header):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama(): apapun {{ untuk ({header}) {{}} }}")

  def test_for_execution_order_and_zero_iterations(self):
    for initial, expected in ((0, "ICBUCBUCA"), (2, "ICA")):
      with self.subTest(initial=initial):
        source = f"""fungsi mark(text: apapun): apapun {{ tampilkan(text); }}
fungsi condition(index: apapun): apapun {{ tampilkan("C"); hasilkan index < 2; }}
fungsi update(index: apapun): apapun {{ tampilkan("U"); hasilkan index + 1; }}
fungsi utama(): apapun {{
  variabel index: apapun = {initial};
  untuk (mark("I"); condition(index); index = update(index)) {{ mark("B"); }}
  mark("A");
}}"""

        assert_program_result(run_source(source), expected)

  def test_for_continue_runs_update_once(self):
    source = """fungsi update(index: apapun): apapun { tampilkan(index); hasilkan index + 1; }
fungsi utama(): apapun {
  untuk (variabel index: apapun = 0; index < 4; index = update(index)) { lewati; }
}
"""

    assert_program_result(run_source(source), "0123")

  def test_for_break_and_return_skip_update(self):
    source = """fungsi update(): apapun { tampilkan("unexpected"); }
fungsi probe(): apapun { untuk (;; update()) { hasilkan 7; } }
fungsi utama(): apapun {
  untuk (;; update()) { berhenti; }
  tampilkan(probe());
}
"""

    assert_program_result(run_source(source), "7")

  def test_for_initializer_is_visible_after_zero_iterations(self):
    source = "fungsi utama(): apapun { untuk (variabel index: apapun = 0; salah; index++) {} tampilkan(index); }"

    assert_program_result(run_source(source), "0")
    self.assert_rejected("fungsi utama(): apapun { untuk (index = 0; salah;) {} }")
    self.assert_rejected("fungsi utama(): apapun { untuk (variabel index: apapun = index; salah;) {} }")
    self.assert_rejected("fungsi utama(): apapun { variabel index: apapun = 0; untuk (variabel index: apapun = 0; salah;) {} }")
    self.assert_rejected("fungsi utama(): apapun { untuk (variabel index: apapun = 0; salah;) { variabel index: apapun = 1; } }")
    self.assert_rejected("fungsi utama(): apapun { untuk (;;) { variabel value: apapun = 1; berhenti; } tampilkan(value); }")

  def test_empty_continue_state_is_a_real_update_path(self):
    source = """fungsi utama(): apapun {
  untuk (; salah; value++) {
    jika (benar) { lewati; }
    variabel value: apapun = 0;
  }
}"""

    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module(source))

  def test_dead_declarations_cannot_authorize_a_live_update(self):
    source = """fungsi probe(flag: apapun): apapun {
  untuk (variabel index: apapun = 0; index < 1; index += step) {
    jika (flag) { lewati; } selainnya { hasilkan; }
    variabel step: apapun = 1;
  }
}
fungsi utama(): apapun {}
"""

    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module(source))

  def test_dead_nested_continues_do_not_poison_update_joins(self):
    source = """fungsi probe(flag: apapun): apapun {
  untuk (variabel index: apapun = 0; index < 1; index += step) {
    jika (flag) {
      hasilkan 8;
      jika (benar) { lewati; } selainnya { lewati; }
    }
    variabel step: apapun = 1;
  }
  hasilkan 9;
}
fungsi utama(): apapun { tampilkan(probe(salah), probe(benar)); }
"""

    assert_program_result(run_source(source), "98")

  def test_breaking_paths_do_not_weaken_live_update_initialization(self):
    source = """fungsi probe(flag: apapun): apapun {
  untuk (variabel index: apapun = 0; index < 1; index += step) {
    jika (flag) { berhenti; }
    variabel step: apapun = 1;
  }
  hasilkan 9;
}
fungsi utama(): apapun { tampilkan(probe(benar), probe(salah)); }
"""

    assert_program_result(run_source(source), "99")

  def test_unreachable_update_uses_diagnostic_cursor_and_checks_constants(self):
    source = """fungsi utama(): apapun {
  untuk (variabel index: apapun = 0; index < 1; index += step) {
    berhenti;
    variabel step: apapun = 1;
  }
  tampilkan("A");
}
"""

    assert_program_result(run_source(source), "A")
    self.assert_rejected("fungsi utama(): apapun { untuk (konstanta limit: apapun = 2; benar; limit++) { berhenti; } }")

  def test_inner_loop_exits_do_not_escape_to_outer_update(self):
    source = """fungsi utama(): apapun {
  untuk (variabel index: apapun = 0; index < 1; index += step) {
    selama (salah) { lewati; }
    selama (benar) { berhenti; }
    variabel step: apapun = 1;
  }
  tampilkan(index);
}
"""

    assert_program_result(run_source(source), "1")

  def test_nested_for_continue_targets_its_own_update(self):
    source = """fungsi utama(): apapun {
  untuk (variabel outer: apapun = 0; outer < 2; outer++) {
    untuk (variabel inner: apapun = 0; inner < 3; inner++) {
      jika (inner == 1) { lewati; }
      jika (inner == 2) { berhenti; }
      tampilkan(outer, inner);
    }
  }
}
"""

    assert_program_result(run_source(source), "0010")

  def test_maka_mixed_arms_and_following_statements(self):
    source = """fungsi pilih(value: apapun): apapun {
  jika (value == 0) maka hasilkan "zero";
  selainnya jika (value == 1) { hasilkan "one"; }
  selainnya maka hasilkan "other";
}
fungsi utama(): apapun {
  tampilkan(pilih(0), pilih(1), pilih(2));
  tampilkan("after");
}
"""

    assert_program_result(run_source(source), "zerooneotherafter")

  def test_maka_simple_writes_and_declarations_use_existing_semantics(self):
    source = """fungsi utama(): apapun {
  variabel value: apapun = 0;
  jika (benar) maka value = 2;
  selainnya maka value = 3;
  jika (benar) maka value++;
  jika (benar) maka variabel unused: apapun = 4;
  jika (salah) maka konstanta fixed: apapun = 5;
  tampilkan(value);
}
"""

    assert_program_result(run_source(source), "3")

  def test_maka_loop_control_preserves_continue_and_break_targets(self):
    source = """fungsi update(index: apapun): apapun { tampilkan(index); hasilkan index + 1; }
fungsi utama(): apapun {
  untuk (variabel index: apapun = 0; index < 4; index = update(index)) {
    jika (index < 3) maka lewati;
    selainnya maka berhenti;
  }
  variabel step: apapun = 0;
  selama (step < 4) {
    step++;
    jika (step == 1) maka lewati;
    jika (step == 3) maka berhenti;
    tampilkan(step);
  }
}
"""

    assert_program_result(run_source(source), "0122")

  def test_maka_requires_one_simple_terminated_statement(self):
    bodies = [
      "jika (benar) maka jika (salah) {}", "jika (benar) maka selama (salah) {}",
      "jika (benar) maka untuk (;;) {}", "jika (benar) maka ;",
      "jika (benar) maka tampilkan(1)", "selama (salah) maka tampilkan(1);",
      "untuk (; salah;) maka tampilkan(1);",
    ]

    for body in bodies:
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama(): apapun {{ {body} }}")

    self.assert_rejected("fungsi utama(): apapun { jika (benar) maka berhenti; }")
    self.assert_rejected("fungsi utama(): apapun { jika (benar) maka lewati; }")

  def test_complete_control_flow_program_and_optimization_option(self):
    for options in ((), ("-O",)):
      with self.subTest(options=options):
        assert_program_result(run_source(CONTROL_FLOW_PROGRAM, options), "8")

  def test_control_flow_disassembly_preserves_unicode_source(self):
    with tempfile.TemporaryDirectory(prefix="pyindo m3 ") as temporary_directory:
      source_path = Path(temporary_directory) / "boucle café.pyind"
      source_path.write_text(CONTROL_FLOW_PROGRAM, encoding="utf-8")
      original_bytes = source_path.read_bytes()

      assert_program_result(run_program(source_path, ("-D",)), "8")
      disassembly = source_path.with_suffix(".dis").read_text(encoding="utf-8")

      self.assertEqual(source_path.read_bytes(), original_bytes)
      for expected in ("JUMP_BACKWARD", "POP_JUMP_IF_FALSE", "utama", "cetak", str(source_path)):
        self.assertIn(expected, disassembly)

  def test_new_control_flow_keeps_checked_loads_facade_and_source_positions(self):
    source = 'fungsi utama(): apapun { variabel text: apapun = "é"; untuk (; salah;) {} }'
    condition = parse_module(source).functions[0].body[1].condition
    start_column = len(source[:condition.span.start].encode("utf-8"))
    end_column = len(source[:condition.span.end].encode("utf-8"))
    script = (
      "import dis\n"
      "from pyindo.compiler import compile_bytecodes, compile_source\n"
      "from pyindo.parser import parse_program\n"
      f"source = {CONTROL_FLOW_PROGRAM!r}\n"
      "for sentinel in ('', '\\0'):\n"
      "  instructions, chunks = parse_program(source + sentinel)\n"
      "  assert [chunk.co_name for chunk in chunks] == ['utama', 'cetak']\n"
      "  namespace = {'__name__': 'inspection'}\n"
      "  exec(compile_bytecodes(instructions, filename='café.pyind').to_code(), namespace)\n"
      "  for name in ('utama', 'cetak'):\n"
      "    function = namespace[name]\n"
      "    assert function.__code__.co_filename == 'café.pyind'\n"
      "    for instruction in dis.get_instructions(function):\n"
      "      if instruction.opname.startswith('LOAD_FAST'):\n"
      "        assert instruction.opname == 'LOAD_FAST_CHECK'\n"
      f"exec(compile_source({source!r}), namespace)\n"
      f"assert (1, 1, {start_column}, {end_column}) in namespace['utama'].__code__.co_positions()"
    )

    assert_program_result(run_python(script), "")
