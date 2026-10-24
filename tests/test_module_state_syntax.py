import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.nodes import Index, Program
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module


class ModuleStateSyntaxTests(unittest.TestCase):
  def test_top_level_declarations_keep_order_types_and_spans(self):
    source = '''variabel base: angka = 2;
fungsi utama(): kosong { tampilkan(base); }
konstanta saved: himpunan<himpunan<desimal>> = [[base]];
'''
    program = parse_module(source)
    self.assertEqual([item.name for item in program.declarations], ["base", "saved"])
    self.assertEqual(source[program.declarations[0].span.start:program.declarations[0].span.end],
                     "variabel base: angka = 2;")
    self.assertEqual(Program([], "", program.span, []).declarations, [])
    symbols = analyze_program(program)
    self.assertEqual(symbols.module_values["base"].type_spec, "desimal")
    self.assertEqual(symbols.module_values["saved"].type_spec, ("himpunan", ("himpunan", "desimal")))
    self.assertTrue(symbols.module_values["saved"].is_constant)
    self.assertEqual(symbols.scopes["utama"].local_names, [])

  def test_member_reads_keep_calls_and_indexing_distinct(self):
    program = parse_module("fungsi utama(): kosong { tampilkan(state.total, state.items[0], state.bump()); }")
    member, indexed, call = program.functions[0].body[0].call.arguments
    self.assertEqual((member.namespace, member.member), ("state", "total"))
    self.assertIsInstance(indexed, Index)
    self.assertEqual(indexed.container.member, "items")
    self.assertEqual(call.callee, "state.bump")

  def test_module_grammar_requires_typed_initialized_declarations(self):
    for text in (
      "variabel value = 1;", "konstanta value: desimal;", "variabel value: desimal = 1",
      "value = 1;", "tampilkan(1);", "jika (benar) {}", "selama (salah) {}",
    ):
      with self.subTest(text=text), self.assertRaises(PyIndoError):
        parse_module(text + "\nfungsi utama(): kosong {}")
    for expression in ("state.", "state.sub.value", "(state).value", "state.value = 1"):
      with self.subTest(expression=expression), self.assertRaises(PyIndoError):
        parse_module(f"fungsi utama(): kosong {{ tampilkan({expression}); }}")

  def test_owned_values_support_function_writes_but_not_shadowing(self):
    analyze_program(parse_module('''variabel total: desimal = 0;
fungsi bump(): desimal { total = total + 1; total += 2; total++; hasilkan total; }
fungsi utama(): kosong { tampilkan(total, bump()); }'''))
    for body in ("variabel total: desimal = 1;", "konstanta total: desimal = 1;"):
      with self.subTest(body=body), self.assertRaises(PyIndoError):
        analyze_program(parse_module(f"variabel total: desimal = 0; fungsi utama(): kosong {{ {body} }}"))
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module("variabel total: desimal = 0; fungsi f(total: desimal): kosong {} fungsi utama(): kosong {}"))

  def test_module_names_cannot_replace_functions_imports_or_runtime_names(self):
    for name in ("utama", "tampilkan", "print", "__name__", "__file__", "__builtins__"):
      with self.subTest(name=name), self.assertRaises(PyIndoError):
        analyze_program(parse_module(f"variabel {name}: apapun = 1; fungsi utama(): kosong {{}}"))
    for declarations in (
      "variabel value: desimal = 1; konstanta value: desimal = 2;",
      "variabel value: desimal = 1; fungsi value(): kosong {}",
      "variabel value: unknown = 1;",
    ):
      with self.subTest(declarations=declarations), self.assertRaises(PyIndoError):
        analyze_program(parse_module(declarations + "fungsi utama(): kosong {}"))

  def test_initializers_require_earlier_owned_values_even_in_dead_arms(self):
    analyze_program(parse_module("variabel base: desimal = 2; variabel doubled: desimal = base * 2; fungsi utama(): kosong {}"))
    analyze_program(parse_module("variabel first: desimal = later(); fungsi later(): desimal { hasilkan value; } variabel value: desimal = 2; fungsi utama(): kosong {}"))
    for initializer in ("later", "first", "1 jika benar selainnya later"):
      source = f"variabel first: desimal = {initializer}; variabel later: desimal = 2; fungsi utama(): kosong {{}}"
      with self.subTest(initializer=initializer), self.assertRaisesRegex(PyIndoError, "not initialized"):
        analyze_program(parse_module(source))

  def test_imported_values_are_reads_and_mutable_elements_not_rebindings(self):
    from pyindo.resolver import ValueBinding

    template = "fungsi utama(): kosong { %s }"
    span = parse_module(template % "").span
    values = {
      "count": ValueBinding("count", "desimal", False, span),
      "state.items": ValueBinding("items", ("himpunan", "desimal"), False, span),
      "saved": ValueBinding("saved", ("himpunan", "desimal"), True, span),
      "state.saved": ValueBinding("saved", ("himpunan", "desimal"), True, span),
    }
    analyze_program(parse_module(template % "tampilkan(count, state.items[0]); state.items[0] = 2;"),
                    imported_values=values, namespace_names={"state"})
    for body in (
      "count = 1;", "count += 1;", "count++;", "count();", "tampilkan(state.missing);",
      "variabel count: desimal = 1;", "saved[0] = 1;", "hapus state.saved[0];",
      "jika (salah) { count = 1; }",
    ):
      with self.subTest(body=body), self.assertRaises(PyIndoError):
        analyze_program(parse_module(template % body), imported_values=values, namespace_names={"state"})

  def test_owned_constant_roots_and_functions_as_values_are_rejected(self):
    for body in ("saved = [2];", "saved[0][0] = 2;", "hapus saved[0];", "tampilkan(helper);"):
      with self.subTest(body=body), self.assertRaises(PyIndoError):
        analyze_program(parse_module(f"konstanta saved: apapun = [[1]]; fungsi helper(): kosong {{}} fungsi utama(): kosong {{ {body} }}"))
