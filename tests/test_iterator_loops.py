import re
import tempfile
import unittest
from pathlib import Path

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module
from tests.fixture_runner import REPOSITORY_PATH, assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled


class IteratorSyntaxTests(unittest.TestCase):
  def analyze(self, source):
    """
    Exercise parsing and flow analysis before any bytecode is assembled.
    """

    return analyze_program(parse_module(source))

  def test_headers_keep_spans_nested_types_and_expression_grammar(self):
    source = '''fungsi utama(): kosong {
  untuk (konstanta rows: himpunan<himpunan<desimal>> didalam [] jika benar selainnya []) {}
  untuk (variabel found: logika didalam [1 didalam [1]]) {}
  untuk (variabel old: himpunan<himpunan<desimal>> = []; salah;) {}
}'''
    program = parse_module(source)
    loop = program.functions[0].body[0]
    self.assertEqual(loop.name, "rows")
    self.assertTrue(loop.is_constant)
    self.assertEqual(loop.annotation.arguments[0].arguments[0].name, "desimal")
    self.assertEqual(source[loop.binding_span.start:loop.binding_span.end],
                     "konstanta rows: himpunan<himpunan<desimal>>")
    self.assertEqual(source[loop.iterable.span.start:loop.iterable.span.end],
                     "[] jika benar selainnya []")
    self.assertEqual(source[loop.span.start:loop.span.end], source.splitlines()[1].strip())
    symbols = analyze_program(program)
    self.assertEqual(symbols.scopes["utama"].local_names, ["rows", "found", "old"])

  def test_header_requires_a_named_typed_declaration_and_braces(self):
    headers = (
      "item: desimal didalam []", "variabel item didalam []",
      "variabel item: didalam []", "variabel item: desimal didalam",
      "variabel item: desimal = 1 didalam []", "variabel a, b: apapun didalam []",
      "variabel items[0]: desimal didalam []",
    )
    for header in headers:
      with self.subTest(header=header):
        with self.assertRaises(PyIndoError) as raised:
          parse_module(f"fungsi utama(): kosong {{ untuk ({header}) {{}} }}")
        self.assertIsNotNone(raised.exception.span)
    with self.assertRaises(PyIndoError):
      parse_module("fungsi utama(): kosong { untuk (variabel n: desimal didalam []) maka tampilkan(n); }")

  def test_targets_use_existing_type_constant_and_duplicate_rules(self):
    symbols = self.analyze("""fungsi utama(): kosong {
  untuk (konstanta item: himpunan<angka> didalam [[1]]) { tampilkan(item); }
}""")
    scope = symbols.scopes["utama"]
    self.assertEqual(scope.binding_types["item"], ("himpunan", "desimal"))
    self.assertEqual(scope.constant_names, {"item"})
    invalid = (
      "untuk (variabel item: mystery didalam []) {}",
      "variabel item: desimal = 0; untuk (variabel item: desimal didalam []) {}",
      "untuk (variabel item: desimal didalam []) {} variabel item: desimal = 0;",
      "untuk (variabel utama: desimal didalam []) {}",
      "untuk (konstanta item: desimal didalam [1]) { item = 2; }",
      "untuk (konstanta item: himpunan<desimal> didalam [[1]]) { item[0] = 2; }",
    )
    for body in invalid:
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          self.analyze(f"fungsi utama(): kosong {{ {body} }}")
    with self.assertRaisesRegex(PyIndoError, "Duplicate local declaration"):
      self.analyze("fungsi f(item: desimal): kosong { untuk (variabel item: desimal didalam []) {} } fungsi utama(): kosong {}")

  def test_only_the_body_sees_the_initialized_target(self):
    self.analyze("fungsi utama(): kosong { untuk (variabel n: desimal didalam [1]) { tampilkan(n); n = 2; } }")
    for body in (
      "untuk (variabel n: desimal didalam n) {}",
      "untuk (variabel n: desimal didalam [1]) {} tampilkan(n);",
      "untuk (variabel n: desimal didalam [1]) { variabel value: desimal = n; } tampilkan(value);",
    ):
      with self.subTest(body=body):
        with self.assertRaisesRegex(PyIndoError, "not initialized"):
          self.analyze(f"fungsi utama(): kosong {{ {body} }}")

  def test_empty_or_dead_bodies_keep_static_checks_and_return_coverage(self):
    for body in (
      "untuk (variabel n: desimal didalam []) { missing(); }",
      "untuk (variabel n: desimal didalam []) { berhenti; tampilkan(missing); }",
      "untuk (variabel n: desimal didalam []) { tampilkan(helper()); }",
    ):
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          self.analyze(f"fungsi helper(n: desimal): kosong {{}} fungsi utama(): kosong {{ {body} }}")
    with self.assertRaisesRegex(PyIndoError, "without a return value"):
      self.analyze("fungsi utama(): desimal { untuk (variabel n: desimal didalam [1]) { hasilkan n; } }")


