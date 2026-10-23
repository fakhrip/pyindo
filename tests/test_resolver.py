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
    symbols = self.analyze("""fungsi utama() { first(1); }
fungsi first(value) { second(value); first(value); }
fungsi second(value) { first(value); }
""")

    self.assertEqual(symbols.signatures["first"].parameters, ["value"])

  def test_invalid_function_contracts_are_rejected(self):
    sources = [
      "fungsi helper() {}", "fungsi utama() {} fungsi utama() {}",
      "fungsi utama(value) {}", "fungsi helper(a, a) {} fungsi utama() {}",
      "fungsi utama() { missing(); }", "fungsi helper(a) {} fungsi utama() { helper(); }",
      "fungsi utama() { variabel utama = 1; }",
      "fungsi utama() { variabel tampilkan = 1; }",
      "fungsi helper() {} fungsi utama() { hasilkan helper; }",
    ]

    for source in sources:
      with self.subTest(source=source):
        self.assert_invalid(source)

  def test_reserved_function_names_cannot_replace_runtime_globals(self):
    for name in ("tampilkan", "print", "__name__", "__file__", "__builtins__"):
      with self.subTest(name=name):
        self.assert_invalid(f"fungsi {name}() {{}} fungsi utama() {{}}", f"Function name '{name}' is reserved")

    self.analyze("fungsi utama() { variabel print = 1; variabel __name__ = 2; tampilkan(); }")

  def test_mutable_locals_constants_and_parameter_initialization(self):
    symbols = self.analyze("""fungsi helper(value) {
  konstanta limit = 10;
  variabel total = value;
  total = total + limit;
  jika (value) { variabel inner = 3; }
  hasilkan total;
}
fungsi utama() { variabel total = 1; tampilkan(helper(total)); }
""")

    self.assertEqual(symbols.scopes["helper"].local_names, ["value", "limit", "total", "inner"])
    self.assertEqual(symbols.scopes["helper"].constant_names, {"limit"})

  def test_invalid_local_access_is_rejected(self):
    bodies = [
      "tampilkan(missing);", "missing = 1;", "variabel value = value;",
      "tampilkan(value); variabel value = 1;", "variabel value = 1; variabel value = 2;",
      "konstanta value = 1; value = 2;", "jika (benar) { variabel value = 1; } value = 2;",
      "variabel value = 1; jika (benar) { konstanta value = 2; }",
    ]

    for body in bodies:
      with self.subTest(body=body):
        self.assert_invalid(f"fungsi utama() {{ {body} }}")

    self.assert_invalid("fungsi helper(value) { variabel value = 1; } fungsi utama() {}")

  def test_only_falling_through_branches_contribute_to_initialization(self):
    self.analyze("""fungsi pilih(flag) {
  jika (flag) { hasilkan 1; }
  selainnya { variabel result = 2; }
  hasilkan result;
}
fungsi utama() { pilih(benar); }
""")

    self.assert_invalid("""fungsi pilih(flag) {
  jika (flag) {} selainnya { variabel result = 2; }
  hasilkan result;
}
fungsi utama() {}
""")
    self.assert_invalid("fungsi utama() { jika (benar) { variabel result = 1; } tampilkan(result); }")
    self.analyze("""fungsi pilih(a, b) {
  jika (a) { jika (b) { hasilkan 1; } selainnya { hasilkan 2; } }
  selainnya jika (b) { hasilkan 3; }
  selainnya { variabel result = 4; }
  hasilkan result;
}
fungsi utama() {}
""")

  def test_unreachable_code_cannot_initialize_a_live_path(self):
    self.assert_invalid("""fungsi utama() {
  jika (benar) { hasilkan; variabel result = 1; }
  tampilkan(result);
}""")
    self.assert_invalid("fungsi utama() { hasilkan; missing(); }")
    self.assert_invalid("fungsi utama() { hasilkan; tampilkan(missing); }")
