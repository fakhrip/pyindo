import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project, write_project


ARGUMENT_PROGRAM = '''fungsi tambah(awal: desimal, langkah: desimal = awal): desimal {
  hasilkan awal + langkah;
}

fungsi daftar(isi: himpunan<desimal> = [1]): himpunan<desimal> {
  isi[0] = isi[0] + 1;
  hasilkan isi;
}

fungsi utama(): kosong {
  tampilkan(tambah(3), "|", tambah(langkah=2, awal=5), "|", daftar(), "|", daftar());
}
'''
ARGUMENT_OUTPUT = "6|7|[2]|[2]"


class KeywordExecutionTests(unittest.TestCase):
  def test_keyword_calls_bind_without_reordering_value_effects(self):
    source = '''fungsi mark(label: campuran, value: desimal): desimal { tampilkan(label); hasilkan value; }
fungsi show(a: desimal, b: desimal): kosong { tampilkan(a, b); }
fungsi add(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi factorial(n: desimal): desimal { jika (n < 2) { hasilkan 1; } hasilkan n * factorial(n=n - 1); }
fungsi utama(): kosong {
  show(b=mark("B", 2), a=mark("A", 1));
  tampilkan("|", add(3, b=add(b=2, a=1)), "|", factorial(n=5));
}'''
    assert_program_result(run_source(source), "BA12|6|120")
    assert_program_result(run_compiled(source, "assert namespace['add'](b=2, a=1) == 3"), "")

  def test_keyword_values_finish_before_declaration_order_type_guards(self):
    definition = '''fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi target(a: desimal, b: desimal): kosong { tampilkan("C"); }'''
    completed = run_source(definition + ' fungsi utama(): kosong { target(b=mark("B", 2), a=mark("A", "bad")); }')
    self.assertEqual(completed.returncode, 1)
    self.assertEqual(completed.stdout, "BA")
    self.assertIn("parameter 'a'", completed.stderr)
    for declaration, callee in (('dari "lib.pyind" impor target sebagai renamed;', "renamed"),
                                ('impor "lib.pyind" sebagai state;', "state.target")):
      source = declaration + f' fungsi utama(): kosong {{ {callee}(b=mark("B", 2), a=mark("A", "bad")); }}'
      # Only the owner supplies target; the caller's marks retain caller order.
      files = {"lib.pyind": definition, "main.pyind": definition.split("fungsi target")[0] + source}
      completed = run_project(files, module_name="__main__")
      self.assertEqual(completed.returncode, 1)
      self.assertEqual(completed.stdout, "BA")
      self.assertIn("parameter 'a'", completed.stderr)

  def test_keyword_calls_preserve_native_frames_and_stack_prefixes(self):
    source = '''fungsi pick(a: apapun, b: apapun): apapun { hasilkan a; }
fungsi add(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi probe(values: himpunan<apapun>): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [0, 1, 2]) {
      jika (add(b=0, a=inner) == 0) { lewati; }
      cocokkan (add(b=0, a=inner)) { kasus 1 { hasilkan pick(b=0, a=item); } selainnya { berhenti; } }
    }
  }
  hasilkan;
}
fungsi main_value(): campuran {
  variabel values: himpunan<desimal> = [add(b=2, a=1), 0];
  values[add(b=0, a=1)] = add(b=3, a=1);
  hasilkan "${values}|${0 < add(b=1, a=1) < 3}|${salah atau add(b=1, a=2)}";
}
fungsi utama(): kosong {}'''
    assertions = '''import inspect
marker = object()
assert namespace['probe']([marker]) is marker and namespace['probe']([]) is None
assert namespace['main_value']() == '[3, 4]|True|3'
function = namespace['add']
assert function.__code__.co_argcount == 2
assert function.__code__.co_posonlyargcount == function.__code__.co_kwonlyargcount == 0
assert function.__code__.co_varnames == ('a', 'b')
assert function.__code__.co_flags & (inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS) == 3
assert namespace['probe'].__code__.co_varnames == ('values', 'item', 'inner')
'''
    assert_program_result(run_compiled(source, assertions), "")