class IteratorExecutionTests(unittest.TestCase):
  def test_lists_unicode_empty_sources_and_one_source_evaluation(self):
    source = '''fungsi source(): apapun { tampilkan("S"); hasilkan [1, 2, 3]; }
fungsi utama(): kosong {
  untuk (variabel item: desimal didalam source()) { tampilkan(item); }
  untuk (konstanta letter: campuran didalam "é☕é") { tampilkan(letter, "|"); }
  untuk (variabel empty: desimal didalam []) { tampilkan("bad"); }
  untuk (variabel text: campuran didalam "") { tampilkan("bad"); }
  tampilkan("end");
}'''
    assert_program_result(run_source(source), "S123é|☕|e|́|end")

  def test_rebinding_does_not_redirect_the_iterator(self):
    source = '''fungsi utama(): kosong {
  variabel values: apapun = [1, 2, 3];
  untuk (variabel item: desimal didalam values) {
    tampilkan(item);
    values = [9];
    item = 8;
  }
  tampilkan(values);
}'''
    assert_program_result(run_source(source), "123[9]")

  def test_live_mutations_match_native_lists_and_checked_lists(self):
    source = '''fungsi visit(values: apapun): kosong {
  untuk (variabel item: desimal didalam values) { observe(item); }
}
fungsi observe(item: desimal): kosong {}
fungsi utama(): kosong {}'''
    assertions = '''from pyindo.type_checks import prepare_typed_value
for checked in (False, True):
  for mutation in ('replace', 'delete', 'append'):
    traces = []
    for native in (True, False):
      values = [1, 2, 3]
      if checked:
        values = prepare_typed_value(values, ('himpunan', 'desimal'), 'source')
      trace = []
      def observe(item):
        trace.append(item)
        if item == 1:
          if mutation == 'replace':
            values[1] = 9
          elif mutation == 'delete':
            del values[0]
          else:
            values.append(4)
      namespace['observe'] = observe
      if native:
        for item in values:
          observe(item)
      else:
        namespace['visit'](values)
      traces.append((trace, list(values)))
    assert traces[0] == traces[1], (checked, mutation, traces)
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_constant_snapshots_are_fresh_and_invalid_items_fail_before_the_body(self):
    source = '''fungsi snapshots(values: apapun): kosong {
  untuk (konstanta row: himpunan<desimal> didalam values) { observe(row); }
}
fungsi anything(values: apapun): kosong {
  untuk (konstanta row: apapun didalam values) { observe(row); }
}
fungsi observe(row: apapun): kosong {}
fungsi utama(): kosong {}'''
    assertions = '''raw = [1]
seen = []
def observe(row):
  seen.append(row)
  raw[0] = 9
namespace['observe'] = observe
namespace['snapshots']([raw, raw])
assert seen[0][0] == 1 and seen[1][0] == 9 and seen[0] is not seen[1]
seen.clear()
try:
  namespace['anything']([object()])
