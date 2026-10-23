import unittest

from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
from tests.fixture_runner import assert_program_result, run_python, run_source
from tests.test_language import run_compiled


class TypeEnforcementTests(unittest.TestCase):
  def test_bindings_updates_and_returns_are_guarded(self):
    source = """fungsi initializer(): kosong { variabel value: desimal = "bad"; }
fungsi assignment(): kosong { variabel value: desimal = 7; value = "bad"; }
fungsi augmented(): kosong { variabel value: desimal = 7; value /= 2; }
fungsi postfix(): kosong { variabel value: logika = benar; value++; }
fungsi wrong_return(): desimal { hasilkan "bad"; }
fungsi none_return(): desimal { hasilkan tampilkan(); }
fungsi dynamic(value: apapun): apapun { variabel other: apapun = value; hasilkan other; }
fungsi utama(): kosong {}
"""
    assertions = """for name in ('initializer', 'assignment', 'augmented', 'postfix', 'wrong_return', 'none_return'):
  try:
    namespace[name]()
  except TypeError as error:
    assert name in str(error) and 'line' in str(error), str(error)
    if name in ('assignment', 'augmented'):
      frame = error.__traceback__
      while frame.tb_frame.f_code.co_name != name:
        frame = frame.tb_next
      assert frame.tb_frame.f_locals['value'] == 7
  else:
    raise AssertionError(name)
value = object()
assert namespace['dynamic'](value) is value
"""
    assert_program_result(run_compiled(source, assertions), "")

  def test_exact_scalars_and_nested_error_context(self):
    for spec, good, bad in (("desimal", "1", "benar"), ("angka", "1", "1.5"),
                            ("pecahan", "1.5", "1"), ("campuran", '"x"', "1"),
                            ("logika", "benar", "1")):
      source = f"fungsi value(x: {spec}): {spec} {{ hasilkan x; }} fungsi utama(): kosong {{ tampilkan(value({good})); }}"
      self.assertEqual(run_source(source).returncode, 0)
      result = run_source(source.replace(f"value({good})", f"value({bad})"))
      self.assertEqual(result.returncode, 1)
      self.assertIn("TypeError", result.stderr)
    source = "fungsi utama(): kosong { variabel rows: himpunan<himpunan<desimal>> = [[1], [2, benar]]; }"
    result = run_source(source)
    self.assertEqual(result.returncode, 1)
    self.assertIn("[1][1]", result.stderr)
    self.assertIn("rows", result.stderr)
    self.assertIn("desimal", result.stderr)

  def test_all_arguments_evaluate_before_parameter_guards(self):
    source = """fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi target(a: desimal, b: desimal): kosong { tampilkan("C"); }
fungsi utama(): kosong { target(mark("A", "bad"), mark("B", 2)); }
"""
    result = run_source(source)
    self.assertEqual(result.stdout, "AB")
    self.assertEqual(result.returncode, 1)
    self.assertIn("parameter 'a'", result.stderr)
    assertions = """try:
  namespace['target']('bad', 2)
except TypeError:
  pass
else:
  raise AssertionError('host caller bypassed guard')
"""
    assert_program_result(run_compiled(source, assertions), "")

  def test_indexed_writes_keep_rhs_base_key_order(self):
    source = """fungsi base(values: himpunan<desimal>): himpunan<desimal> { tampilkan("B"); hasilkan values; }
fungsi key(): desimal { tampilkan("I"); hasilkan 0; }
fungsi rhs(): apapun { tampilkan("R"); hasilkan "bad"; }
fungsi utama(): kosong {
  variabel values: himpunan<desimal> = [1];
  base(values)[key()] = rhs();
}
"""
    result = run_source(source)
    self.assertEqual(result.stdout, "RBI")
    self.assertEqual(result.returncode, 1)
    assertions = """from pyindo.type_checks import prepare_typed_value
values = prepare_typed_value([1], ('himpunan', 'desimal'), 'host')
class Index:
  calls = 0
  def __index__(self):
    self.calls += 1
    return 9
index = Index()
try:
  namespace['store'](values, index, 'bad')
except IndexError:
  pass
else:
  raise AssertionError('bounds should precede element validation')
assert index.calls == 1 and values == [1]
"""
    source = "fungsi store(a: apapun, key: apapun, value: apapun): kosong { a[key] = value; } fungsi utama(): kosong {}"
    assert_program_result(run_compiled(source, assertions), "")

  def test_checked_values_cross_functions_and_any_aliases(self):
    source = """fungsi pair(a: himpunan<angka>, b: himpunan<desimal>): apapun { hasilkan [a, b]; }
fungsi nested(a: himpunan<himpunan<desimal>>): himpunan<desimal> { hasilkan a[0]; }
fungsi alias(a: himpunan<desimal>): apapun { variabel other: apapun = a; hasilkan other; }
fungsi conflict(a: himpunan<apapun>): apapun { hasilkan a; }
fungsi utama(): kosong {}
"""
    assertions = """raw = [1]
first, second = namespace['pair'](raw, raw)
assert first is not second and first is not raw
raw[0] = 9
assert first == [1]
a, b = namespace['pair'](first, first)
assert a is b is first
assert namespace['alias'](first) is first
for value in (first, namespace['nested']([[1]])):
  try:
    value[0] = 'bad'
  except TypeError:
    pass
  else:
    raise AssertionError('unguarded alias')
first.clear()
try:
  namespace['conflict'](first)
except TypeError:
  pass
else:
  raise AssertionError('mutable covariance')
"""
    assert_program_result(run_compiled(source, assertions), "")

  def test_constant_contracts(self):
    source = """fungsi snapshot(a: himpunan<himpunan<desimal>>): himpunan<himpunan<desimal>> {
  konstanta saved: himpunan<himpunan<desimal>> = a;
  hasilkan saved;
}
fungsi freeze(a: apapun): apapun { konstanta saved: apapun = a; hasilkan saved; }
fungsi utama(): kosong {}
"""
    assertions = """raw = [[1]]
saved = namespace['snapshot'](raw)
raw[0][0] = 9
assert saved == [[1]]
try:
  saved[0][0] = 2
except TypeError:
  pass
else:
  raise AssertionError('mutable snapshot')
cycle = []
cycle.append(cycle)
for value in (cycle, object()):
  try:
    namespace['freeze'](value)
  except TypeError:
    pass
  else:
    raise AssertionError('Any bypassed freezing')
"""
    assert_program_result(run_compiled(source, assertions), "")

  def test_typed_loops_maka_and_rebinding_keep_contracts(self):
    source = """fungsi utama(): kosong {
  variabel values: himpunan<desimal> = [1];
  variabel alias: apapun = values;
  untuk (variabel i: desimal = 0; i < 2; i++) {
    konstanta saved: himpunan<desimal> = values;
    tampilkan(saved);
    values += [2];
  }
  jika (benar) maka variabel last: desimal = 3;
  tampilkan(alias, values);
}
"""
    assert_program_result(run_source(source), "[1][1, 2][1][1, 2, 2]")

  def test_forward_recursion_and_unexecuted_mismatches(self):
    source = """fungsi first(n: desimal): desimal { jika (n > 0) { hasilkan second(n - 1); } hasilkan 0; }
fungsi second(n: angka): desimal { hasilkan first(n); }
fungsi utama(): kosong {
  jika (salah) maka variabel bad: desimal = "never executed";
  tampilkan(first(4));
}
"""
    assert_program_result(run_source(source), "0")
    with self.assertRaisesRegex(PyIndoError, "Unknown function"):
      compile_source(source.replace('"never executed"', "missing()"))

  def test_typed_program_across_cli_and_facades(self):
    source = """fungsi jumlah(kiri: desimal, kanan: desimal): desimal { hasilkan kiri + kanan; }
fungsi utama(): kosong {
  konstanta batas: angka = 10;
  variabel total: desimal = jumlah(2, 3);
  variabel nilai: himpunan<desimal> = [1, 2, 3];
  untuk (variabel indeks: desimal = 0; indeks < 3; indeks++) {
    nilai[indeks] = total + batas;
  }
  tampilkan(nilai);
}
"""
    for options in ((), ("-O",), ("-D",)):
      assert_program_result(run_source(source, options), "[15, 15, 15]")
    script = """import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
""" + f"source = {source!r}\n" + """codes = [compile_source(source)]
for sentinel in ('', '\\0'):
  instructions, chunks = parse_program(source + sentinel)
  codes.append(compile_bytecodes(instructions).to_code())
for code in codes:
  namespace = {'__name__': 'inspection'}
  exec(marshal.loads(marshal.dumps(code)), namespace)
  assert namespace['jumlah'](2, 3) == 5
"""
    assert_program_result(run_python(script), "")

  def test_annotation_errors_keep_cli_compiler_status(self):
    result = run_source("fungsi utama() {}")
    self.assertEqual(result.returncode, 70)
    self.assertIn("line number 1", result.stdout)
    self.assertNotIn("Traceback", result.stdout + result.stderr)
