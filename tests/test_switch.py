import tempfile
import unittest
from pathlib import Path

from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project, write_project


SWITCH_PROGRAM = '''konstanta berhasil: desimal = 200;

fungsi uraikan(kode: desimal): campuran {
  cocokkan (kode) {
    kasus berhasil, 201 {
      hasilkan "berhasil";
    }
    kasus 404 {
      hasilkan "tidak ditemukan";
    }
    selainnya {
      hasilkan "lainnya";
    }
  }
}

fungsi utama(): kosong {
  tampilkan(uraikan(201), "|", uraikan(404), "|", uraikan(500));
}
'''
SWITCH_OUTPUT = "berhasil|tidak ditemukan|lainnya"


class SwitchExecutionTests(unittest.TestCase):
  def test_subject_once_and_lazy_values_choose_only_first_match(self):
    source = '''fungsi subject(): desimal { tampilkan("S"); hasilkan 2; }
fungsi candidate(label: campuran, value: desimal): desimal { tampilkan(label); hasilkan value; }
fungsi utama(): kosong {
  cocokkan (subject()) {
    kasus candidate("A", 0), candidate("B", 2), candidate("X", 3) { tampilkan("M"); }
    kasus candidate("C", 2) { tampilkan("wrong"); }
    selainnya { tampilkan("wrong"); }
  }
  tampilkan("E");
}'''
    assert_program_result(run_compiled(source, module_name="__main__"), "SABME")

  def test_empty_matches_duplicates_fallback_and_no_match_never_fall_through(self):
    cases = (
      (1, 'kasus 1 {} kasus 1 { tampilkan("wrong"); } selainnya { tampilkan("wrong"); }', "E"),
      (1, 'kasus 1 { tampilkan("A"); } kasus 1 { tampilkan("wrong"); }', "AE"),
      (3, 'kasus 1 {} selainnya { tampilkan("F"); }', "FE"),
      (3, 'kasus 1 {}', "E"),
      (3, 'kasus 1 {} selainnya {}', "E"),
    )
    for subject, arms, expected in cases:
      source = f'fungsi utama(): kosong {{ cocokkan ({subject}) {{ {arms} }} tampilkan("E"); }}'
      with self.subTest(arms=arms):
        assert_program_result(run_compiled(source, module_name="__main__"), expected)

  def test_normal_equality_handles_native_values_and_nonreflexive_identity(self):
    source = '''variabel checked: himpunan<desimal> = [1, 2];
konstanta frozen: himpunan<desimal> = checked;
fungsi pick(subject: apapun, candidate: apapun): desimal {
  cocokkan (subject) { kasus candidate { hasilkan 1; } selainnya { hasilkan 0; } }
}
fungsi utama(): kosong {}'''
    assertions = '''pick = namespace['pick']
for subject, candidate, expected in [(1, True, 1), ('café', 'café', 1), (None, None, 1), (1, '1', 0),
    (namespace['checked'], [1, 2], 1), (namespace['frozen'], namespace['checked'], 1)]:
  assert pick(subject, candidate) == expected
nan = float('nan')
assert pick(nan, nan) == 0
assert pick.__code__.co_varnames == ('subject', 'candidate')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_rich_equality_direction_and_one_truth_check_per_comparison(self):
    source = '''fungsi pick(subject: apapun, candidate: apapun): desimal {
  cocokkan (subject) { kasus candidate { hasilkan 1; } selainnya { hasilkan 0; } }
}
fungsi utama(): kosong {}'''
    assertions = '''events = []
class Truth:
  def __init__(self, answer):
    self.answer = answer
    self.calls = 0
  def __bool__(self):
    self.calls += 1
    assert self.calls == 1, 'comparison truth was tested twice'
    return self.answer
class Subject:
  def __init__(self, result):
    self.result = result
  def __eq__(self, other):
    events.append('subject')
    return self.result
class Candidate:
  def __eq__(self, other):
    events.append('candidate')
    return True
for answer in (False, True):
  events.clear()
  truth = Truth(answer)
  assert namespace['pick'](Subject(truth), Candidate()) == int(answer)
  assert events == ['subject'] and truth.calls == 1