except TypeError:
  pass
else:
  raise AssertionError('foreign object frozen as constant')
assert seen == []
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_iterators_are_released_on_normal_early_and_exceptional_exits(self):
    source = '''fungsi exhaust(values: apapun, marker: apapun): apapun {
  untuk (variabel item: desimal didalam values) {}
  hasilkan marker;
}
fungsi stop(values: apapun, marker: apapun): apapun {
  untuk (variabel item: desimal didalam values) { berhenti; }
  hasilkan marker;
}
fungsi skip(values: apapun, marker: apapun): apapun {
  untuk (variabel item: desimal didalam values) { lewati; }
  hasilkan marker;
}
fungsi early(values: apapun, marker: apapun): apapun {
  untuk (variabel item: desimal didalam values) { hasilkan marker; }
  hasilkan marker;
}
fungsi guarded(values: apapun, marker: apapun): desimal {
  untuk (variabel item: desimal didalam values) { hasilkan marker; }
  hasilkan 0;
}
fungsi nested(first: apapun, second: apapun, marker: apapun): apapun {
  untuk (variabel outer: desimal didalam first) {
    untuk (variabel inner: desimal didalam second) { hasilkan marker; }
  }
  hasilkan marker;
}
fungsi utama(): kosong {}'''
    assertions = '''import weakref
class Cursor:
  def __init__(self, values, failure):
    self.values, self.failure, self.index = values, failure, 0
  def __iter__(self):
    return self
  def __next__(self):
    if self.failure:
      raise ValueError('next failed')
    if self.index == len(self.values):
      raise StopIteration
    item = self.values[self.index]
    self.index += 1
    return item
class Source:
  def __init__(self, values=(1, 2), failure=False):
    self.values, self.failure, self.references = values, failure, []
  def __iter__(self):
    cursor = Cursor(self.values, self.failure)
    self.references.append(weakref.ref(cursor))
    return cursor
marker = object()
for repeat in range(50):
  for name in ('exhaust', 'stop', 'skip', 'early', 'guarded'):
    for values, failure in (((1, 2), False), ((), False), (('bad',), False), ((1,), True)):
      source = Source(values, failure)
      try:
        result = namespace[name](source, marker)
      except (TypeError, ValueError):
        pass
      else:
        assert result is marker or name == 'guarded' and result == 0
      assert source.references and all(reference() is None for reference in source.references), name
  first, second = Source(), Source()
  assert namespace['nested'](first, second, marker) is marker
  assert all(reference() is None for source in (first, second) for reference in source.references)
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_each_item_is_guarded_before_binding_or_body_effects(self):
    source = '''fungsi visit(values: apapun): kosong {
  untuk (variabel item: desimal didalam values) { observe(item); }
}
fungsi observe(item: desimal): kosong {}
fungsi utama(): kosong {}'''
    assertions = '''for values, previous in ((['bad'], None), ([1, 'bad'], 1)):
  seen = []
  namespace['observe'] = seen.append
  try:
    namespace['visit'](values)
  except TypeError as error:
    assert "binding 'item'" in str(error) and 'line 2' in str(error), str(error)
    frame = error.__traceback__
    while frame.tb_frame.f_code.co_name != 'visit':
      frame = frame.tb_next
    if previous is None:
      assert 'item' not in frame.tb_frame.f_locals
    else:
      assert frame.tb_frame.f_locals['item'] == previous
  else:
    raise AssertionError('invalid item accepted')
  assert seen == ([] if previous is None else [1])
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_nested_list_targets_keep_checked_copies_and_frozen_snapshots(self):
    source = '''fungsi mutable(values: apapun): apapun {
  untuk (variabel row: himpunan<desimal> didalam values) { hasilkan row; }
  hasilkan kosong_value();
}
fungsi frozen(values: apapun): apapun {
  untuk (konstanta row: himpunan<himpunan<desimal>> didalam values) { hasilkan row; }
  hasilkan kosong_value();
}
fungsi kosong_value(): kosong {}
fungsi utama(): kosong {
  konstanta rows: himpunan<himpunan<desimal>> = [[1], [2]];
  untuk (variabel row: himpunan<desimal> didalam rows) { tampilkan(row); }
}'''
    assertions = '''raw = [[1, 2]]
checked = namespace['mutable'](raw)
checked[0] = 9
assert raw == [[1, 2]] and list(checked) == [9, 2]
try:
  checked[0] = 'bad'
except TypeError:
  pass
else:
  raise AssertionError('unchecked target list')
raw = [[[1]]]
frozen = namespace['frozen'](raw)
raw[0][0][0] = 7
assert frozen[0][0] == 1
try:
  frozen[0][0] = 9
except TypeError:
  pass
else:
  raise AssertionError('mutable constant snapshot')
'''
    assert_program_result(run_compiled(source, assertions, module_name="__main__"), "[1][2]")

  def test_nested_and_mixed_loop_control_preserves_outer_iterators(self):
    source = '''fungsi utama(): kosong {
  untuk (variabel outer: desimal didalam [1, 2, 3]) {
    jika (outer adalah 2) maka lewati;
    untuk (variabel inner: desimal didalam [4, 5, 6]) {
      jika (inner adalah 4) maka lewati;
      tampilkan(outer, inner);
      berhenti;
    }
    selama (benar) { berhenti; }
    untuk (variabel index: desimal = 0; index < 2; index++) { lewati; }
    tampilkan(outer);
  }
  untuk (variabel last: desimal = 0; last < 2; last++) {
    untuk (variabel item: desimal didalam [7, 8]) { tampilkan(item); berhenti; }
  }
  tampilkan("end");
}'''
    assert_program_result(run_source(source), "15135377end")

  def test_returns_keep_identity_through_nested_and_mixed_loops(self):
    source = '''fungsi nested(value: apapun): apapun {
  untuk (variabel outer: desimal didalam [1, 2]) {
    selama (benar) {
      untuk (variabel index: desimal = 0; index < 2; index++) {
        untuk (konstanta inner: desimal didalam [3, 4]) { hasilkan value; }
      }
    }
  }
  hasilkan value;
}
fungsi bare(): kosong { untuk (variabel item: desimal didalam [1]) { hasilkan; } }
fungsi guarded(): desimal {
  untuk (variabel item: desimal didalam [1]) { hasilkan "bad"; }
  hasilkan 0;
}
fungsi utama(): kosong {}'''
    assertions = '''value = object()
for repeat in range(100):
  assert namespace['nested'](value) is value
  assert namespace['bare']() is None
  try:
    namespace['guarded']()
  except TypeError:
    pass
  else:
    raise AssertionError('return guard bypassed')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_iterator_protocol_events_and_errors_are_native(self):
    source = '''fungsi exhaust(values: apapun): kosong {
  untuk (variabel item: desimal didalam values) { observe(item); }
}
fungsi first(values: apapun): kosong {
  untuk (variabel item: desimal didalam values) { observe(item); berhenti; }
}
fungsi observe(item: desimal): kosong {}
fungsi utama(): kosong {}'''
    assertions = '''class Source:
  def __init__(self, trace, failure):
    self.trace, self.failure = trace, failure
  def __iter__(self):
    self.trace.append('iter')
    if self.failure == 'iter':
      raise ValueError('iter failed')
    return Cursor(self.trace, self.failure)
