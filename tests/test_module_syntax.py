import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import FunctionSignature, analyze_program
from pyindo.syntax import parse_module


class ModuleSyntaxTests(unittest.TestCase):
  def test_named_and_namespace_imports_keep_aliases_and_source_spans(self):
    source = '''dari "café/hitung.pyind" impor jumlah, kali sebagai kalikan;
fungsi utama(): kosong { tampilkan(hitung.jumlah(1, 2)); }
impor "other.pyind" sebagai hitung;
'''
    program = parse_module(source)
    named, namespace = program.imports
    self.assertEqual(named.path, "café/hitung.pyind")
    self.assertEqual([(item.name, item.alias) for item in named.bindings],
                     [("jumlah", "jumlah"), ("kali", "kalikan")])
    self.assertEqual(source[named.path_span.start:named.path_span.end], '"café/hitung.pyind"')
    self.assertEqual(source[named.bindings[1].span.start:named.bindings[1].span.end],
                     "kali sebagai kalikan")
    self.assertEqual(namespace.namespace, "hitung")
    call = program.functions[0].body[0].call.arguments[0]
    self.assertEqual(call.callee, "hitung.jumlah")
    self.assertEqual(len(call.arguments), 2)

  def test_paths_and_headers_are_literal_complete_top_level_statements(self):
    invalid = (
      'dari path impor jumlah;', 'dari "${name}.pyind" impor jumlah;',
      'dari "" impor jumlah;', 'dari "x.pyind" impor;',
      'dari "x.pyind" impor jumlah sebagai;', 'dari "x.pyind" impor *;',
      'dari "x.pyind" impor jumlah,;', 'impor "x.pyind";',
      'impor "x.pyind" sebagai x',
      'fungsi bad(): kosong { dari "x.pyind" impor jumlah; }',
    )
    for text in invalid:
      with self.subTest(text=text):
        with self.assertRaises(PyIndoError) as raised:
          parse_module(text + "\nfungsi utama(): kosong {}")
        self.assertIsNotNone(raised.exception.span)

  def test_import_words_remain_contextual_and_qualified_calls_are_bounded(self):
    program = parse_module('''fungsi impor(dari: desimal): desimal {
  variabel sebagai: desimal = dari;
  hasilkan sebagai;
}
fungsi utama(): kosong { tampilkan(impor(2)); }
''')
    analyze_program(program)
    for expression in ("math.value", "math.sub.value()", "(math).value()", "math.value = 1"):
      with self.subTest(expression=expression):
        with self.assertRaises(PyIndoError):
          parse_module(f"fungsi utama(): kosong {{ tampilkan({expression}); }}")

  def test_libraries_may_omit_an_entry_but_roots_require_a_local_one(self):
    library = parse_module("fungsi jumlah(a: desimal, b: desimal): desimal { hasilkan a + b; }")
    analyze_program(library, require_entrypoint=False)
    signature = FunctionSignature("utama", [], library.span, (), "kosong")
    with self.assertRaisesRegex(PyIndoError, "Entrypoint"):
      analyze_program(library, imported_signatures={"utama": signature})
    # A library's named utama remains an ordinary typed function until called.
    library = parse_module("fungsi utama(a: desimal): desimal { hasilkan a; }")
    analyze_program(library, require_entrypoint=False)
    with self.assertRaisesRegex(PyIndoError, "zero or two"):
      analyze_program(library)

  def test_imported_signatures_check_arity_and_reserve_namespace_names(self):
    program = parse_module("fungsi utama(): kosong { tampilkan(math.sum(1, 2), add(3, 4)); }")
    signature = FunctionSignature("sum", ["a", "b"], program.span, ("desimal", "desimal"), "desimal")
    symbols = analyze_program(program, imported_signatures={"math.sum": signature, "add": signature},
                              namespace_names={"math"})
    self.assertEqual(set(symbols.scopes), {"utama"})
    for body in ("math.sum(1);", "add(1, 2, 3);", "variabel math: apapun = 1;", "math.unknown();"):
      with self.subTest(body=body):
        with self.assertRaises(PyIndoError):
          analyze_program(parse_module(f"fungsi utama(): kosong {{ {body} }}"),
                          imported_signatures={"math.sum": signature, "add": signature},
                          namespace_names={"math"})
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module("fungsi add(): kosong {} fungsi utama(): kosong {}"),
                      imported_signatures={"add": signature})
    with self.assertRaises(PyIndoError):
      analyze_program(parse_module("fungsi math(): kosong {} fungsi utama(): kosong {}"),
                      namespace_names={"math"})

  def test_library_bodies_keep_mandatory_types_and_return_checks(self):
    for source in ("fungsi f(a: unknown): kosong {}", "fungsi f(): desimal {}",
                   "fungsi f(): kosong { tampilkan(missing); }"):
      with self.subTest(source=source):
        with self.assertRaises(PyIndoError):
          analyze_program(parse_module(source), require_entrypoint=False)