events.clear()
assert namespace['pick'](Subject(NotImplemented), Candidate()) == 1
assert events == ['subject', 'candidate']
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_comparison_and_truth_failures_stop_later_values_and_bodies(self):
    source = '''fungsi later(): desimal { tampilkan("L"); hasilkan 2; }
fungsi pick(subject: apapun, candidate: apapun): desimal {
  cocokkan (subject) {
    kasus candidate, later() { tampilkan("M"); hasilkan 1; }
    selainnya { tampilkan("F"); hasilkan 0; }
  }
}
fungsi utama(): kosong {}'''
    assertions = '''class BadTruth:
  def __bool__(self):
    raise RuntimeError('truth failure')
class BadEquality:
  def __eq__(self, other):
    raise ValueError('equality failure')
class TruthEquality:
  def __eq__(self, other):
    return BadTruth()
for subject, exception, message in [(BadEquality(), ValueError, 'equality failure'), (TruthEquality(), RuntimeError, 'truth failure')]:
  try:
    namespace['pick'](subject, 1)
  except exception as error:
    assert str(error) == message
  else:
    raise AssertionError('comparison failure was swallowed')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_captured_subject_survives_rebinding_and_observes_object_mutation(self):
    source = '''variabel selector: desimal = 1;
variabel values: apapun = [1];
fungsi rebind(): desimal { selector = 2; hasilkan 1; }
fungsi mutate(): apapun { values[0] = 2; hasilkan [0]; }
fungsi utama(): kosong {
  cocokkan (selector) { kasus rebind() { tampilkan(selector); } selainnya { tampilkan("wrong"); } }
  cocokkan (values) { kasus mutate() {} kasus [2] { tampilkan("|", values); } }
}'''
    assert_program_result(run_compiled(source, module_name="__main__"), "2|[2]")

  def test_later_candidates_read_current_named_and_namespace_imports(self):
    files = {
      "state.pyind": '''variabel choice: desimal = 2;
fungsi change(): desimal { choice = 3; hasilkan 0; }''',
      "main.pyind": '''dari "state.pyind" impor choice sebagai current, change;
impor "state.pyind" sebagai state;
fungsi utama(): kosong {
  cocokkan (3) { kasus change(), current { tampilkan("A"); } }
  cocokkan (3) { kasus state.choice { tampilkan("N"); } }
}''',
    }
    assert_program_result(run_project(files, module_name="__main__"), "AN")

  def test_nested_switches_preserve_loop_stack_and_exit_targets(self):
    source = '''fungsi probe(): desimal {
  variabel total: desimal = 0;
  untuk (variabel index: desimal = 0; index < 4; index++) {
    cocokkan (index) { kasus 0 { lewati; } kasus 3 { berhenti; } selainnya { total += index; } }
  }
  variabel turns: desimal = 0;
  selama (turns < 3) {
    turns++;
    cocokkan (turns) { kasus 1 { lewati; } kasus 2 { total += 10; } selainnya { berhenti; } }
  }
  untuk (variabel row: himpunan<desimal> didalam [[1, 2], [3, 4]]) {
    untuk (variabel item: desimal didalam row) {
      cocokkan (item) {
        kasus 1 {}
        kasus 2 { lewati; }
        kasus 3 { cocokkan (item) { kasus 3 { lewati; } } }
        selainnya { berhenti; }
      }
      total += 100;
    }
  }
  hasilkan total;
}
fungsi no_match(): desimal {
  variabel total: desimal = 0;
  untuk (variabel item: desimal didalam [1, 2]) { cocokkan (item) { kasus 99 {} } total += item; }
  hasilkan total;
}
fungsi utama(): kosong {}'''
    assertions = '''assert namespace['probe']() == 113