class Cursor:
  def __init__(self, trace, failure):
    self.trace, self.failure, self.index = trace, failure, 0
  def __iter__(self):
    return self
  def __next__(self):
    self.trace.append('next')
    self.index += 1
    if self.failure == 'next' and self.index == 2:
      raise ValueError('next failed')
    if self.index > 2:
      raise StopIteration
    return self.index
for mode in ('exhaust', 'first'):
  for failure in ('none', 'iter', 'next'):
    outcomes = []
    for native in (True, False):
      trace = []
      source = Source(trace, failure)
      namespace['observe'] = trace.append
      try:
        if native:
          for item in source:
            trace.append(item)
            if mode == 'first':
              break
        else:
          namespace[mode](source)
      except ValueError as error:
        trace.append(str(error))
      outcomes.append(trace)
    assert outcomes[0] == outcomes[1], (mode, failure, outcomes)
for bad in (None, 1, True):
  try:
    namespace['exhaust'](bad)
  except TypeError:
    pass
  else:
    raise AssertionError('noniterable accepted')
'''
    assert_program_result(run_compiled(source, assertions), "")


class IteratorIntegrationTests(unittest.TestCase):
  def test_facades_marshal_and_utf8_metadata_keep_original_locations(self):
    source = '''fungsi choose(values: apapun, flag: logika): apapun {
  /* café ☕ */ untuk (variabel item: apapun didalam values jika flag selainnya []) {
    hasilkan item;
  }
  hasilkan empty();
}
fungsi empty(): kosong {}
fungsi utama(): kosong {}
'''.replace("\n", "\r\n")
    script = """import dis
import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
""" + f"source = {source!r}\n" + """codes = [compile_source(source, filename='iterator café.pyind')]
for sentinel in ('', '\\0'):
  instructions, chunks = parse_program(source + sentinel)
  codes.append(compile_bytecodes(instructions, filename='iterator café.pyind').to_code())
for code in codes:
  namespace = {'__name__': 'inspection'}
  exec(marshal.loads(marshal.dumps(code)), namespace)
  function = namespace['choose']
  assert function.__code__.co_varnames == ('values', 'flag', 'item')
  assert function.__code__.co_filename == 'iterator café.pyind'
  marker = object()
  assert function([marker], True) is marker
  assert function([marker], False) is None and function([], True) is None
  for instruction in dis.get_instructions(function):
    if instruction.opname in ('GET_ITER', 'FOR_ITER'):
      line = source.splitlines()[1]
      assert instruction.positions.lineno == instruction.positions.end_lineno == 2
      assert instruction.positions.col_offset == len(line[:line.index('values jika')].encode('utf-8'))
"""
    assert_program_result(run_python(script), "")

  def test_cli_arguments_status_and_debug_output_with_iterator_loops(self):
    source = '''fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal {
  variabel total: desimal = 0;
  untuk (konstanta word: campuran didalam argv) {
    jika (word adalah argv[0]) maka lewati;
    tampilkan(word, "|");
    total++;
  }
  tampilkan(total);
  hasilkan 7;
}'''
    with tempfile.TemporaryDirectory(prefix="pyindo iterator é ") as directory:
      source_path = Path(directory) / "iterator example.pyind"
      source_path.write_text(source, encoding="utf-8")
      original = source_path.read_bytes()
      for options in ((), ("-O",), ("-D",), ("-O", "-D")):
        for arguments, output in ((None, "0"), (("one", "café ☕", "-D", "--"), "one|café ☕|-D|--|4")):
          assert_program_result(run_program(source_path, options, program_arguments=arguments), output, 7)
      self.assertIn("FOR_ITER", source_path.with_suffix(".dis").read_text(encoding="utf-8"))
      self.assertEqual(source_path.read_bytes(), original)

  def test_readme_iterator_example_runs_with_exact_output(self):
    readme = (REPOSITORY_PATH / "README.md").read_text(encoding="utf-8")
    section = readme.split("### Iterator loops\n", 1)
    self.assertEqual(len(section), 2, "README iterator example is missing")
    program = re.search(r"```pyindo\n(.*?)```", section[1], re.S).group(1)
    assert_program_result(run_source(program), "café ☕|4")
