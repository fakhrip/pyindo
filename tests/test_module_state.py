import unittest

from tests.fixture_runner import assert_program_result, run_python, run_source
from tests.test_language import run_compiled


class OwnedModuleStateTests(unittest.TestCase):
  def test_owned_globals_support_reads_and_existing_name_updates(self):
    source = '''variabel total: desimal = 0;
fungsi bump(): desimal { total++; hasilkan total; }
fungsi utama(): kosong { tampilkan(total, "|", bump(), "|", bump(), "|", total); }
'''
    assert_program_result(run_compiled(source, module_name="__main__"), "0|1|2|2")
    updates = '''variabel total: desimal = 2;
fungsi update(): desimal { total = total + 1; total *= 2; total--; hasilkan total; }
fungsi utama(): kosong { tampilkan(update(), "|", total); }'''
    assert_program_result(run_compiled(updates, module_name="__main__"), "5|5")

  def test_initializers_run_once_in_order_before_main_and_forward_calls(self):
    source = '''variabel first: desimal = initialize("A", 1);
fungsi utama(): kosong { tampilkan("M"); }
variabel second: desimal = initialize("B", first + 1);
fungsi initialize(label: campuran, value: desimal): desimal { tampilkan(label); hasilkan value; }
'''
    assert_program_result(run_compiled(source, module_name="__main__"), "ABM")
    script = f'''from pyindo.compiler import compile_source
code = compile_source({source!r})
print("compiled")
namespace = {{'__name__': 'inspection'}}
exec(code, namespace)
assert namespace['first'] == 1 and namespace['second'] == 2
'''
    assert_program_result(run_python(script), "compiled\nAB")

  def test_module_stores_keep_types_and_previous_values_on_failure(self):
    source = '''variabel total: desimal = 3;
variabel values: himpunan<himpunan<desimal>> = [[1]];
fungsi set_total(value: apapun): kosong { total = value; }
fungsi set_values(value: apapun): kosong { values = value; }
fungsi utama(): kosong {}'''
    assertions = '''original = namespace['values']
for setter, bad in [('set_total', True), ('set_values', [[2], ['wrong']])]:
  try:
    namespace[setter](bad)
  except TypeError:
    pass
  else:
    raise AssertionError('bad module store succeeded')
assert namespace['total'] == 3 and namespace['values'] is original
raw = [[7]]
namespace['set_values'](raw)
raw[0][0] = 99
assert namespace['values'][0][0] == 7
prepared = namespace['values']
namespace['set_values'](prepared)
assert namespace['values'] is prepared
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_module_constants_keep_detached_deep_snapshots(self):
    source = '''variabel current: himpunan<himpunan<desimal>> = [[1]];
konstanta saved: apapun = current;
fungsi saved_value(): apapun { hasilkan saved; }
fungsi utama(): kosong { current[0][0] = 2; tampilkan(saved, "|", current); }'''
    assertions = '''saved = namespace['saved_value']()
try:
  saved[0][0] = 9
except TypeError:
  pass
else:
  raise AssertionError('nested snapshot was mutable')
'''
    assert_program_result(run_compiled(source, assertions, module_name="__main__"), "[[1]]|[[2]]")
    for source, error in (
      ("konstanta invalid: apapun = 1 / 0; fungsi utama(): kosong {}", "ZeroDivisionError"),
      ("variabel invalid: desimal = benar; fungsi utama(): kosong {}", "TypeError"),
    ):
      completed = run_source(source)
      self.assertEqual(completed.returncode, 1)
      self.assertIn(error, completed.stderr)

  def test_indirect_early_reads_never_use_builtins_or_stale_namespace_values(self):
    source = '''variabel first: desimal = read_later();
variabel len: desimal = 2;
fungsi read_later(): desimal { hasilkan len; }
fungsi utama(): kosong { tampilkan("main"); }'''
    script = f'''from pyindo.compiler import compile_source
code = compile_source({source!r}, filename='early.pyind')
namespace = {{'__name__': '__main__', 'len': 999}}
for attempt in range(2):
  try:
    exec(code, namespace)
  except NameError as error:
    assert "Module binding 'len' is not initialized" in str(error)
    frames = []
    trace = error.__traceback__
    while trace is not None:
      frames.append((trace.tb_frame.f_code.co_filename, trace.tb_lineno))
      trace = trace.tb_next
    assert ('early.pyind', 3) in frames, frames
  else:
    raise AssertionError('early read succeeded')
'''
    assert_program_result(run_python(script), "")

  def test_early_rebinding_checks_target_before_rhs_but_indexing_keeps_rhs_first(self):
    for statement, expected in (("later = rhs();", ""), ("later[0] = rhs();", "R")):
      source = f'''variabel first: desimal = initialize();
variabel later: apapun = [0];
fungsi initialize(): desimal {{ {statement} hasilkan 1; }}
fungsi rhs(): desimal {{ tampilkan("R"); hasilkan 2; }}
fungsi utama(): kosong {{ tampilkan("M"); }}'''
      script = f'''from pyindo.compiler import compile_source
try:
  exec(compile_source({source!r}), {{'__name__': '__main__'}})
except NameError as error:
  assert "Module binding 'later' is not initialized" in str(error)
else:
  raise AssertionError('early write succeeded')
'''
      with self.subTest(statement=statement):
        assert_program_result(run_python(script), expected)

  def test_repeated_execution_into_one_namespace_resets_owned_state(self):
    source = '''variabel count: desimal = 0;
variabel items: himpunan<desimal> = [1];
fungsi bump(): kosong { count++; items[0] = count; }
fungsi utama(): kosong { bump(); }'''
    script = f'''from pyindo.compiler import compile_source
import marshal
code = marshal.loads(marshal.dumps(compile_source({source!r})))
namespace = {{'__name__': '__main__'}}
exec(code, namespace)
original = namespace['items']
namespace['bump']()
assert namespace['count'] == 2
exec(code, namespace)
assert namespace['count'] == 1 and list(namespace['items']) == [1]
assert namespace['items'] is not original
assert namespace['bump'].__code__.co_varnames == ()
'''
    assert_program_result(run_python(script), "")

  def test_failed_initialization_keeps_prior_effects_and_never_starts_main(self):
    source = '''variabel first: kosong = tampilkan("A");
variabel invalid: desimal = 1 / 0;
variabel last: kosong = tampilkan("B");
fungsi utama(): kosong { tampilkan("M"); }'''
    completed = run_source(source)
    self.assertEqual(completed.returncode, 1)
    self.assertEqual(completed.stdout, "A")
    self.assertIn("ZeroDivisionError", completed.stderr)

