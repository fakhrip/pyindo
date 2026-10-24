import tempfile
import unittest
from pathlib import Path

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Binary, Conditional, Logical, NonEmpty, Unary
from pyindo.resolver import FunctionSignature, ValueBinding, analyze_program
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_program, run_python, run_source
from tests.test_language import run_compiled
from tests.test_modules import run_project, write_project


COMPARISON_PROGRAM = '''fungsi utama(): kosong {
  variabel nilai: desimal = 7;
  konstanta dilarang: himpunan<desimal> = [0, 13];

  tampilkan(0 < nilai < 10, "|", nilai tidak didalam dilarang, "|", 3 > 2 > 5);
}
'''
COMPARISON_OUTPUT = "True|True|False"


class ComparisonSyntaxTests(unittest.TestCase):
  def expression(self, text):
    """
    Parse an expression without assembling or executing its new bytecode.
    """

    return parse_module(f"fungsi utama(): apapun {{ hasilkan {text}; }}").functions[0].body[0].value

  def test_chain_nodes_preserve_links_and_grouping(self):
    chain = self.expression("a < b <= c")
    self.assertEqual(type(chain).__name__, "ComparisonChain")
    self.assertEqual(chain.first.identifier, "a")
    self.assertEqual([link.operator for link in chain.comparisons], ["<", "<="])
    self.assertEqual([link.operand.identifier for link in chain.comparisons], ["b", "c"])
    self.assertIsInstance(self.expression("a < b"), Binary)
    self.assertIsInstance(self.expression("(a < b) < c").left, Binary)
    self.assertIsInstance(self.expression("a < (b < c)").right, Binary)
    grouped = self.expression("(a < b < c) == d == e")
    self.assertEqual(type(grouped.first).__name__, "ComparisonChain")
    self.assertEqual(len(grouped.comparisons), 2)
    self.assertEqual(len(self.expression("a < b > c != d").comparisons), 3)

  def test_aliases_negated_membership_and_precedence(self):
    chain = self.expression("a adalah b bukan c didalam d tidak didalam e")
    self.assertEqual([link.operator for link in chain.comparisons], ["==", "!=", "in", "not in"])
    for phrase in ("tidak didalam", "tidak /* comment */ didalam", "tidak\n// comment\ndidalam"):
      with self.subTest(phrase=phrase):
        value = self.expression(f"a {phrase} b")
        self.assertIsInstance(value, Binary)
        self.assertEqual(value.operator, "not in")
    value = self.expression("tidak -2 ** 2 < a + 3 < b dan c atau d")
    self.assertIsInstance(value, Logical)
    self.assertIsInstance(value.left.left, Unary)
    self.assertEqual(value.left.left.operand.first.operator, "-")
    self.assertEqual(self.expression("tidak a tidak didalam b").operand.operator, "not in")
    value = self.expression("a < b < c jika d < e < f selainnya g < h < i")
    self.assertIsInstance(value, Conditional)
    for child in (value.true_value, value.condition, value.false_value):
      self.assertEqual(len(child.comparisons), 2)
    for text in ("f(a < b < c, [a < b < c][0])", '"${a < b < c}"', "values[a < b < c]"):
      self.expression(text)
    parse_module("variabel value: logika = 0 < 1 < 2; fungsi utama(): kosong { cocokkan (value) { kasus 0 < 1 < 2 {} } }")

  def test_predicate_boundaries_and_malformed_chains_are_located(self):
    for text in (
      "a <", "a < < b", "a tidak didalam", "a tidak b", "a ! didalam b", "a tidak adalah b",
      "a < b tidak kosong", "a tidak kosong == benar", "a tidak kosong tidak kosong",
      "a tidak kosong()", "a tidak kosong[0]", "a tidak kosong + 1", "a tidak kosongkan",
    ):
      with self.subTest(text=text), self.assertRaises(PyIndoError) as raised:
        self.expression(text)
      self.assertIsNotNone(raised.exception.span)
    self.assertIsInstance(self.expression("(a < b) tidak kosong"), NonEmpty)
    self.assertIsInstance(self.expression("(a tidak kosong) == benar").left, NonEmpty)
    self.assertEqual(self.expression("a didalam b == c").comparisons[0].operator, "in")
    self.assertEqual(self.expression("a < b didalam c").comparisons[1].operator, "in")
    self.assertEqual(self.expression("a tidak didalam kosong()").right.callee, "kosong")
    self.assertEqual(self.expression("tidak_sama tidak didalam kosong").left.identifier, "tidak_sama")
    for suffix in ("a <", "a tidak didalam", "a < b <"):
      source = "fungsi utama(): apapun { hasilkan " + suffix
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError) as raised:
        parse_module(source)
      self.assertEqual(raised.exception.span.start, len(source))

  def test_chain_and_link_spans_keep_crlf_and_unicode(self):
    source = 'fungsi utama(): apapun { hasilkan "café ☕ ${a < b tidak /* é */\r\ndidalam c}"; }'
    chain = parse_module(source).functions[0].body[0].value.parts[1]
    slices = [source[link.span.start:link.span.end] for link in chain.comparisons]
    self.assertEqual(slices, ["a < b", "b tidak /* é */\r\ndidalam c"])
    self.assertEqual(source[chain.span.start:chain.span.end], "a < b tidak /* é */\r\ndidalam c")
    self.assertEqual(chain.comparisons[1].span.end_line, 2)

  def test_skipped_operands_still_receive_static_checks(self):
    for text in ("3 < 2 < missing", "3 < 2 < unknown()", "3 < 2 < helper()", "3 < 2 < later"):
      source = f"fungsi helper(value: apapun): apapun {{ hasilkan value; }} fungsi utama(): apapun {{ hasilkan {text}; variabel later: desimal = 1; }}"
      with self.subTest(text=text), self.assertRaises(PyIndoError):
        analyze_program(parse_module(source))
    with self.assertRaisesRegex(PyIndoError, "missing_first"):
      analyze_program(parse_module("fungsi utama(): apapun { hasilkan missing_first < missing_second < missing_last; }"))
    program = parse_module("fungsi utama(): apapun { hasilkan 3 < 2 < state.helper(); }")
    with self.assertRaisesRegex(PyIndoError, "expects 1 arguments"):
      analyze_program(program, imported_signatures={"state.helper": FunctionSignature("helper", ["value"], program.span)}, namespace_names={"state"})
    program = parse_module("variabel local: desimal = 1; fungsi utama(): apapun { hasilkan local < imported < state.value; }")
    binding = ValueBinding("value", "desimal", False, program.span)
    analyze_program(program, imported_values={"imported": binding, "state.value": binding}, namespace_names={"state"})
    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module("variabel first: logika = 3 < 2 < later; variabel later: desimal = 1; fungsi utama(): kosong {}"))

  def test_long_flat_chains_and_nested_complexity_keep_diagnostics(self):
    program = parse_module("fungsi utama(): apapun { hasilkan " + " < ".join(map(str, range(301))) + "; }")
    self.assertEqual(len(program.functions[0].body[0].value.comparisons), 300)
    analyze_program(program)
    with self.assertRaisesRegex(PyIndoError, "complexity exceeds compiler limit") as raised:
      self.expression("(" * 1200 + "1" + ")" * 1200)
    self.assertIsNotNone(raised.exception.span)


