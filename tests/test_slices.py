import tempfile
import unittest
from pathlib import Path

from pyindo import runtime
from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project, write_project


SLICE_FUNCTIONS = '''fungsi read(values: apapun, start: apapun, stop: apapun): apapun { hasilkan values[start hingga stop]; }
fungsi store(values: apapun, start: apapun, stop: apapun, incoming: apapun): kosong { values[start hingga stop] = incoming; }
fungsi remove(values: apapun, start: apapun, stop: apapun): kosong { hapus values[start hingga stop]; }
fungsi checked(): himpunan<desimal> { hasilkan [0, 1, 2, 3, 4, 5]; }
'''
SLICE_PROGRAM = '''fungsi utama(): kosong {
  variabel angka: himpunan<desimal> = [0, 1, 2, 3, 4, 5];

  tampilkan(angka[1 hingga 3], "|");
  angka[1 hingga 3] = [8, 9];
  hapus angka[2 hingga 3];
  tampilkan(angka, "|", "café"[1 hingga 2]);
}
'''
SLICE_OUTPUT = "[1, 2, 3]|[0, 8, 5]|af"


class InclusiveSliceKeyTests(unittest.TestCase):
  def setUp(self):
    self.assertTrue(hasattr(runtime, "make_inclusive_slice"), "inclusive slice key constructor is missing")
    self.key = runtime.make_inclusive_slice

  def test_inclusive_keys_require_both_forward_bounds(self):
    values = [0, 1, 2, 3, 4]
    for start, stop, expected in ((1, 3, [1, 2, 3]), (0, -1, values),
                                  (-3, -1, [2, 3, 4]), (3, 1, []), (2, 2, [2])):
      with self.subTest(start=start, stop=stop):
        self.assertEqual(values[self.key(start, stop)], expected)
    self.assertEqual("café ☕"[self.key(3, 5)], "é ☕")

  def test_inclusive_key_matrix_matches_closed_interval_model(self):
    for length in range(7):
      values = list(range(length))
      bounds = [*range(-10, 11), -(10 ** 100), 10 ** 100]
      for start in bounds:
        for stop in bounds:
          # Walk valid indices against the inclusive end, independently of the
          # runtime helper's conversion to an exclusive Python slice stop.
          first = start + length if start < 0 else start
          last = stop + length if stop < 0 else stop
          first = min(max(first, 0), length)
          expected = [index for index in range(first, length) if index <= last]
          self.assertEqual(values[self.key(start, stop)], expected, (length, start, stop))

  def test_key_protocols_run_once_in_start_stop_order(self):
    events = []
    values = [0, 1, 2]

    class Bound:
      def __init__(self, label, value, fails=False):
        self.label, self.value, self.fails = label, value, fails

      def __index__(self):
        events.append(self.label)
        values.append(3)
        if self.fails:
          raise RuntimeError(self.label)
        return self.value

      def __eq__(self, other):
        raise AssertionError("bound equality was used")

      def __bool__(self):
        raise AssertionError("bound truth was used")

    self.assertEqual(values[self.key(Bound("start", 1), Bound("stop", -1))], [1, 2, 3, 3])
    self.assertEqual(events, ["start", "stop"])
    for first_fails, expected in ((True, ["start"]), (False, ["start", "stop"])):
      events.clear()
      with self.assertRaisesRegex(RuntimeError, expected[-1]):
        self.key(Bound("start", 0, first_fails), Bound("stop", 1, True))
      self.assertEqual(events, expected)

  def test_key_native_types_and_extreme_values_preserve_errors(self):
    self.assertEqual([0, 1, 2][self.key(False, True)], [0, 1])
    self.assertEqual([0, 1, 2][self.key(-(10 ** 100), 10 ** 100)], [0, 1, 2])
    for invalid in (None, 1.5, "1", object()):
      for bounds in ((invalid, 1), (0, invalid)):
        with self.subTest(bounds=bounds), self.assertRaises(TypeError):
          self.key(*bounds)
    for arguments in ((), (0,), (0, 1, 2)):
      with self.assertRaises(TypeError):
        self.key(*arguments)


