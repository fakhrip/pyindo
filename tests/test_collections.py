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