class ComparisonExecutionTests(unittest.TestCase):
  def test_operands_run_once_left_to_right_and_skip_later_links(self):
    for values, expected in (([1, 2, 3], "ABCTrue"), ([3, 2, 1], "ABFalse"),
                             ([1, 2, 1, 4], "ABCFalse"), ([1, 2, 3, 0], "ABCDFalse")):
      expression = " < ".join(f'mark("{label}", {value})' for label, value in zip("ABCD", values))
      source = f'''fungsi mark(label: campuran, value: desimal): desimal {{ tampilkan(label); hasilkan value; }}
fungsi utama(): kosong {{ tampilkan({expression}); }}'''
      with self.subTest(values=values):
        assert_program_result(run_source(source), expected)
    assert_program_result(run_source("fungsi utama(): kosong { tampilkan(3 < 2 < 1 / 0); }"), "False")
    long_chain = " < ".join(map(str, range(301)))
    assert_program_result(run_source(f"fungsi utama(): kosong {{ tampilkan({long_chain}); }}"), "True")

  def test_mixed_comparisons_aliases_and_negated_membership(self):
    pairs = (
      ("1 < 2 didalam [2]", "1 < 2 in [2]"),
      ("1 didalam [1] == [1]", "1 in [1] == [1]"),
      ("1 adalah 1 bukan 2 <= 3 > 0 >= 0", "1 == 1 != 2 <= 3 > 0 >= 0"),
      ('"é" didalam "café" tidak didalam ["tea"]', '"é" in "café" not in ["tea"]'),
      ("[1] == checked == frozen", "[1] == checked == frozen"),
      ("(1 < 2) < 3", "(1 < 2) < 3"), ("1 < (2 < 3)", "1 < (2 < 3)"),
      ("a == a == a", "a == a == a"), ("a != a != a", "a != a != a"),
      ("benar == 1 < 2", "True == 1 < 2"),
    )
    source = "variabel checked: himpunan<desimal> = [1]; konstanta frozen: himpunan<desimal> = checked;\n"
    source += "\n".join(f"fungsi probe_{index}(a: apapun): apapun {{ hasilkan {text}; }}" for index, (text, _) in enumerate(pairs))
    source += "\nfungsi utama(): kosong {}"
    assertions = f'''references = {[reference for _, reference in pairs]!r}
for value in (1, float('nan')):
  for index, reference in enumerate(references):
    expected = eval(reference, {{}}, dict(a=value, checked=[1], frozen=[1]))
    actual = namespace[f'probe_{{index}}'](value)
    assert type(actual) is bool and actual is expected, (reference, value)
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_negated_membership_preserves_protocols_order_and_errors(self):
    source = '''fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi probe(item: apapun, values: apapun): logika { hasilkan mark("I", item) tidak didalam mark("C", values); }
