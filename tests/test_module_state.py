import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project, write_project


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
fungsi halve(): kosong { total /= 2; }
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
try:
  namespace['halve']()
except TypeError:
  pass
else:
  raise AssertionError('augmented store ignored its declared type')
assert namespace['total'] == 3
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
      ('''konstanta invalid: apapun = cycle();
fungsi cycle(): apapun { variabel value: apapun = [0]; value[0] = value; hasilkan value; }
fungsi utama(): kosong {}''', "Cannot freeze a cyclic collection"),
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


class ImportedModuleStateTests(unittest.TestCase):
  def test_named_and_namespace_value_imports_remain_live(self):
    files = {
      "state.pyind": '''variabel total: desimal = 0;
variabel angka: himpunan<desimal> = [1, 2];
konstanta awal: himpunan<desimal> = angka;
fungsi tambah(jumlah: desimal): kosong { total += jumlah; }''',
      "main.pyind": '''dari "state.pyind" impor total sebagai jumlah_sekarang, tambah;
impor "state.pyind" sebagai state;
fungsi utama(): kosong {
  tampilkan(jumlah_sekarang, "|");
  tambah(2);
  state.angka[0] = 9;
  tampilkan(jumlah_sekarang, "|", state.total, "|", state.awal, "|", state.angka);
}''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "0|2|2|[1, 2]|[9, 2]")
    files["main.pyind"] = '''dari "state.pyind" impor total, tambah;
fungsi utama(): kosong { tampilkan(total, "|", tambah(3), "|", total); }'''
    assert_program_result(run_project(files, module_name="__main__"), "0|None|3")

  def test_state_only_libraries_install_value_and_constant_helpers(self):
    files = {
      "data.pyind": "konstanta saved: himpunan<desimal> = [1]; variabel value: desimal = 2;",
      "main.pyind": '''impor "data.pyind" sebagai data;
variabel first: desimal = data.value;
fungsi utama(): kosong { tampilkan(first, "|", data.saved); }''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "2|[1]")

  def test_imported_bindings_reject_writes_wrong_kinds_collisions_and_reexports(self):
    library = "variabel value: desimal = 1; konstanta saved: apapun = [1]; fungsi helper(): kosong {}"
    for body in (
      "value = 2;", "value += 2;", "value++;", "data.value = 2;", "value();",
      "data.value();", "tampilkan(helper);", "tampilkan(data.helper);", "tampilkan(data.missing);",
      "variabel value: desimal = 2;", "saved[0] = 2;", "hapus data.saved[0];",
    ):
      files = {"data.pyind": library, "main.pyind":
               f'dari "data.pyind" impor value, saved, helper; impor "data.pyind" sebagai data; fungsi utama(): kosong {{ {body} }}'}
      with self.subTest(body=body):
        completed = run_project(files)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PyIndoError", completed.stderr)
    for source in (
      'dari "data.pyind" impor value; variabel value: desimal = 2; fungsi utama(): kosong {}',
      'impor "data.pyind" sebagai value; variabel value: desimal = 2; fungsi utama(): kosong {}',
      'dari "data.pyind" impor value;',
      'dari "middle.pyind" impor value; fungsi utama(): kosong {}',
    ):
      with self.subTest(source=source):
        completed = run_project({"data.pyind": library, "middle.pyind": 'dari "data.pyind" impor value;', "main.pyind": source})
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("PyIndoError", completed.stderr)

  def test_diamond_initialization_order_and_fresh_execution(self):
    files = {
      "common.pyind": '''variabel marker: kosong = tampilkan("C"); variabel count: desimal = 0;
fungsi bump(): kosong { count++; }''',
      "left.pyind": 'impor "common.pyind" sebagai common; variabel marker: kosong = tampilkan("L"); fungsi bump(): kosong { common.bump(); }',
      "right.pyind": 'dari "common.pyind" impor count; variabel marker: kosong = tampilkan("R"); fungsi read(): desimal { hasilkan count; }',
      "main.pyind": '''variabel marker: kosong = tampilkan("I");
impor "left.pyind" sebagai left; impor "right.pyind" sebagai right;
fungsi utama(): kosong { left.bump(); tampilkan(right.read()); }''',
    }
    repeat = "exec(code, namespace)\n"
    assert_program_result(run_project(files, repeat, module_name="__main__"), "CLRI1CLRI1")

  def test_aliases_keep_old_objects_while_imports_see_rebinding(self):
    files = {
      "data.pyind": '''variabel items: himpunan<desimal> = [1];
fungsi replace(): kosong { items = [2]; }''',
      "main.pyind": '''dari "data.pyind" impor items, replace;
impor "data.pyind" sebagai data;
fungsi utama(): kosong {
  variabel old: himpunan<desimal> = items;
  konstanta snapshot: himpunan<desimal> = items;
  replace(); old[0] = 9;
  tampilkan(old, "|", items, "|", data.items, "|", snapshot);
}''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "[9]|[2]|[2]|[1]")

  def test_imported_collection_reads_capture_before_index_and_iteration(self):
    files = {
      "data.pyind": '''variabel items: himpunan<desimal> = [1, 2];
konstanta index: himpunan<desimal> = [0];
fungsi replace_index(): desimal { items = [7, 8]; hasilkan 0; }''',
      "main.pyind": '''dari "data.pyind" impor items;
impor "data.pyind" sebagai data;
fungsi utama(): kosong {
  items[data.replace_index()] = 9;
  tampilkan(items, "|");
  untuk (variabel item: desimal didalam items) { data.replace_index(); tampilkan(item); }
  items[data.index[0]] = 3;
  tampilkan("|", items);
}''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "[7, 8]|78|[3, 8]")

  def test_imported_collections_keep_checked_mutations_and_frozen_aliases(self):
    library = "variabel items: himpunan<desimal> = [1]; konstanta saved: apapun = [[1]];"
    for statement in ('data.items[0] = "bad";', 'items[0] = benar;', 'variabel alias: apapun = data.saved; alias[0][0] = 2;'):
      files = {"data.pyind": library, "main.pyind": f'dari "data.pyind" impor items; impor "data.pyind" sebagai data; fungsi utama(): kosong {{ {statement} }}'}
      with self.subTest(statement=statement):
        completed = run_project(files, module_name="__main__")
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("TypeError", completed.stderr)
    assertions = '''import types
assert isinstance(namespace['replace'], types.FunctionType)
old = namespace['data'].items
assert namespace['replace'].__globals__ is object.__getattribute__(namespace['data'], '__dict__')
try:
  old.extend([2, 'bad'])
except TypeError:
  pass
else:
  raise AssertionError('unchecked batch mutation')
assert list(old) == [1]
'''
    assert_program_result(run_project({"data.pyind": library + " fungsi replace(): kosong {}", "main.pyind":
                         'impor "data.pyind" sebagai data; dari "data.pyind" impor replace; fungsi utama(): kosong {}'}, assertions), "")

  def test_descriptor_named_value_exports_remain_safe_when_warmed(self):
    library = "variabel __dict__: desimal = 41; konstanta __class__: desimal = 42;"
    for source in (
      'dari "data.pyind" impor __dict__ sebagai mapping, __class__ sebagai kind; fungsi utama(): kosong { tampilkan(mapping, "|", kind); }',
      'impor "data.pyind" sebagai data; fungsi utama(): kosong { tampilkan(data.__dict__, "|", data.__class__); }',
    ):
      with self.subTest(source=source):
        assert_program_result(run_project({"data.pyind": library, "main.pyind": source},
                              "for attempt in range(50):\n  exec(code, namespace)\n", module_name="__main__"), "41|42" * 51)

  def test_dependency_failure_prevents_importer_main_and_retains_source(self):
    files = {"café.pyind": '''variabel first: kosong = tampilkan("D");
variabel fail: desimal = 1 / 0;''', "main.pyind": '''impor "café.pyind" sebagai data;
variabel own: kosong = tampilkan("I"); fungsi utama(): kosong { tampilkan("M"); }'''}
    completed = run_project(files, module_name="__main__")
    self.assertEqual(completed.stdout, "D")
    self.assertIn("ZeroDivisionError", completed.stderr)
    self.assertIn('café.pyind", line 2', completed.stderr)
    files["café.pyind"] += "\nvariabel invalid: unknown = 1;"
    completed = run_project(files, module_name="__main__")
    self.assertEqual(completed.stdout, "")
    self.assertIn("PyIndoError", completed.stderr)

  def test_initializer_failure_positions_survive_facades_marshal_and_cli_flags(self):
    script = '''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
for api in ('direct', 'legacy', 'sentinel'):
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    entry = write_project(root, {
      'café.pyind': 'variabel first: kosong = tampilkan("D");\\nvariabel fail: desimal = 1 / 0;',
      'main.pyind': 'impor "café.pyind" sebagai data; variabel own: kosong = tampilkan("I"); fungsi utama(): kosong { tampilkan("M"); }',
    })
    source = entry.read_text(encoding='utf-8')
    dependency_name = str(root / 'café.pyind')
    if api == 'direct':
      code = compile_source(source, filename=str(entry))
    else:
      instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename=str(entry))
      code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
    code = marshal.loads(marshal.dumps(code))
    for path in root.glob('*.pyind'):
      path.unlink()
    try:
      exec(code, {'__name__': '__main__'})
    except ZeroDivisionError as error:
      frames = []
      trace = error.__traceback__
      while trace is not None:
        frames.append((trace.tb_frame.f_code.co_filename, trace.tb_lineno))
        trace = trace.tb_next
      assert (dependency_name, 2) in frames, frames
    else:
      raise AssertionError('initializer did not fail')
'''
    assert_program_result(run_python(script), "DDD")
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "café.pyind": 'variabel first: kosong = tampilkan("D");\nvariabel fail: desimal = 1 / 0;',
        "main.pyind": 'impor "café.pyind" sebagai data; variabel own: kosong = tampilkan("I"); fungsi utama(): kosong { tampilkan("M"); }',
      })
      for options in ((), ("-O",), ("-D",)):
        with self.subTest(options=options):
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 1)
          self.assertEqual(completed.stdout, "D")
          self.assertIn('café.pyind", line 2', completed.stderr)
          self.assertIn("ZeroDivisionError", completed.stderr)

  def test_facades_marshal_and_root_filename_override_keep_live_state(self):
    script = '''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
for api in ('direct', 'legacy', 'sentinel'):
  with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    entry = write_project(root, {
      'state.pyind': 'variabel total: desimal = 2; fungsi bump(): kosong { total++; }',
      'main.pyind': 'impor "state.pyind" sebagai state; dari "state.pyind" impor total; variabel first: desimal = total; fungsi read(): desimal { hasilkan first + state.total; } fungsi utama(): kosong {}',
    })
    source = entry.read_text(encoding='utf-8')
    dependency_name = str(root / 'state.pyind')
    if api == 'direct':
      code = compile_source(source, filename=str(entry))
    else:
      instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename=str(entry))
      assert [chunk.co_name for chunk in chunks] == ['read', 'utama']
      code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
    code = marshal.loads(marshal.dumps(code))
    for path in root.glob('*.pyind'):
      path.unlink()
    namespace = {'__name__': 'inspection'}
    exec(code, namespace)
    assert namespace['read']() == 4
    namespace['state'].bump()
    assert namespace['read']() == 5
    assert namespace['state'].bump.__code__.co_filename == dependency_name
    if api != 'direct':
      assert namespace['read'].__code__.co_filename == 'renamed.pyind'
'''
    assert_program_result(run_python(script), "")

  def test_module_state_cli_preserves_options_argv_status_and_debug_sources(self):
    # Each CLI invocation owns its timeout; an outer child would aggregate five
    # independent Windows startups under one ten-second deadline.
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "state.pyind": "variabel total: desimal = 0; fungsi bump(): kosong { total++; }",
        "main.pyind": '''impor "state.pyind" sebagai state;
variabel initial: desimal = state.total;
fungsi utama(args: himpunan<campuran>, count: desimal): desimal {
  state.bump(); tampilkan(initial, "|", state.total, "|", count, "|", args[1]); hasilkan 7;
}''',
      })
      dependency = entry.parent / "state.pyind"
      original = dependency.read_bytes()
      for options in ((), ("-O",), ("-D",)):
        with self.subTest(options=options):
          assert_program_result(run_program(entry, options, program_arguments=["halo"]), "0|1|2|halo", 7)
          self.assertEqual(dependency.read_bytes(), original)
      listing = entry.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn(str(dependency), listing)
      self.assertIn("bump", listing)
      dependency.write_text(original.decode("utf-8") + " variabel bad: desimal = benar;", encoding="utf-8")
      completed = run_program(entry, program_arguments=["halo"])
      self.assertEqual(completed.returncode, 1)
      self.assertEqual(completed.stdout, "")
      self.assertIn("TypeError", completed.stderr)
      entry.write_text('dari "state.pyind" impor bad; fungsi utama(): kosong { bad = 2; }', encoding="utf-8")
      completed = run_program(entry)
      self.assertEqual(completed.returncode, 70)
      self.assertEqual(completed.stderr, "")
      self.assertIn("imported value", completed.stdout)