class SliceExecutionTests(unittest.TestCase):
  def test_source_slices_cover_required_inclusive_bounds_and_native_receivers(self):
    source = SLICE_FUNCTIONS + "fungsi utama(): kosong {}"
    assertions = '''from pyindo.values import freeze_constant_value
read = namespace['read']
for values in ([0, 1, 2, 3, 4, 5], namespace['checked'](), freeze_constant_value([0, 1, 2, 3, 4, 5])):
  for start, stop, expected in [(1, 3, [1, 2, 3]), (0, -1, [0, 1, 2, 3, 4, 5]), (-3, -1, [3, 4, 5]), (3, 1, []), (2, 2, [2]), (-99, 99, [0, 1, 2, 3, 4, 5]), (False, True, [0, 1])]:
    assert read(values, start, stop) == expected
assert read([], 0, -1) == [] and read('café ☕', 3, 5) == 'é ☕'
assert read([1], -(10 ** 100), 10 ** 100) == [1]
marker = object()
class Receiver:
  def __getitem__(self, key):
    assert key == slice(1, 4) and key.step is None
    return marker
assert read(Receiver(), 1, 3) is marker
for bounds in [(None, 1), (0, None), ('0', 1), (0, 1.5)]:
  try:
    read(Receiver(), *bounds)
  except TypeError:
    pass
  else:
    raise AssertionError('invalid or None bound reached receiver')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_readme_slicing_example_runs_through_all_facades(self):
    script = f'''import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
source = {SLICE_PROGRAM!r}
for api in ('direct', 'legacy', 'sentinel'):
  if api == 'direct':
    code = compile_source(source, filename='slicing.pyind')
  else:
    instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename='slicing.pyind')
    assert [chunk.co_name for chunk in chunks] == ['utama']
    code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
  exec(marshal.loads(marshal.dumps(code)), {{'__name__': '__main__'}})
'''
    assert_program_result(run_python(script), SLICE_OUTPUT * 3)
    self.assertIn(SLICE_PROGRAM.rstrip(), Path("README.md").read_text(encoding="utf-8"))

  def test_slice_error_positions_survive_module_marshal_and_source_removal(self):
    library = '''fungsi operand(): apapun {
  /* café ☕ */ hasilkan [0, 1][0 hingga
    1 / 0];
}
fungsi key(value: apapun): apapun {
  /* café ☕ */ hasilkan [0, 1][
    0 hingga value];
}
fungsi get(value: apapun): apapun {
  /* café ☕ */ hasilkan value[0 hingga 1];
}
fungsi set(value: apapun): kosong {
  /* café ☕ */ value[0 hingga 1] = [9];
}
fungsi remove(value: apapun): kosong {
  /* café ☕ */ hapus value[0 hingga 1];
}'''
    script = f'''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
library = {library!r}
def expected_position(name, fragment):
  """Locate original source text independently of emitted instruction metadata."""
  start = library.index(fragment, library.index('fungsi ' + name + '('))
  end = start + len(fragment)
  before, through = library[:start], library[:end]
  return (before.count('\\n') + 1, through.count('\\n') + 1,
          len(before.rsplit('\\n', 1)[-1].encode('utf-8')), len(through.rsplit('\\n', 1)[-1].encode('utf-8')))
