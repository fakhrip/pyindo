import unittest

from pyindo.diagnostics import PyIndoError
from pyindo.resolver import analyze_program
from pyindo.syntax import parse_module


class ResolverTests(unittest.TestCase):
  def analyze(self, source):
    return analyze_program(parse_module(source))

  def assert_invalid(self, source, message=None):
    with self.assertRaises(PyIndoError) as raised:
      self.analyze(source)

    if message:
      self.assertIn(message, raised.exception.message)

  def test_signatures_allow_forward_and_recursive_calls(self):
    symbols = self.analyze("""fungsi utama(): apapun { first(1); }
fungsi first(value: apapun): apapun { second(value); first(value); }
fungsi second(value: apapun): apapun { first(value); }
""")

    self.assertEqual(symbols.signatures["first"].parameters, ["value"])

  def test_invalid_function_contracts_are_rejected(self):
    sources = [
      "fungsi helper(): apapun {}", "fungsi utama(): apapun {} fungsi utama(): apapun {}",
      "fungsi utama(value: apapun): apapun {}", "fungsi helper(a: apapun, a: apapun): apapun {} fungsi utama(): apapun {}",
      "fungsi utama(): apapun { missing(); }", "fungsi helper(a: apapun): apapun {} fungsi utama(): apapun { helper(); }",
      "fungsi utama(): apapun { variabel utama: apapun = 1; }",
      "fungsi utama(): apapun { variabel tampilkan: apapun = 1; }",
      "fungsi helper(): apapun {} fungsi utama(): apapun { hasilkan helper; }",
    ]

    for source in sources:
      with self.subTest(source=source):
        self.assert_invalid(source)

  def test_reserved_function_names_cannot_replace_runtime_globals(self):
    for name in ("tampilkan", "print", "__name__", "__file__", "__builtins__"):
      with self.subTest(name=name):
        self.assert_invalid(f"fungsi {name}(): apapun {{}} fungsi utama(): apapun {{}}", f"Function name '{name}' is reserved")

    self.analyze("fungsi utama(): apapun { variabel print: apapun = 1; variabel __name__: apapun = 2; tampilkan(); }")

  def test_reserved_function_error_points_to_the_name(self):
    source = "fungsi\n  print(): apapun {}\nfungsi utama(): apapun {}"

    with self.assertRaises(PyIndoError) as raised:
      self.analyze(source)

    self.assertEqual(raised.exception.span.line, 2)
    self.assertEqual(raised.exception.span.column, 3)
    self.assertEqual(source[raised.exception.span.start:raised.exception.span.end], "print")

  def test_mutable_locals_constants_and_parameter_initialization(self):
    symbols = self.analyze("""fungsi helper(value: apapun): apapun {
  konstanta limit: apapun = 10;
  variabel total: apapun = value;
  total = total + limit;
  jika (value) { variabel inner: apapun = 3; }
  hasilkan total;
}
fungsi utama(): apapun { variabel total: apapun = 1; tampilkan(helper(total)); }
""")

    self.assertEqual(symbols.scopes["helper"].local_names, ["value", "limit", "total", "inner"])
    self.assertEqual(symbols.scopes["helper"].constant_names, {"limit"})

  def test_invalid_local_access_is_rejected(self):
    bodies = [
      "tampilkan(missing);", "missing = 1;", "variabel value: apapun = value;",
      "tampilkan(value); variabel value: apapun = 1;", "variabel value: apapun = 1; variabel value: apapun = 2;",
      "konstanta value: apapun = 1; value = 2;", "jika (benar) { variabel value: apapun = 1; } value = 2;",
      "variabel value: apapun = 1; jika (benar) { konstanta value: apapun = 2; }",
    ]

    for body in bodies:
      with self.subTest(body=body):
        self.assert_invalid(f"fungsi utama(): apapun {{ {body} }}")

    self.assert_invalid("fungsi helper(value: apapun): apapun { variabel value: apapun = 1; } fungsi utama(): apapun {}")

  def test_only_falling_through_branches_contribute_to_initialization(self):
    self.analyze("""fungsi pilih(flag: apapun): apapun {
  jika (flag) { hasilkan 1; }
  selainnya { variabel result: apapun = 2; }
  hasilkan result;
}
fungsi utama(): apapun { pilih(benar); }
""")

    self.assert_invalid("""fungsi pilih(flag: apapun): apapun {
  jika (flag) {} selainnya { variabel result: apapun = 2; }
  hasilkan result;
}
fungsi utama(): apapun {}
""")
    self.assert_invalid("fungsi utama(): apapun { jika (benar) { variabel result: apapun = 1; } tampilkan(result); }")
    self.analyze("""fungsi pilih(a: apapun, b: apapun): apapun {
  jika (a) { jika (b) { hasilkan 1; } selainnya { hasilkan 2; } }
  selainnya jika (b) { hasilkan 3; }
  selainnya { variabel result: apapun = 4; }
  hasilkan result;
}
fungsi utama(): apapun {}
""")

  def test_unreachable_code_cannot_initialize_a_live_path(self):
    self.assert_invalid("""fungsi utama(): apapun {
  jika (benar) { hasilkan; variabel result: apapun = 1; }
  tampilkan(result);
}""")
    self.assert_invalid("fungsi utama(): apapun { hasilkan; missing(); }")
    self.assert_invalid("fungsi utama(): apapun { hasilkan; tampilkan(missing); }")
