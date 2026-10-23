import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import Parser, parse_module
from pyindo.types import resolve_type


class TypeAnnotationTests(unittest.TestCase):
  def test_annotations_on_every_binding_and_signature(self):
    source = """fungsi jumlah(a: angka, b: desimal): desimal {
  konstanta batas: desimal = 2;
  untuk (variabel i: desimal = 0; i < 1; i++) {}
  jika (benar) maka variabel nilai: himpunan<desimal> = [a, b];
  hasilkan a + b;
}
fungsi utama(): kosong {}
"""
    program = parse_module(source)
    function = program.functions[0]
    self.assertEqual(function.parameters[0].annotation.name, "angka")
    self.assertEqual(resolve_type(function.parameters[0].annotation), "desimal")
    annotation = function.body[2].branches[0][1][0].annotation
    self.assertEqual(resolve_type(annotation), ("himpunan", "desimal"))
    self.assertEqual(source[annotation.span.start:annotation.span.end], "himpunan<desimal>")
    self.assertEqual(resolve_type(function.return_annotation), "desimal")
    symbols = analyze_program(program)
    self.assertEqual(symbols.scopes["jumlah"].binding_types["i"], "desimal")
    self.assertEqual(symbols.signatures["jumlah"].parameter_types, ("desimal", "desimal"))

  def test_missing_and_malformed_annotations_are_located(self):
    sources = (
      "fungsi utama() {}",
      "fungsi helper(a): kosong {} fungsi utama(): kosong {}",
      "fungsi utama(): kosong { variabel x = 1; }",
      "fungsi utama(): kosong { konstanta x = 1; }",
      "fungsi utama(): kosong { untuk (variabel i = 0;;) {} }",
      "fungsi utama(): kosong { jika (benar) maka variabel x = 1; }",
      "fungsi utama(): unknown {}",
      "fungsi utama(): kosong { variabel x: himpunan = []; }",
      "fungsi utama(): kosong { variabel x: desimal<desimal> = 1; }",
      "fungsi utama(): kosong { variabel x: himpunan<> = []; }",
      "fungsi utama(): kosong { variabel x: himpunan<desimal, desimal> = []; }",
      "fungsi utama(): kosong { variabel x: himpunan<desimal = []; }",
      "fungsi utama(): kosong { untuk (i: desimal = 0;;) {} }",
    )
    for source in sources:
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError) as raised:
          analyze_program(parse_module(source))
        self.assertIsNotNone(raised.exception.span)

  def test_compact_generic_closers_preserve_operator_tokens(self):
    for spelling in ("himpunan<desimal>", "himpunan<himpunan<desimal>>"):
      for separator in ("=", " = "):
        source = f"fungsi utama(): kosong {{ variabel a: {spelling}{separator}[]; }}"
        annotation = parse_module(source).functions[0].body[0].annotation
        self.assertEqual(source[annotation.span.start:annotation.span.end], spelling)
    parser = Parser("himpunan<himpunan<desimal>>=[]")
    parser.parse_type_annotation()
    self.assertEqual(parser.current.text, "=")
    self.assertEqual(parser.current.span.start, parser.source_text.index("="))
    source = "fungsi utama(): kosong { variabel v: desimal = 8 >> 1; v >>= 1; hasilkan; }"
    statements = parse_module(source).functions[0].body
    self.assertEqual(statements[0].value.operator, ">>")
    self.assertEqual(statements[1].operator, ">>")

  def test_contextual_type_names_and_complexity(self):
    source = """fungsi kosong(): logika { hasilkan benar; }
fungsi angka(himpunan: apapun): apapun { hasilkan himpunan; }
fungsi utama(): kosong {
  variabel himpunan: campuran = "café";
  tampilkan(himpunan tidak kosong, tidak kosong());
}
"""
    analyze_program(parse_module(source))
    source = "fungsi utama(): " + "himpunan<" * 1200 + "desimal" + ">" * 1200 + " {}"
    with self.assertRaisesRegex(PyIndoError, "complexity exceeds compiler limit"):
      parse_module(source)

  def test_return_coverage_uses_existing_flow(self):
    for body in ("", "hasilkan;", "jika (benar) { hasilkan 1; }",
                 "selama (benar) { hasilkan 1; }", "hasilkan 1; hasilkan;"):
      with self.subTest(body=body):
        with self.assertRaisesRegex(PyIndoError, "return|Return"):
          analyze_program(parse_module(
            f"fungsi value(): desimal {{ {body} }} fungsi utama(): kosong {{}}"
          ))
    for body in ("jika (benar) { hasilkan 1; } selainnya { hasilkan 2; }",
                 "selama (salah) { hasilkan 1; } hasilkan 2;",
                 "hasilkan tampilkan();"):
      analyze_program(parse_module(
        f"fungsi value(): desimal {{ {body} }} fungsi utama(): kosong {{}}"
      ))
    for spec in ("kosong", "apapun"):
      analyze_program(parse_module(f"fungsi utama(): {spec} {{}}"))

  def test_all_type_tables_precede_body_analysis(self):
    source = """fungsi first(a: desimal): desimal { hasilkan second(a); }
fungsi second(a: angka): desimal { jika (a > 0) { hasilkan first(a - 1); } hasilkan 0; }
fungsi utama(): kosong {}
"""
    symbols = analyze_program(parse_module(source))
    self.assertEqual(symbols.signatures["second"].return_type, "desimal")
    source = "fungsi utama(): kosong { jika (salah) maka variabel x: desimal = 1; tampilkan(x); }"
    with self.assertRaisesRegex(PyIndoError, "not initialized"):
      analyze_program(parse_module(source))