fungsi chain(item: apapun, values: apapun): apapun { hasilkan item tidak didalam values < 1 / 0; }
fungsi utama(): kosong {}'''
    assertions = '''events = []
class Truth:
  def __bool__(self):
    events.append('truth')
    return True
class Contains:
  def __contains__(self, item):
    events.append(('contains', item))
    return Truth()
class Iterates:
  def __iter__(self):
    yield 1
    yield 2
assert namespace['probe'](2, Contains()) is False
assert events == [('contains', 2), 'truth']
assert namespace['probe'](2, Iterates()) is False
assert namespace['probe'](3, Iterates()) is True
assert namespace['chain'](2, [2]) is False
class Fails:
  def __contains__(self, item):
    raise RuntimeError('contains')
class BadTruth:
  def __bool__(self):
    raise RuntimeError('truth')
class ContainsBadTruth:
  def __contains__(self, item):
    return BadTruth()
class BadIterator:
  def __iter__(self):
    raise RuntimeError('iterator')
for container, message in [(Fails(), 'contains'), (ContainsBadTruth(), 'truth'), (BadIterator(), 'iterator')]:
  try:
    namespace['probe'](1, container)
  except RuntimeError as error:
    assert str(error) == message
  else:
    raise AssertionError('membership error swallowed')
'''
    assert_program_result(run_compiled(source, assertions), "IC" * 6)

  def test_raw_chain_returns_the_original_comparison_result(self):
    source = '''fungsi probe(a: apapun, b: apapun, c: apapun, d: apapun): apapun { hasilkan a < b < c < d; }
fungsi reflect(a: apapun, b: apapun, c: apapun): apapun { hasilkan a < b < c; }
fungsi utama(): kosong {}'''
    assertions = '''events = []
class Truth:
  def __init__(self, answer):
    self.answer, self.calls = answer, 0
  def __bool__(self):
    self.calls += 1
    assert self.calls == 1
    return self.answer
class Untested:
  def __bool__(self):
    raise AssertionError('final raw result was tested')
class Item:
  def __init__(self, result):
    self.result = result
  def __lt__(self, other):
    events.append(self)
    return self.result
first, middle, final = Truth(True), Truth(False), Untested()
a, b, c, d = Item(first), Item(middle), Item(final), object()
assert namespace['probe'](a, b, c, d) is middle
assert events == [a, b] and (first.calls, middle.calls) == (1, 1)
events.clear()
first, middle = Truth(True), Truth(True)
a, b = Item(first), Item(middle)
assert namespace['probe'](a, b, c, d) is final
assert events == [a, b, c]
class Base:
  def __lt__(self, other):
    raise AssertionError('subclass reflection lost priority')
