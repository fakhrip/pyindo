import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Binary, Call, Declaration, If, InterpolatedString, Return, Unary
from pyindo.syntax import parse_module


class SyntaxTests(unittest.TestCase):
  def expression(self, text):
    return parse_module(f"fungsi utama() {{ hasilkan {text}; }}").functions[0].body[0].value

  def test_function_parameters_and_statement_nodes(self):
    program = parse_module("""fungsi jumlah(a, b) {
  variabel total = a + b;
  konstanta batas = 10;
  total = total + batas;
  tampilkan(total);
  hasilkan total;
}
fungsi utama() { hasilkan; }
""")

    self.assertEqual([parameter.name for parameter in program.functions[0].parameters], ["a", "b"])
    statements = program.functions[0].body
    self.assertIsInstance(statements[0], Declaration)
    self.assertTrue(statements[1].is_constant)
    self.assertEqual(statements[2].target, "total")
    self.assertEqual(statements[3].call.callee, "tampilkan")
    self.assertIsInstance(statements[4], Return)
    self.assertIsNone(program.functions[1].body[0].value)
    self.assertEqual(statements[0].span.line, 2)

  def test_nested_conditions_keep_their_own_else(self):
    body = parse_module("""fungsi utama() {
  jika (benar) {
    jika (salah) {} selainnya {}
  } selainnya jika (salah) {} selainnya {}
  tampilkan("after");
}""").functions[0].body

    self.assertIsInstance(body[0], If)
    self.assertEqual(len(body[0].branches), 2)
    self.assertEqual(body[0].else_body, [])
    self.assertEqual(body[0].branches[0][1][0].else_body, [])
    self.assertEqual(body[1].call.callee, "tampilkan")

  def test_nested_call_arguments_keep_expression_boundaries(self):
    expression = self.expression("jumlah(1 + 2, kali(3, 4))")

    self.assertIsInstance(expression, Call)
    self.assertIsInstance(expression.arguments[0], Binary)
    self.assertEqual(expression.arguments[1].callee, "kali")
    self.assertEqual(len(expression.arguments[1].arguments), 2)

  def test_precedence_and_associativity(self):
    self.assertEqual(self.expression("2 + 3 * 4").right.operator, "*")
    self.assertEqual(self.expression("20 - 5 - 3").left.operator, "-")
    self.assertEqual(self.expression("2 ** 3 ** 2").right.operator, "**")
    self.assertIsInstance(self.expression("-2 ** 2"), Unary)
    self.assertEqual(self.expression("-2 ** 2").operand.operator, "**")
    self.assertIsInstance(self.expression("2 ** -2").right, Unary)
    self.assertEqual(self.expression("1 + 2 == 3").left.operator, "+")
    self.assertEqual(self.expression("1 | 2 & 3 << 1 < 8").left.operator, "|")
    self.assertEqual(self.expression("1 adalah 1").operator, "==")

  def test_chained_comparisons_are_rejected(self):
    with self.assertRaises(PyIndoError) as raised:
      self.expression("1 < 2 < 3")

    self.assertIn("Chained comparisons", raised.exception.message)

  def test_earlier_syntax_error_is_not_masked_by_later_lexical_error(self):
    with self.assertRaises(PyIndoError) as raised:
      parse_module("fungsiutama() {}\n@")

    self.assertEqual(raised.exception.span.line, 1)
    self.assertIn("Expecting 'fungsi'", raised.exception.message)

  def test_invalid_or_unsupported_syntax_is_located(self):
    sources = [
      "fungsi utama() { jika () {} }", "fungsi utama() { tampilkan(1) }",
      "fungsi utama(a: desimal) {}", "fungsi utama() { untuk (;;) {} }",
      "fungsi utama() { hasilkan 1 && 2; }", "fungsi utama() { x += 1; }",
      "fungsi utama() { jika (benar) maka tampilkan(1); }",
      'fungsi utama() { tampilkan("${}"); }', "fungsi utama() {} extra",
      "fungsi utama() { hasilkan (1 + 2; }",
    ]

    for source in sources:
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError) as raised:
          parse_module(source)

        self.assertIsNotNone(raised.exception.span)

  def test_interpolation_reuses_expression_grammar_and_original_spans(self):
    source = '''fungsi utama() { hasilkan "café ☕ ${gabung("}", kali(2, 3))}"; }'''
    expression = parse_module(source).functions[0].body[0].value

    self.assertIsInstance(expression, InterpolatedString)
    inner_call = expression.parts[1]
    self.assertEqual(inner_call.callee, "gabung")
    self.assertEqual(source[inner_call.span.start:inner_call.span.end], 'gabung("}", kali(2, 3))')
    self.assertEqual(inner_call.arguments[0].value, "}")
