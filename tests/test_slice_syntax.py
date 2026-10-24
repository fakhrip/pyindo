import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Index, Literal
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module


class SliceSyntaxTests(unittest.TestCase):
  def expression(self, text):
    """Parse one subscript without executing newly assembled bytecode."""

    return parse_module(f"fungsi utama(): apapun {{ hasilkan {text}; }}").functions[0].body[0].value

  def test_slice_nodes_preserve_index_constructor_and_component_shapes(self):
    ordinary = self.expression("values[1]")
    self.assertIsInstance(ordinary, Index)
    self.assertIsInstance(ordinary.index, Literal)
    self.assertIsInstance(Index(ordinary.container, ordinary.index, ordinary.span).index, Literal)
    sliced = self.expression("values[1 hingga 3][0]").container
    self.assertEqual(type(sliced.index).__name__, "SliceKey")
    self.assertEqual((sliced.index.start.value, sliced.index.stop.value), (1, 3))
    self.assertFalse(hasattr(sliced.index, "step"))

  def test_slice_grammar_accepts_required_expressions_and_preserves_names(self):
    for text in (
      "values[hingga]", "values[hingga()]", "values[0 hingga langkah]",
      "values[hingga hingga batas]", "values[1 hingga hingga]",
      "buat()[pick(value=[0, 1][0]) hingga 3 jika benar selainnya 4][0]",
      'values[0 hingga pick(value="${1 < 2 < 3}")]',
    ):
      self.expression(text)
    self.assertEqual(self.expression("values[hingga]").index.identifier, "hingga")
    source = '''fungsi hingga(langkah: desimal = 1): desimal { hasilkan langkah; }
fungsi utama(): kosong {
  variabel values: apapun = [0, 1, 2];
  variabel langkah: desimal = 2;
  tampilkan(values[hingga(langkah=0) hingga langkah]);
}'''
    analyze_program(parse_module(source))

  def test_slice_spans_and_malformed_forms_keep_real_eof(self):
    source = 'fungsi utama(): apapun { hasilkan "café ☕ ${values[1\r\n hingga 3]}"; }'
    indexed = parse_module(source).functions[0].body[0].value.parts[1]
    key = indexed.index
    self.assertEqual(source[indexed.span.start:indexed.span.end], "values[1\r\n hingga 3]")
    self.assertEqual(source[key.span.start:key.span.end], "[1\r\n hingga 3]")
    self.assertEqual(source[key.start.span.start:key.start.span.end], "1")
    self.assertEqual(source[key.stop.span.start:key.stop.span.end], "3")
    for suffix in ("[1:3]", "[:]", "[::-1]", "[1:2:2]", "[]", "[1, 2]", "[hingga 2]",
                   "[1 hingga]", "[1 hingga 2 langkah 2]", "[hingga langkah -1]",
                   "[1 hingga 2,]", "[1 hingga 2 hingga 3]", "[1 hingga 2](0)"):
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError):
        self.expression("values" + suffix)
    for suffix in ("values[1 hingga", "values[1 hingga 2", "values[helper(value=1) hingga"):
      source = "fungsi utama(): apapun { hasilkan " + suffix
      with self.subTest(suffix=suffix), self.assertRaises(PyIndoError) as raised:
        parse_module(source)
      self.assertEqual(raised.exception.span.start, len(source))

  def test_both_slice_bounds_receive_static_source_order_checks(self):
    for expression in ("missing[0 hingga 1]", "values[missing hingga 1]", "values[0 hingga missing]",
                       "values[unknown() hingga 1]", "values[0 hingga helper()]",
                       "values[0 hingga helper(wrong=1)]", "values[later hingga 1]"):
      source = f'''fungsi helper(value: apapun): apapun {{ hasilkan value; }}
fungsi utama(): apapun {{ variabel values: apapun = [1]; hasilkan benar atau {expression}; variabel later: apapun = 1; }}'''
      with self.subTest(expression=expression), self.assertRaises(PyIndoError):
        analyze_program(parse_module(source))
    with self.assertRaisesRegex(PyIndoError, "first_missing"):
      analyze_program(parse_module("fungsi utama(): apapun { hasilkan [1][first_missing hingga last_missing]; }"))
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module("fungsi f(value: apapun = [1][0 hingga missing]): apapun {} fungsi utama(): kosong { f(value=1); }"))
    with self.assertRaisesRegex(PyIndoError, "complexity"):
      self.expression("values[0 hingga " + "(" * 1200 + "1" + ")" * 1200 + "]")

  def test_slice_mutation_keeps_constant_and_import_ownership_rules(self):
    for statement in ("saved[0 hingga 1] = [];", "hapus saved[0 hingga 1];", "saved[0 hingga 1][0] = 9;"):
      with self.subTest(statement=statement), self.assertRaisesRegex(PyIndoError, "constant"):
        analyze_program(parse_module("fungsi utama(): kosong { konstanta saved: apapun = [1, 2]; " + statement + " }"))
    owner = analyze_program(parse_module("konstanta saved: apapun = [1]; variabel values: apapun = [1];"), require_entrypoint=False)
    for name in ("saved", "state.saved"):
      source = f"fungsi utama(): kosong {{ hapus {name}[0 hingga 1]; }}"
      with self.subTest(name=name), self.assertRaisesRegex(PyIndoError, "constant"):
        analyze_program(parse_module(source), imported_values={name: owner.module_values["saved"]})
    analyze_program(parse_module("fungsi utama(): kosong { values[0 hingga 1] = []; hapus values[0 hingga 1]; }"), imported_values={"values": owner.module_values["values"]})
    with self.assertRaisesRegex(PyIndoError, "rebind imported"):
      analyze_program(parse_module("fungsi utama(): kosong { values = []; }"), imported_values={"values": owner.module_values["values"]})

  def test_slice_statements_keep_header_maka_and_expression_boundaries(self):
    source = '''variabel first: apapun = [1, 2][0 hingga 1];
fungsi f(value: apapun = first[0 hingga 0]): apapun { hasilkan value; }
fungsi utama(): kosong {
  jika (benar) maka first[0 hingga 0] = [3];
  untuk (first[0 hingga 0] = []; salah; hapus first[0 hingga 0]) {}
}'''
    analyze_program(parse_module(source))
    for statement in ("values[0 hingga 1];", "values[0 hingga 1] += [];", "values[0 hingga 1]++;",
                      "values[0 hingga 1]--;", "hapus values;", "hapus values[0 hingga 1], values[0];"):
      with self.subTest(statement=statement), self.assertRaises(PyIndoError):
        parse_module("fungsi utama(): kosong { variabel values: apapun = [1]; " + statement + " }")