class Sub(Base):
  def __gt__(self, other):
    return True
  def __lt__(self, other):
    return final
assert namespace['reflect'](Base(), Sub(), object()) is final
assert namespace['probe'].__code__.co_varnames == ('a', 'b', 'c', 'd')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_truth_context_matrix_matches_native_cpython(self):
    chain = "a < b < c"
    variants = [
      (chain, chain), (f"tidak ({chain})", f"not ({chain})"),
      (f"({chain}) dan d", f"({chain}) and d"), (f"({chain}) atau d", f"({chain}) or d"),
      (f"({chain}) jika flag selainnya d", f"({chain}) if flag else d"),
      (f"d jika flag selainnya ({chain})", f"d if flag else ({chain})"),
      (f"(({chain}) jika flag selainnya d) dan d", f"(({chain}) if flag else d) and d"),
      (f"(d jika flag selainnya ({chain})) atau d", f"(d if flag else ({chain})) or d"),
      (f"({chain}) dan d atau a", f"({chain}) and d or a"),
    ]
    cases = []
    for expression, reference in variants:
      cases.append((f"hasilkan {expression};", reference))
      for predicate, native in ((expression, reference), (f"tidak ({expression})", f"not ({reference})")):
        cases.extend([
          (f"jika ({predicate}) {{ hasilkan benar; }} hasilkan salah;", f"True if ({native}) else False"),
          (f"selama ({predicate}) {{ hasilkan benar; }} hasilkan salah;", f"True if ({native}) else False"),
          (f"untuk (; {predicate};) {{ hasilkan benar; }} hasilkan salah;", f"True if ({native}) else False"),
        ])
    source = "\n".join(f"fungsi probe_{index}(a: apapun, b: apapun, c: apapun, d: apapun, flag: logika): apapun {{ {body} }}" for index, (body, _) in enumerate(cases))
    source += "\nfungsi utama(): kosong {}"
    assertions = f'''from itertools import product
references = {[reference for _, reference in cases]!r}
def make_values(initial):
  events = []
  class Truth:
    def __init__(self, name, answer):
      self.name, self.answer, self.calls = name, answer, 0
    def __bool__(self):
      self.calls += 1
      events.append(('truth', self.name, self.calls))
      return self.answer if self.calls == 1 else not self.answer
  class Item:
    def __init__(self, name, result):
      self.name, self.result = name, result
    def __lt__(self, other):
      events.append(('compare', self.name, other.name))
      return self.result
  results = [Truth('first', initial[0]), Truth('last', initial[1])]
  values = [Item('a', results[0]), Item('b', results[1]), Item('c', None), Truth('d', initial[2])]
  return values, results, events
for index, reference in enumerate(references):
  for initial in product((False, True), repeat=3):
    for flag in (False, True):
      expected_values, expected_results, expected_events = make_values(initial)
      actual_values, actual_results, actual_events = make_values(initial)
      expected = eval(reference, {{}}, dict(zip('abcd', expected_values), flag=flag))
      actual = namespace[f'probe_{{index}}'](*actual_values, flag)
      if type(expected) is bool:
        assert actual is expected, (reference, initial, flag)
      else:
        choices = expected_values + expected_results
        position = next(i for i, value in enumerate(choices) if value is expected)
        assert actual is (actual_values + actual_results)[position], (reference, initial, flag)
      assert actual_events == expected_events, (reference, initial, flag, actual_events, expected_events)
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_retained_middle_and_live_later_operands_keep_timing(self):
    files = {
      "state.pyind": '''variabel middle: apapun = 2;
variabel last: apapun = 0;
fungsi change(): desimal { middle = 99; last = 4; hasilkan 1; }''',
      "main.pyind": '''impor "state.pyind" sebagai state;
dari "state.pyind" impor last;
fungsi probe(first: apapun): apapun { hasilkan first < state.middle < state.change() + last; }
fungsi utama(): kosong {}''',
    }
    assertions = '''class First:
  def __lt__(self, other):
    assert other == 2
    namespace['state'].middle = 50
    return True
assert namespace['probe'](First()) is True
assert namespace['state'].middle == 99 and namespace['state'].last == 4
'''
    assert_program_result(run_project(files, assertions), "")
    source = "fungsi probe(a: apapun, b: apapun, c: apapun): apapun { hasilkan a < b < c; } fungsi utama(): kosong {}"
    assertions = '''events = []
