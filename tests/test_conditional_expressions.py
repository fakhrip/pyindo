import unittest

from pyindo.compiler import compile_source
from pyindo.diagnostics import PyIndoError
from pyindo.syntax import parse_module
from tests.fixture_runner import assert_program_result, run_python, run_source
from tests.test_language import run_compiled


class ConditionalExpressionTests(unittest.TestCase):
  def expression(self, text):
    return parse_module(f"fungsi utama(): apapun {{ hasilkan {text}; }}").functions[0].body[0].value

  def test_conditional_precedence_association_and_delimiters(self):
    value = self.expression("a atau b jika c dan d selainnya e atau f")
    self.assertEqual(value.true_value.operator, "or")
    self.assertEqual(value.condition.operator, "and")
    self.assertEqual(value.false_value.operator, "or")
    value = self.expression("a jika b selainnya c jika d selainnya e")
    self.assertEqual(value.false_value.condition.identifier, "d")
    for text in ("(a jika b selainnya c) jika d selainnya e",
                 "a jika (b jika c selainnya d) selainnya e",
                 "f(a jika b selainnya c, [1 jika b selainnya 2][0])"):
      self.expression(text)
    source = "fungsi f(a: apapun, b: apapun): apapun { jika (a) maka hasilkan 1 jika b selainnya 2; selainnya maka hasilkan 3; } fungsi utama(): kosong {}"
    compile_source(source)

  def test_incomplete_conditionals_are_located(self):
    for text in ("1 jika", "1 jika benar", "1 jika selainnya 2", "1 jika benar selainnya",
                 "1 jika benar jika salah selainnya 2 selainnya 3",
                 "1 jika benar selainnya 2 selainnya 3", "1 < 2 < 3 jika benar selainnya 0"):
      with self.subTest(text=text):
        with self.assertRaises(PyIndoError) as raised:
          self.expression(text)
        self.assertIsNotNone(raised.exception.span)
    with self.assertRaises(PyIndoError):
      parse_module("fungsi utama(): kosong { f() jika benar selainnya g(); }")
    with self.assertRaisesRegex(PyIndoError, "complexity exceeds compiler limit"):
      self.expression("0 jika benar selainnya " * 1200 + "1")

  def test_condition_first_one_arm_and_identity(self):
    source = """fungsi mark(label: campuran, value: apapun): apapun { tampilkan(label); hasilkan value; }
fungsi choose(flag: apapun, a: apapun, b: apapun): apapun {
  hasilkan mark("T", a) jika mark("C", flag) selainnya mark("F", b);
}
fungsi utama(): kosong {}
"""
    assertions = "a = object()\nb = object()\nassert namespace['choose'](True, a, b) is a\nassert namespace['choose'](False, a, b) is b"
    assert_program_result(run_compiled(source, assertions), "CTCF")
    assert_program_result(run_source("fungsi utama(): kosong { tampilkan(7 jika benar selainnya 1 / 0); }"), "7")

  def test_static_checks_visit_all_children(self):
    for expression in ("missing jika benar selainnya 2", "1 jika missing selainnya 2",
                       "1 jika benar selainnya missing", "unknown() jika salah selainnya 1",
                       "1 jika benar selainnya helper()"):
      with self.subTest(expression=expression):
        source = f"fungsi helper(a: apapun): apapun {{ hasilkan a; }} fungsi utama(): apapun {{ hasilkan {expression}; }}"
        with self.assertRaises(PyIndoError):
          compile_source(source)
    source = "fungsi utama(): apapun { hasilkan missing_first jika missing_condition selainnya missing_last; }"
    with self.assertRaisesRegex(PyIndoError, "missing_first"):
      compile_source(source)
    source = "fungsi utama(): apapun { hasilkan 1 jika benar selainnya later; variabel later: desimal = 2; }"
    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      compile_source(source)

  def test_selected_results_use_existing_type_contracts(self):
    for flag, status in (("benar", 0), ("salah", 1)):
      source = f'fungsi utama(): kosong {{ variabel value: desimal = 1 jika {flag} selainnya "bad"; }}'
      result = run_source(source)
      self.assertEqual(result.returncode, status)
      if status:
        self.assertIn("TypeError", result.stderr)

  def test_nested_stack_joins(self):
    source = """fungsi combine(a: desimal, b: desimal): desimal { hasilkan a + b; }
fungsi value(flag: logika): campuran {
  variabel values: himpunan<desimal> = [1, 2 jika flag selainnya 3];
  values[0 jika flag selainnya 1] = combine(4, 5 jika flag selainnya 6);
  hasilkan "café ☕ ${10 + (values[0] jika flag selainnya values[1])}|${values}";
}
fungsi utama(): kosong { tampilkan(value(benar), "/", value(salah)); }
"""
    assert_program_result(run_source(source), "café ☕ 19|[9, 2]/café ☕ 20|[1, 10]")

  def test_changing_truth_probes_match_native_contexts(self):
    variants = [
      ("a dan b jika c selainnya d", "a and b if c else d"),
      ("(a dan b jika c selainnya d) atau e", "(a and b if c else d) or e"),
      ("(a dan b jika c selainnya d) dan e", "(a and b if c else d) and e"),
      ("tidak (a dan b jika c selainnya d)", "not (a and b if c else d)"),
      ("tidak ((a dan b jika c selainnya d) atau e)", "not ((a and b if c else d) or e)"),
      ("a atau b jika c selainnya d", "a or b if c else d"),
      ("a jika (b jika c selainnya d) selainnya e", "a if (b if c else d) else e"),
      ("tidak (a dan b) jika c selainnya d", "not (a and b) if c else d"),
      ("d jika c selainnya a dan b", "d if c else a and b"),
    ]
    contexts = (
      ("hasilkan {expression};", "return {expression}"),
      ("jika ({expression}) {{ hasilkan benar; }} hasilkan salah;", "return True if ({expression}) else False"),
      ("selama ({expression}) {{ hasilkan benar; }} hasilkan salah;", "return True if ({expression}) else False"),
      ("untuk (; {expression};) {{ hasilkan benar; }} hasilkan salah;", "return True if ({expression}) else False"),
    )
    sources = []
    references = []
    for expression, native in variants:
      for body, reference in contexts:
        index = len(sources)
        sources.append(f"fungsi probe_{index}(a: apapun, b: apapun, c: apapun, d: apapun, e: apapun): apapun {{ {body.format(expression=expression)} }}")
        references.append(reference.format(expression=native))
    source = "\n".join(sources) + "\nfungsi utama(): kosong {}"
    script = "from pyindo.compiler import compile_source\n" + f"source = {source!r}\nreferences = {references!r}\n" + """namespace = {'__name__': 'inspection'}
exec(compile_source(source), namespace)
class Probe:
  def __init__(self, label, values, trace):
    self.label, self.values, self.trace, self.calls = label, values, trace, 0
  def __bool__(self):
    self.trace.append(self.label)
    value = self.values[min(self.calls, len(self.values) - 1)]
    self.calls += 1
    return value
for index, reference in enumerate(references):
  native_scope = {}
  exec('def expected(a,b,c,d,e):\\n  ' + reference, native_scope)
  for condition in (False, True):
    traces, outcomes = [], []
    for function in (native_scope['expected'], namespace[f'probe_{index}']):
      trace = []
      arguments = [Probe(label, values, trace) for label, values in (
        ('a', [False, True]), ('b', [True, False]), ('c', [condition]),
        ('d', [False, True]), ('e', [True, False]))]
      result = function(*arguments)
      outcomes.append(next((item.label for item in arguments if result is item), result))
      traces.append(trace)
    assert traces[0] == traces[1] and outcomes[0] == outcomes[1], (index, condition, traces, outcomes)
"""
    assert_program_result(run_python(script), "")