assert namespace['no_match']() == 3
assert namespace['probe'].__code__.co_varnames == ('total', 'index', 'turns', 'row', 'item')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_returns_preserve_identity_through_nested_iterator_switches(self):
    source = '''fungsi find(values: himpunan<apapun>): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [1, 2]) {
      cocokkan (inner) {
        kasus 1 { lewati; }
        selainnya { cocokkan (inner) { kasus 2 { hasilkan item; } } }
      }
    }
  }
  hasilkan;
}
fungsi utama(): kosong {}'''
    assertions = "marker = object()\nassert namespace['find']([marker]) is marker\nassert namespace['find']([]) is None"
    assert_program_result(run_compiled(source, assertions), "")

  def test_logical_and_conditional_candidates_preserve_iterator_stack_prefix(self):
    source = '''fungsi utama(): kosong {
  untuk (variabel item: desimal didalam [-1, 0, 1, 2]) {
    cocokkan (item) {
      kasus (0 atau item) jika item > 0 selainnya (item dan -1) { tampilkan(item); }
      selainnya { tampilkan("wrong"); }
    }
  }
}'''
    assert_program_result(run_compiled(source, module_name="__main__"), "-1012")

  def test_candidate_failure_inside_iterator_skips_bodies_and_following_code(self):
    source = '''fungsi fail(): kosong {
  untuk (variabel item: desimal didalam [1, 2]) {
    cocokkan (item) { kasus 1 / 0 { tampilkan("body"); } selainnya { tampilkan("fallback"); } }
  }
  tampilkan("after");
}
fungsi utama(): kosong {}'''
    assertions = '''try:
  namespace['fail']()
except ZeroDivisionError:
  pass
else:
  raise AssertionError('candidate failure was lost inside the iterator')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_selected_body_releases_the_captured_subject_before_running(self):
    source = '''variabel held: apapun = tampilkan();
fungsi clear(): desimal { held = tampilkan(); hasilkan 1; }
fungsi pick(): desimal {
  cocokkan (held) { kasus clear() { tampilkan("B"); hasilkan 1; } selainnya { hasilkan 0; } }
}
fungsi utama(): kosong {}'''
    assertions = '''class Subject:
  def __eq__(self, other):
    return True
  def __del__(self):
    print('D', end='')
namespace['held'] = Subject()
assert namespace['pick']() == 1
'''
    assert_program_result(run_compiled(source, assertions), "DB")

  def test_switch_bodies_retain_store_snapshot_and_initialization_contracts(self):
    source = '''variabel total: desimal = 3;
konstanta saved: apapun = [1];
variabel initialized: desimal = choose(1);
fungsi choose(value: desimal): desimal {
  cocokkan (value) { kasus 1 { hasilkan 4; } selainnya { hasilkan 0; } }
}
fungsi store(value: apapun): kosong { cocokkan (1) { kasus 1 { total = value; } } }
fungsi mutate(value: apapun): kosong { cocokkan (1) { kasus 1 { value[0] = 2; } } }
fungsi utama(): kosong {}'''
    assertions = '''for name, value in [('store', True), ('mutate', namespace['saved'])]:
  try:
    namespace[name](value)
  except TypeError:
    pass
  else:
    raise AssertionError('switch bypassed a value contract')
assert namespace['total'] == 3 and list(namespace['saved']) == [1]
assert namespace['initialized'] == 4
'''
    assert_program_result(run_compiled(source, assertions), "")
    early = '''variabel first: desimal = choose();
variabel later: desimal = 1;
fungsi choose(): desimal { cocokkan (1) { kasus later { hasilkan 1; } selainnya { hasilkan 2; } } }
fungsi utama(): kosong {}'''
    completed = run_source(early)
    self.assertEqual(completed.returncode, 1)
    self.assertIn("Module binding 'later' is not initialized", completed.stderr)

  def test_complete_example_through_facades_and_marshal(self):
    script = f'''import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
source = {SWITCH_PROGRAM!r}
for api in ('direct', 'legacy', 'sentinel'):
  if api == 'direct':
    code = compile_source(source, filename='switch.pyind')
  else:
    instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename='switch.pyind')
    assert [chunk.co_name for chunk in chunks] == ['uraikan', 'utama']
    code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
  exec(marshal.loads(marshal.dumps(code)), {{'__name__': '__main__'}})
'''
    assert_program_result(run_python(script), SWITCH_OUTPUT * 3)

  def test_dependency_comparison_locations_survive_facades_marshal_and_source_removal(self):
    library = '''fungsi pick(subject: apapun, candidate: apapun): desimal {
  cocokkan (subject) {
    kasus ("café" jika salah selainnya candidate) { tampilkan("M"); hasilkan 1; }
    selainnya { tampilkan("F"); hasilkan 0; }
  }
}'''
    script = f'''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
library = {library!r}
candidate_line = library.splitlines()[2]
start_column = len(candidate_line[:candidate_line.index('"café"')].encode('utf-8'))
end_column = len(candidate_line[:candidate_line.index('candidate') + len('candidate')].encode('utf-8'))
class BadTruth:
  def __bool__(self):
    raise RuntimeError('truth failure')