class DefaultExecutionTests(unittest.TestCase):
  def test_readme_default_keyword_example_runs_through_all_facades(self):
    script = f'''import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
source = {ARGUMENT_PROGRAM!r}
for api in ('direct', 'legacy', 'sentinel'):
  if api == 'direct':
    code = compile_source(source, filename='arguments.pyind')
  else:
    instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename='arguments.pyind')
    assert [chunk.co_name for chunk in chunks] == ['tambah', 'daftar', 'utama']
    code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
  exec(marshal.loads(marshal.dumps(code)), {{'__name__': '__main__'}})
'''
    assert_program_result(run_python(script), ARGUMENT_OUTPUT * 3)
    self.assertIn(ARGUMENT_PROGRAM.rstrip(), Path("README.md").read_text(encoding="utf-8"))

  def test_dependency_default_argument_and_guard_locations_survive_source_removal(self):
    library = '''fungsi number(
  value: desimal = ("café" jika salah selainnya 1 / 0)
): desimal { hasilkan value; }
fungsi typed(
  value: desimal = "bad"
): desimal { tampilkan("T"); hasilkan value; }
fungsi accepts(value: desimal): desimal { hasilkan value; }'''
    source = '''impor "café.pyind" sebagai lib;
fungsi call(): desimal { /* café ☕ */ hasilkan lib.number(value=1 / 0); }
fungsi invoke(value: apapun): desimal { hasilkan lib.typed(value=value); }
fungsi utama(): kosong {}'''
    early = '''variabel first: desimal = read();
variabel later: desimal = 2;
fungsi read(
  /* café ☕ */ value: desimal = later
): desimal { hasilkan value; }'''
    script = f'''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
library, source, early = {library!r}, {source!r}, {early!r}
def column(text, token):
  """Convert a token's source column to CPython's UTF-8 byte column."""
  return len(text[:text.index(token)].encode('utf-8'))
def locations(error, filename, name):
  """Select the original frame's instruction position after source removal."""
  result = []
  trace = error.__traceback__
  while trace is not None:
    frame_code = trace.tb_frame.f_code
    if frame_code.co_filename == filename and frame_code.co_name == name:
      result.append(list(frame_code.co_positions())[trace.tb_lasti // 2])
    trace = trace.tb_next
  return result
for api in ('direct', 'legacy', 'sentinel'):
  for dependency, root, fails_early in [(library, source, False), (early, 'impor "café.pyind" sebagai lib; fungsi utama(): kosong {{}}', True)]:
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {{'café.pyind': dependency, 'main.pyind': root}})
      dependency_name = str(entry.parent / 'café.pyind')
      root_name = str(entry) if api == 'direct' else 'renamed.pyind'
      if api == 'direct':
        code = compile_source(root, filename=str(entry))
      else:
        instructions, chunks = parse_program(root + ('\\0' if api == 'sentinel' else ''), filename=str(entry))
        code = compile_bytecodes(instructions, filename=root_name).to_code()
      code = marshal.loads(marshal.dumps(code))
      for path in entry.parent.glob('*.pyind'):
        path.unlink()
      namespace = {{'__name__': 'inspection'}}
      if fails_early:
        try:
          exec(code, namespace)
        except NameError as error:
          start = column(early.splitlines()[3], 'later')
          assert 'not initialized' in str(error)
          assert locations(error, dependency_name, 'read') == [(4, 4, start, start + 5)]
        else:
          raise AssertionError('default bypassed module publication guard')
        continue
      exec(code, namespace)
      lib = namespace['lib']
      assert lib.number(value=7) == 7 and lib.typed(value=7) == 7 and lib.accepts(value=1) == 1
      default_start = column(library.splitlines()[1], '1 / 0')
      argument_start = column(source.splitlines()[1], '1 / 0')
      cases = [
        (lib.number, (), ZeroDivisionError, dependency_name, 'number', (2, 2, default_start, default_start + 5)),
        (lib.typed, (), TypeError, dependency_name, 'typed', (5, 5, 2, 7)),
        (namespace['invoke'], (True,), TypeError, dependency_name, 'typed', (5, 5, 2, 7)),
        (namespace['call'], (), ZeroDivisionError, root_name, 'call', (2, 2, argument_start, argument_start + 5)),
      ]
      for function, arguments, exception, filename, name, expected in cases:
        try:
          function(*arguments)
        except exception as error:
          assert locations(error, filename, name) == [expected], (name, locations(error, filename, name), expected)
        else:
          raise AssertionError('default or supplied-argument failure was swallowed')
'''
    assert_program_result(run_python(script), "TTT")

  def test_cli_options_arguments_status_and_default_failures(self):
    options_list = ((), ("-O",), ("-D",))
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "library.pyind": ARGUMENT_PROGRAM,
        "main.pyind": '''impor "library.pyind" sebagai library;
fungsi args_default(): himpunan<campuran> { tampilkan("D"); hasilkan []; }
fungsi count_default(): desimal { tampilkan("E"); hasilkan 0; }
fungsi utama(argv: himpunan<campuran> = args_default(), argc: desimal = count_default()): desimal {
  tampilkan(argc, "|", argv[0], "|", argv[1], "|", library.tambah(langkah=2, awal=5), "|", library.daftar());
  hasilkan 7;
}''',
      })
      library = entry.parent / "library.pyind"
      original_sources = entry.read_bytes(), library.read_bytes()
      for options in options_list:
        with self.subTest(options=options):
          assert_program_result(run_program(entry, options, program_arguments=["halo", "dunia"]), f"3|{entry}|halo|7|[2]", 7)
          self.assertEqual((entry.read_bytes(), library.read_bytes()), original_sources)
      listing = entry.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn(str(library), listing)
      self.assertIn("tambah", listing)
      for default, exception in (("1 / 0", "ZeroDivisionError"), ('"bad"', "TypeError")):
        library.write_text(f"fungsi fail(\n  value: desimal = {default}\n): desimal {{ hasilkan value; }}", encoding="utf-8")
        entry.write_text('impor "library.pyind" sebagai lib; fungsi utama(): kosong { tampilkan("A"); lib.fail(); tampilkan("wrong"); }', encoding="utf-8")
        for options in options_list:
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 1)
          self.assertEqual(completed.stdout, "A")
          self.assertIn('library.pyind", line 2', completed.stderr)
          self.assertIn(exception, completed.stderr)
        entry.write_text('impor "library.pyind" sebagai lib; fungsi utama(): kosong { tampilkan(lib.fail(value=5)); }', encoding="utf-8")
        for options in options_list:
          assert_program_result(run_program(entry, options), "5")
      for invalid in (
        'impor "library.pyind" sebagai lib; fungsi utama(): kosong { lib.fail(wrong=1); }',
        'fungsi bad(a: desimal = 1, b: desimal): kosong {} fungsi utama(): kosong {}',
      ):
        entry.write_text(invalid, encoding="utf-8")
        for options in options_list:
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 70)
          self.assertEqual(completed.stderr, "")
          self.assertTrue(completed.stdout.startswith("Error: "))

  def test_omitted_defaults_run_once_per_call_and_explicit_values_skip_them(self):
    source = '''fungsi mark(): desimal { tampilkan("D"); hasilkan 7; }
fungsi value(item: apapun = mark()): apapun { hasilkan item; }
fungsi skipped(item: desimal = 1 / 0): desimal { hasilkan item; }
fungsi bad_type(item: desimal = "bad"): desimal { hasilkan item; }
fungsi forward_value(item: desimal = forward()): desimal { hasilkan item; }
fungsi forward(): desimal { hasilkan 8; }
fungsi sum(n: desimal, step: desimal = n): desimal {
  jika (n == 0) { hasilkan step; } hasilkan step + sum(n=n - 1);
}
fungsi utama(): kosong {}'''
    assertions = '''class Foreign:
  def __eq__(self, other):
    raise AssertionError('omission used equality')
  def __bool__(self):
    raise AssertionError('omission used truth')
for explicit in (None, False, 0, '', [], Foreign()):
  assert namespace['value'](item=explicit) is explicit
assert namespace['value']() == namespace['value']() == 7
assert namespace['skipped'](item=5) == 5
assert namespace['bad_type'](item=5) == 5
for name, exception in [('skipped', ZeroDivisionError), ('bad_type', TypeError)]:
  try:
    namespace[name]()
  except exception:
    pass
  else:
    raise AssertionError('selected invalid default was accepted')
assert namespace['forward_value']() == 8
assert namespace['sum'](n=3) == 6
assert namespace['sum'](step=10, n=2) == 11
'''
    assert_program_result(run_compiled(source, assertions), "DD")

  def test_supplied_effects_then_default_and_guard_order_is_declaration_order(self):
    source = '''fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi f(a: desimal = mark("D", 1), b: desimal = mark("E", 2)): kosong { tampilkan("C"); }
fungsi bad_b(): kosong { f(b=mark("B", "bad")); }
fungsi bad_a(): kosong { f(a=mark("A", "bad")); }
fungsi utama(): kosong {}'''
    assertions = '''for name, parameter in [('bad_b', 'b'), ('bad_a', 'a')]:
  try:
    namespace[name]()
  except TypeError as error:
    assert "parameter '" + parameter + "'" in str(error)
  else:
    raise AssertionError('parameter contract was skipped')
namespace['f']()
'''
    assert_program_result(run_compiled(source, assertions), "BDADEC")

  def test_fresh_default_literals_and_existing_checked_frozen_alias_rules(self):
    source = '''variabel shared: himpunan<desimal> = [1];
konstanta snapshot: himpunan<desimal> = shared;
fungsi fresh(values: himpunan<himpunan<desimal>> = [[1]]): himpunan<himpunan<desimal>> {
  values[0][0] = values[0][0] + 1; hasilkan values;
}
fungsi alias(first: himpunan<desimal>, second: himpunan<desimal> = first): himpunan<desimal> {
  second[0] = 9; tampilkan(first[0], "|", second[0]); hasilkan second;
}
fungsi existing(value: himpunan<desimal> = shared): himpunan<desimal> { hasilkan value; }
fungsi frozen(value: himpunan<desimal> = snapshot): himpunan<desimal> { hasilkan value; }
fungsi bad(value: himpunan<desimal> = [benar]): kosong { tampilkan("wrong"); }
fungsi utama(): kosong {}'''
    assertions = '''first, second = namespace['fresh'](), namespace['fresh']()
assert first is not second and first[0] is not second[0]
assert first == second == [[2]]
original = [1]
result = namespace['alias'](first=original)
assert result == [9] and original == [1]
assert namespace['existing']() is namespace['shared']
assert namespace['frozen']() is namespace['snapshot']
try:
  namespace['frozen']()[0] = 2
except TypeError:
  pass
else:
  raise AssertionError('default unfroze a snapshot')
try:
  namespace['bad']()
except TypeError:
  pass
else:
  raise AssertionError('default collection bypassed checking')
'''
    assert_program_result(run_compiled(source, assertions), "9|9")

  def test_default_globals_imports_initializers_and_reentrancy_keep_timing(self):
    files = {
      "state.pyind": "variabel base: desimal = 2; fungsi change(): kosong { base = 10; }",
      "library.pyind": '''impor "state.pyind" sebagai state;
variabel local: desimal = 3;
fungsi value(a: desimal = local, b: desimal = state.base): desimal { hasilkan a + b; }
fungsi change(): kosong { local = 7; state.change(); }
fungsi __dict__(__class__: desimal = local): desimal { hasilkan __class__; }''',
      "main.pyind": '''impor "library.pyind" sebagai library;
dari "library.pyind" impor value sebagai renamed, __dict__ sebagai descriptor;
fungsi run(): desimal { hasilkan renamed(b=2); }
fungsi utama(): kosong {}''',
    }
    assertions = '''assert namespace['renamed']() == 5
namespace['library'].change()
assert namespace['renamed']() == 17
assert namespace['library'].value(a=1) == 11 and namespace['run']() == 9
assert namespace['descriptor'](__class__=2) == 2
again = {'__name__': 'inspection'}
exec(code, again)
assert again['renamed']() == 5 and again['descriptor']() == 3
'''
    assert_program_result(run_project(files, assertions), "")
    source = '''variabel count: desimal = 0;
fungsi next(): desimal { count++; hasilkan count; }
fungsi recurse(n: desimal, value: desimal = next()): desimal {
  jika (n == 0) { hasilkan value; } hasilkan value + recurse(n=n - 1);
}
fungsi utama(): kosong {}'''
    assertions = "assert namespace['recurse'](n=2) == 6\nassert namespace['recurse'](n=0) == 4\nassert namespace['count'] == 4"
    assert_program_result(run_compiled(source, assertions), "")
    for initializer, expected_status in (("probe()", 1), ("probe(value=1)", 0)):
      source = f"variabel first: desimal = {initializer}; variabel later: desimal = 2; fungsi probe(value: desimal = later): desimal {{ hasilkan value; }} fungsi utama(): kosong {{}}"
      completed = run_source(source)
      self.assertEqual(completed.returncode, expected_status)
      if expected_status:
        self.assertIn("Module binding 'later' is not initialized", completed.stderr)
    assert_program_result(run_source("variabel base: desimal = 1; variabel first: desimal = probe(); fungsi probe(value: desimal = base): desimal { hasilkan value; } fungsi utama(): kosong { tampilkan(first); }"), "1")

  def test_optional_function_frames_and_wide_signatures_remain_native(self):
    parameters = ", ".join(f"p{index}: desimal = 0" for index in range(260))
    source = f'''fungsi wide({parameters}): desimal {{ hasilkan p0 + p259; }}
fungsi side(): desimal {{ tampilkan("D"); hasilkan 2; }}
fungsi binding(a: desimal, b: desimal = side()): desimal {{ tampilkan("B"); hasilkan a + b; }}
fungsi utama(): kosong {{}}'''
    assertions = '''import inspect
import marshal
from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
for arguments, keywords in [((), {}), ((1,), {'wrong': 2}), ((1,), {'a': 2}), ((1, 2, 3), {})]:
  try:
    namespace['binding'](*arguments, **keywords)
  except TypeError:
    pass
  else:
    raise AssertionError('host binding error was accepted')
assert namespace['binding'](b=2, a=1) == 3
assert namespace['binding'](a=1) == 3
assert namespace['wide'](p259=7) == 7 and namespace['wide']() == 0
function = namespace['wide']
assert function.__code__.co_argcount == 260
assert function.__code__.co_posonlyargcount == function.__code__.co_kwonlyargcount == 0
assert function.__code__.co_varnames == tuple('p' + str(index) for index in range(260))
assert function.__code__.co_flags & (inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS) == 3
again = {'__name__': 'inspection'}
exec(marshal.loads(marshal.dumps(code)), again)
assert again['wide'](p259=9) == 9
try:
  compile_source('fungsi f(value: apapun = ' + '(' * 1200 + '1' + ')' * 1200 + '): apapun {} fungsi utama(): kosong {}')
except PyIndoError as error:
  assert error.span is not None and 'complexity' in error.message
else:
  raise AssertionError('deep default lost complexity diagnostic')
'''
    assert_program_result(run_compiled(source, assertions), "BDB")

  def test_defaults_and_named_calls_preserve_expression_and_iterator_prefixes(self):
    source = '''fungsi pick(value: apapun, other: apapun = 0): apapun { hasilkan value; }
fungsi add(a: desimal, b: desimal = a): desimal { hasilkan a + b; }
fungsi fail(value: desimal = 1 / 0): desimal { hasilkan value; }
fungsi probe(values: himpunan<apapun>): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [0, 1, 2]) {
      jika (add(b=0, a=inner) == 0) { lewati; }
      cocokkan (add(b=0, a=inner)) { kasus 1 { hasilkan pick(value=item); } selainnya { berhenti; } }
    }
  }
  hasilkan;
}
fungsi main_value(): campuran {
  variabel values: himpunan<desimal> = [add(b=2, a=1), 0];
  values[add(b=1, a=0)] = add(a=2);
  cocokkan (add(a=1)) { kasus add(b=1, a=1) {} selainnya { tampilkan("wrong"); } }
  hasilkan "${values}|${0 < add(a=1) < 3}|${salah atau add(b=1, a=2)}";
}
fungsi nested_failure(): kosong {
  untuk (variabel row: apapun didalam [[1]]) {
    untuk (variabel item: apapun didalam row) { pick(value=fail(), other=tampilkan("wrong")); }
  }
}
fungsi utama(): kosong {}'''
    assertions = '''marker = object()
assert namespace['probe']([marker]) is marker and namespace['probe']([]) is None
assert namespace['main_value']() == '[3, 4]|True|3'
assert namespace['probe'].__code__.co_varnames == ('values', 'item', 'inner')
try:
  namespace['nested_failure']()
except ZeroDivisionError:
  pass
else:
  raise AssertionError('default failure was swallowed')
'''
    assert_program_result(run_compiled(source, assertions), "")