for api in ('direct', 'legacy', 'sentinel'):
  with tempfile.TemporaryDirectory() as directory:
    entry = write_project(Path(directory), {{'café.pyind': library, 'main.pyind': 'impor "café.pyind" sebagai lib; fungsi call(value: apapun): apapun {{ hasilkan lib.key(value=value); }} fungsi utama(): kosong {{}}'}})
    dependency_name = str(entry.parent / 'café.pyind')
    root_name = str(entry) if api == 'direct' else 'renamed.pyind'
    source = entry.read_text(encoding='utf-8')
    if api == 'direct':
      code = compile_source(source, filename=str(entry))
    else:
      instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename=str(entry))
      code = compile_bytecodes(instructions, filename=root_name).to_code()
    code = marshal.loads(marshal.dumps(code))
    for path in entry.parent.glob('*.pyind'):
      path.unlink()
    namespace = {{'__name__': 'inspection'}}
    exec(code, namespace)
    lib = namespace['lib']
    assert namespace['call'](1) == [0, 1] and lib.get('abc') == 'ab'
    assert namespace['call'].__code__.co_filename == root_name
    assert lib.key.__code__.co_filename == dependency_name
    values = [1, 2]
    lib.set(values)
    assert values == [9]
    lib.remove(values)
    assert values == []
    cases = [(lib.operand, (), ZeroDivisionError, 'operand', '1 / 0'),
             (namespace['call'], (None,), TypeError, 'key', '[\\n    0 hingga value]'),
             (namespace['call'], (1.5,), TypeError, 'key', '[\\n    0 hingga value]'),
             (lib.get, (0,), TypeError, 'get', 'value[0 hingga 1]'),
             (lib.set, ('a',), TypeError, 'set', 'value[0 hingga 1]'),
             (lib.remove, ('a',), TypeError, 'remove', 'value[0 hingga 1]')]
    for function, arguments, exception, name, fragment in cases:
      try:
        function(*arguments)
      except exception as error:
        positions = []
        trace = error.__traceback__
        while trace is not None:
          frame_code = trace.tb_frame.f_code
          if frame_code.co_filename == dependency_name and frame_code.co_name == name:
            positions.append(list(frame_code.co_positions())[trace.tb_lasti // 2])
          trace = trace.tb_next
        assert positions == [expected_position(name, fragment)], (name, positions, expected_position(name, fragment))
      else:
        raise AssertionError('slicing error was swallowed')
'''
    assert_program_result(run_python(script), "")

  def test_cli_slicing_options_arguments_statuses_and_debug(self):
    options_list = ((), ("-O",), ("-D",))
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "library.pyind": SLICE_FUNCTIONS,
        "main.pyind": '''impor "library.pyind" sebagai lib;
fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal {
  tampilkan(argv[0], "|", argv[1 hingga argc - 1], "|", lib.read([0, 1, 2], start=0, stop=1));
  hasilkan 7;
}''',
      })
      library = entry.parent / "library.pyind"
      originals = entry.read_bytes(), library.read_bytes()
      for options in options_list:
        assert_program_result(run_program(entry, options, program_arguments=["halo", "dunia"]), f"{entry}|['halo', 'dunia']|[0, 1]", 7)
        self.assertEqual((entry.read_bytes(), library.read_bytes()), originals)
      listing = entry.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn(str(library), listing)
      self.assertIn("<pyindo:make_inclusive_slice>", listing)
      for call in ("lib.read([1], 0, tampilkan())", "lib.read(1, 0, 1)", "lib.store([1], 0, 0, 2)", "lib.store(saved, 0, 0, [2])"):
        entry.write_text(f'impor "library.pyind" sebagai lib; konstanta saved: apapun = [1]; fungsi utama(): kosong {{ tampilkan("A"); {call}; tampilkan("wrong"); }}', encoding="utf-8")
        for options in options_list:
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 1)
          self.assertEqual(completed.stdout, "A")
          self.assertIn("library.pyind", completed.stderr)
          self.assertIn("TypeError", completed.stderr)
      for suffix in ("[hingga 2]", "[1 hingga]", "[1 hingga 2 langkah 2]", "[::-1]", "[1:2:2]"):
        entry.write_text(f"fungsi utama(): kosong {{ tampilkan([1, 2]{suffix}); }}", encoding="utf-8")
        for options in options_list:
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 70)
          self.assertEqual(completed.stderr, "")
          self.assertTrue(completed.stdout.startswith("Error: "))

  def test_slice_expressions_and_coercions_preserve_effect_order(self):
    source = '''fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi read(values: apapun, start: apapun, stop: apapun): apapun { hasilkan mark("B", values)[mark("A", start) hingga mark("Z", stop)]; }
fungsi store(values: apapun, start: apapun, stop: apapun): kosong { mark("B", values)[mark("A", start) hingga mark("Z", stop)] = mark("R", []); }
fungsi remove(values: apapun, start: apapun, stop: apapun): kosong { hapus mark("B", values)[mark("A", start) hingga mark("Z", stop)]; }
fungsi fail(): apapun { tampilkan("R"); hasilkan 1 / 0; }
fungsi bad_rhs(values: apapun): kosong { mark("B", values)[0 hingga 1] = fail(); }
fungsi utama(): kosong {}'''
    assertions = '''import contextlib, io
class Bound:
  def __init__(self, label, fails=False):
    self.label, self.fails = label, fails
  def __index__(self):
    print(self.label, end='')
    if self.fails:
      raise RuntimeError('bound')
    return 0
class Receiver:
  def __getitem__(self, key):
    print('G', end='')
    return 1
  def __setitem__(self, key, value):
    print('S', end='')
  def __delitem__(self, key):
    print('D', end='')
for name in ('read', 'store', 'remove'):
  namespace[name](Receiver(), Bound('a'), Bound('z'))
for action, expected, exception in [(lambda: namespace['bad_rhs'](Receiver()), 'R', ZeroDivisionError), (lambda: namespace['read'](Receiver(), Bound('a', True), Bound('z')), 'BAZa', RuntimeError), (lambda: namespace['read'](Receiver(), 0, None), 'BAZ', TypeError)]:
  output = io.StringIO()
  with contextlib.redirect_stdout(output):
    try:
      action()
    except exception:
      pass
    else:
      raise AssertionError('failed operand continued')
  assert output.getvalue() == expected, output.getvalue()
'''
    assert_program_result(run_compiled(source, assertions), "BAZazGRBAZazSBAZazD")

  def test_slice_assignment_and_delete_follow_inclusive_selections(self):
    source = SLICE_FUNCTIONS + '''fungsi replace(values: apapun): apapun { values[0 hingga 0] = [[9]]; hasilkan [8]; }
fungsi nested(values: apapun): kosong { values[0][0 hingga 0] = replace(values); }
fungsi headers(): kosong {
  variabel values: apapun = [0, 1, 2];
  jika (benar) maka values[0 hingga 1] = [9];
  untuk (values[0 hingga 0] = []; values; hapus values[0 hingga 0]) { tampilkan(values[0]); }
}
fungsi utama(): kosong {}'''
    assertions = '''for values in ([0, 1, 2, 3, 4, 5], namespace['checked']()):
  namespace['store'](values, 1, 3, [8, 9])
  namespace['remove'](values, 2, 3)
  assert values == [0, 8, 5]
  namespace['store'](values, 2, 0, [7])
  assert values == [0, 8, 7, 5]
  namespace['store'](values, 0, -1, values)
  assert values == [0, 8, 7, 5]
  namespace['store'](values, 1, 2, namespace['read'](values, 0, 2))
  assert values == [0, 0, 8, 7, 5]
  namespace['remove'](values, 99, 100)
  namespace['remove'](values, 0, -1)
  assert values == []
rows = [[1], [2]]
namespace['nested'](rows)
assert rows == [[8], [2]]
namespace['headers']()
'''
    assert_program_result(run_compiled(source, assertions), "2")

  def test_checked_slice_failures_are_atomic_except_prior_callback_effects(self):
    source = SLICE_FUNCTIONS + '''fungsi rows(): himpunan<himpunan<desimal>> { hasilkan []; }
fungsi utama(): kosong {}'''
    assertions = '''def failing():
  yield 9
  raise RuntimeError('incoming')
for incoming, exception in [([9, True], TypeError), (failing(), RuntimeError)]:
  values = namespace['checked']()
  try:
    namespace['store'](values, 0, -1, incoming)
  except exception:
    pass
  else:
    raise AssertionError('failed batch was accepted')
  assert values == [0, 1, 2, 3, 4, 5]
for fails in (False, True):
  values = namespace['checked']()
  class Bound:
    def __index__(self):
      values.append(6)
      return 0
  class Incoming:
    def __iter__(self):
      values.append(7)
      yield 9
      if fails:
        yield 'bad'
  try:
    namespace['store'](values, Bound(), -1, Incoming())
  except TypeError:
    assert fails and values == [0, 1, 2, 3, 4, 5, 6, 7]
  else:
    assert not fails and values == [9]
rows, child = namespace['rows'](), [1]
namespace['store'](rows, 0, -1, [child, child])
assert rows[0] is rows[1] and rows[0] is not child
namespace['store'](rows, 0, 0, [[2], [3], [4]])
assert rows == [[2], [3], [4], [1]]
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_slice_results_preserve_shallow_aliases_and_frozen_protection(self):
    source = SLICE_FUNCTIONS + '''konstanta saved: himpunan<himpunan<desimal>> = [[1]];
fungsi rows(): himpunan<himpunan<desimal>> { hasilkan [[1]]; }
fungsi typed(values: himpunan<himpunan<desimal>>): himpunan<himpunan<desimal>> { hasilkan values; }
fungsi utama(): kosong {}'''
    assertions = '''read, store = namespace['read'], namespace['store']
for original in ([[1]], namespace['rows']()):
  sliced = read(original, 0, -1)
  assert type(sliced) is list and sliced is not original and sliced[0] is original[0]
  sliced[0][0] = 9
  assert original[0][0] == 9
  sliced.clear()
  assert len(original) == 1
checked = namespace['rows']()
converted = namespace['typed'](read(checked, 0, -1))
assert converted is not checked and converted[0] is checked[0]
frozen = read(namespace['saved'], 0, -1)
assert namespace['typed'](frozen) is frozen
for values in (frozen, 'abc'):
  for action in (lambda: store(values, 0, 0, [2]), lambda: namespace['remove'](values, 0, 0)):
    try:
      action()
    except TypeError:
      pass
    else:
      raise AssertionError('immutable slice target changed')
assert frozen == [[1]]
try:
  store(frozen[0], 0, 0, [2])
except TypeError:
  pass
else:
  raise AssertionError('nested frozen child changed')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_slices_keep_live_imports_default_timing_and_module_initialization(self):
    files = {
      "state.pyind": '''variabel values: himpunan<desimal> = [0, 1, 2];
fungsi change(): kosong { values = [3, 4, 5]; }''',
      "main.pyind": '''impor "state.pyind" sebagai state;
dari "state.pyind" impor values;
fungsi read(): apapun { hasilkan values[0 hingga -1]; }
fungsi mutate(): kosong { state.values[1 hingga 2] = [9]; hapus values[0 hingga 0]; }
fungsi tail(values_in: himpunan<desimal>, part: himpunan<desimal> = values_in[1 hingga -1]): himpunan<desimal> { hasilkan part; }
fungsi fresh(part: himpunan<desimal> = [1, 2][0 hingga 1]): himpunan<desimal> { part[0] = part[0] + 1; hasilkan part; }
fungsi utama(): kosong {}''',
    }
    assertions = '''assert namespace['read']() == [0, 1, 2]
namespace['state'].change()
assert namespace['read']() == [3, 4, 5]
namespace['mutate']()
assert namespace['read']() == [9] and namespace['state'].values == [9]
assert namespace['tail'](values_in=[1, 2, 3]) == [2, 3]
assert namespace['tail'](part=[9], values_in=[1]) == [9]
first, second = namespace['fresh'](), namespace['fresh']()
assert first == second == [2, 2] and first is not second
'''
    assert_program_result(run_project(files, assertions), "")
    for call, status in (("probe()", 1), ("probe(value=[1])", 0)):
      source = f"variabel first: apapun = {call}; variabel later: apapun = [2]; fungsi probe(value: apapun = later[0 hingga 0]): apapun {{ hasilkan value; }} fungsi utama(): kosong {{}}"
      completed = run_source(source)
      self.assertEqual(completed.returncode, status)
      if status:
        self.assertIn("not initialized", completed.stderr)

  def test_slice_helper_calls_preserve_stack_prefixes_and_native_frames(self):
    source = '''fungsi add(value: desimal, extra: desimal = value): desimal { hasilkan value + extra; }
fungsi probe(values: apapun): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [0, 1, 2]) {
      jika (inner == 0) { lewati; }
      cocokkan (inner) { kasus 1 { hasilkan item[0 hingga 0][0]; } selainnya { berhenti; } }
    }
  }
  hasilkan;
}
fungsi text(): campuran {
  variabel values: himpunan<desimal> = [0, 4];
  values[0 hingga 0] = [add(value=[1, 2][0 hingga 0][0])];
  cocokkan (values[0 hingga 0][0]) { kasus add(value=1) {} selainnya { tampilkan("wrong"); } }
  hasilkan "${values[0 hingga 1]}|${0 < values[0 hingga 0][0] < 3}|${salah atau values[1 hingga 1][0]}";
}
fungsi fail(): kosong {
  untuk (variabel row: apapun didalam [[1]]) {
    untuk (variabel item: apapun didalam row) { tampilkan(row[0 hingga tampilkan()]); tampilkan("wrong"); }
  }
}
fungsi utama(): kosong {}'''
    assertions = '''import inspect
marker = object()
assert namespace['probe']([[marker]]) is marker and namespace['probe']([]) is None
assert namespace['text']() == '[2, 4]|True|4'
function = namespace['probe']
assert function.__code__.co_varnames == ('values', 'item', 'inner')
assert function.__code__.co_argcount == 1
assert function.__code__.co_posonlyargcount == function.__code__.co_kwonlyargcount == 0
assert function.__code__.co_flags & (inspect.CO_OPTIMIZED | inspect.CO_NEWLOCALS) == 3
try:
  namespace['fail']()
except TypeError:
  pass
else:
  raise AssertionError('None stop accepted above iterator stack')
'''
    assert_program_result(run_compiled(source, assertions), "")
