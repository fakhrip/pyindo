import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_python, run_source


class CollectionTests(unittest.TestCase):
  def assert_rejected(self, body):
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module(f"fungsi utama() {{ {body} }}"))

  def test_literal_elements_and_empty_trailing_comma_forms(self):
    source = """fungsi mark(value) { tampilkan(value); hasilkan value; }
fungsi utama() {
  tampilkan([]);
  tampilkan([mark("L"), mark("R")]);
  tampilkan([1,]);
}
"""
    assert_program_result(run_source(source), "[]LR['L', 'R'][1]")

  def test_index_reads_bind_above_signs_and_power(self):
    source = """fungsi buat() { hasilkan [0, [5]]; }
fungsi utama() {
  tampilkan(buat()[1][0], "café"[-1], ([7, 8])[0]);
  tampilkan(-[2][0] ** 2, 2 ** [3][0], [2][0] ** -[3][0]);
}
"""
    assert_program_result(run_source(source), "5é7-480.125")

  def test_nested_literals_are_fresh_on_every_call(self):
    source = "fungsi buat() { hasilkan [0, [1]]; } fungsi utama() {}"
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "first, second = namespace['buat'](), namespace['buat']()\n"
      "assert type(first) is list and type(first[1]) is list\n"
      "assert first is not second and first[1] is not second[1]\n"
      "first[1][0] = 9\n"
      "assert second == [0, [1]]\n"
    )
    assert_program_result(run_python(script), "")

  def test_index_protocol_and_native_errors(self):
    source = "fungsi baca(values, key) { hasilkan values[key]; } fungsi utama() {}"
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "read = namespace['baca']\n"
      "assert read([4, 5], True) == 5 and read([4, 5], -1) == 5\n"
      "assert read('café', -1) == 'é'\n"
      "for values, key, error in (([], 0, IndexError), ([1], 1.5, TypeError), (1, 0, TypeError)):\n"
      "  try:\n"
      "    read(values, key)\n"
      "  except error:\n"
      "    pass\n"
      "  else:\n"
      "    raise AssertionError((values, key, error))\n"
    )
    assert_program_result(run_python(script), "")

  def test_malformed_collection_and_call_suffix_syntax_is_rejected(self):
    bodies = (
      "hasilkan [1,,2];", "hasilkan [,1];", "hasilkan [1;",
      "hasilkan [1][];", "hasilkan [1][0,];", "hasilkan [1][0,1];",
      "hasilkan [1][:];", "[1];", "values[0];",
      "tampilkan(1,);", "(tampilkan)(1);", "tampilkan()(0);",
      "tampilkan()[0](0);", "(tampilkan())[0](0);",
      "(values) = 1;", "(values)++;", "(values) += 1;",
      "values[0] += 1;", "values[0]++;",
    )
    for body in bodies:
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ variabel values = [1]; {body} }}")

  def test_new_reads_keep_static_dead_and_skipped_source_checks(self):
    bodies = (
      "variabel values = [missing];",
      "variabel values = [values];",
      "variabel values = [1]; tampilkan(values[key]);",
      "hasilkan; tampilkan([missing]);",
      "tampilkan(salah dan [missing]);",
      "tampilkan(benar atau missing[0]);",
      "tampilkan(later[0]); variabel later = [1];",
      "untuk (variabel index = 0; index < 1; index += step[0]) { lewati; variabel step = [1]; }",
    )
    for body in bodies:
      with self.subTest(body=body):
        self.assert_rejected(body)

  def test_indexed_store_and_delete_evaluate_each_operand_once(self):
    source = """fungsi base(values) { tampilkan("B"); hasilkan values; }
fungsi key() { tampilkan("I"); hasilkan 0; }
fungsi rhs() { tampilkan("R"); hasilkan 9; }
fungsi utama() {
  variabel values = [0];
  base(values)[key()] = rhs();
  tampilkan(values);
  hapus base(values)[key()];
  tampilkan(values);
}
"""
    assert_program_result(run_source(source), "RBI[9]BI[]")

  def test_nested_target_lookup_follows_rhs_mutation(self):
    source = """fungsi replace(values) { hapus values[0]; hasilkan 9; }
fungsi utama() {
  variabel rows = [[1], [2]];
  rows[0][0] = replace(rows);
  tampilkan(rows);
  variabel alias = rows;
  hapus alias[0][0];
  tampilkan(rows);
  hapus rows[0];
  tampilkan(rows);
}
"""
    assert_program_result(run_source(source), "[[9]][[]][]")

  def test_store_errors_stop_later_target_effects(self):
    source = """fungsi base(values) { tampilkan("B"); hasilkan values[0]; }
fungsi key(value) { tampilkan("I"); hasilkan value; }
fungsi rhs(value) { tampilkan("R"); hasilkan value[0]; }
fungsi store(values, right) { base(values)[key(0)] = rhs(right); }
fungsi nested(values, right) { base(values)[key(1)][key(0)] = rhs(right); }
fungsi utama() {}
"""
    script = (
      "import contextlib, io\n"
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "cases = [('store', [[0]], 0, TypeError, 'R'),\n"
      "         ('store', 0, [9], TypeError, 'RB'),\n"
      "         ('nested', [[[0]]], [9], IndexError, 'RBI')]\n"
      "for name, values, right, error, expected in cases:\n"
      "  output = io.StringIO()\n"
      "  with contextlib.redirect_stdout(output):\n"
      "    try:\n"
      "      namespace[name](values, right)\n"
      "    except error:\n"
      "      pass\n"
      "    else:\n"
      "      raise AssertionError(name)\n"
      "  assert output.getvalue() == expected, output.getvalue()\n"
    )
    assert_program_result(run_python(script), "")

  def test_indexed_statements_work_in_headers_and_maka(self):
    source = """fungsi utama() {
  variabel values = [0, 2, 3];
  untuk (values[0] = 1; values; hapus values[0]) { tampilkan(values[0]); }
  variabel rows = [[4], [5]];
  jika (benar) maka rows[0][0] = 6;
  jika (benar) maka hapus rows[1];
  tampilkan(rows);
  untuk (hapus rows[0]; salah;) {}
  tampilkan(rows);
  variabel count = [0];
  untuk (; count[0] < 2; count[0] = count[0] + 1) { tampilkan(count[0]); }
}
"""
    assert_program_result(run_source(source), "123[[6]][]01")

  def test_element_changes_keep_binding_and_update_initialization_rules(self):
    bodies = (
      "missing[0] = 1;", "hapus missing[0];",
      "values[0] = 1; variabel values = [0];",
      "variabel values = [0]; hasilkan; values[key] = 1;",
      "variabel values = [0]; hasilkan; hapus values[key];",
      "variabel values = [0]; values[0] = missing;",
      "selama (salah) { variabel values = [0]; values[0] = 1; } tampilkan(values);",
    )
    for body in bodies:
      with self.subTest(body=body):
        self.assert_rejected(body)

    source = """fungsi probe(flag) {
  untuk (variabel index = 0; index < 1; index += step[0]) {
    jika (flag) { berhenti; }
    variabel step = [1];
  }
  hasilkan 9;
}
fungsi utama() { tampilkan(probe(benar), probe(salah)); }
"""
    assert_program_result(run_source(source), "99")

  def test_delete_requires_one_indexed_target(self):
    for body in ("hapus values;", "hapus tampilkan();", "hapus;", "hapus values[0], values[1];"):
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ variabel values = [1, 2]; {body} }}")

  def test_native_mutation_errors_remain_runtime_errors(self):
    source = """fungsi store(values, key) { values[key] = 9; }
fungsi remove(values, key) { hapus values[key]; }
fungsi utama() {}
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "for name in ('store', 'remove'):\n"
      "  for values, key, error in (([], 0, IndexError), ('a', 0, TypeError), ([1], 1.5, TypeError)):\n"
      "    try:\n"
      "      namespace[name](values, key)\n"
      "    except error:\n"
      "      pass\n"
      "    else:\n"
      "      raise AssertionError((name, values, key))\n"
    )
    assert_program_result(run_python(script), "")

  def test_membership_evaluates_left_to_right_and_returns_booleans(self):
    source = """fungsi mark(label, value) { tampilkan(label); hasilkan value; }
