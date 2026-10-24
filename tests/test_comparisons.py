import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Binary, Conditional, Logical, NonEmpty, Unary
from pyindo.resolver import FunctionSignature, ValueBinding, analyze_program
from pyindo.syntax import parse_module


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