class Subject:
  def __init__(self, fail_equality):
    self.fail_equality = fail_equality
  def __eq__(self, other):
    if self.fail_equality:
      raise RuntimeError('equality failure')
    return BadTruth()
for api in ('direct', 'legacy', 'sentinel'):
  with tempfile.TemporaryDirectory() as directory:
    entry = write_project(Path(directory), {{
      'café.pyind': library,
      'main.pyind': 'impor "café.pyind" sebagai lib; fungsi call(subject: apapun, candidate: apapun): desimal {{ hasilkan lib.pick(subject, candidate); }} fungsi utama(): kosong {{}}',
    }})
    source = entry.read_text(encoding='utf-8')
    dependency_name = str(entry.parent / 'café.pyind')
    if api == 'direct':
      code = compile_source(source, filename=str(entry))
    else:
      instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename=str(entry))
      code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
    code = marshal.loads(marshal.dumps(code))
    for path in entry.parent.glob('*.pyind'):
      path.unlink()
    namespace = {{'__name__': 'inspection'}}
    exec(code, namespace)
    assert namespace['call'](1, 1) == 1
    assert namespace['lib'].pick.__code__.co_filename == dependency_name
    if api != 'direct':
      assert namespace['call'].__code__.co_filename == 'renamed.pyind'
    for fail_equality, message in ((True, 'equality failure'), (False, 'truth failure')):
      try:
        namespace['call'](Subject(fail_equality), 1)
      except RuntimeError as error:
        assert str(error) == message
        locations = []
        trace = error.__traceback__
        while trace is not None:
          frame_code = trace.tb_frame.f_code
          if frame_code.co_filename == dependency_name:
            positions = list(frame_code.co_positions())
            locations.append(positions[trace.tb_lasti // 2])
          trace = trace.tb_next
        assert locations == [(3, 3, start_column, end_column)], locations
      else:
        raise AssertionError('case comparison did not fail')
'''
    assert_program_result(run_python(script), "MMM")

  def test_cli_options_arguments_status_and_dependency_failure_positions(self):
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "library.pyind": SWITCH_PROGRAM,
        "main.pyind": '''impor "library.pyind" sebagai library;
fungsi utama(args: himpunan<campuran>, count: desimal): desimal {
  cocokkan (count) {
    kasus 2 { tampilkan(count, "|", args[1], "|", library.uraikan(201)); hasilkan 7; }
    selainnya { hasilkan 8; }
  }
}''',
      })
      library = entry.parent / "library.pyind"
      original = library.read_bytes()
      for options in ((), ("-O",), ("-D",)):
        with self.subTest(options=options):
          assert_program_result(run_program(entry, options, program_arguments=["halo"]), "2|halo|berhasil", 7)
          self.assertEqual(library.read_bytes(), original)
      listing = entry.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn(str(library), listing)
      self.assertIn("uraikan", listing)

      library.write_text('''fungsi fail(): desimal {
  tampilkan("A");
  cocokkan (1) { kasus 1 / 0 { hasilkan 1; } selainnya { hasilkan 2; } }
}''', encoding="utf-8")
      entry.write_text('impor "library.pyind" sebagai library; fungsi utama(): kosong { library.fail(); tampilkan("wrong"); }', encoding="utf-8")
      for options in ((), ("-O",), ("-D",)):
        with self.subTest(failure_options=options):
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 1)
          self.assertEqual(completed.stdout, "A")
          self.assertIn('library.pyind", line 3', completed.stderr)
          self.assertIn("ZeroDivisionError", completed.stderr)
      library.write_text('''fungsi fail(): desimal {
  cocokkan (1) {
    kasus 1 { tampilkan("B"); variabel wrong: desimal = benar; hasilkan 0; }
    selainnya { hasilkan 0; }
  }
}''', encoding="utf-8")
      for options in ((), ("-O",), ("-D",)):
        with self.subTest(body_failure_options=options):
          completed = run_program(entry, options)
          self.assertEqual(completed.returncode, 1)
          self.assertEqual(completed.stdout, "B")
          self.assertIn('library.pyind", line 3', completed.stderr)
          self.assertIn("TypeError", completed.stderr)
      entry.write_text("fungsi utama(): kosong { cocokkan (1) {} }", encoding="utf-8")
      completed = run_program(entry)
      self.assertEqual(completed.returncode, 70)
      self.assertEqual(completed.stderr, "")
      self.assertIn("kasus", completed.stdout)