fungsi contains(item, values) { hasilkan item didalam values; }
fungsi utama() {
  tampilkan(mark("I", 2) didalam mark("C", [1, 2]));
  tampilkan([1] didalam [[1]], "afé" didalam "café", 7 didalam []);
}
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "from pyindo.values import freeze_constant_value\n"
      "class Container:\n"
      "  def __contains__(self, value):\n"
      "    return 7\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "contains = namespace['contains']\n"
      "for item, values in ((1, [1]), ([1], freeze_constant_value([[1]])), ('', ''), (0, Container())):\n"
      "  result = contains(item, values)\n"
      "  assert type(result) is bool and result\n"
    )
    assert_program_result(run_python(script), "")
    assert_program_result(run_source(source), "ICTrueTrueTrueFalse")

  def test_nonempty_returns_exact_bool_for_supported_values(self):
    source = "fungsi nonempty(value) { hasilkan value tidak kosong; } fungsi utama() {}"
    script = (
      "from pyindo.compiler import compile_source\n"
      "from pyindo.values import freeze_constant_value\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "values = [[], [1], freeze_constant_value([]), freeze_constant_value([1]), '', 'é', 0, 2, None]\n"
      "for value in values:\n"
      "  result = namespace['nonempty'](value)\n"
      "  assert type(result) is bool and result == bool(value)\n"
    )
    assert_program_result(run_python(script), "")

  def test_nonempty_tests_host_truth_once_in_value_and_control_contexts(self):
    source = """fungsi value(item) { hasilkan item tidak kosong; }
fungsi negated(item) { hasilkan tidak item tidak kosong; }
fungsi logic(item) { hasilkan item tidak kosong dan 7; }
fungsi condition(item) { jika (item tidak kosong) { hasilkan 1; } hasilkan 0; }
fungsi looping(item) { selama (item tidak kosong) { hasilkan 1; } hasilkan 0; }
fungsi counting(item) { untuk (; item tidak kosong;) { hasilkan 1; } hasilkan 0; }
fungsi utama() {}
"""
    script = (
      "from pyindo.compiler import compile_source\n"
      "class Truth:\n"
      "  def __init__(self, initial):\n"
      "    self.initial, self.count = initial, 0\n"
      "  def __bool__(self):\n"
      "    self.count += 1\n"
      "    return self.initial if self.count == 1 else not self.initial\n"
      "namespace = {'__name__': 'inspection'}\n"
      f"exec(compile_source({source!r}), namespace)\n"
      "for initial in (False, True):\n"
      "  expected = {'value': initial, 'negated': not initial, 'logic': 7 if initial else False,\n"
      "              'condition': int(initial), 'looping': int(initial), 'counting': int(initial)}\n"
      "  for name, result in expected.items():\n"
      "    item = Truth(initial)\n"
      "    actual = namespace[name](item)\n"
      "    assert type(actual) is type(result) and actual == result, name\n"
      "    assert item.count == 1, (name, item.count)\n"
    )
    assert_program_result(run_python(script), "")

  def test_contextual_phrase_preserves_names_and_precedence(self):
    local_source = """fungsi utama() {
  variabel kosong = [1];
  variabel kosongkan = [1];
  tampilkan(kosong tidak kosong, tidak kosong);
  tampilkan(kosongkan tidak /* comment */ kosong);
  tampilkan(0 + 1 tidak kosong, (kosong tidak kosong) + 1);
  tampilkan((1 didalam [1]) tidak kosong, kosong tidak kosong dan [] tidak kosong);
}
"""
    assert_program_result(run_source(local_source), "TrueFalseTrueTrue2TrueFalse")
    assert_program_result(
      run_source("fungsi kosong() {} fungsi utama() { tampilkan(tidak kosong()); }"), "True",
    )

  def test_predicate_suffixes_and_mixed_comparison_chains_are_rejected(self):
    expressions = (
      "items tidak kosong + 1", "items tidak kosong * 2", "items tidak kosong()",
      "items tidak kosong[0]", "items tidak kosongkan", "items tidak",
      "items tidak kosong tidak kosong", "items tidak kosong == benar",
      "1 didalam items tidak kosong", "1 didalam items == benar",
      "1 < 2 didalam items", "1 didalam items didalam items", "1 tidak didalam items",
      "1 < 2 < 3",
    )
    for expression in expressions:
      with self.subTest(expression=expression):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama() {{ hasilkan {expression}; }}")

  def test_predicate_laziness_does_not_hide_static_errors(self):
    source = """fungsi marker() { tampilkan("R"); hasilkan [1]; }
fungsi utama() {
  tampilkan(salah dan 1 didalam marker(), benar atau marker() tidak kosong);
}
"""
    assert_program_result(run_source(source), "FalseTrue")
    for body in (
      "tampilkan(salah dan 1 didalam missing);",
      "tampilkan(benar atau missing tidak kosong);",
      "hasilkan; tampilkan(missing tidak kosong);",
      "tampilkan(values tidak kosong); variabel values = [];",
    ):
      with self.subTest(body=body):
        self.assert_rejected(body)
