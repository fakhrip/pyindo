import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module


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