class Middle:
  def __init__(self):
    self.value = 1
  def __lt__(self, other):
    events.append(self.value)
    return self.value < other
class First:
  def __lt__(self, other):
    other.value = 2
    return True
middle = Middle()
assert namespace['probe'](First(), middle, 3) is True
assert events == [2]
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_chain_stack_prefixes_survive_every_exit(self):
    source = '''variabel held: apapun = 0;
fungsi choose(value: apapun, other: apapun): apapun { hasilkan value; }
fungsi take(): apapun { variabel captured: apapun = held; held = 0; hasilkan captured; }
fungsi released(): kosong { jika (0 < take() < 3) { tampilkan("wrong"); } selainnya { tampilkan("B"); } }
fungsi switch_value(a: apapun, b: apapun, c: apapun, expected: apapun): logika {
  cocokkan (expected) { kasus a < b < c { hasilkan benar; } selainnya { hasilkan salah; } }
}
fungsi probe(a: desimal, b: desimal, c: desimal): campuran {
  variabel result: logika = a < b < c;
  variabel values: himpunan<apapun> = [9, a < b < c];
  values[(a < b < c) + 0] = choose(a < b < c, 7);
  cocokkan (a < b < c) { kasus a < b < c {} selainnya { tampilkan("wrong"); } }
  hasilkan "${result}|${values}|${10 + (a < b < c)}";
}
fungsi utama(): kosong {}'''
    assertions = '''assert namespace['probe'](1, 2, 3) == 'True|[9, True]|11'
assert namespace['probe'](3, 2, 1) == 'False|[False, False]|10'
assert namespace['probe'](1, 3, 2) == 'False|[False, False]|10'
assert namespace['probe'].__code__.co_varnames == ('a', 'b', 'c', 'result', 'values')
class Raw:
  def __bool__(self):
    raise AssertionError('switch candidate was coerced')
class Item:
  def __init__(self, result):
    self.result = result
  def __lt__(self, other):
    return self.result
class Expected:
  def __eq__(self, other):
    assert other is raw
    return True
raw = Raw()
assert namespace['switch_value'](Item(True), Item(raw), object(), Expected()) is True
class Temporary:
  def __gt__(self, other):
    return False
  def __del__(self):
    print('D', end='')
namespace['held'] = Temporary()
namespace['released']()
'''
    assert_program_result(run_compiled(source, assertions), "DB")

  def test_nested_iterator_conditions_returns_breaks_and_continues(self):
    source = '''fungsi find(values: himpunan<apapun>): apapun {
  untuk (variabel item: apapun didalam values) {
    untuk (variabel inner: desimal didalam [0, 1, 2]) {
      cocokkan (inner) {
        kasus 0 { jika (0 < inner < 3) { berhenti; } lewati; }
        kasus 1 { jika (tidak (0 < inner < 3)) { berhenti; } hasilkan item; }
        selainnya { berhenti; }
      }
    }
  }
  hasilkan;
}
fungsi count(): desimal {
  variabel total: desimal = 0;
  untuk (variabel index: desimal = 0; -1 < index < 4; index++) { jika (0 < index < 3) { total += index; lewati; } }
  selama (0 < total < 5) { total++; }
  hasilkan total;
}
fungsi middle_failure(negated: logika): desimal {
  variabel total: desimal = 0;
  untuk (variabel item: desimal didalam [-1, 0, 1, 2, 3, 4]) {
    jika ((0 < 1 < item < 4) jika tidak negated selainnya tidak (0 < 1 < item < 4)) {
      total += item;
    }
  }
  hasilkan total;
}
fungsi fail(): kosong {
  untuk (variabel row: apapun didalam [[1]]) {
    untuk (variabel item: apapun didalam row) { jika (0 < 1 / 0 < 2) { tampilkan("wrong"); } }
  }
}
fungsi utama(): kosong {}'''
    assertions = '''marker = object()
assert namespace['find']([marker]) is marker
assert namespace['find']([]) is None
assert namespace['count']() == 5
assert namespace['middle_failure'](False) == 5
assert namespace['middle_failure'](True) == 4
try:
  namespace['fail']()
except ZeroDivisionError:
  pass
else:
  raise AssertionError('operand failure was swallowed')
'''
    assert_program_result(run_compiled(source, assertions), "")

  def test_existing_type_constant_and_module_guards_remain_enforced(self):
    source = '''variabel saved: logika = benar;
konstanta frozen: himpunan<desimal> = [1];
variabel initialized: logika = probe(1, 2, 3);
fungsi probe(a: apapun, b: apapun, c: apapun): apapun { hasilkan a < b < c; }
fungsi store(a: apapun, b: apapun, c: apapun): kosong { saved = a < b < c; }
fungsi mutate(): kosong { variabel alias: apapun = frozen; alias[0] = 2; }
fungsi utama(): kosong {}'''
    assertions = '''class Result:
  def __bool__(self):
    return False
class Item:
  def __lt__(self, other):
    return result
result = Result()
assert namespace['probe'](Item(), object(), object()) is result
for name, arguments in [('store', (Item(), object(), object())), ('mutate', ())]:
  try:
    namespace[name](*arguments)
  except TypeError:
    pass
  else:
    raise AssertionError('existing contract was bypassed')
assert namespace['saved'] is True and namespace['initialized'] is True
assert list(namespace['frozen']) == [1]
'''
    assert_program_result(run_compiled(source, assertions), "")
    early = "variabel first: apapun = probe(); variabel later: desimal = 2; fungsi probe(): apapun { hasilkan 0 < later < 3; } fungsi utama(): kosong {}"
    completed = run_source(early)
    self.assertEqual(completed.returncode, 1)
    self.assertIn("Module binding 'later' is not initialized", completed.stderr)

  def test_readme_program_runs_through_every_compiler_facade(self):
    script = f'''import marshal
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
source = {COMPARISON_PROGRAM!r}
for api in ('direct', 'legacy', 'sentinel'):
  if api == 'direct':
    code = compile_source(source, filename='comparisons.pyind')
  else:
    instructions, chunks = parse_program(source + ('\\0' if api == 'sentinel' else ''), filename='comparisons.pyind')
    assert [chunk.co_name for chunk in chunks] == ['utama']
    code = compile_bytecodes(instructions, filename='renamed.pyind').to_code()
  exec(marshal.loads(marshal.dumps(code)), {{'__name__': '__main__'}})
'''
    assert_program_result(run_python(script), COMPARISON_OUTPUT * 3)
    self.assertIn(COMPARISON_PROGRAM.rstrip(), Path("README.md").read_text(encoding="utf-8"))

  def test_dependency_chain_failures_keep_link_positions_after_marshal(self):
    library = '''fungsi raw(a: apapun, b: apapun, c: apapun): apapun {
  /* café ☕ */ hasilkan a <
    b <
    c;
}
fungsi truth(a: apapun, b: apapun, c: apapun): logika {
  /* café ☕ */ jika (a <
    b <
    c) { hasilkan benar; } hasilkan salah;
}
fungsi contains(item: apapun, values: apapun): logika {
  /* café ☕ */ hasilkan item tidak
    didalam values;
}
fungsi operand(): apapun {
  /* café ☕ */ hasilkan 0 < 1 <
    1 / 0;
}'''
    script = f'''import marshal
import tempfile
from pathlib import Path
from pyindo.compiler import compile_source, compile_bytecodes
from pyindo.parser import parse_program
from tests.test_modules import write_project
library = {library!r}
lines = library.splitlines()
raw_start = len(lines[1][:lines[1].index('a <')].encode('utf-8'))
truth_start = len(lines[6][:lines[6].index('a <')].encode('utf-8'))
contains_start = len(lines[11][:lines[11].index('item tidak')].encode('utf-8'))
class BadTruth:
  def __bool__(self):
    raise RuntimeError('truth')
class Item:
  def __init__(self, result=True):
    self.result = result
  def __lt__(self, other):
    return self.result
class Broken:
  def __lt__(self, other):
    raise RuntimeError('compare')
class BadContains:
  def __contains__(self, item):
    raise RuntimeError('contains')
for api in ('direct', 'legacy', 'sentinel'):
  with tempfile.TemporaryDirectory() as directory:
    entry = write_project(Path(directory), {{
      'café.pyind': library,
      'main.pyind': 'impor "café.pyind" sebagai lib; fungsi call(a: apapun, b: apapun, c: apapun): apapun {{ hasilkan lib.raw(a, b, c); }} fungsi utama(): kosong {{}}',
    }})
    dependency_name = str(entry.parent / 'café.pyind')
    source = entry.read_text(encoding='utf-8')
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
    lib = namespace['lib']
    assert namespace['call'](1, 2, 3) is True
    assert lib.truth(1, 2, 3) is True and lib.contains(2, [1]) is True
    assert lib.raw.__code__.co_filename == dependency_name
    if api != 'direct':
      assert namespace['call'].__code__.co_filename == 'renamed.pyind'
    cases = [
      (namespace['call'], (Broken(), Item(), object()), RuntimeError, (2, 3, raw_start, 5)),
      (namespace['call'], (Item(), Broken(), object()), RuntimeError, (3, 4, 4, 5)),
      (namespace['call'], (Item(BadTruth()), Broken(), object()), RuntimeError, (2, 3, raw_start, 5)),
      (lib.truth, (Item(BadTruth()), Broken(), object()), RuntimeError, (7, 8, truth_start, 5)),
      (lib.truth, (Item(), Item(BadTruth()), object()), RuntimeError, (8, 9, 4, 5)),
      (lib.contains, (1, BadContains()), RuntimeError, (12, 13, contains_start, 18)),
      (lib.operand, (), ZeroDivisionError, (17, 17, 4, 9)),
    ]
    for function, arguments, exception, expected in cases:
      try:
        function(*arguments)
      except exception as error:
        locations = []
        trace = error.__traceback__
        while trace is not None:
          frame_code = trace.tb_frame.f_code
          if frame_code.co_filename == dependency_name:
            locations.append(list(frame_code.co_positions())[trace.tb_lasti // 2])
          trace = trace.tb_next
        assert locations == [expected], (function.__name__, locations, expected)
      else:
        raise AssertionError('chain failure was swallowed')
'''
    assert_program_result(run_python(script), "")

  def test_cli_flags_arguments_statuses_debug_and_failures(self):
    options_list = ((), ("-O",), ("-D",))
    with tempfile.TemporaryDirectory() as directory:
      entry = write_project(Path(directory), {
        "library.pyind": "fungsi value(n: desimal): logika { hasilkan 0 < n < 10; }",
        "main.pyind": '''impor "library.pyind" sebagai library;
fungsi utama(argv: himpunan<campuran>, argc: desimal): desimal {
  tampilkan(argc == 3, "|", argv[1] tidak didalam ["bad"], "|", library.value(argc));
  hasilkan 7;
}''',
      })
      library = entry.parent / "library.pyind"
      original = library.read_bytes()
      for options in options_list:
        with self.subTest(options=options):
          assert_program_result(run_program(entry, options, program_arguments=["hello", "world"]), "True|True|True", 7)
          self.assertEqual(library.read_bytes(), original)
      listing = entry.with_suffix(".dis").read_text(encoding="utf-8")
      self.assertIn(str(library), listing)
      self.assertIn("CONTAINS_OP", listing)
      entry.write_text('impor "library.pyind" sebagai library; fungsi utama(): kosong { library.fail(); tampilkan("wrong"); }', encoding="utf-8")
      for expression, exception in (('1 < 2 < "x"', "TypeError"), ("0 < 1 < 1 / 0", "ZeroDivisionError"), ("1 tidak didalam 2", "TypeError")):
        library.write_text(f'fungsi fail(): apapun {{\n  tampilkan("A");\n  hasilkan {expression};\n}}', encoding="utf-8")
        for options in options_list:
          with self.subTest(expression=expression, options=options):
            completed = run_program(entry, options)
            self.assertEqual(completed.returncode, 1)
            self.assertEqual(completed.stdout, "A")
            self.assertIn('library.pyind", line 3', completed.stderr)
            self.assertIn(exception, completed.stderr)
      entry.write_text("fungsi utama(): kosong { tampilkan(1 < < 3); }", encoding="utf-8")
      for options in options_list:
        completed = run_program(entry, options)
        self.assertEqual(completed.returncode, 70)
        self.assertEqual(completed.stderr, "")
        self.assertTrue(completed.stdout.startswith("Error: "))
